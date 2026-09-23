import unittest
from datetime import date
from unittest.mock import patch

from ml.pipeline import _combine, _kazllm_suggestions, _resolve_due_date, _validate_extraction
from ml.evaluate import _edit_distance, _normalize
from ml.mixed_asr import decode_words


class PipelineTests(unittest.TestCase):
    def test_ctc_repeat_after_blank_and_word_timestamps(self):
        words = decode_words([0, 0, 3, 0, 1, 2, 2], {0: "а", 1: "|", 2: "б"}, 3, 1000, 700)
        self.assertEqual([w["text"] for w in words], ["аа", "б"])
        self.assertEqual(words[0]["start_ms"], 1000)
        self.assertEqual(words[-1]["end_ms"], 1700)

    def test_speaker_change_within_asr_segment(self):
        segments, _ = _combine([{"words": [
            {"text": "Жұмаға", "start_ms": 0, "end_ms": 400},
            {"text": "дайын", "start_ms": 500, "end_ms": 900}]}], [
                {"speaker": "a", "start_ms": 0, "end_ms": 450},
                {"speaker": "b", "start_ms": 450, "end_ms": 1000}])
        self.assertEqual([s["speaker_id"] for s in segments], ["SPEAKER_00", "SPEAKER_01"])

    def test_cer_counts_kazakh_letters(self):
        self.assertEqual(_normalize("Қазақша, орысша!"), "қазақша орысша")
        self.assertEqual(_edit_distance("срок", "срок"), 0)
        self.assertEqual(_edit_distance("жұма", "жума"), 1)

    def test_kazllm_keeps_original_and_adds_suggestion(self):
        segments = [{"id": "seg_0001", "text": "Жумағадейн отчетты дайндап"}]
        with patch.dict("os.environ", {"TALDAU_KAZLLM_MODEL": "taldau-kazllm"}):
            with patch("ml.pipeline._ollama_chat", return_value={"segments": [
                {"id": "seg_0001", "text": "Жұмаға дейін отчетты дайындап"}]}) as call:
                warnings = _kazllm_suggestions(segments)
        self.assertEqual(warnings, [])
        self.assertEqual(segments[0]["text"], "Жумағадейн отчетты дайндап")
        self.assertEqual(segments[0]["suggested_text"], "Жұмаға дейін отчетты дайындап")
        self.assertEqual(call.call_args.args[0], "taldau-kazllm")

    def test_speaker_overlap_and_unknown_speaker(self):
        segments, speakers = _combine(
            [{"start_ms": 0, "end_ms": 1000, "text": "Первое"},
             {"start_ms": 2000, "end_ms": 3000, "text": "Второе"}],
            [{"start_ms": 0, "end_ms": 800, "speaker": "original_B"}],
        )
        self.assertEqual(segments[0]["speaker_id"], "SPEAKER_00")
        self.assertIsNone(segments[1]["speaker_id"])
        self.assertEqual(speakers, [{"id": "SPEAKER_00", "display_name": None}])

    def test_relative_date_uses_meeting_day(self):
        self.assertEqual(_resolve_due_date(None, "до пятницы", date(2026, 9, 23)), "2026-09-25")
        self.assertEqual(_resolve_due_date(None, "до 15 октября", date(2026, 9, 23)), "2026-10-15")
        self.assertIsNone(_resolve_due_date("2026-09-25", "после согласования", date(2026, 9, 23)))
        self.assertEqual(_resolve_due_date(None, "ертең", date(2026, 9, 23)), "2026-09-24")
        self.assertEqual(_resolve_due_date(None, "жексенбіге дейін", date(2026, 9, 23)), "2026-09-27")
        self.assertEqual(_resolve_due_date(None, "15 қазанға дейін", date(2026, 9, 23)), "2026-10-15")
        self.assertIsNone(_resolve_due_date(None, "келесі апта", date(2026, 9, 23)))
        self.assertIsNone(_resolve_due_date(None, "до 15 сентября", date(2026, 9, 23)))

    def test_rejects_task_without_evidence_and_marks_uncertain_task(self):
        raw = {"summary": "Обсудили график.", "tasks": [
            {"description": "Прислать график", "assignee_name": "Айнур",
             "assignee_speaker_id": "SPEAKER_01", "assigner_speaker_id": "SPEAKER_00",
             "due_date": None, "due_text": "после согласования",
             "source_segment_ids": ["seg_0001"]},
            {"description": "Выдуманное поручение", "source_segment_ids": ["seg_9999"]},
        ]}
        tasks, _, warnings = _validate_extraction(
            raw, [{"id": "seg_0001"}],
            [{"id": "SPEAKER_00"}, {"id": "SPEAKER_01"}], date(2026, 9, 23),
        )
        self.assertEqual(len(tasks), 1)
        self.assertTrue(tasks[0]["needs_review"])
        self.assertIsNone(tasks[0]["due_date"])
        self.assertEqual(len(warnings), 1)


if __name__ == "__main__":
    unittest.main()
