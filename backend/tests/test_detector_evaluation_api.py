from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.deps import get_current_user
from app.models.user import User
from app.routers import phase34 as phase34_router
from app.services import deepfake_model


def _client(authenticated: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(phase34_router.detector_router)
    if authenticated:
        app.dependency_overrides[get_current_user] = lambda: User(id="u1", email="a@b.co", hashed_password="x")
    return TestClient(app)


def test_latest_evaluation_reports_not_run_honestly(monkeypatch):
    monkeypatch.setattr(phase34_router.eval_harness, "load_latest", lambda path=None: None)
    body = _client().get("/detection/evaluation/latest").json()
    assert body["available"] is False and body["report"] is None and body["smoke_test"] is False
    assert "run_eval.py" in body["how_to_generate"]
    assert body["configured_models"]["primary"] == get_settings().DETECTOR_MODEL_ID


def test_latest_evaluation_returns_saved_report(monkeypatch):
    report = {"generated_at": "2026-10-02T00:00:00+00:00", "threshold": 50.0, "images": 10,
              "sources": ["x"], "conditions": ["original"], "models": {"m": {"rows_total": 10, "unscored": 0}}, "warning": "w"}
    monkeypatch.setattr(phase34_router.eval_harness, "load_latest", lambda path=None: report)
    body = _client().get("/detection/evaluation/latest").json()
    assert body["available"] is True and body["report"]["images"] == 10 and body["how_to_generate"] is None
    assert body["smoke_test"] is True            # 10 images is far too few to quote


def test_latest_evaluation_flags_smoke_test_by_original_images_not_file_count(monkeypatch):
    base = {"generated_at": "2026-10-02T00:00:00+00:00", "threshold": 50.0, "images": 5000, "sources": ["x"],
            "conditions": ["original"], "models": {"m": {"rows_total": 1, "unscored": 0}}, "warning": "w"}
    for originals, expected in ((60, True), (250, False)):
        monkeypatch.setattr(phase34_router.eval_harness, "load_latest", lambda path=None, o=originals: dict(base, originals_test=o))
        assert _client().get("/detection/evaluation/latest").json()["smoke_test"] is expected


def test_latest_evaluation_requires_login():
    assert _client(authenticated=False).get("/detection/evaluation/latest").status_code == 401


def test_primary_detector_is_the_configured_model():
    # Regression: the single-model path used to run a different model than the config and /health reported.
    assert deepfake_model.DEFAULT_MODEL_ID == get_settings().DETECTOR_MODEL_ID
    assert deepfake_model.model_status()["model_id"] == get_settings().DETECTOR_MODEL_ID
