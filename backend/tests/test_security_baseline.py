"""Tests for mitigations that had no test before the threat model was written (docs/THREAT_MODEL.md)."""
import os
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

BACKEND = Path(__file__).resolve().parent.parent


def test_oversized_request_body_is_rejected_before_reaching_the_app():
    c = TestClient(app)
    r = c.post("/auth/login", content=b"x", headers={"content-length": str(10 ** 12), "content-type": "application/x-www-form-urlencoded"})
    assert r.status_code == 413


def test_default_jwt_secret_is_refused_outside_development():
    code = "import app.core.security"
    env = {**os.environ, "ENV": "production", "JWT_SECRET_KEY": "dev-only-secret-change-me"}
    p = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=env, capture_output=True, text=True)
    assert p.returncode != 0 and "JWT_SECRET_KEY must be changed" in p.stderr
    ok = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env={**env, "JWT_SECRET_KEY": "x" * 48}, capture_output=True, text=True)
    assert ok.returncode == 0, ok.stderr
