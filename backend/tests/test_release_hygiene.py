"""Guards against the packaging and wiring slips found in review: secrets in zips, prod config gaps, unmounted UI."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_production_compose_supplies_the_manifest_signing_key_and_schedules_the_sweep():
    prod = _text("deploy/docker-compose.prod.yml")
    assert "MANIFEST_SIGNING_KEY: ${MANIFEST_SIGNING_KEY:?Set MANIFEST_SIGNING_KEY}" in prod
    worker = prod[prod.index("  worker:"):prod.index("  web:")]
    assert 'CAPTURE_SWEEP_ENABLED: "true"' in worker
    assert "MANIFEST_SIGNING_KEY=" in _text("deploy/.env.production.example")
    assert "LEGAL_REVIEW_STATUS=pending" in _text("deploy/.env.production.example")


def test_release_zip_script_excludes_secrets_and_checks_the_lock():
    script = _text("scripts/make_release_zip.sh")
    for needle in ("check_lock_sync.py", "backend/data/*", ".file_encryption_key", ".manifest_signing_key", "node_modules"):
        assert needle in script, needle
    assert "package-lock.json" in _text("scripts/check_lock_sync.py")


def test_manifest_panel_is_wired_end_to_end():
    api = _text("frontend/src/lib/api.ts")
    for name in ("getManifestKey", "listManifests", "createManifest", "verifyManifest"):
        assert name in api, name
    assert "/evidence/manifests/${manifestId}/verify" in api
    panel = _text("frontend/src/components/ManifestPanel.tsx")
    assert "api.createManifest" in panel and "api.verifyManifest" in panel and "role=\"alert\"" in panel
    locker = _text("frontend/src/screens/EvidenceLocker.tsx")
    assert "<ManifestPanel incidentId={incidentId} />" in locker


def test_manifest_routes_match_what_the_frontend_calls():
    router = _text("backend/app/routers/manifest.py")
    for route in ('"/trust/manifest-key"', '"/incidents/{incident_id}/evidence/manifest"',
                  '"/incidents/{incident_id}/evidence/manifests"', '"/incidents/{incident_id}/evidence/manifests/{manifest_id}/verify"'):
        assert route in router, route


def test_feature_matching_is_documented_as_a_setting():
    assert "TRACE_FEATURE_MATCH_ENABLED=true" in _text("backend/.env.example")
