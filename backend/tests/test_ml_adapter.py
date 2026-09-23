import json
import unittest
from datetime import date
from pathlib import Path

from app.services.ml_adapter import adapt_ml_result


FIXTURE = Path(__file__).resolve().parents[2] / "examples" / "results" / "meeting_result.json"


class MLAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.result = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_maps_fixture_without_losing_review_evidence(self) -> None:
        mapped = adapt_ml_result("meeting-test", self.result)

        self.assertEqual(len(mapped["segments"]), 2)
        self.assertEqual(len(mapped["action_items"]), 3)
        self.assertEqual(mapped["segments"][0]["source_segment_id"], "seg_0001")
        self.assertEqual(mapped["segments"][0]["text"], self.result["segments"][0]["text"])
        self.assertEqual(mapped["segments"][0]["suggested_text"], self.result["segments"][0]["suggested_text"])
        self.assertEqual(mapped["action_items"][0]["id"], "meeting-test-task_0001")
        self.assertEqual(mapped["action_items"][0]["source_segment_ids"], ["seg_0001"])
        self.assertTrue(all(item["needs_review"] for item in mapped["action_items"]))

    def test_rejects_task_without_valid_source_segment(self) -> None:
        self.result["tasks"][0]["source_segment_ids"] = ["seg_missing"]
        with self.assertRaisesRegex(ValueError, "source_segment_ids"):
            adapt_ml_result("meeting-test", self.result)

    def test_preserves_warnings(self) -> None:
        self.result["warnings"] = ["Диаризация требует ручной проверки"]
        mapped = adapt_ml_result("meeting-test", self.result)
        self.assertEqual(mapped["warnings"], self.result["warnings"])

    def test_deadline_priority_boundaries_still_require_human_review(self) -> None:
        for deadline, expected in (("2026-09-22", "high"), ("2026-09-23", "high"),
                                   ("2026-09-25", "high"), ("2026-09-26", "medium"),
                                   ("2026-09-30", "medium"), ("2026-10-01", "low")):
            with self.subTest(deadline=deadline):
                self.result["tasks"][0]["due_date"] = deadline
                action = adapt_ml_result("meeting-test", self.result, today=date(2026, 9, 23))["action_items"][0]
                self.assertEqual(action["urgency"], expected)
                self.assertTrue(action["needs_review"])
                self.assertEqual(action["deadline_date"], deadline)

    def test_missing_deadline_does_not_invent_date_or_high_priority(self) -> None:
        self.result["tasks"][0]["due_date"] = None
        action = adapt_ml_result("meeting-test", self.result, today=date(2026, 9, 23))["action_items"][0]
        self.assertEqual(action["urgency"], "medium")
        self.assertIsNone(action["deadline_date"])
        self.assertTrue(action["needs_review"])


if __name__ == "__main__":
    unittest.main()
