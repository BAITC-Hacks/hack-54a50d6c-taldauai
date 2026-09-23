"""API/processor tests in a disposable PostgreSQL schema, never production tables.

Set TEST_DATABASE_URL explicitly to enable. Inference is mocked only inside
tests; this does not enable TALDAU_ML_RESULT_FIXTURE in the running application.
"""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4
from zipfile import ZipFile

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.config import PROJECT_ROOT, settings
from app.database import get_db
from app.main import app
from app.models import Meeting
from app.services import processor


@unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), "Set TEST_DATABASE_URL for PostgreSQL integration tests")
class PostgreSQLWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url = os.environ["TEST_DATABASE_URL"]
        cls.schema = "test_ml_" + uuid4().hex
        cls.admin = create_engine(cls.url)
        with cls.admin.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{cls.schema}"'))
        cls.addClassCleanup(cls.cleanup_schema)
        env = {**os.environ, "DATABASE_URL": cls.url, "PGOPTIONS": f"-c search_path={cls.schema}"}
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                       cwd=PROJECT_ROOT / "backend", env=env, check=True, capture_output=True)
        cls.engine = create_engine(cls.url, connect_args={"options": f"-c search_path={cls.schema}"})
        cls.addClassCleanup(cls.engine.dispose)
        cls.sessions = sessionmaker(bind=cls.engine, expire_on_commit=False)
        with cls.engine.connect() as conn:
            assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "20260923_0003"

    @classmethod
    def cleanup_schema(cls):
        # Only the random schema created by this test; no user records touched.
        with cls.admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{cls.schema}" CASCADE'))
        cls.admin.dispose()

    def setUp(self):
        self.uploads = tempfile.TemporaryDirectory(prefix="taldau-test-upload-")
        self.addCleanup(self.uploads.cleanup)
        for name, value in (("uploads_dir", Path(self.uploads.name)),
                            ("ml_result_fixture", None), ("reminders_enabled", False), ("asr_backend", "local_ml"),
                            ("llm_backend", "local_ml")):
            previous = getattr(settings, name)
            object.__setattr__(settings, name, value)
            self.addCleanup(object.__setattr__, settings, name, previous)
        session_patch = patch.object(processor, "SessionLocal", self.sessions)
        session_patch.start()
        self.addCleanup(session_patch.stop)

        def db():
            with self.sessions() as session:
                yield session
        app.dependency_overrides[get_db] = db
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def upload(self, speakers="2"):
        data = {"title": "Integration test", "date": "2026-09-23", "consent_confirmed": "true"}
        if speakers is not None:
            data["num_speakers"] = speakers
        return self.client.post("/api/meetings", data=data,
                                files={"file": ("test.wav", b"test-only audio", "audio/wav")})

    def test_draft_persistence_confirmation_and_docx(self):
        result = json.loads((PROJECT_ROOT / "examples/results/acceptance-result.json").read_text())
        result["warnings"] = ["Проверьте разделение говорящих"]
        result["tasks"][0]["needs_review"] = False  # confidence must not bypass approval
        with patch.object(processor, "run_ml_pipeline", return_value=result) as run:
            response = self.upload()
        self.assertEqual(response.status_code, 201, response.text)
        meeting_id = response.json()["id"]
        self.assertEqual(run.call_args.kwargs, {"num_speakers": 2})
        self.assertTrue(run.call_args.args[1].endswith("+00:00") or run.call_args.args[1].endswith("+05:00"))
        self.engine.dispose()  # fresh connections, not an in-memory API result
        meeting = self.client.get(f"/api/meetings/{meeting_id}").json()
        self.assertEqual(meeting["status"], "done")
        self.assertEqual(meeting["warnings"], result["warnings"])
        self.assertEqual([s["text"] for s in meeting["segments"]], [s["text"] for s in result["segments"]])
        self.assertEqual(len(meeting["action_items"]), len(result["tasks"]))
        for action, raw in zip(meeting["action_items"], result["tasks"]):
            self.assertEqual(action["source_segment_ids"], raw["source_segment_ids"])
            self.assertTrue(action["needs_review"])
        with self.sessions() as session:
            self.assertEqual(session.get(Meeting, meeting_id).ml_result, result)
        self.assertEqual(self.client.get(f"/api/meetings/{meeting_id}/export.docx").status_code, 409)
        participant = meeting["participants"][0]
        edited = self.client.patch(f"/api/participants/{participant['id']}",
                                  json={"name": "Проверенное имя", "role": "Участник"})
        self.assertEqual(edited.status_code, 200)
        meeting = self.client.get(f"/api/meetings/{meeting_id}").json()
        for action in meeting["action_items"]:
            action_url = f"/api/action-items/{action['id']}"
            self.assertEqual(self.client.post(action_url + "/remind").status_code, 409)
            invalid = self.client.patch(action_url, json={"deadline_date": None, "needs_review": False, "expected_revision": action["revision"]})
            self.assertEqual(invalid.status_code, 422)
            edited = self.client.patch(action_url, json={"assignee": "Марат", "speaker_label": None, "deadline_date": "2026-10-01", "expected_revision": action["revision"]})
            self.assertEqual(edited.status_code, 200, edited.text)
            confirmed = self.client.patch(action_url, json={"needs_review": False, "expected_revision": edited.json()["revision"]})
            self.assertEqual(confirmed.status_code, 200, confirmed.text)
        self.engine.dispose()
        with TestClient(app) as restarted_client:
            saved = restarted_client.get(f"/api/meetings/{meeting_id}").json()
            self.assertEqual(saved["participants"][0]["name"], "Проверенное имя")
            self.assertTrue(all(not a["needs_review"] and a["assignee"] == "Марат" for a in saved["action_items"]))
            exported = restarted_client.get(f"/api/meetings/{meeting_id}/export.docx")
        self.assertEqual(exported.status_code, 200)
        with ZipFile(io.BytesIO(exported.content)) as document:
            xml = document.read("word/document.xml").decode()
        self.assertIn("Протокол совещания", xml)
        self.assertIn("Марат", xml)
        self.assertIn("01.10.2026", xml)

    def test_manual_edit_stale_confirmation_and_automatic_reminders(self):
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        from app.services.reminders import generate_notifications
        now = datetime.now(ZoneInfo(settings.timezone))
        today = now.date()
        result = json.loads((PROJECT_ROOT / "examples/results/acceptance-result.json").read_text())
        with patch.object(processor, "run_ml_pipeline", return_value=result):
            meeting_id = self.upload().json()["id"]
        base = f"/api/meetings/{meeting_id}/action-items"
        self.assertEqual(self.client.post(base, json={"task": "  "}).status_code, 422)
        action = self.client.post(base, json={"task": "Согласовать договор", "assignee": "Внешний юридический отдел", "deadline_date": str(today)}).json()
        self.assertTrue(action["needs_review"])
        self.assertIsNone(action["speaker_label"])
        url = f"/api/action-items/{action['id']}"
        def edit(payload, revision=None):
            return self.client.patch(url, json={**payload, "expected_revision": revision or action["revision"]})
        generate_notifications(self.sessions, now)
        self.assertFalse(any(n["action_item_id"] == action["id"] for n in self.client.get("/api/notifications").json()))
        for key in ("task", "status", "urgency", "needs_review"):
            self.assertEqual(edit({key: None}).status_code, 422)
        self.assertEqual(edit({"task": "  "}).status_code, 422)
        action = edit({"needs_review": False}).json()
        generate_notifications(self.sessions, now)
        generate_notifications(self.sessions, now)
        notices = [n for n in self.client.get("/api/notifications").json() if n["action_item_id"] == action["id"]]
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0]["kind"], "due_soon")
        self.assertEqual(self.client.patch(f"/api/notifications/{notices[0]['id']}/read").status_code, 200)
        self.engine.dispose()
        self.assertTrue(next(n for n in self.client.get("/api/notifications").json() if n["id"] == notices[0]["id"])["read_at"])
        old_revision = action["revision"]
        action = edit({"task": "Согласовать новую редакцию договора"}).json()
        self.assertTrue(action["needs_review"])
        self.assertEqual(edit({"needs_review": False}, old_revision).status_code, 409)
        self.assertEqual(self.client.post(url + "/remind").status_code, 409)
        self.assertFalse(any(n["action_item_id"] == action["id"] for n in self.client.get("/api/notifications").json()))
        action = edit({"deadline_date": str(today - timedelta(days=1))}).json()
        action = edit({"needs_review": False}).json()
        generate_notifications(self.sessions, now)
        notices = [n for n in self.client.get("/api/notifications").json() if n["action_item_id"] == action["id"]]
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0]["kind"], "overdue")
        self.assertIsNone(notices[0]["read_at"])
        action = edit({"status": "done"}).json()
        self.assertFalse(action["needs_review"])
        self.assertFalse(any(n["action_item_id"] == action["id"] for n in self.client.get("/api/notifications").json()))
        self.assertEqual(self.client.delete(url).status_code, 204)

    def test_renaming_linked_participant_requires_review(self):
        result = json.loads((PROJECT_ROOT / "examples/results/acceptance-result.json").read_text())
        with patch.object(processor, "run_ml_pipeline", return_value=result):
            meeting_id = self.upload().json()["id"]
        meeting = self.client.get(f"/api/meetings/{meeting_id}").json()
        person = meeting["participants"][0]
        action = self.client.post(f"/api/meetings/{meeting_id}/action-items", json={
            "task": "Подготовить справку", "assignee": person["name"], "speaker_label": person["speaker_label"], "deadline_date": "2026-10-01"}).json()
        url = f"/api/action-items/{action['id']}"
        action = self.client.patch(url, json={"needs_review": False, "expected_revision": action["revision"]}).json()
        self.client.patch(f"/api/participants/{person['id']}", json={"name": "Уточнённое имя", "role": "Участник"})
        revised = next(a for a in self.client.get(f"/api/meetings/{meeting_id}").json()["action_items"] if a["id"] == action["id"])
        self.assertTrue(revised["needs_review"])
        self.assertEqual(revised["assignee"], "Уточнённое имя")
        self.assertGreater(revised["revision"], action["revision"])

    def test_summary_refresh_keeps_raw_ml_and_current_task_edits(self):
        from app import refresh_summary
        result = json.loads((PROJECT_ROOT / "examples/results/acceptance-result.json").read_text())
        with patch.object(processor, "run_ml_pipeline", return_value=result):
            meeting_id = self.upload().json()["id"]
        meeting = self.client.get(f"/api/meetings/{meeting_id}").json()
        action = meeting["action_items"][0]
        edited = self.client.patch(f"/api/action-items/{action['id']}", json={
            "expected_revision": action["revision"], "assignee": "Юридический отдел", "speaker_label": None}).json()
        with patch.object(refresh_summary, "SessionLocal", self.sessions), patch(
                "ml.summary.summarize_meeting", return_value=("Тема встречи\nОбсудили договор.", [])) as summarize:
            refresh_summary.refresh_summary(meeting_id)
        self.assertIn("Юридический отдел", [a["assignee_name"] for a in summarize.call_args.args[1]])
        saved = self.client.get(f"/api/meetings/{meeting_id}").json()
        self.assertEqual(saved["summary"], "Тема встречи\nОбсудили договор.")
        self.assertEqual(saved["action_items"][0], edited)
        with self.sessions() as session:
            self.assertEqual(session.get(Meeting, meeting_id).ml_result, result)

    def test_exception_is_persisted_as_failed_without_fake_results(self):
        with patch.object(processor, "run_ml_pipeline", side_effect=RuntimeError("ML unavailable")) as run:
            response = self.upload(speakers=None)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(run.call_args.kwargs, {"num_speakers": None})
        meeting_id = response.json()["id"]
        with self.sessions() as session:
            meeting = session.get(Meeting, meeting_id)
            self.assertEqual(meeting.status, "failed")
            self.assertEqual(meeting.error_message, "ML unavailable")
            self.assertIsNone(meeting.ml_result)
            self.assertEqual(meeting.segments, [])
            self.assertEqual(meeting.action_items, [])
        self.assertEqual(self.client.get(f"/api/meetings/{meeting_id}/export.docx").status_code, 409)

    def test_invalid_result_does_not_persist_partial_rows(self):
        result = json.loads((PROJECT_ROOT / "examples/results/acceptance-result.json").read_text())
        result["tasks"][0]["due_date"] = "not-a-date"
        with patch.object(processor, "run_ml_pipeline", return_value=result):
            response = self.upload()
        with self.sessions() as session:
            meeting = session.get(Meeting, response.json()["id"])
            self.assertEqual(meeting.status, "failed")
            self.assertEqual(meeting.segments, [])
            self.assertEqual(meeting.action_items, [])


if __name__ == "__main__":
    unittest.main()
