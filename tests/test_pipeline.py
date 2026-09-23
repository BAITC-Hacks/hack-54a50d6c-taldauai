import unittest
from datetime import date

from ml.pipeline import _combine, _resolve_due_date, _validate_extraction
from ml.evaluate import _edit_distance, _normalize


class PipelineTests(unittest.TestCase):
    def test_cer_counts_kazakh_letters(self):
        self.assertEqual(_normalize("Қазақша, орысша!"), "қазақша орысша")
        self.assertEqual(_edit_distance("срок", "срок"), 0)
        self.assertEqual(_edit_distance("жұма", "жума"), 1)

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
