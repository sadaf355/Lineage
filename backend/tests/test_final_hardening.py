from pathlib import Path


def test_frontend_login_uses_cookie_credentials():
    text = Path(__file__).parents[2].joinpath("frontend/src/lib/api.ts").read_text()
    block = text[text.index("async login("):text.index("async refresh(")]
    assert 'credentials: "include"' in block


def test_frontend_routes_use_real_incident_ids():
    text = Path(__file__).parents[2].joinpath("frontend/src/App.tsx").read_text()
    assert 'const base = `/investigations/${encodeURIComponent(id)}`' in text
    assert 'INC-2024-012' not in text


def test_audio_is_accepted_in_new_investigation():
    text = Path(__file__).parents[2].joinpath("frontend/src/screens/NewInvestigation.tsx").read_text()
    assert 'accept="image/*,video/*,audio/*"' in text
    assert 'audio\\/' in text


def test_report_ui_uses_background_job():
    text = Path(__file__).parents[2].joinpath("frontend/src/screens/CaseAutomation.tsx").read_text()
    assert 'api.queueReport(incidentId!)' in text
    assert 'api.getJob(incidentId!,queued.job_id)' in text
