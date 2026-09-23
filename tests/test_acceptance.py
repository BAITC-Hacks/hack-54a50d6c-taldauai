from datetime import date
from io import BytesIO
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from ml.evaluate_tasks import compare_tasks
from ml.evaluate_meeting import compare_speakers
from ml.export import docx_bytes
from ml.pipeline import _suggest_speaker_names, _validate_extraction, _ollama_chat, _NoRedirect, _resolve_due_date, _review_assignments


class AcceptanceTests(unittest.TestCase):
    def test_matcher_does_not_count_a_prediction_twice(self):
        task = {"description": "Договор", "assignee_name": "Марат", "due_date": None, "source_segment_ids": ["s1"]}
        expected = {"assignee_name": "Марат", "due_date": None, "keywords": ["договор"], "source": "s1"}
        report = compare_tasks([task], [expected, expected])
        self.assertFalse(report["passed"])
        self.assertEqual(report["matched"], 1)
        self.assertTrue(compare_tasks([], [])["passed"])

    def test_speaker_score_handles_permutations_and_collapsed_clusters(self):
        reference = [{"start_ms": 0, "end_ms": 1000, "speaker": "a"}, {"start_ms": 1000, "end_ms": 2000, "speaker": "b"}]
        segments = [{"start_ms": 0, "end_ms": 1000, "speaker_id": "second"}, {"start_ms": 1000, "end_ms": 2000, "speaker_id": "first"}]
        self.assertTrue(compare_speakers(segments, reference)["passed"])
        segments[1]["speaker_id"] = "second"
        self.assertFalse(compare_speakers(segments, reference)["passed"])

    def test_docx_contains_cyrillic_sources_and_draft_warning(self):
        protocol = json.loads(Path("examples/results/meeting_result.json").read_text())
        protocol["summary"] = "Қазақша <мәтін> & русский"
        with ZipFile(BytesIO(docx_bytes(protocol))) as archive:
            self.assertIsNone(archive.testzip())
            self.assertIn("[Content_Types].xml", archive.namelist())
            root = ET.fromstring(archive.read("word/document.xml"))
            text = ''.join(root.itertext())
            for expected in (protocol["summary"], "Черновик", "seg_0001", "Ответственный"):
                self.assertIn(expected, text)
        with self.assertRaises(ValueError):
            docx_bytes({**protocol, "status": "failed"})

    def test_self_introduction_suggestions_are_not_confirmed_names(self):
        speakers = [{"id": "a", "display_name": None}, {"id": "b", "display_name": None}]
        _suggest_speaker_names([{"speaker_id": "a", "text": "Сәлем, мен Айданамын."},
                                {"speaker_id": "b", "text": "Я готов. Мен дайынмын."}], speakers)
        self.assertEqual(speakers[0]["suggested_name"], "Айдана")
        self.assertIsNone(speakers[0]["display_name"])
        self.assertNotIn("suggested_name", speakers[1])
        speakers = [{"id": "a", "display_name": None}]
        _suggest_speaker_names([{"speaker_id": "a", "text": "Меня зовут Алия. Меня зовут Марат."}], speakers)
        self.assertNotIn("suggested_name", speakers[0])

    def test_human_mapping_overrides_wrong_llm_speaker_id(self):
        raw = {"summary": "", "tasks": [{"description": "Отчёт", "assignee_name": "Марат",
                "assignee_speaker_id": "a", "source_segment_ids": ["s1"]}]}
        tasks, _, _ = _validate_extraction(raw, [{"id": "s1", "speaker_id": "a"}],
            [{"id": "a", "display_name": "Алия"}, {"id": "b", "display_name": "Марат"}], date(2026, 9, 23))
        self.assertEqual(tasks[0]["assignee_speaker_id"], "b")
        raw["tasks"][0]["assignee_name"] = "Неизвестно"
        tasks, _, _ = _validate_extraction(raw, [{"id": "s1"}], [{"id": "a"}], date(2026, 9, 23))
        self.assertIsNone(tasks[0]["assignee_name"])
        self.assertIsNone(tasks[0]["assignee_speaker_id"])

    def test_local_transport_rejects_redirects_and_malformed_envelopes(self):
        with self.assertRaises(RuntimeError):
            _NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.com")
        with patch("ml.pipeline._local_open") as request:
            request.return_value.__enter__.return_value = BytesIO(b'{"message":null}')
            with self.assertRaises(RuntimeError):
                _ollama_chat("test", "fictional", {})

    def test_spoken_dates_and_calendar_durations(self):
        day = date(2026, 9, 23)
        for text, expected in [("к пятнадцатому октября", "2026-10-15"),
                               ("до двадцать первого октября", "2026-10-21"),
                               ("за две недели", "2026-10-07"), ("в течение трёх дней", "2026-09-26"),
                               ("екі апта ішінде", "2026-10-07"), ("до конца квартала", "2026-09-30"),
                               ("на следующем совещании к 20 октября", "2026-10-20"),
                               ("после согласования", None), ("за пять рабочих дней", None)]:
            with self.subTest(text=text):
                self.assertEqual(_resolve_due_date(None, text, day), expected)

    def test_assignment_review_requires_literal_source_and_name(self):
        segments = [{"id": "s1", "speaker_id": "a", "text": "Алия, подготовьте отчёт."}]
        raw = {"summary": "Марат готовит отчёт", "tasks": [{"description": "подготовьте отчёт",
               "assignee_name": "Марат", "assigner_speaker_id": "b", "source_segment_ids": ["s1"]}]}
        with patch("ml.pipeline._ollama_chat", return_value={"tasks": [{"task_index": 0,
                "assignee_name": "Алия", "assignment_segment_id": "s1"}]}):
            reviewed = _review_assignments(raw, segments, [], "test")
        self.assertEqual(reviewed["tasks"][0]["assignee_name"], "Алия")
        self.assertEqual(reviewed["tasks"][0]["assigner_speaker_id"], "a")
        self.assertTrue(reviewed["_assignees_corrected"])
        with patch("ml.pipeline._ollama_chat", return_value={"tasks": [{"task_index": 0,
                "assignee_name": "Другой", "assignment_segment_id": "s1"}]}):
            reviewed = _review_assignments(raw, segments, [], "test")
        self.assertEqual(reviewed["tasks"][0]["assignee_name"], "Алия")


if __name__ == "__main__":
    unittest.main()
