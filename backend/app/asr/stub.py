from .base import ASRBackend, TranscriptSegment


class StubASR(ASRBackend):
    def transcribe(self, audio_path: str) -> list[TranscriptSegment]:
        del audio_path
        return [
            {
                "start": 8,
                "end": 25,
                "speaker_label": "SPEAKER_00",
                "lang": "ru",
                "text": "Коллеги, обсудим текущий статус задач и зафиксируем решения по итогам совещания.",
            },
            {
                "start": 28,
                "end": 48,
                "speaker_label": "SPEAKER_01",
                "lang": "mixed",
                "text": "Основные показатели собраны. Қалған мәселелер бойынша ақпаратты ертең дайындаймыз.",
            },
            {
                "start": 52,
                "end": 70,
                "speaker_label": "SPEAKER_00",
                "lang": "ru",
                "text": "Подготовьте итоговую справку в течение недели и направьте её всем участникам.",
            },
        ]
