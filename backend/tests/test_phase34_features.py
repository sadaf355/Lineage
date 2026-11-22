import io
import json
import math
import struct
import wave
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.deps import get_current_user
from app.models.user import User
from app.routers import auth as auth_router, incidents as incidents_router, phase34 as phase34_router

from app.services.phase34 import evaluate_binary_predictions, audio_spectrogram_fingerprint
from app.services.source_tracing import validate_trace_accept_payload


def test_detection_evaluation_reports_real_metrics():
    rows = [
        {"label": 1, "score": 90},
        {"label": 0, "score": 10},
        {"label": 1, "score": 80},
        {"label": 0, "score": 20},
    ]
    result = evaluate_binary_predictions(rows)
    assert result["samples"] == 4
    assert result["accuracy"] == 100.0
    assert result["f1"] == 100.0


def test_audio_fingerprint_is_deterministic():
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000)
        for i in range(16000):
            wf.writeframes(struct.pack("<h", int(10000 * math.sin(2 * math.pi * 440 * i / 16000))))
    raw = buf.getvalue()
    assert audio_spectrogram_fingerprint(raw) == audio_spectrogram_fingerprint(raw)


def test_trace_accept_requires_strict_match():
    payload = {"url": "https://example.com", "platform": "example.com", "observed_at": "2026-09-30T10:00:00", "similarity_score": 84, "page_sha256": "a", "page_storage_path": "/tmp/a", "agreeing_hashes": 3}
    try:
        validate_trace_accept_payload(payload)
        assert False, "expected validation failure"
    except ValueError as exc:
        assert "85" in str(exc)


def test_trace_accept_requires_two_hashes():
    payload = {"url": "https://example.com", "platform": "example.com", "observed_at": "2026-09-30T10:00:00", "similarity_score": 92, "page_sha256": "a", "page_storage_path": "/tmp/a", "agreeing_hashes": 1}
    try:
        validate_trace_accept_payload(payload)
        assert False, "expected validation failure"
    except ValueError as exc:
        assert "two" in str(exc).lower()


CSRF = {"X-Lineage-CSRF": "1"}


def test_refresh_token_is_single_use_and_logout_revokes_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    db = Session()
    app = FastAPI()
    app.include_router(auth_router.router)
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    try:
        assert client.post("/auth/register", json={"email": "refresh@example.com", "password": "StrongPass123!"}).status_code == 201
        first = client.post("/auth/login", data={"username": "refresh@example.com", "password": "StrongPass123!"})
        assert first.status_code == 200
        old_cookie = first.cookies.get("lineage_refresh")
        assert old_cookie
        rotated = client.post("/auth/refresh", headers=CSRF)
        assert rotated.status_code == 200
        replay = TestClient(app, cookies={"lineage_refresh": old_cookie})
        replay_resp = replay.post("/auth/refresh", headers=CSRF)
        assert replay_resp.status_code == 401
        assert client.post("/auth/logout", headers=CSRF).status_code == 204
        assert client.post("/auth/refresh", headers=CSRF).status_code == 401
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_retention_purge_deletes_stored_files(monkeypatch):
    from datetime import datetime, timedelta
    from app.models.incident import Incident
    from app.models.media import MediaItem
    from app.routers.incidents import _delete_incident_record

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    db = Session()
    user = User(email="purge@example.invalid", hashed_password="unused")
    db.add(user); db.commit()
    incident = Incident(owner_id=user.id, title="old", status="created", updated_at=datetime.utcnow() - timedelta(days=90))
    db.add(incident); db.commit()
    media = MediaItem(incident_id=incident.id, kind="image", original_filename="x.png", storage_path="/tmp/x.enc", file_size_bytes=1)
    db.add(media); db.commit()
    with patch("app.routers.incidents.file_storage.delete_encrypted") as delete_mock:
        _delete_incident_record(incident, db)
        delete_mock.assert_called_once_with("/tmp/x.enc")
    assert db.query(Incident).filter_by(id=incident.id).first() is None
    db.close()


def test_detection_evaluation_normalizes_csv_style_labels():
    result = evaluate_binary_predictions([
        {"label": "1", "score": "90"},
        {"label": "0", "score": "10"},
        {"label": "fake", "score": "80"},
        {"label": "real", "score": "20"},
    ])
    assert result["accuracy"] == 100.0
    assert result["f1"] == 100.0


def test_request_body_limit_rejects_chunked_payloads_without_content_length():
    import asyncio
    from app.main import RequestBodyLimitMiddleware

    async def downstream(scope, receive, send):
        while True:
            message = await receive()
            if message.get("type") == "http.disconnect":
                return
            if not message.get("more_body"):
                break
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    middleware = RequestBodyLimitMiddleware(downstream)
    middleware.limit = 5
    messages = [
        {"type": "http.request", "body": b"123", "more_body": True},
        {"type": "http.request", "body": b"456", "more_body": False},
    ]
    sent = []

    async def receive():
        return messages.pop(0) if messages else {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    asyncio.run(middleware({"type": "http", "method": "POST", "path": "/upload", "headers": []}, receive, send))
    assert sent[0]["status"] == 413
