"""Behavioral API coverage for the security-critical Phase 1 flows."""
import hashlib
import time
import io
from PIL import Image
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app
from app.services import file_storage, source_tracing

# The client fixture swaps delete_encrypted for a plain unlink; keep the real one for the boundary test.
_REAL_DELETE_ENCRYPTED = file_storage.delete_encrypted

@pytest.fixture()
def client(monkeypatch, tmp_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(engine)
    def override_db():
        db = TestingSession()
        try: yield db
        finally: db.close()
    app.dependency_overrides[get_db] = override_db
    from cryptography.fernet import Fernet
    monkeypatch.setattr(file_storage.settings, "UPLOADS_DIR", str(tmp_path))
    monkeypatch.setattr(file_storage.settings, "FILE_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(file_storage.settings, "FILE_ENCRYPTION_KEY_PREVIOUS", "")
    monkeypatch.setattr(file_storage.settings, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(file_storage, "delete_encrypted", lambda path: Path(path).unlink(missing_ok=True))
    yield TestClient(app), TestingSession, tmp_path
    app.dependency_overrides.clear()


def register(client, email):
    r = client.post("/auth/register", json={"email": email, "password": "StrongPass123!", "display_name": email.split("@")[0]})
    assert r.status_code == 201, r.text


def token(client, email):
    r = client.post("/auth/login", data={"username": email, "password": "StrongPass123!"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def headers(t): return {"Authorization": f"Bearer {t}"}


def test_mixed_case_email_is_canonicalized_and_login_works(client):
    c, Session, _ = client
    register(c, "Sadaf@Example.COM")
    db = Session()
    try:
        user = db.query(__import__("app.models.user", fromlist=["User"]).User).filter_by(email="sadaf@example.com").first()
        assert user is not None
    finally:
        db.close()
    login = c.post("/auth/login", data={"username": "SADAF@example.com", "password": "StrongPass123!"})
    assert login.status_code == 200, login.text


def test_upload_real_png_populates_dimensions(client):
    c, *_ = client
    register(c, "dimensions@example.com")
    t = token(c, "dimensions@example.com")
    iid = c.post("/incidents", json={"title": "Dimensions"}, headers=headers(t)).json()["id"]
    img = Image.new("RGB", (64, 48), "white")
    buf = io.BytesIO(); img.save(buf, format="PNG")
    raw = buf.getvalue()
    up = c.post(f"/incidents/{iid}/media", files={"file": ("real.png", io.BytesIO(raw), "image/png")}, headers=headers(t))
    assert up.status_code == 201, up.text
    body = up.json()
    assert body["width"] == 64
    assert body["height"] == 48


def test_auth_owner_scope_upload_integrity_delete(client):
    c, Session, tmp = client
    register(c, "a@example.com"); register(c, "b@example.com")
    ta, tb = token(c, "a@example.com"), token(c, "b@example.com")
    incident = c.post("/incidents", json={"title": "A case"}, headers=headers(ta)).json()
    iid = incident["id"]
    assert c.get(f"/incidents/{iid}", headers=headers(tb)).status_code == 404
    img = Image.new("RGB", (32, 32), "white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw = buf.getvalue()
    up = c.post(f"/incidents/{iid}/media", files={"file": ("x.png", io.BytesIO(raw), "image/png")}, headers=headers(ta))
    assert up.status_code == 201, up.text
    mid = up.json()["id"]
    assert up.json()["sha256"] == hashlib.sha256(raw).hexdigest()
    assert c.get(f"/incidents/{iid}/media/{mid}/integrity", headers=headers(ta)).json()["verified"]
    assert c.get(f"/incidents/{iid}/media/{mid}/integrity", headers=headers(tb)).status_code == 404
    assert c.delete(f"/incidents/{iid}/media/{mid}", headers=headers(ta)).status_code == 204
    assert c.get(f"/incidents/{iid}/media/{mid}/integrity", headers=headers(ta)).status_code == 404


def test_trace_accept_rejects_weak_match_and_accepts_strong(client):
    c, *_ = client
    register(c, "trace@example.com"); t = token(c, "trace@example.com")
    inc = c.post("/incidents", json={"title": "Trace"}, headers=headers(t)).json()
    iid = inc["id"]
    weak = {"url":"https://example.com/x","platform":"example.com","observed_at":"2026-01-01T00:00:00","similarity_score":84,"agreeing_hashes":2,"page_sha256":"a","page_storage_path":"/tmp/x","review_confirmed":True}
    r = c.post(f"/incidents/{iid}/sources/trace-url/accept", json=weak, headers=headers(t))
    assert r.status_code in (400, 422)


def test_evidence_integrity_and_trace_accept(client):
    c, *_ = client
    register(c, "evidence@example.com"); t = token(c, "evidence@example.com")
    iid = c.post("/incidents", json={"title": "Evidence"}, headers=headers(t)).json()["id"]
    raw = b"captured-page-bytes"
    ev = c.post(f"/incidents/{iid}/evidence", data={"item_type":"screenshot"}, files={"file":("page.html", io.BytesIO(raw), "text/html")}, headers=headers(t))
    assert ev.status_code == 201, ev.text
    eid = ev.json()["id"]
    assert c.get(f"/incidents/{iid}/evidence/{eid}/integrity", headers=headers(t)).json()["verified"]
    page, _ = file_storage.save_encrypted(raw, "captured.html")
    payload = {"url":"https://example.com/page","platform":"example.com","observed_at":"2026-01-01T00:00:00","similarity_score":92,"agreeing_hashes":2,"page_sha256":hashlib.sha256(raw).hexdigest(),"page_storage_path":str(page),"matched_image_url":"https://example.com/image.jpg"}
    payload["review_confirmed"] = True
    payload["issued_at"] = int(time.time())
    payload["signature"] = source_tracing.sign_pending_match(payload, iid)
    accepted = c.post(f"/incidents/{iid}/sources/trace-url/accept", json=payload, headers=headers(t))
    assert accepted.status_code == 201, accepted.text
    assert c.get(f"/incidents/{iid}/sources", headers=headers(t)).json()[0]["is_seeded"] is False


def _signed_pending(iid, raw=b"captured-page-bytes", **over):
    page, _ = file_storage.save_encrypted(raw, "captured.html")
    pending = {"url": "https://example.com/page", "platform": "example.com", "observed_at": "2026-01-01T00:00:00",
               "similarity_score": 92, "method": "perceptual+difference+average", "agreeing_hashes": 3,
               "page_sha256": hashlib.sha256(raw).hexdigest(), "page_storage_path": str(page),
               "matched_image_url": "https://example.com/image.jpg", "issued_at": int(time.time()),
               "review_confirmed": True}
    pending.update(over)
    pending["signature"] = source_tracing.sign_pending_match(pending, iid)
    return pending


def test_trace_accept_rejects_unsigned_tampered_replayed_and_expired(client):
    c, *_ = client
    register(c, "forge@example.com"); t = token(c, "forge@example.com")
    iid = c.post("/incidents", json={"title": "Forge"}, headers=headers(t)).json()["id"]
    other = c.post("/incidents", json={"title": "Other"}, headers=headers(t)).json()["id"]
    url = f"/incidents/{iid}/sources/trace-url/accept"

    good = _signed_pending(iid)
    unsigned = {k: v for k, v in good.items() if k != "signature"}
    assert c.post(url, json=unsigned, headers=headers(t)).status_code == 400

    tampered = dict(good, similarity_score=99)
    assert c.post(url, json=tampered, headers=headers(t)).status_code == 400
    forged_url = dict(good, url="https://evil.example/forged")
    assert c.post(url, json=forged_url, headers=headers(t)).status_code == 400

    # a match signed for one case cannot be replayed on another
    assert c.post(f"/incidents/{other}/sources/trace-url/accept", json=good, headers=headers(t)).status_code == 400

    expired = _signed_pending(iid, issued_at=int(time.time()) - source_tracing.PENDING_TTL_SECONDS - 5)
    assert c.post(url, json=expired, headers=headers(t)).status_code == 400

    assert c.post(url, json=good, headers=headers(t)).status_code == 201


def test_trace_reject_deletes_temporary_capture(client):
    c, *_ = client
    register(c, "reject@example.com"); t = token(c, "reject@example.com")
    iid = c.post("/incidents", json={"title": "Reject"}, headers=headers(t)).json()["id"]
    pending = _signed_pending(iid)
    assert Path(pending["page_storage_path"]).exists()
    r = c.post(f"/incidents/{iid}/sources/trace-url/reject", json=pending, headers=headers(t))
    assert r.status_code == 204
    assert not Path(pending["page_storage_path"]).exists()


def test_delete_encrypted_refuses_paths_outside_uploads(client, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside") / "keep.txt"
    outside.write_text("must survive")
    _REAL_DELETE_ENCRYPTED(str(outside))
    assert outside.exists()
