from __future__ import annotations

import json
import sys
from typing import Any

from app.config import PROJECT_ROOT, settings


def run_ml_pipeline(
    audio_path: str,
    meeting_started_at: str,
    *,
    num_speakers: int | None = None,
) -> dict[str, Any]:
    """Run the real local pipeline or an explicitly configured JSON fixture."""
    if settings.ml_result_fixture is not None:
        try:
            result = json.loads(settings.ml_result_fixture.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Could not load ML result fixture: {exc}") from exc
        result["meeting_started_at"] = meeting_started_at
        return result

    # The backend is normally started from backend/, while ml/ lives at repo root.
    root = str(PROJECT_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    from ml import process_meeting as process_local_meeting

    return process_local_meeting(
        audio_path,
        meeting_started_at,
        num_speakers=num_speakers,
    )


def adapt_ml_result(meeting_id: str, result: dict[str, Any]) -> dict[str, Any]:
    """Validate and map ML JSON v1 to backend persistence records."""
    if not isinstance(result, dict) or result.get("schema_version") != "1.0":
        raise ValueError("ML returned an unsupported result schema")
    if result.get("status") != "completed":
        raise RuntimeError("ML processing did not complete")

    raw_segments = result.get("segments")
    raw_speakers = result.get("speakers")
    raw_tasks = result.get("tasks")
    raw_warnings = result.get("warnings", [])
    if not isinstance(raw_segments, list) or not isinstance(raw_speakers, list) or not isinstance(raw_tasks, list):
        raise ValueError("ML result must contain speakers, segments and tasks lists")
    if not isinstance(raw_warnings, list) or any(not isinstance(item, str) for item in raw_warnings):
        raise ValueError("ML warnings must be a list of strings")

    segments: list[dict[str, Any]] = []
    segment_by_source_id: dict[str, dict[str, Any]] = {}
    for item in raw_segments:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not isinstance(item.get("text"), str):
            raise ValueError("ML returned an invalid segment")
        start_ms = item.get("start_ms")
        end_ms = item.get("end_ms")
        if not isinstance(start_ms, (int, float)) or not isinstance(end_ms, (int, float)) or end_ms < start_ms:
            raise ValueError(f"ML segment {item['id']} has invalid timestamps")
        language = item.get("language")
        if language not in {None, "ru", "kk", "mixed"}:
            language = None
        record = {
            "source_segment_id": item["id"],
            "start": start_ms / 1000,
            "end": end_ms / 1000,
            "speaker_label": item.get("speaker_id") if isinstance(item.get("speaker_id"), str) else None,
            "text": item["text"],
            "suggested_text": item.get("suggested_text") if isinstance(item.get("suggested_text"), str) else None,
            "lang": language,
        }
        segments.append(record)
        segment_by_source_id[item["id"]] = record

    participants: list[dict[str, Any]] = []
    for index, item in enumerate(raw_speakers, start=1):
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise ValueError("ML returned an invalid speaker")
        display_name = item.get("display_name")
        has_name = isinstance(display_name, str) and bool(display_name.strip())
        participants.append({
            "speaker_label": item["id"],
            "name": display_name.strip() if has_name else f"Спикер {index}",
            "role": "Должность не определена",
            "auto_detected": not has_name,
        })

    action_items: list[dict[str, Any]] = []
    for index, item in enumerate(raw_tasks, start=1):
        if not isinstance(item, dict) or not isinstance(item.get("description"), str):
            raise ValueError("ML returned an invalid task")
        source_ids = item.get("source_segment_ids")
        if not isinstance(source_ids, list) or not source_ids or any(source_id not in segment_by_source_id for source_id in source_ids):
            raise ValueError(f"ML task {item.get('id', index)} has invalid source_segment_ids")
        source_segments = [segment_by_source_id[source_id] for source_id in source_ids]
        source_task_id = item.get("id") if isinstance(item.get("id"), str) else f"task_{index:04d}"
        action_items.append({
            "id": f"{meeting_id}-{source_task_id}",
            "source_task_id": source_task_id,
            "task": item["description"].strip(),
            "assignee": item.get("assignee_name") if isinstance(item.get("assignee_name"), str) else None,
            "speaker_label": item.get("assignee_speaker_id") if isinstance(item.get("assignee_speaker_id"), str) else None,
            "assigner_speaker_label": item.get("assigner_speaker_id") if isinstance(item.get("assigner_speaker_id"), str) else None,
            "deadline_raw": item.get("due_text") if isinstance(item.get("due_text"), str) else None,
            "deadline_date": item.get("due_date") if isinstance(item.get("due_date"), str) else None,
            "status": "in_progress",
            "urgency": "medium",
            "quote": " ".join(segment["text"] for segment in source_segments),
            "timestamp": min(segment["start"] for segment in source_segments),
            "needs_review": bool(item.get("needs_review", True)),
            "source_segment_ids": list(source_ids),
            "reminded_at": None,
        })

    summary = result.get("summary")
    if not isinstance(summary, str):
        raise ValueError("ML summary must be a string")
    return {
        "summary": summary,
        "warnings": list(raw_warnings),
        "segments": segments,
        "participants": participants,
        "action_items": action_items,
    }
