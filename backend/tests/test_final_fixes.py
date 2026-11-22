"""Regression tests for the final-build fixes: inline report jobs, CSRF on cookie endpoints, security headers,
BSA draft as POST, reduced-motion scene. TEST-ONLY data in an in-memory database."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from graph_fakes import make_db, seed_case

from app.db.session import Base, get_db
from app.deps import get_current_user
from app.routers import auth as auth_router, phase56 as phase56_router

ROOT = Path(__file__).parents[2]


def _phase56_client(db, user):
    app = FastAPI()
    app.include_router(phase56_router.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app, raise_server_exceptions=False)


def test_report_job_runs_inline_when_no_worker(monkeypatch):
    monkeypatch.setattr(phase56_router.settings, "JOB_QUEUE_ENABLED", False)
    db = make_db()
    case = seed_case(db, "Inline")
    c = _phase56_client(db, case["user"])
    iid = case["incident"].id
    r = c.post(f"/incidents/{iid}/jobs/report")
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "succeeded", body        # never left "queued" for a worker that does not exist
    assert body["ran_inline"] is True and body["worker_required"] is False
    job = c.get(f"/incidents/{iid}/jobs/{body['job_id']}").json()
    assert job["status"] == "succeeded" and job["result"]["version"] == 1


def test_report_job_is_left_queued_when_a_worker_is_configured(monkeypatch):
    monkeypatch.setattr(phase56_router.settings, "JOB_QUEUE_ENABLED", True)
    monkeypatch.setattr(phase56_router.settings, "REDIS_URL", "redis://127.0.0.1:1/0")
    db = make_db()
    case = seed_case(db, "Queued")
    c = _phase56_client(db, case["user"])
    r = c.post(f"/incidents/{case['incident'].id}/jobs/report")
    assert r.status_code == 202
    assert r.json()["status"] == "queued" and r.json()["worker_required"] is True


def test_bsa_certificate_is_post_only():
    db = make_db()
    case = seed_case(db, "Cert")
    c = _phase56_client(db, case["user"])
    url = f"/incidents/{case['incident'].id}/evidence/bsa63-certificate"
    assert c.get(url).status_code == 405                  # a read must not create a certificate row
    r = c.post(url)
    assert r.status_code == 200 and "draft" in str(r.json()).lower()


def _auth_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    app = FastAPI()
    app.include_router(auth_router.router)
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def test_refresh_and_logout_require_the_csrf_header():
    c = _auth_client()
    assert c.post("/auth/register", json={"email": "csrf@example.com", "password": "StrongPass123!"}).status_code == 201
    assert c.post("/auth/login", data={"username": "csrf@example.com", "password": "StrongPass123!"}).status_code == 200
    assert c.post("/auth/refresh").status_code == 403
    assert c.post("/auth/logout").status_code == 403
    bad_origin = {"X-Lineage-CSRF": "1", "Origin": "https://evil.example"}
    assert c.post("/auth/refresh", headers=bad_origin).status_code == 403
    assert c.post("/auth/refresh", headers={"X-Lineage-CSRF": "1"}).status_code == 200


def test_api_sends_security_headers_and_docs_are_exempt_from_framing_rules():
    from app.main import app
    c = TestClient(app)
    r = c.get("/definitely-not-a-route")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
    assert r.headers["Referrer-Policy"] == "no-referrer"
    docs = c.get("/openapi.json")
    assert "Content-Security-Policy" not in docs.headers   # keeps /docs usable


def test_frontend_sends_csrf_header_and_scene_respects_reduced_motion():
    api = (ROOT / "frontend/src/lib/api.ts").read_text()
    assert api.count("CSRF_HEADERS") >= 3
    assert "bsa63-certificate`, { method: \"POST\" }" in api
    scene = (ROOT / "frontend/src/components/visual/ForensicScene.tsx").read_text()
    assert "prefers-reduced-motion: reduce" in scene and "if(!reduceMotion)" in scene
    assert "fonts.googleapis.com" not in (ROOT / "frontend/index.html").read_text()
