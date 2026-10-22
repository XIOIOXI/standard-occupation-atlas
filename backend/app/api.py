"""Minimal stdlib HTTP API boundary for the frozen single-agent MVP."""
from __future__ import annotations

import json
import cgi
from typing import Callable

from app.agent.curriculum_intelligence import AgentRunError, CurriculumIntelligenceAgent
from app.recruitment_update_service import UpdateJobManager

PROGRAM_ID = "demo-it-practice-program"


def _error(message: str, status: int) -> tuple[int, dict]:
    return status, {"error": {"code": "invalid_request" if status == 400 else "agent_execution_failed", "message": message}}


def validate_analyze_request(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return ["request body must be a JSON object"]
    if payload.get("mode", "offline") != "offline":
        return ["only offline mode is supported in the MVP"]
    program = payload.get("program")
    if program is not None:
        if not isinstance(program, dict): return ["program must be a JSON object"]
        if program.get("program_id") not in (None, PROGRAM_ID): return ["only the frozen demo program is supported"]
    curriculum = payload.get("curriculum")
    if curriculum is not None and not isinstance(curriculum, dict):
        return ["curriculum must be a JSON object"]
    return []


def handle_analyze(payload: object, agent_factory: Callable[[], CurriculumIntelligenceAgent] = CurriculumIntelligenceAgent) -> tuple[int, dict]:
    errors = validate_analyze_request(payload)
    if errors: return _error(errors[0], 400)
    try:
        result = agent_factory().run_offline()
    except AgentRunError:
        return _error("Curriculum analysis could not be completed.", 500)
    except Exception:
        return _error("Curriculum analysis could not be completed.", 500)
    # Keep the agent's unified result as the source of truth; these are API-facing
    # aliases for the names requested by the frontend contract.
    response = dict(result)
    response["status"] = result["run_metadata"]["state"]
    response["coverage"] = result["coverage_summary"]
    response["evidence_references"] = result["evidence"]
    return 200, response


def create_app(job_manager: UpdateJobManager | None = None):
    """Return a tiny WSGI app; no framework, database, queue, or API call required."""
    manager = job_manager or UpdateJobManager()
    def application(environ, start_response):
        method = environ.get("REQUEST_METHOD", "GET")
        path = environ.get("PATH_INFO", "")
        if method == "GET" and path.startswith("/api/recruitment-updates/"):
            job = manager.get(path.rsplit("/", 1)[-1])
            status, payload = (200, job) if job else _error("not found", 404)
        elif method == "POST" and path == "/api/recruitment-updates":
            try:
                content_type = environ.get("CONTENT_TYPE", "")
                if not content_type.startswith("multipart/form-data"):
                    raise ValueError("content type must be multipart/form-data")
                form = cgi.FieldStorage(fp=environ["wsgi.input"], environ=environ, keep_blank_values=True)
                upload = form["file"] if "file" in form else None
                if upload is None or not getattr(upload, "filename", None):
                    raise ValueError("请选择 CSV 或 XLSX 文件")
                mode = form.getfirst("mapping_mode", "cached")
                budget = float(form.getfirst("budget_usd", "0.20"))
                status, payload = 202, manager.start(upload.filename, upload.file.read(), mode, budget)
            except (ValueError, KeyError, TypeError) as exc:
                status, payload = _error(str(exc), 400)
        elif method == "POST" and path == "/api/agent/analyze":
            try:
                length = int(environ.get("CONTENT_LENGTH") or 0)
                raw = environ["wsgi.input"].read(length)
                payload_in = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                status, payload = _error("request body must be valid JSON", 400)
            else:
                status, payload = handle_analyze(payload_in)
        else:
            status, payload = _error("not found", 404)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        start_response(f"{status} {'OK' if status == 200 else 'Error'}", [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(body)))])
        return [body]
    return application
