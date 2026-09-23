from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal, TypedDict

from app.config import settings


class TranscriptSegment(TypedDict):
    start: float
    end: float
    speaker_label: str
    text: str
    lang: Literal["ru", "kk", "mixed"]


class ASRBackend(ABC):
    @abstractmethod
    def transcribe(self, audio_path: str) -> list[TranscriptSegment]:
        """Return timestamped, diarized transcript segments for an audio file."""


def get_asr_backend() -> ASRBackend:
    if settings.asr_backend == "stub":
        from .stub import StubASR
        return StubASR()
    raise ValueError(f"Unsupported ASR_BACKEND: {settings.asr_backend}")
