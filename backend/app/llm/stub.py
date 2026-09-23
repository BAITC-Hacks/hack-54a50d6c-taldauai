from datetime import date, timedelta

from app.asr.base import TranscriptSegment

from .base import ExtractionBackend, ExtractionResult


class StubExtraction(ExtractionBackend):
    def extract(self, meeting_id: str, segments: list[TranscriptSegment]) -> ExtractionResult:
        quote = segments[-1]["text"]
        return {
            "summary": "На совещании рассмотрены текущие вопросы исполнения планов. Система выделила ключевые решения и поручения для дальнейшего контроля.",
            "participants": [
                {"speaker_label": "SPEAKER_00", "name": "Спикер 1", "role": "Должность не определена", "auto_detected": True},
                {"speaker_label": "SPEAKER_01", "name": "Спикер 2", "role": "Должность не определена", "auto_detected": True},
            ],
            "action_items": [
                {
                    "id": f"{meeting_id}-a1",
                    "task": "Подготовить итоговую справку и направить участникам",
                    "assignee": "Спикер 2",
                    "speaker_label": "SPEAKER_01",
                    "deadline_raw": "в течение недели",
                    "deadline_date": date.today() + timedelta(days=7),
                    "status": "in_progress",
                    "urgency": "medium",
                    "quote": quote,
                    "timestamp": segments[-1]["start"],
                    "needs_review": False,
                    "source_segment_ids": [],
                    "reminded_at": None,
                }
            ],
        }
