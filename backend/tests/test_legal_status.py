"""Phase E — the certificate may only claim counsel review for the exact template version that was reviewed."""
from types import SimpleNamespace

import app.routers.phase56 as p56


def _with(status, reviewed, version):
    p56.settings = SimpleNamespace(LEGAL_REVIEW_STATUS=status, LEGAL_REVIEWED_TEMPLATE_VERSION=reviewed, BSA_CERTIFICATE_TEMPLATE_VERSION=version)
    return p56.legal_status_text()


def test_default_is_draft():
    assert _with("pending", "", "1.0").startswith("DRAFT")


def test_approval_is_bound_to_the_reviewed_template_version():
    original = p56.settings
    try:
        assert "reviewed by counsel" in _with("approved", "1.0", "1.0")
        assert _with("approved", "1.0", "1.1").startswith("DRAFT")   # template edited after review -> un-approved
        assert _with("approved", "", "1.0").startswith("DRAFT")      # status flag alone is not enough
    finally:
        p56.settings = original
