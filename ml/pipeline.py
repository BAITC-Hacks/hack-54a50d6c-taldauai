"""Offline audio processing with a local Ollama inference server.

Models are loaded from local paths. No meeting content is sent to an external API.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import wave
import calendar
from difflib import SequenceMatcher
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


SUPPORTED_AUDIO = {".wav", ".mp3", ".m4a", ".mp4", ".ogg", ".flac", ".webm", ".opus", ".aac"}

# Local inference must not upload diagnostics or attempt lazy weight downloads.
os.environ["PYANNOTE_METRICS_ENABLED"] = "0"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("Local Ollama redirects are not allowed")


def _local_open(request, timeout):
    # Meeting data must not be routed through a proxy from shell configuration.
    return build_opener(ProxyHandler({}), _NoRedirect()).open(request, timeout=timeout)


def _meeting_date(value: str) -> date:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("meeting_started_at must include a timezone offset")
    return parsed.date()


def _convert_audio(path: Path, destination: Path) -> None:
    try:
        subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(path),
             "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-f", "wav", str(destination)],
            check=True, capture_output=True, text=True, timeout=600,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg is required to decode audio") from exc
    except subprocess.CalledProcessError as exc:
        raise ValueError(f"Audio decoding failed: {exc.stderr.strip()}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Audio decoding timed out after 600 seconds") from exc
    with wave.open(str(destination), "rb") as stream:
        if stream.getnframes() == 0:
            raise ValueError("Audio contains no samples")


def _transcribe(path: Path, *, language: str | None = None,
                hotwords: str | None = None) -> list[dict]:
    import onnxruntime
    onnxruntime.disable_telemetry_events()
    engine = os.environ.get("TALDAU_ASR_ENGINE", "whisper")
    if engine == "mixed-ctc":
        if language not in {None, "ru", "kk"} or hotwords:
            raise ValueError("Mixed CTC supports ru/kk only and no hotwords; select whisper for other languages or terminology hints")
        from .mixed_asr import transcribe
        return transcribe(path, os.environ.get("TALDAU_ASR_MODEL", ""), os.environ.get("TALDAU_DEVICE", "cpu"))
    if engine != "whisper":
        raise ValueError("TALDAU_ASR_ENGINE must be whisper or mixed-ctc")
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
        str(path), task="transcribe", language=language, vad_filter=True,
        word_timestamps=True, beam_size=5, multilingual=language is None,
        condition_on_previous_text=False,
        hotwords=hotwords,
    )
    segments = []
    for item in result:
        if not item.text.strip():
            continue
        segments.append({
            "start_ms": round(item.start * 1000),
            "end_ms": round(item.end * 1000),
            "text": item.text.strip(),
            "words": [{"text": word.word.strip(), "start_ms": round(word.start * 1000),
                       "end_ms": round(word.end * 1000)} for word in (item.words or []) if word.word.strip()],
        })
    return segments


def _diarize(path: Path, num_speakers: int | None = None) -> list[dict]:
    model_path = os.environ.get("TALDAU_DIARIZATION_MODEL")
    if not model_path or not Path(model_path).is_dir():
        raise RuntimeError("TALDAU_DIARIZATION_MODEL must point to a downloaded local pipeline")
    try:
        import torch
        from pyannote.audio import Pipeline
    except ImportError as exc:
        raise RuntimeError("Install pyannote.audio to identify speakers") from exc
    pipeline = Pipeline.from_pretrained(model_path)
    if pipeline is None:
        raise RuntimeError("Could not load the local diarization pipeline")
    if os.environ.get("TALDAU_DEVICE") == "cuda":
        pipeline.to(torch.device("cuda"))
    # Audio was already decoded by ffmpeg. Passing PCM avoids a second decoder
    # and torchcodec/FFmpeg shared-library mismatches on macOS.
    import numpy as np
    with wave.open(str(path), "rb") as stream:
        if (stream.getnchannels(), stream.getframerate(), stream.getsampwidth()) != (1, 16000, 2):
            raise ValueError("Diarization requires mono 16 kHz PCM16 WAV")
        samples = np.frombuffer(stream.readframes(stream.getnframes()), dtype="<i2").astype(np.float32) / 32768
    options = {"num_speakers": num_speakers} if num_speakers is not None else {}
    output = pipeline({"waveform": torch.from_numpy(samples).unsqueeze(0), "sample_rate": 16000}, **options)
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
    def speaker_for(item):
        overlaps: dict[str, int] = {}
        for turn in turns:
            overlap = max(0, min(item["end_ms"], turn["end_ms"]) - max(item["start_ms"], turn["start_ms"]))
            overlaps[turn["speaker"]] = overlaps.get(turn["speaker"], 0) + overlap
        best = max(overlaps, key=overlaps.get) if overlaps else None
        duration = max(1, item["end_ms"] - item["start_ms"])
        ranked = sorted(overlaps.values(), reverse=True)
        if (best is not None and overlaps[best] >= duration * 0.5
                and (len(ranked) < 2 or ranked[1] < duration * 0.2)):
            return speaker_ids[best]
        return None

    for item in asr:
        current = None
        for word in item.get("words") or [item]:
            speaker_id = speaker_for(word)
            if (current and current["speaker_id"] == speaker_id
                    and word["start_ms"] - current["end_ms"] < 800):
                current["text"] += " " + word["text"]
                current["end_ms"] = word["end_ms"]
            else:
                current = {"id": f"seg_{len(segments)+1:04d}", "start_ms": word["start_ms"],
                           "end_ms": word["end_ms"], "text": word["text"],
                           "speaker_id": speaker_id, "language": None}
                segments.append(current)
    speakers = [{"id": sid, "display_name": None} for sid in speaker_ids.values()]
    return segments, speakers


def _suggest_speaker_names(segments: list[dict], speakers: list[dict]) -> None:
    """Conservative suggestions from explicit self-introductions, not voice ID.

    Keep these separate from human-confirmed display_name. Conflicting names
    in one cluster are not resolved automatically (possible diarization error).
    """
    candidates = {s["id"]: set() for s in speakers}
    word = r"[а-яёәғқңөұүһі-]{2,40}"
    patterns = [rf"\b(?:меня зовут|менің атым|менің есімім)\s+({word})\b",
                rf"\bмен\s+({word}?)(?:мын|мін|бын|бін|пын|пін)\b"]
    non_names = {"дайын", "келісем", "жауапты", "осында", "жақсы", "мұғалім", "дәрігер", "инженер"}
    for segment in segments:
        sid = segment.get("speaker_id")
        if sid not in candidates:
            continue
        text = segment["text"].casefold()
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                if match[1] not in non_names:
                    candidates[sid].add(match[1].capitalize())
    for speaker in speakers:
        names = candidates[speaker["id"]]
        if len(names) == 1 and not speaker.get("display_name"):
            speaker["suggested_name"] = next(iter(names))


def _ollama_chat(model: str, prompt: str, schema: dict) -> dict:
    base_url = os.environ.get("TALDAU_OLLAMA_URL", "http://127.0.0.1:11434")
    if not re.fullmatch(r"http://(127\.0\.0\.1|localhost)(:\d+)?", base_url):
        raise ValueError("TALDAU_OLLAMA_URL must be a local HTTP address")
    payload = {"model": model, "stream": False, "format": schema,
               "options": {"temperature": 0, "num_ctx": 16384, "num_predict": 4096},
               "messages": [{"role": "user", "content": prompt}]}
    request = Request(base_url + "/api/chat", data=json.dumps(payload).encode(),
                      headers={"Content-Type": "application/json"})
    try:
        with _local_open(request, timeout=300) as response:
            answer = json.load(response)
    except OSError as exc:
        raise RuntimeError(f"Local Ollama inference failed: {exc}") from exc
    if (not isinstance(answer, dict) or not isinstance(answer.get("message"), dict)
            or not isinstance(answer["message"].get("content"), str)):
        raise RuntimeError("Local Ollama returned an invalid chat response")
    return json.loads(answer["message"]["content"])


def _kazllm_suggestions(segments: list[dict]) -> list[str]:
    """Propose text corrections; always retain the original ASR text."""
    model = os.environ.get("TALDAU_KAZLLM_MODEL")
    if not model:
        return []
    schema = {"type": "object", "required": ["segments"], "properties": {
        "segments": {"type": "array", "items": {"type": "object",
            "required": ["id", "text"], "properties": {
                "id": {"type": "string"}, "text": {"type": "string"}}}}}}
    warnings = []
    for offset in range(0, len(segments), 20):
        batch = segments[offset:offset + 20]
        prompt = (
            "Ты корректируешь результат распознавания шала-казахской речи. "
            "Исправь только очевидные ошибки написания казахских и русских слов. "
            "Сохраняй переключения языков: не переводи, не перефразируй, "
            "не добавляй имена, числа, сроки и поручения. "
            "При сомнении возвращай исходный текст без изменений. "
            "Верни каждый id и исправленный text в том же порядке. "
            f"Сегменты: {json.dumps([{'id': s['id'], 'text': s['text']} for s in batch], ensure_ascii=False)}"
        )
        try:
            response = _ollama_chat(model, prompt, schema)
            if not isinstance(response, dict):
                raise ValueError("KazLLM returned a non-object result")
            proposals = response["segments"]
            if (not isinstance(proposals, list) or len(proposals) != len(batch)
                    or any(not isinstance(p, dict) or p.get("id") != s["id"]
                           or not isinstance(p.get("text"), str)
                           for p, s in zip(proposals, batch))):
                raise ValueError("KazLLM returned segments in an invalid format")
            for segment, proposed in zip(batch, proposals):
                suggestion = proposed["text"].strip()
                if suggestion and suggestion != segment["text"]:
                    segment["suggested_text"] = suggestion
        except (RuntimeError, ValueError, KeyError, json.JSONDecodeError) as exc:
            warnings.append(f"KazLLM suggestions unavailable for segments {batch[0]['id']}–{batch[-1]['id']}: {exc}")
    return warnings


def _extract(segments: list[dict], started_at: str, speakers: list[dict]) -> dict:
    model = os.environ.get("TALDAU_LLM_MODEL", "qwen2.5:7b")
    prompt = (
        "Ты секретарь совещания на русском и казахском языках. "
        "В description сохраняй исходную формулировку поручения на языке записи: "
        "цитируй действие, НЕ переводи и НЕ перефразируй. Имена людей не переводи. "
        "Саммари пиши на русском или казахском, без добавления отсутствующих фактов. "
        "Извлеки ВСЕ явные поручения из протокола. Сохрани несколько поручений из одной реплики. "
        "В tasks включай только действующие поручения, которые ещё предстоит выполнить. "
        "Сообщения о выполненной работе, отмена старого поручения и отсутствие новых задач "
        "не являются новыми поручениями: при их отсутствии верни tasks=[]. "
        "Повтор поручения или подтверждение исполнителя не создаёт новое поручение. "
        "При обсуждении нескольких сроков используй окончательный согласованный срок; "
        "предварительные варианты не создают дополнительные поручения. "
        "Исполнитель может отсутствовать на совещании (например, названный юрист или отдел): "
        "сохрани его имя, а assignee_speaker_id оставь null. "
        "Используй источник, где поручение назначили, а не только ответ с подтверждением. "
        "В сегментах text — дословный ASR, suggested_text — необязательная подсказка KazLLM. "
        "Опирайся на text; используй suggested_text только для исправления очевидных ошибок. "
        "Исполнитель — адресат поручения, а не обязательно говорящий. "
        "Укажи assignee_speaker_id только при явной связи имени с говорящим в диалоге; иначе null. "
        "В списке говорящих suggested_name — неподтверждённое имя из самопредставления; "
        "display_name — имя, подтверждённое человеком. "
        "Если исполнитель или срок неясен, верни null. Для срока сохрани исходные слова в due_text. "
        "Казахские сроки: ертең = завтра, бүгін = сегодня, жұмаға дейін = до пятницы. "
        "Например, при слове ертең поле due_text должно содержать ертең, а не null. "
        "Не подставляй слова 'неизвестно' и местоимения 'я'/'мен' в имя: верни null. "
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
    raw = _ollama_chat(model, prompt, schema)
    if (isinstance(raw, dict) and isinstance(raw.get("tasks"), list)
            and sum(len(s["text"]) for s in segments) > 2500):
        # A separate coverage pass reduces the tendency to omit late agenda
        # items in longer meetings. It receives no reference answers.
        coverage_prompt = (
            "Проверь полноту списка поручений: прочитай транскрипт до конца, включая вторую тему. "
            "Верни ТОЛЬКО пропущенные действующие поручения, которых нет в уже извлечённом списке. "
            "Если поручение уже покрыто по смыслу, не повторяй его. Подтверждения, отмены и завершённые "
            "действия не являются новыми поручениями. Сохраняй исходную формулировку действия, "
            "ответственного и окончательный срок. due_text — точная исходная формулировка срока. "
            "source_segment_ids должны ссылаться на назначение. Если пропусков нет, tasks=[]. "
            + json.dumps({"started_at": started_at, "speakers": speakers, "segments": segments,
                          "already_extracted": raw["tasks"]}, ensure_ascii=False)
        )
        try:
            missing = _ollama_chat(model, coverage_prompt, schema)
            if not isinstance(missing, dict) or not isinstance(missing.get("tasks"), list):
                raise ValueError("Invalid coverage result")
            if missing["tasks"]:
                raw["tasks"].extend(missing["tasks"])
                raw["_assignees_corrected"] = True
        except (ValueError, RuntimeError, KeyError, TypeError):
            raw["_review_failed"] = True
    return _review_assignments(raw, segments, speakers, model)


def _normalized_quote(text: str) -> str:
    return " ".join(re.findall(r"\w+", text.casefold().replace("ё", "е")))


def _review_assignments(raw: dict, segments: list[dict], speakers: list[dict], model: str) -> dict:
    """Audit addressees separately; accept changes only with literal evidence.

    The reviewer cannot create or delete tasks. Speaker guesses from this pass
    are not accepted: the assigner comes from the quoted segment, and assignee
    mapping remains subject to the regular validator and human confirmation.
    """
    if not isinstance(raw, dict) or not isinstance(raw.get("tasks"), list) or not raw["tasks"]:
        return raw
    prompt = (
        "Проверь адресатов черновика поручений по исходному транскрипту. "
        "В реплике 'Имя, сделайте действие' исполнитель — адресат, а не говорящий. "
        "Имя адресата может быть в конце предыдущего сегмента того же говорящего. "
        "Подтверждение 'сделаю' и самопредставление не являются новыми назначениями. "
        "Для каждого task_index верни исправленное assignee_name и assignment_segment_id — "
        "идентификатор сегмента с назначением, НЕ с подтверждением или самопредставлением. "
        "Имена бери из обращения при назначении, не из похожей фразы в другом месте. "
        "Если адресат не определён, assignee_name=null. Не добавляй и не удаляй задачи. "
        + json.dumps({"segments": segments, "speakers": speakers,
                      "tasks": [{"task_index": i, **task} for i, task in enumerate(raw["tasks"]) if isinstance(task, dict)]}, ensure_ascii=False)
    )
    schema = {"type": "object", "required": ["tasks"], "properties": {
        "tasks": {"type": "array", "items": {"type": "object", "required": ["task_index", "assignee_name", "assignment_segment_id"],
                  "properties": {"task_index": {"type": "integer"}, "assignee_name": {"type": ["string", "null"]},
                                 "assignment_segment_id": {"type": "string", "enum": [s["id"] for s in segments]}}}}}}
    try:
        audit = _ollama_chat(model, prompt, schema)
        proposals = audit.get("tasks") if isinstance(audit, dict) else None
        if (not isinstance(proposals, list) or len(proposals) != len(raw["tasks"])
                or any(not isinstance(p, dict) or type(p.get("task_index")) is not int for p in proposals)
                or {p["task_index"] for p in proposals} != set(range(len(raw["tasks"])) )):
            raise ValueError("Invalid assignment review")
        for proposal in proposals:
            name = proposal.get("assignee_name")
            if not isinstance(name, str) or not name.strip():
                continue
            matches = [i for i, segment in enumerate(segments) if segment["id"] == proposal.get("assignment_segment_id")]
            if len(matches) != 1:
                continue
            index = matches[0]
            segment = segments[index]
            context = segment["text"]
            if index and segment.get("speaker_id") is not None and segments[index - 1].get("speaker_id") == segment["speaker_id"]:
                context = segments[index - 1]["text"] + " " + context
            if " " + _normalized_quote(name) + " " not in " " + _normalized_quote(context) + " ":
                continue
            task = raw["tasks"][proposal["task_index"]]
            if not isinstance(task, dict):
                continue
            sources = task.get("source_segment_ids")
            if not isinstance(sources, list):
                continue
            adjacent_source = (index + 1 < len(segments) and segments[index + 1]["id"] in sources
                               and segment.get("speaker_id") is not None
                               and segments[index + 1].get("speaker_id") == segment["speaker_id"])
            if segment["id"] not in sources and not adjacent_source:
                continue
            if task.get("assignee_name") != name or task.get("assigner_speaker_id") != segment.get("speaker_id"):
                raw["_assignees_corrected"] = True
            task["assignee_name"] = name.strip()
            task["assigner_speaker_id"] = segment.get("speaker_id")
            task["source_segment_ids"] = list(dict.fromkeys(sources + [segment["id"]]))
            task["assignment_quote"] = segment["text"]
    except (ValueError, RuntimeError, KeyError, TypeError):
        raw["_review_failed"] = True
    return raw


def _resolve_due_date(value: str | None, due_text: str | None, meeting_day: date) -> str | None:
    if not due_text:
        return None
    text = due_text.lower().strip()
    if re.fullmatch(r"(?:до |к )?(?:завтра|ертең|ертеңге дейін)", text):
        return (meeting_day + timedelta(days=1)).isoformat()
    if text in {"сегодня", "до конца дня", "бүгін", "бүгінге дейін"}:
        return meeting_day.isoformat()
    # Spoken ordinal dates are common in meetings. Replace only an ordinal
    # immediately before a Russian month, leaving durations untouched.
    ordinals = {"перв": 1, "втор": 2, "треть": 3, "четвёрт": 4, "четверт": 4,
                "пят": 5, "шест": 6, "седьм": 7, "восьм": 8, "девят": 9,
                "десят": 10, "одиннадцат": 11, "двенадцат": 12, "тринадцат": 13,
                "четырнадцат": 14, "пятнадцат": 15, "шестнадцат": 16,
                "семнадцат": 17, "восемнадцат": 18, "девятнадцат": 19,
                "двадцат": 20, "тридцат": 30}
    month_pattern = r"(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)"
    for stem, number in ordinals.items():
        text = re.sub(r"\b" + stem + r"(?:ого|ому|ое|ый|ой|его|ему|е)\s+(?=" + month_pattern + r"\b)", str(number) + " ", text)
    text = re.sub(r"\bдвадцать\s+([1-9])\b", lambda m: str(20 + int(m[1])), text)
    text = re.sub(r"\bтридцать\s+1\b", "31", text)
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
                return None
            return result.isoformat()
        except ValueError:
            return None
    months = {"январ": 1, "феврал": 2, "март": 3, "апрел": 4,
              "мая": 5, "май": 5, "июн": 6, "июл": 7, "август": 8,
              "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12,
              "қаңтар": 1, "ақпан": 2, "наурыз": 3, "сәуір": 4, "мамыр": 5,
              "маусым": 6, "шілде": 7, "тамыз": 8, "қыркүйек": 9,
              "қазан": 10, "қараша": 11, "желтоқсан": 12}
    match = re.search(r"\b(\d{1,2})\s+([^\W\d_]+)(?:\s+(\d{4}))?\b", text)
    if match:
        month = next((number for name, number in months.items() if match[2].startswith(name)), None)
        if month:
            year = int(match[3]) if match[3] else meeting_day.year
            try:
                result = date(year, month, int(match[1]))
                if not match[3] and result < meeting_day:
                    return None
                return result.isoformat()
            except ValueError:
                return None
    if text in {"до конца квартала", "к концу квартала"}:
        month = ((meeting_day.month - 1) // 3 + 1) * 3
        return date(meeting_day.year, month, calendar.monthrange(meeting_day.year, month)[1]).isoformat()
    amounts = {"один": 1, "одну": 1, "одна": 1, "одной": 1, "два": 2, "две": 2, "двух": 2,
               "три": 3, "трёх": 3, "трех": 3, "четыре": 4, "четырёх": 4, "четырех": 4,
               "пять": 5, "пяти": 5, "семь": 7, "семи": 7, "десять": 10, "десяти": 10,
               "бір": 1, "екі": 2, "үш": 3, "төрт": 4, "бес": 5, "жеті": 7, "он": 10}
    amount = r"(\d{1,3}|" + "|".join(amounts) + r")"
    duration = re.fullmatch(r"(?:через |за |в течение )?" + amount + r"\s+(день|дня|дней|неделю|недели|недель)", text)
    if duration is None:
        duration = re.fullmatch(amount + r"\s+(күн|апта)(?:\s+(ішінде|кейін))?", text)
    if duration:
        count = int(duration[1]) if duration[1].isdigit() else amounts[duration[1]]
        multiplier = 7 if duration[2].startswith("недел") or duration[2] == "апта" else 1
        if count > 0:
            return (meeting_day + timedelta(days=count * multiplier)).isoformat()
    if re.search(r"\b(после|келесі|следующ)", text):
        return None
    weekdays = {"понедельник": 0, "вторник": 1, "сред": 2, "четверг": 3,
                "пятниц": 4, "суббот": 5, "воскресень": 6,
                "дүйсенб": 0, "сейсенб": 1, "сәрсенб": 2,
                "бейсенб": 3, "жұма": 4, "сенб": 5, "жексенб": 6}
    for name, number in weekdays.items():
        if re.search(r"\b" + name, text):
            days = (number - meeting_day.weekday()) % 7
            return (meeting_day + timedelta(days=days)).isoformat()
    # A candidate from the LLM is deliberately ignored when the source wording
    # cannot be resolved by these rules. The reviewer sees due_text instead.
    return None


def _validate_extraction(raw: dict, segments: list[dict], speakers: list[dict], meeting_day: date) -> tuple[list[dict], str, list[str]]:
    if not isinstance(raw, dict) or not isinstance(raw.get("tasks"), list) or not isinstance(raw.get("summary"), str):
        raise ValueError("LLM returned an invalid result")
    segment_by_id = {s["id"]: s for s in segments}
    valid_segments = set(segment_by_id)
    valid_speakers = {s["id"] for s in speakers}
    confirmed_names = {s["id"]: s.get("display_name") for s in speakers}
    known_names = {s["id"]: s.get("display_name") or s.get("suggested_name") for s in speakers}
    tasks = []
    warnings = []
    if raw.get("_review_failed"):
        warnings.append("Assignment verification unavailable; all tasks require review")
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
        if (not isinstance(assignee_name, str) or assignee_name.strip().casefold()
                in {"", "null", "none", "неизвестно", "неизвестен", "не определён", "не определен", "белгісіз", "я", "мы", "мен", "біз"}):
            assignee_name = None
        else:
            assignee_name = assignee_name.strip()
        # Prefer a literal address at the start of the extracted directive over
        # a near-spelling in a later self-introduction. This is only a draft
        # spelling repair; it never confirms the person's identity.
        if assignee_name:
            description = _normalized_quote(item["description"])
            direct = [segment_by_id[s] for s in source_ids
                      if description and description in _normalized_quote(segment_by_id[s].get("text", ""))]
            words = _normalized_quote(assignee_name).split()
            prefix = " ".join(description.split()[:len(words)])
            if (len(direct) == 1 and len(description.split()) > len(words)
                    and len(prefix) >= 4 and SequenceMatcher(None, prefix, " ".join(words)).ratio() >= 0.85):
                if prefix != " ".join(words):
                    assignee_name = " ".join(word.capitalize() for word in prefix.split())
                    raw["_assignees_corrected"] = True
                item = {**item, "assigner_speaker_id": direct[0].get("speaker_id"),
                        "assignment_quote": direct[0].get("text", "")}
        assignee_id = item.get("assignee_speaker_id")
        assigner_id = item.get("assigner_speaker_id")
        if not isinstance(assignee_id, str) or assignee_id not in valid_speakers:
            assignee_id = None
        if assignee_name:
            mapped = [sid for sid, name in known_names.items()
                      if isinstance(name, str) and name.strip().casefold() == assignee_name.casefold()]
            if len(mapped) == 1:
                assignee_id = mapped[0]
            elif assignee_id and confirmed_names.get(assignee_id):
                warnings.append(f"Task {index}: assignee conflicts with the confirmed speaker name")
                assignee_id = None
        else:
            assignee_id = None
        if not isinstance(assigner_id, str) or assigner_id not in valid_speakers:
            assigner_id = None
        source_speakers = {segment_by_id[s].get("speaker_id") for s in source_ids}
        if assigner_id is not None and assigner_id not in source_speakers:
            warnings.append(f"Task {index}: assigner is not a speaker in the cited segments")
            assigner_id = None
        due_text = item.get("due_text")
        if (not isinstance(due_text, str) or due_text.strip().casefold()
                in {"", "null", "none", "неизвестно", "белгісіз"}):
            due_text = None
        due_date = _resolve_due_date(item.get("due_date"), due_text, meeting_day)
        deadline_repaired = False
        if due_date:
            evidence = " ".join(_normalized_quote(segment_by_id[s].get("text", ""))
                                for s in source_ids)
            quoted_deadline = _normalized_quote(due_text)
            if not quoted_deadline or f" {quoted_deadline} " not in f" {evidence} ":
                # Models sometimes translate a correct deadline between RU/KK.
                # Recover only a literal span resolving to that same date;
                # never search outside the task's cited evidence.
                spans = []
                for sid in source_ids:
                    words = segment_by_id[sid].get("text", "").split()
                    for width in range(1, min(10, len(words)) + 1):
                        for start in range(len(words) - width + 1):
                            span = " ".join(words[start:start + width]).strip(".,;:!?—– ")
                            if _resolve_due_date(None, span, meeting_day) == due_date:
                                spans.append(span)
                        if spans:
                            break
                if spans:
                    due_text = min(spans, key=lambda span: len(span.split()))
                    deadline_repaired = True
                    warnings.append(f"Task {index}: deadline wording recovered from transcript; review required")
                else:
                    due_date = None
                    warnings.append(f"Task {index}: deadline wording is not in the cited transcript; date requires review")
        tasks.append({
            "id": f"task_{len(tasks)+1:04d}",
            "description": item["description"].strip(),
            "assignee_name": assignee_name,
            "assignee_speaker_id": assignee_id,
            "assigner_speaker_id": assigner_id,
            "due_date": due_date,
            "due_text": due_text,
            "source_segment_ids": source_ids,
            "needs_review": (not (assignee_name and assignee_id and assigner_id and due_date)
                             or bool(raw.get("_review_failed"))
                             or deadline_repaired
                             or confirmed_names.get(assignee_id) != assignee_name
                             or any(s.get("suggested_text") for s in segments if s["id"] in source_ids)),
        })
        if isinstance(item.get("assignment_quote"), str):
            tasks[-1]["assignment_quote"] = item["assignment_quote"]
    # Only merge identical task facts with shared evidence. Similar wording alone
    # is insufficient: recurring tasks and different recipients must survive.
    unique = []
    for task in tasks:
        fields = ("description", "assignee_name", "assignee_speaker_id", "assigner_speaker_id", "due_date", "due_text")
        duplicate = next((t for t in unique if all(t[k] == task[k] for k in fields)
                          and set(t["source_segment_ids"]) & set(task["source_segment_ids"])), None)
        if duplicate is not None:
            duplicate["source_segment_ids"] = list(dict.fromkeys(duplicate["source_segment_ids"] + task["source_segment_ids"]))
            duplicate["needs_review"] |= task["needs_review"]
            warnings.append("Merged an identical task with overlapping source evidence")
        else:
            task["id"] = f"task_{len(unique)+1:04d}"
            unique.append(task)
    summary = raw["summary"].strip()
    if raw.get("_assignees_corrected"):
        # Do not retain a prose summary naming the assignee that was corrected.
        summary = "Поручения по итогам совещания: " + "; ".join(
            f"{t['assignee_name'] or 'исполнитель не определён'} — {t['description']} "
            f"(срок: {t['due_date'] or t['due_text'] or 'не указан'})" for t in unique)
    return unique, summary, warnings


def process_meeting(audio_path: str, meeting_started_at: str,
                    speaker_names: dict[str, str] | None = None,
                    *, num_speakers: int | None = None,
                    language: str | None = None, hotwords: str | None = None) -> dict:
    """Process a local recording and return JSON-serializable protocol v1.

    Raises ValueError for bad input and RuntimeError for unavailable local models.
    """
    meeting_day = _meeting_date(meeting_started_at)
    if language is not None and (not isinstance(language, str) or not re.fullmatch(r"[a-z]{2,3}", language)):
        raise ValueError("language must be a language code such as ru, kk, en, or None for automatic detection")
    if hotwords is not None and (not isinstance(hotwords, str) or len(hotwords) > 1000):
        raise ValueError("hotwords must be a string of at most 1000 characters")
    if num_speakers is not None and (type(num_speakers) is not int or not 1 <= num_speakers <= 32):
        raise ValueError("num_speakers must be between 1 and 32")
    source = Path(audio_path).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() not in SUPPORTED_AUDIO:
        raise ValueError("audio_path must point to an existing supported audio file")
    if speaker_names is not None and not isinstance(speaker_names, dict):
        raise ValueError("speaker_names must be a mapping")
    with tempfile.TemporaryDirectory(prefix="taldau-ml-") as tmp:
        wav_path = Path(tmp) / "audio.wav"
        _convert_audio(source, wav_path)
        asr = _transcribe(wav_path, language=language, hotwords=hotwords)
        turns = _diarize(wav_path, num_speakers) if asr else []
    segments, speakers = _combine(asr, turns)
    for speaker in speakers:
        speaker["display_name"] = (speaker_names or {}).get(speaker["id"])
    _suggest_speaker_names(segments, speakers)
    if segments:
        correction_warnings = _kazllm_suggestions(segments)
        raw = _extract(segments, meeting_started_at, speakers)
        tasks, summary, warnings = _validate_extraction(raw, segments, speakers, meeting_day)
        warnings = correction_warnings + warnings
        if any(s["speaker_id"] is None for s in segments):
            warnings.append("Some speech has no reliable speaker assignment; review overlapping voices and diarization")
    else:
        tasks, summary, warnings = [], "", ["Речь в записи не обнаружена"]
    return {"schema_version": "1.0", "meeting_started_at": meeting_started_at,
            "status": "completed", "speakers": speakers, "segments": segments,
            "tasks": tasks, "summary": summary, "warnings": warnings}
