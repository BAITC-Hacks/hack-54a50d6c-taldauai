from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TypedDict

from app.asr.base import TranscriptSegment
from app.config import settings


class ExtractionResult(TypedDict):
    summary: str
    participants: list[dict[str, Any]]
    action_items: list[dict[str, Any]]


class ExtractionBackend(ABC):
    @abstractmethod
    def extract(self, meeting_id: str, segments: list[TranscriptSegment]) -> ExtractionResult:
        """Extract meeting summary, participants and action items."""


def get_extraction_backend() -> ExtractionBackend:
    if settings.llm_backend == "stub":
        from .stub import StubExtraction
        return StubExtraction()
    if settings.llm_backend == "ollama":
        from .ollama import OllamaExtraction
        return OllamaExtraction(settings.llm_base_url, settings.llm_model)
    raise ValueError(f"Unsupported LLM_BACKEND: {settings.llm_backend}")
