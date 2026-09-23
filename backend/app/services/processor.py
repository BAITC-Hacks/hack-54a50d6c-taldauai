from __future__ import annotations

import time
from datetime import date, timezone

from sqlalchemy import delete, select

from app.asr import get_asr_backend
from app.config import settings
from app.database import SessionLocal
from app.llm import get_extraction_backend
from app.models import ActionItem, Meeting, Participant, Segment

from .ml_adapter import adapt_ml_result, run_ml_pipeline


def _set_status(meeting_id: str, status: str) -> None:
    with SessionLocal() as session:
        meeting = session.get(Meeting, meeting_id)
        if meeting is None:
            return
        meeting.status = status
        session.commit()


def _replace_results(
    meeting_id: str,
    segments: list[dict],
    participants: list[dict],
    actions: list[dict],
    summary: str,
    *,
    warnings: list[str] | None = None,
    ml_result: dict | None = None,
) -> None:
    with SessionLocal() as session:
        meeting = session.get(Meeting, meeting_id)
        if meeting is None:
            return
        session.execute(delete(ActionItem).where(ActionItem.meeting_id == meeting_id))
        session.execute(delete(Segment).where(Segment.meeting_id == meeting_id))
        session.execute(delete(Participant).where(Participant.meeting_id == meeting_id))
        session.add_all(Segment(meeting_id=meeting_id, **item) for item in segments)
        session.add_all(Participant(meeting_id=meeting_id, **item) for item in participants)
        for item in actions:
            deadline = item.get("deadline_date")
            if isinstance(deadline, str):
                item["deadline_date"] = date.fromisoformat(deadline)
            session.add(ActionItem(meeting_id=meeting_id, **item))
        meeting.summary = summary
        meeting.warnings = warnings or []
        meeting.ml_result = ml_result
        meeting.status = "done"
        meeting.error_message = None
        session.commit()


def _process_local_ml(meeting_id: str, meeting: Meeting) -> None:
    _set_status(meeting_id, "transcribing")
    started_at = meeting.date
    if started_at.tzinfo is None or started_at.utcoffset() is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    result = run_ml_pipeline(meeting.audio_path or "", started_at.isoformat(), num_speakers=meeting.num_speakers)
    _set_status(meeting_id, "extracting")
    mapped = adapt_ml_result(meeting_id, result)
    _replace_results(
        meeting_id,
        mapped["segments"],
        mapped["participants"],
        mapped["action_items"],
        mapped["summary"],
        warnings=mapped["warnings"],
        ml_result=result,
    )


def _process_stub(meeting_id: str, audio_path: str) -> None:
    time.sleep(2)
    _set_status(meeting_id, "transcribing")
    segments = get_asr_backend().transcribe(audio_path)
    time.sleep(2)
    _set_status(meeting_id, "diarizing")
    time.sleep(2)
    _set_status(meeting_id, "extracting")
    extracted = get_extraction_backend().extract(meeting_id, segments)
    time.sleep(2)
    _replace_results(
        meeting_id,
        list(segments),
        extracted["participants"],
        extracted["action_items"],
        extracted["summary"],
    )


def process_meeting(meeting_id: str) -> None:
    try:
        with SessionLocal() as session:
            meeting = session.get(Meeting, meeting_id)
            if meeting is None or not meeting.audio_path:
                raise ValueError("Meeting or audio file is unavailable")
            audio_path = meeting.audio_path
            session.expunge(meeting)
        if settings.asr_backend == "stub" and settings.llm_backend == "stub":
            _process_stub(meeting_id, audio_path)
        else:
            _process_local_ml(meeting_id, meeting)
    except Exception as exc:  # background jobs must persist their failure state
        with SessionLocal() as session:
            meeting = session.scalar(select(Meeting).where(Meeting.id == meeting_id))
            if meeting is not None:
                meeting.status = "error"
                meeting.error_message = str(exc)
                session.commit()
