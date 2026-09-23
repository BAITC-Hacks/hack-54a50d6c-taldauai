"""Offline audio processing with a local Ollama inference server.

Models are loaded from local paths. No meeting content is sent to an external API.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen


SUPPORTED_AUDIO = {".wav", ".mp3", ".m4a", ".mp4", ".ogg", ".flac"}


def _meeting_date(value: str) -> date:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("meeting_started_at must include a timezone offset")
    return parsed.date()


def _convert_audio(path: Path, destination: Path) -> None:
    try:
        subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(path),
             "-ac", "1", "-ar", "16000", "-f", "wav", str(destination)],
            check=True, capture_output=True, text=True, timeout=600,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg is required to decode audio") from exc
    except subprocess.CalledProcessError as exc:
        raise ValueError(f"Audio decoding failed: {exc.stderr.strip()}") from exc


def _transcribe(path: Path) -> list[dict]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("Install faster-whisper to process audio") from exc
    model_path = os.environ.get("TALDAU_ASR_MODEL")
    if not model_path or not Path(model_path).is_dir():
        raise RuntimeError("TALDAU_ASR_MODEL must point to a downloaded local model directory")
    device = os.environ.get("TALDAU_DEVICE", "cpu")
    compute_type = "float16" if device == "cuda" else "int8"
    model = WhisperModel(model_path, device=device, compute_type=compute_type, local_files_only=True)
    result, _ = model.transcribe(
        str(path), task="transcribe", language=None, vad_filter=True,
        word_timestamps=True, beam_size=5, multilingual=True,
        condition_on_previous_text=False,
    )
    segments = []
    for item in result:
        if not item.text.strip():
            continue
        segments.append({
            "start_ms": round(item.start * 1000),
            "end_ms": round(item.end * 1000),
            "text": item.text.strip(),
        })
    return segments


def _diarize(path: Path) -> list[dict]:
    try:
        import torch
        from pyannote.audio import Pipeline
    except ImportError as exc:
        raise RuntimeError("Install pyannote.audio to identify speakers") from exc
    model_path = os.environ.get("TALDAU_DIARIZATION_MODEL")
    if not model_path or not Path(model_path).is_dir():
        raise RuntimeError("TALDAU_DIARIZATION_MODEL must point to a downloaded local pipeline")
    pipeline = Pipeline.from_pretrained(model_path)
    if os.environ.get("TALDAU_DEVICE") == "cuda":
        pipeline.to(torch.device("cuda"))
    output = pipeline(str(path))
    annotation = getattr(output, "exclusive_speaker_diarization", None)
    if annotation is None:
        annotation = output.speaker_diarization
    turns = []
    for turn, _, speaker in annotation.itertracks(yield_label=True):
        turns.append({"start_ms": round(turn.start * 1000),
                      "end_ms": round(turn.end * 1000), "speaker": str(speaker)})
    return turns


def _combine(asr: list[dict], turns: list[dict]) -> tuple[list[dict], list[dict]]:
    speaker_ids = {name: f"SPEAKER_{i:02d}" for i, name in enumerate(
        sorted({item["speaker"] for item in turns},
               key=lambda name: min(t["start_ms"] for t in turns if t["speaker"] == name))
    )}
    segments = []
    for index, item in enumerate(asr, 1):
        overlaps: dict[str, int] = {}
        for turn in turns:
            overlap = max(0, min(item["end_ms"], turn["end_ms"]) - max(item["start_ms"], turn["start_ms"]))
            overlaps[turn["speaker"]] = overlaps.get(turn["speaker"], 0) + overlap
        best = max(overlaps, key=overlaps.get) if overlaps else None
        duration = max(1, item["end_ms"] - item["start_ms"])
        speaker_id = speaker_ids[best] if best and overlaps[best] >= duration * 0.5 else None
        segments.append({"id": f"seg_{index:04d}", **item,
                         "speaker_id": speaker_id, "language": None})
    speakers = [{"id": sid, "display_name": None} for sid in speaker_ids.values()]
    return segments, speakers


def _extract(segments: list[dict], started_at: str, speakers: list[dict]) -> dict:
    base_url = os.environ.get("TALDAU_OLLAMA_URL", "http://127.0.0.1:11434")
    if not re.fullmatch(r"http://(127\.0\.0\.1|localhost)(:\d+)?", base_url):
        raise ValueError("TALDAU_OLLAMA_URL must be a local HTTP address")
    model = os.environ.get("TALDAU_LLM_MODEL", "qwen2.5:7b")
    prompt = (
        "Извлеки ВСЕ явные поручения из протокола. Сохрани несколько поручений из одной реплики. "
        "Исполнитель — адресат поручения, а не обязательно говорящий. "
        "Укажи assignee_speaker_id только при явной связи имени с говорящим в диалоге; иначе null. "
        "Если исполнитель или срок неясен, верни null. Для срока сохрани исходные слова в due_text. "
        "due_date заполняй только для однозначной календарной даты; иначе null. "
        "Каждому поручению дай source_segment_ids из приведённых сегментов. "
        "Краткое саммари должно опираться только на реплики. "
        f"Дата совещания: {started_at}. Говорящие: {json.dumps(speakers, ensure_ascii=False)}. "
        f"Сегменты: {json.dumps(segments, ensure_ascii=False)}"
    )
    schema = {
        "type": "object", "required": ["tasks", "summary"],
        "properties": {
            "summary": {"type": "string"},
            "tasks": {"type": "array", "items": {
                "type": "object",
                "required": ["description", "assignee_name", "assignee_speaker_id",
                             "assigner_speaker_id", "due_date", "due_text", "source_segment_ids"],
                "properties": {
                    "description": {"type": "string"},
                    "assignee_name": {"type": ["string", "null"]},
                    "assignee_speaker_id": {"type": ["string", "null"]},
                    "assigner_speaker_id": {"type": ["string", "null"]},
                    "due_date": {"type": ["string", "null"]},
                    "due_text": {"type": ["string", "null"]},
                    "source_segment_ids": {"type": "array", "items": {"type": "string"}},
                },
            }},
        },
    }
    payload = {"model": model, "stream": False, "format": schema,
               "options": {"temperature": 0},
               "messages": [{"role": "user", "content": prompt}]}
    request = Request(base_url + "/api/chat", data=json.dumps(payload).encode(),
                      headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=300) as response:
            answer = json.load(response)
    except OSError as exc:
        raise RuntimeError(f"Local Ollama inference failed: {exc}") from exc
    return json.loads(answer["message"]["content"])


def _resolve_due_date(value: str | None, due_text: str | None, meeting_day: date) -> str | None:
    if not due_text:
        return None
    text = due_text.lower().strip()
    # Keep the model's candidate only when the original words contain the date.
    # This prevents an invented date for phrases such as "after approval".
    iso_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", text)
    if iso_match:
        try:
            return date.fromisoformat(iso_match.group()).isoformat()
        except ValueError:
            return None
    match = re.search(r"\b(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?\b", text)
    if match:
        day, month = int(match[1]), int(match[2])
        year = int(match[3]) if match[3] else meeting_day.year
        try:
            result = date(year, month, day)
            if not match[3] and result < meeting_day:
                result = date(year + 1, month, day)
            return result.isoformat()
        except ValueError:
            return None
    months = {"январ": 1, "феврал": 2, "март": 3, "апрел": 4,
              "мая": 5, "май": 5, "июн": 6, "июл": 7, "август": 8,
              "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12}
    match = re.search(r"\b(\d{1,2})\s+([а-яё]+)(?:\s+(\d{4}))?\b", text)
    if match:
        month = next((number for name, number in months.items() if match[2].startswith(name)), None)
        if month:
            year = int(match[3]) if match[3] else meeting_day.year
            try:
                result = date(year, month, int(match[1]))
                if not match[3] and result < meeting_day:
                    result = date(year + 1, month, int(match[1]))
                return result.isoformat()
            except ValueError:
                return None
    weekdays = {"понедельник": 0, "вторник": 1, "сред": 2, "четверг": 3,
                "пятниц": 4, "суббот": 5, "воскресень": 6,
                "дүйсенб": 0, "сейсенб": 1, "сәрсенб": 2,
                "бейсенб": 3, "жұма": 4, "сенб": 5, "жексенб": 6}
    for name, number in weekdays.items():
        if name in text:
            days = (number - meeting_day.weekday()) % 7
            if days == 0:
                days = 7
            return (meeting_day + timedelta(days=days)).isoformat()
    # A candidate from the LLM is deliberately ignored when the source wording
    # cannot be resolved by these rules. The reviewer sees due_text instead.
    return None


def _validate_extraction(raw: dict, segments: list[dict], speakers: list[dict], meeting_day: date) -> tuple[list[dict], str, list[str]]:
    if not isinstance(raw, dict) or not isinstance(raw.get("tasks"), list) or not isinstance(raw.get("summary"), str):
        raise ValueError("LLM returned an invalid result")
    valid_segments = {s["id"] for s in segments}
    valid_speakers = {s["id"] for s in speakers}
    tasks = []
    warnings = []
    for index, item in enumerate(raw["tasks"], 1):
        if not isinstance(item, dict) or not isinstance(item.get("description"), str) or not item["description"].strip():
            warnings.append(f"Task {index} omitted: empty description")
            continue
        source_ids = item.get("source_segment_ids")
        if (not isinstance(source_ids, list) or not source_ids
                or any(not isinstance(s, str) or s not in valid_segments for s in source_ids)):
            warnings.append(f"Task {index} omitted: invalid source segments")
            continue
        assignee_name = item.get("assignee_name")
        if not isinstance(assignee_name, str) or not assignee_name.strip():
            assignee_name = None
        assignee_id = item.get("assignee_speaker_id")
        assigner_id = item.get("assigner_speaker_id")
        if assignee_id not in valid_speakers:
            assignee_id = None
        if assigner_id not in valid_speakers:
            assigner_id = None
        due_text = item.get("due_text")
        if not isinstance(due_text, str) or not due_text.strip():
            due_text = None
        due_date = _resolve_due_date(item.get("due_date"), due_text, meeting_day)
        tasks.append({
            "id": f"task_{len(tasks)+1:04d}",
            "description": item["description"].strip(),
            "assignee_name": assignee_name,
            "assignee_speaker_id": assignee_id,
            "assigner_speaker_id": assigner_id,
            "due_date": due_date,
            "due_text": due_text,
            "source_segment_ids": source_ids,
            "needs_review": not (assignee_name and assignee_id and due_date),
        })
    return tasks, raw["summary"].strip(), warnings


def process_meeting(audio_path: str, meeting_started_at: str,
                    speaker_names: dict[str, str] | None = None) -> dict:
    """Process a local recording and return JSON-serializable protocol v1.

    Raises ValueError for bad input and RuntimeError for unavailable local models.
    """
    meeting_day = _meeting_date(meeting_started_at)
    source = Path(audio_path).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() not in SUPPORTED_AUDIO:
        raise ValueError("audio_path must point to an existing supported audio file")
    if speaker_names is not None and not isinstance(speaker_names, dict):
        raise ValueError("speaker_names must be a mapping")
    with tempfile.TemporaryDirectory(prefix="taldau-ml-") as tmp:
        wav_path = Path(tmp) / "audio.wav"
        _convert_audio(source, wav_path)
        asr = _transcribe(wav_path)
        turns = _diarize(wav_path)
    segments, speakers = _combine(asr, turns)
    for speaker in speakers:
        speaker["display_name"] = (speaker_names or {}).get(speaker["id"])
    if segments:
        raw = _extract(segments, meeting_started_at, speakers)
        tasks, summary, warnings = _validate_extraction(raw, segments, speakers, meeting_day)
    else:
        tasks, summary, warnings = [], "", ["Речь в записи не обнаружена"]
    return {"schema_version": "1.0", "meeting_started_at": meeting_started_at,
            "status": "completed", "speakers": speakers, "segments": segments,
            "tasks": tasks, "summary": summary, "warnings": warnings}
