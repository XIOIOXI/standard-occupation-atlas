"""Serve the local recruitment-update management API on loopback only."""
from __future__ import annotations

import sys
import os
from pathlib import Path
from wsgiref.simple_server import make_server

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.api import create_app  # noqa: E402

if __name__ == "__main__":
    port = int(os.getenv("RECRUITMENT_API_PORT", "18087"))
    server = make_server("127.0.0.1", port, create_app())
    print(f"Local management API: http://127.0.0.1:{port} (loopback only)")
    server.serve_forever()
