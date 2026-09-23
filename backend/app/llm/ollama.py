from __future__ import annotations

import json
from urllib.request import Request, urlopen

from app.asr.base import TranscriptSegment

from .base import ExtractionBackend, ExtractionResult


class OllamaExtraction(ExtractionBackend):
    """OpenAI-compatible Ollama client for a later local-model rollout."""

    def __init__(self, base_url: str, model: str) -> None:
        self.endpoint = f"{base_url.rstrip('/')}/chat/completions"
        self.model = model

    def extract(self, meeting_id: str, segments: list[TranscriptSegment]) -> ExtractionResult:
        transcript = "\n".join(f"[{item['start']}] {item['speaker_label']}: {item['text']}" for item in segments)
        prompt = (
            "Верни только JSON с полями summary, participants, action_items. "
            "participants: speaker_label, name, role, auto_detected. "
            "action_items: task, assignee, speaker_label, deadline_raw, deadline_date, status, urgency, quote, timestamp.\n\n"
            f"Транскрипт:\n{transcript}"
        )
        payload = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "stream": False,
        }).encode("utf-8")
        request = Request(self.endpoint, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=120) as response:  # noqa: S310 - configured local endpoint
            result = json.loads(response.read().decode("utf-8"))
        extracted: ExtractionResult = json.loads(result["choices"][0]["message"]["content"])
        for index, item in enumerate(extracted["action_items"], start=1):
            item.setdefault("id", f"{meeting_id}-a{index}")
        return extracted
