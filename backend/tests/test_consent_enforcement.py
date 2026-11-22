"""Consent is enforced for every outbound call that carries case data (docs/THREAT_MODEL.md T-PRIVACY-1..4)."""
import ast
import io
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.session import Base, get_db
from app.main import app
from app.models.source import Source
from app.services import audit, consent, file_storage, report_builder


@pytest.fixture()
def api(monkeypatch, tmp_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(engine)

    def override():
        db = Session()
        try: yield db
        finally: db.close()
    app.dependency_overrides[get_db] = override
    from cryptography.fernet import Fernet
    monkeypatch.setattr(file_storage.settings, "UPLOADS_DIR", str(tmp_path))
    monkeypatch.setattr(file_storage.settings, "FILE_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(file_storage.settings, "FILE_ENCRYPTION_KEY_PREVIOUS", "")
    monkeypatch.setattr(file_storage.settings, "DATA_DIR", str(tmp_path))
    c = TestClient(app)
    assert c.post("/auth/register", json={"email": "c@example.com", "password": "StrongPass123!", "display_name": "c"}).status_code == 201
    tok = c.post("/auth/login", data={"username": "c@example.com", "password": "StrongPass123!"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    iid = c.post("/incidents", json={"title": "t"}, headers=h).json()["id"]
    buf = io.BytesIO(); Image.new("RGB", (8, 8)).save(buf, "PNG")
    mid = c.post(f"/incidents/{iid}/media", files={"file": ("a.png", io.BytesIO(buf.getvalue()), "image/png")}, headers=h).json()["id"]
    yield c, h, iid, mid
    app.dependency_overrides.clear()


def _consent(c, h, iid, purpose, granted=True):
    return c.post(f"/incidents/{iid}/privacy/consent", json={"purpose": purpose, "granted": granted}, headers=h)


def test_unknown_consent_purpose_is_rejected_known_is_stored(api):
    c, h, iid, _ = api
    assert _consent(c, h, iid, "external_web_serch").status_code == 422
    for purpose in consent.KNOWN_PURPOSES:
        assert _consent(c, h, iid, purpose).status_code == 201


def test_revoking_consent_takes_effect(api):
    """Regression: the old query only looked at granted=True rows, so a later revoke never won."""
    c, h, iid, _ = api
    from app.db.session import get_db as gd
    db = next(app.dependency_overrides[gd]())
    uid = db.execute(__import__("sqlalchemy").text("select id from users")).scalar()
    assert not consent.has_granted_consent(db, iid, uid, consent.PURPOSE_LLM)
    _consent(c, h, iid, consent.PURPOSE_LLM, True)
    assert consent.has_granted_consent(db, iid, uid, consent.PURPOSE_LLM)
    from app.models.phase56 import ConsentRecord
    row = db.query(ConsentRecord).first(); row.created_at = datetime.utcnow() - timedelta(minutes=5); db.commit()
    _consent(c, h, iid, consent.PURPOSE_LLM, False)
    assert not consent.has_granted_consent(db, iid, uid, consent.PURPOSE_LLM)
    db.close()


def test_consent_is_per_investigation_and_per_purpose(api):
    c, h, iid, _ = api
    other = c.post("/incidents", json={"title": "other"}, headers=h).json()["id"]
    _consent(c, h, iid, consent.PURPOSE_LLM)
    db = next(app.dependency_overrides[get_db]())
    uid = db.execute(__import__("sqlalchemy").text("select id from users")).scalar()
    assert not consent.has_granted_consent(db, other, uid, consent.PURPOSE_LLM)
    assert not consent.has_granted_consent(db, iid, uid, consent.PURPOSE_REVERSE_SEARCH)
    db.close()


# ---- reverse image search ---------------------------------------------------------------------------
def test_reverse_search_requires_consent_when_provider_configured(api, monkeypatch):
    c, h, iid, mid = api
    from app.routers import phase34 as r
    monkeypatch.setattr(r.settings, "REVERSE_SEARCH_PROVIDER", "google_vision")
    with patch.object(r.phase34, "licensed_reverse_image_search", return_value={"configured": True, "provider": "google_vision", "pages": []}) as call:
        denied = c.post(f"/incidents/{iid}/media/{mid}/reverse-search", headers=h)
        assert denied.status_code == 403 and consent.PURPOSE_REVERSE_SEARCH in denied.json()["detail"]
        call.assert_not_called()
        _consent(c, h, iid, consent.PURPOSE_REVERSE_SEARCH)
        ok = c.post(f"/incidents/{iid}/media/{mid}/reverse-search", headers=h)
        assert ok.status_code == 200, ok.text      # also proves the audit action is registered (was a 500 before)
        call.assert_called_once()


def test_reverse_search_without_provider_sends_nothing_and_needs_no_consent(api, monkeypatch):
    c, h, iid, mid = api
    from app.routers import phase34 as r
    monkeypatch.setattr(r.settings, "REVERSE_SEARCH_PROVIDER", "none")
    ok = c.post(f"/incidents/{iid}/media/{mid}/reverse-search", headers=h)
    assert ok.status_code == 200 and ok.json()["configured"] is False


# ---- Copilot LLM ------------------------------------------------------------------------------------
def _fake_anthropic(calls):
    mod = ModuleType("anthropic")
    for name in ("RateLimitError", "APIStatusError", "APIConnectionError"):
        setattr(mod, name, type(name, (Exception,), {}))

    class _Messages:
        @staticmethod
        def create(**kw):
            calls.append(kw); raise RuntimeError("stop here: the call was attempted")

    class Client:
        def __init__(self, **kw):
            self.messages = _Messages()
            self.beta = type("Beta", (), {"messages": _Messages()})()   # newer models go through client.beta.messages
    mod.Anthropic = Client
    return mod


def test_copilot_does_not_call_external_llm_without_consent(api, monkeypatch):
    c, h, iid, _ = api
    s = get_settings()
    monkeypatch.setattr(s, "ANTHROPIC_API_KEY", "k"); monkeypatch.setattr(s, "COPILOT_LLM_PROVIDER", "anthropic")
    calls = []
    with patch.dict(sys.modules, {"anthropic": _fake_anthropic(calls)}):
        r = c.post(f"/incidents/{iid}/copilot", json={"question": "Where has this media appeared?"}, headers=h)
        assert r.status_code == 200, r.text
        assert r.json()["llm"]["status"] == "consent_required" and r.json()["answer_source"] == "deterministic"
        assert calls == []
        _consent(c, h, iid, consent.PURPOSE_LLM)
        r2 = c.post(f"/incidents/{iid}/copilot", json={"question": "Where has this media appeared?"}, headers=h)
        assert r2.status_code == 200 and r2.json()["llm"]["status"] != "consent_required"
        assert len(calls) == 1


# ---- report summary LLM -----------------------------------------------------------------------------
def _external_source():
    return Source(platform="example.com", observed_at=datetime(2026, 1, 1), account_identifier="acct", incident_id="x")


def test_report_summary_only_uses_llm_when_allowed():
    with patch.object(report_builder, "generate_summary_with_llm", return_value="LLM text") as llm:
        text = report_builder._build_summary(None, [_external_source()], 0)
        assert "LLM text" not in text
        llm.assert_not_called()
        assert report_builder._build_summary(None, [_external_source()], 0, allow_llm=True) == "LLM text"


def test_report_route_passes_consent_to_builder(api):
    c, h, iid, _ = api
    from app.routers import reports
    seen = []
    real = reports.build_report_payload
    with patch.object(reports, "build_report_payload", side_effect=lambda *a, **kw: (seen.append(kw.get("allow_llm")), real(*a, **kw))[1]):
        assert c.post(f"/incidents/{iid}/report", headers=h).status_code == 200
        _consent(c, h, iid, consent.PURPOSE_LLM)
        assert c.post(f"/incidents/{iid}/report", headers=h).status_code == 200
    assert seen == [False, True]


# ---- every audit action used in code is registered --------------------------------------------------
def test_every_audit_action_used_in_code_is_registered():
    """Regression: four endpoints logged unregistered actions, so audit.record raised ValueError (HTTP 500)."""
    missing = []
    for path in (Path(__file__).parents[1] / "app").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "record"
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == "audit" and len(node.args) >= 4
                    and isinstance(node.args[3], ast.Constant) and isinstance(node.args[3].value, str)):
                if node.args[3].value not in audit.ACTIONS:
                    missing.append((path.name, node.args[3].value))
    assert not missing, missing
