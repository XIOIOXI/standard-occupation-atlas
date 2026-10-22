import json
import unittest
from io import BytesIO
from app.api import create_app, handle_analyze
from app.recruitment_update_service import _last_json


class ApiTests(unittest.TestCase):
    def test_job_result_parser_returns_outer_json(self):
        self.assertEqual(_last_json('{"old": 1}\n{"status":"completed","counts":{"new_atomic_jobs":2}}'), {"status": "completed", "counts": {"new_atomic_jobs": 2}})
    def test_valid_request_returns_existing_agent_contract(self):
        status, payload = handle_analyze({"mode": "offline", "program": {"program_id": "demo-it-practice-program"}})
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "completed")
        for key in ("program", "market_summary", "curriculum_summary", "coverage", "priority_gaps", "recommendations", "evidence_references", "limitations", "run_metadata"):
            self.assertIn(key, payload)
        self.assertEqual(payload["run_metadata"]["api_calls"], 0)

    def test_invalid_request_returns_400(self):
        status, payload = handle_analyze({"mode": "unsupported"})
        self.assertEqual(status, 400)
        self.assertIn("error", payload)
        self.assertNotIn("traceback", json_text(payload))

    def test_internal_failure_returns_safe_500(self):
        class FailingAgent:
            def run_offline(self): raise RuntimeError("secret internal detail")
        status, payload = handle_analyze({}, lambda: FailingAgent())
        self.assertEqual(status, 500)
        self.assertEqual(payload["error"]["message"], "Curriculum analysis could not be completed.")
        self.assertNotIn("secret", json_text(payload))

    def test_local_update_upload_starts_existing_job_manager(self):
        class Manager:
            def start(self, filename, content, mode, budget):
                self.called = (filename, content, mode, budget)
                return {"job_id": "WEB-test", "status": "queued"}
            def get(self, job_id): return {"job_id": job_id, "status": "completed"}
        manager = Manager()
        boundary = "----test-boundary"
        content = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"update.csv\"\r\nContent-Type: text/csv\r\n\r\na,b\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"mapping_mode\"\r\n\r\ncached\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"budget_usd\"\r\n\r\n0.20\r\n--{boundary}--\r\n").encode()
        captured = []
        response = create_app(manager)({"REQUEST_METHOD": "POST", "PATH_INFO": "/api/recruitment-updates", "CONTENT_TYPE": f"multipart/form-data; boundary={boundary}", "CONTENT_LENGTH": str(len(content)), "wsgi.input": BytesIO(content)}, lambda status, headers: captured.append(status))
        self.assertTrue(captured[0].startswith("202"))
        self.assertEqual(json.loads(b"".join(response))["job_id"], "WEB-test")
        self.assertEqual(manager.called[0], "update.csv")


def json_text(value):
    import json
    return json.dumps(value)
