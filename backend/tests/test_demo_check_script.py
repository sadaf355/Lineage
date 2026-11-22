"""scripts/demo_check.py against a stand-in HTTP server (tests the script's logic, not the real API)."""
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

pytest.importorskip("requests")
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "demo_check.py"


def _server(overrides=None):
    overrides = overrides or {}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body=None, headers=None):
            raw = json.dumps(body).encode() if body is not None else b""
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            return self.rfile.read(n) if n else b""

        def do_GET(self):
            if self.path == "/health":
                return self._send(200, {"env": "development", "detector": {"loaded": True, "model_id": "toy"}},
                                  overrides.get("health_headers", {"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer"}))
            if self.path.endswith("/integrity"):
                return self._send(200, {"ok": True})
            self._send(404, {"detail": "nope"})

        def do_DELETE(self):
            self._send(204)

        def do_POST(self):
            body, p = self._body(), self.path
            if p == "/auth/refresh":
                return self._send(403, {"detail": "Missing CSRF header"})
            if p == "/auth/register":
                return self._send(201, {"id": "u1"})
            if p == "/auth/login":
                return self._send(200, {"access_token": "tok"})
            if p == "/incidents":
                return self._send(201, {"id": "i1"})
            if p == "/incidents/i1/media":
                return self._send(400, {"detail": "looks like an executable"}) if b"MZ\x90" in body else self._send(201, {"id": "m1"})
            if p.endswith("/detect"):
                return self._send(200, {"model_name": "toy", "manipulation_likelihood": 12.0})
            if p.endswith("/fingerprint"):
                return self._send(200, {})
            if p == "/incidents/i1/evidence/manifest":
                code = overrides.get("manifest_status", 201)
                return self._send(code, {"id": "mf1", "key_id": "k1"} if code == 201 else {"detail": "not configured"})
            if p.endswith("/verify"):
                return self._send(200, {"verification": {"signature_valid": True, "manifest_sha256_matches": True, "entries_digest_matches": True},
                                        "case_drift_since_signing": {"unchanged": True}})
            if p.endswith("/trace-url"):
                return self._send(400, {"detail": "private address"})
            if p == "/incidents/i1/report":
                return self._send(201, {})
            if p == "/incidents/i1/jobs/report":
                return self._send(202, overrides.get("job", {"status": "succeeded", "ran_inline": True, "worker_required": False}))
            if p.endswith("/bsa63-certificate"):
                return self._send(200, {"status": "DRAFT", "legal_review": "pending"})
            self._send(404, {"detail": "nope"})

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _run(srv, *extra):
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    return subprocess.run([sys.executable, str(SCRIPT), "--api", url, *extra], capture_output=True, text=True, timeout=120)


def test_all_steps_pass_against_a_healthy_stand_in():
    srv = _server()
    try:
        done = _run(srv)
    finally:
        srv.shutdown()
    assert done.returncode == 0, done.stdout + done.stderr
    for step in ("Security headers present", "Refresh without CSRF header is refused", "Renamed executable refused at upload",
                 "Sign evidence manifest", "Manifest signature verifies", "Report job completes", "BSA section 63 certificate is marked draft"):
        assert step in done.stdout, step


def test_missing_signing_key_is_reported_as_a_failure_with_the_fix():
    srv = _server({"manifest_status": 503})
    try:
        done = _run(srv)
    finally:
        srv.shutdown()
    assert done.returncode == 1
    assert "MANIFEST_SIGNING_KEY" in done.stdout


def test_queued_report_job_with_a_worker_is_a_warning_not_a_failure():
    srv = _server({"job": {"status": "queued", "ran_inline": False, "worker_required": True}})
    try:
        done = _run(srv)
    finally:
        srv.shutdown()
    assert done.returncode == 0 and "WARN" in done.stdout


def test_missing_security_headers_fail_the_check():
    srv = _server({"health_headers": {}})
    try:
        done = _run(srv)
    finally:
        srv.shutdown()
    assert done.returncode == 1 and "missing" in done.stdout
