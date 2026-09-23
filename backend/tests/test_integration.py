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
            assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "20260923_0002"

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
                            ("ml_result_fixture", None), ("asr_backend", "local_ml"),
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
        for action in meeting["action_items"]:
            action_url = f"/api/action-items/{action['id']}"
            self.assertEqual(self.client.post(action_url + "/remind").status_code, 409)
            invalid = self.client.patch(action_url, json={"deadline_date": None, "needs_review": False})
            self.assertEqual(invalid.status_code, 422)
            confirmed = self.client.patch(action_url, json={"assignee": "Марат", "deadline_date": "2026-10-01", "needs_review": False})
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
