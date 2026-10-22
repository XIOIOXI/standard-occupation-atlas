"""Local-only launcher for the existing auditable recruitment update script.

This module owns uploads and job status only.  Increment detection, SNO
classification, validation, persistence, and frontend data export remain in
``scripts/process_recruitment_update.py``.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = ROOT / "data" / "managed_uploads"
UPDATE_SCRIPT = ROOT / "scripts" / "process_recruitment_update.py"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class UpdateJobManager:
    def __init__(self, runner: Any = subprocess.Popen) -> None:
        self.runner = runner
        self.sandbox = Path(os.environ["RECRUITMENT_SANDBOX_DIR"]).resolve() if os.environ.get("RECRUITMENT_SANDBOX_DIR") else None
        self.jobs: dict[str, dict[str, Any]] = {}
        self.active_checksums: set[str] = set()
        self.lock = threading.Lock()

    def start(self, filename: str, content: bytes, mapping_mode: str, budget_usd: float) -> dict[str, Any]:
        if Path(filename).suffix.casefold() not in {".csv", ".xlsx"}:
            raise ValueError("只支持 CSV 或 XLSX 文件")
        if not content or len(content) > MAX_UPLOAD_BYTES:
            raise ValueError("文件为空或超过 50 MB 限制")
        if mapping_mode not in {"cached", "model"} or not 0.01 <= budget_usd <= 1000:
            raise ValueError("处理参数无效")
        checksum = hashlib.sha256(content).hexdigest()
        with self.lock:
            active = next((job for job in self.jobs.values() if job["checksum"] == checksum and job["status"] in {"queued", "running"}), None)
            if active:
                return {**active, "duplicate_submission": True}
            if self.sandbox and any(job["status"] in {"queued", "running"} for job in self.jobs.values()):
                raise ValueError("隔离预算账本已有任务运行，请等待完成")
            upload_dir = self.sandbox / "uploads" if self.sandbox else UPLOAD_DIR
            upload_dir.mkdir(parents=True, exist_ok=True)
            job_id = "WEB-" + uuid.uuid4().hex[:12]
            suffix = Path(filename).suffix.casefold()
            source = upload_dir / f"{job_id}{suffix}"
            source.write_bytes(content)
            job = {"job_id": job_id, "filename": Path(filename).name, "checksum": checksum, "status": "queued", "created_at": timestamp(), "mapping_mode": mapping_mode, "budget_usd": budget_usd, "result": None, "error": None}
            self.jobs[job_id] = job
            self.active_checksums.add(checksum)
            thread = threading.Thread(target=self._run, args=(job_id, source), daemon=True)
            thread.start()
            return dict(job)

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self.lock:
            job = self.jobs.get(job_id)
            return dict(job) if job else None

    def _run(self, job_id: str, source: Path) -> None:
        with self.lock:
            job = self.jobs[job_id]
            job["status"] = "running"
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(ROOT / "backend")
        command = [sys.executable, str(UPDATE_SCRIPT), str(source), "--mapping-mode", job["mapping_mode"], "--budget-usd", str(job["budget_usd"])]
        if self.sandbox:
            command += ["--sandbox-dir", str(self.sandbox), "--budget-ledger", str(self.sandbox / "shared_budget.json")]
        try:
            completed = self.runner(command, cwd=ROOT, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if hasattr(completed, "communicate"):
                stdout, stderr = completed.communicate()
                returncode = completed.returncode
            else:  # test runner accepts subprocess.run-style completed results
                stdout, stderr, returncode = completed.stdout, completed.stderr, completed.returncode
            result = _last_json(stdout)
            with self.lock:
                job = self.jobs[job_id]
                job["completed_at"] = timestamp()
                job["result"] = result
                job["status"] = "completed" if returncode == 0 else "failed"
                job["error"] = None if returncode == 0 else _safe_error(stderr or stdout)
        except Exception as exc:
            with self.lock:
                job = self.jobs[job_id]
                job["status"] = "failed"
                job["completed_at"] = timestamp()
                job["error"] = _safe_error(str(exc))
        finally:
            with self.lock:
                self.active_checksums.discard(self.jobs[job_id]["checksum"])


def _last_json(stdout: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    candidates: list[dict[str, Any]] = []
    offset = 0
    while offset < len(stdout):
        character = stdout[offset]
        if character != "{":
            offset += 1
            continue
        try:
            parsed, length = decoder.raw_decode(stdout[offset:])
        except json.JSONDecodeError:
            offset += 1
            continue
        if isinstance(parsed, dict):
            candidates.append(parsed)
        offset += length
    return candidates[-1] if candidates else None


def _safe_error(message: str) -> str:
    return message.strip()[-1000:] or "更新任务未返回可用结果"
