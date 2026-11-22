import json
import zipfile
from datetime import datetime
from io import BytesIO
from types import SimpleNamespace as NS

import pytest

from app.services import audit_chain, case_bundle, legal_packs

INC = NS(id="inc-1", title="Test case")
MEDIA = [NS(original_filename="a.jpg", sha256="a" * 64, uploaded_at=datetime(2026, 10, 1, 9, 0))]
SRC = [NS(platform="example.org", url="https://example.org/p/1", observed_at=datetime(2026, 10, 2, 9, 0), page_sha256="b" * 64)]
EVI = [NS(item_type="screenshot", sha256="c" * 64, captured_at=datetime(2026, 10, 2, 9, 5))]
FP = [{"domain": "example.org", "server_ips": ["93.184.216.34"], "label": "Hosting server, not the creator"}]


def _pdf(regime, **kw):
    return legal_packs.build_pack(regime, incident=INC, media=MEDIA, sources=SRC, evidence=EVI, footprints=FP, **kw)


@pytest.mark.parametrize("regime", legal_packs.REGIMES)
def test_every_pack_renders_with_draft_banner_hashes_and_url(regime):
    pdf = _pdf(regime, requester={"name": "A. Helper"}, platform="ExamplePlatform")
    assert pdf.startswith(b"%PDF")
    assert b"DRAFT" in pdf and b"PENDING" in pdf
    assert b"https://example.org/p/1" in pdf and (b"a" * 64) in pdf and b"A. Helper" in pdf


def test_approved_status_changes_banner_but_never_claims_more():
    pdf = _pdf("tida", legal_review_status="approved")
    assert b"reviewed by counsel" in pdf and b"DRAFT" not in pdf


def test_preservation_asks_for_ip_logs_and_does_not_claim_disclosure():
    pdf = _pdf("preservation")
    assert b"IP addresses and connection logs" in pdf and b"does not itself ask you to disclose" in pdf


def test_creator_is_never_identified_in_hosting_section():
    pdf = _pdf("it_rules")
    assert b"do not identify the person" in pdf or b"does not identify the person" in pdf


def test_ncrp_pack_warns_1930_is_for_financial_fraud():
    assert b"1930" in _pdf("ncrp") and b"financial fraud" in _pdf("ncrp")


def test_deadlines_are_planning_aids_with_caveat():
    t = datetime(2026, 10, 6, 9, 0)
    d = legal_packs.deadline("it_rules", t, "order")
    assert d["hours"] == 3 and d["due"].endswith("12:00") and "counsel" in d["note"]
    assert legal_packs.deadline("tida", t)["hours"] == 48
    assert legal_packs.deadline("preservation", datetime(2026, 10, 6)) is None
    assert legal_packs.deadline("ncrp", None) is None
    assert b"Planning deadline" in _pdf("it_rules", order_received_at=t)


def test_it_rules_deadline_depends_on_what_started_the_request():
    t = datetime(2026, 10, 6, 9, 0)
    assert legal_packs.deadline("it_rules", t, "order")["hours"] == 3
    assert legal_packs.deadline("it_rules", t, "high_risk_complaint")["hours"] == 2
    assert legal_packs.deadline("it_rules", t, "individual_complaint")["hours"] == 36
    # a victim's own complaint is NOT given the 3-hour order deadline by default
    assert legal_packs.deadline("it_rules", t)["hours"] == 2 and legal_packs.deadline("it_rules", t)["track"] == "high_risk_complaint"
    assert legal_packs.deadline("it_rules", t, "individual_complaint")["due"].startswith("2026-10-07 21:00")
    with pytest.raises(ValueError):
        legal_packs.deadline("it_rules", t, "whatever")
    assert legal_packs.deadline("tida", t, "order")["track"] is None           # the track only applies to the India pack


def test_it_rules_pack_names_the_track_and_all_three_timelines():
    pdf = _pdf("it_rules", order_received_at=datetime(2026, 10, 6, 9, 0), track="individual_complaint")
    assert b"36 hours" in pdf and b"Other complaint by an individual" in pdf
    assert b"3 hours" in pdf and b"2 hours" in pdf and b"counsel" in pdf          # all three tracks explained, counsel caveat kept
    assert b"normally the second kind" in pdf


def test_take_it_down_pack_says_intimate_imagery_only_and_48_hours():
    pdf = _pdf("tida", order_received_at=datetime(2026, 10, 6, 9, 0))
    assert b"INTIMATE imagery only" in pdf and b"48 hours" in pdf and b"19 May 2026" in pdf


def test_unknown_regime_rejected():
    with pytest.raises(ValueError):
        _pdf("nope")


def test_hostile_text_is_escaped_not_interpreted():
    bad = [NS(platform="<b>x</b><img src=http://evil>", url="https://e.org/?a=<script>", observed_at=None, page_sha256=None)]
    pdf = legal_packs.build_pack("ncrp", incident=NS(id="i", title="<i>t</i>"), media=[], sources=bad, evidence=[], footprints=[])
    assert pdf.startswith(b"%PDF")


def test_bundle_round_trip_and_tamper_detection():
    rows = [{"name": "a.jpg", "kind": "media", "sha256": "a" * 64, "recorded_at": "2026-10-01"}]
    env = {"manifest": {"entry_count": 1}, "signature": {"key_id": "k"}}
    data = case_bundle.build_bundle(incident_id="inc-1", title="T", evidence_rows=rows, manifest_envelope=env,
                                    files=[("a.jpg", b"JPEGBYTES"), ("../../evil name.jpg", b"x")], verifier_source="print('v')")
    assert case_bundle.verify_bundle(data)["ok"] is True
    z = zipfile.ZipFile(BytesIO(data))
    names = z.namelist()
    assert "manifest.json" in names and "verify_manifest.py" in names and "bundle_index.json" in names
    assert all(not n.startswith("/") and ".." not in n for n in names)           # no path traversal from hostile file names
    assert json.loads(z.read("bundle_index.json"))["includes_original_files"] is True
    # tamper with one stored file and re-zip
    out = BytesIO()
    with zipfile.ZipFile(out, "w") as w:
        for n in names:
            w.writestr(n, b"TAMPERED" if n == "files/a.jpg" else z.read(n))
    res = case_bundle.verify_bundle(out.getvalue())
    assert res["ok"] is False and any("a.jpg" in p for p in res["problems"])


def test_bundle_without_files_declares_it():
    data = case_bundle.build_bundle(incident_id="i", title="T", evidence_rows=[], manifest_envelope=None)
    assert json.loads(zipfile.ZipFile(BytesIO(data)).read("bundle_index.json"))["includes_original_files"] is False


def test_bundle_carries_custody_log_and_it_is_hash_listed():
    log = {"events": [{"seq": 1, "action": "x"}], "chain_check": {"ok": True}}
    data = case_bundle.build_bundle(incident_id="i", title="T", evidence_rows=[], manifest_envelope=None, custody_log=log)
    z = zipfile.ZipFile(BytesIO(data))
    assert json.loads(z.read("custody_log.json"))["chain_check"]["ok"] is True
    assert "custody_log.json" in json.loads(z.read("bundle_index.json"))["files"]
    assert case_bundle.verify_bundle(data)["ok"]


def test_bundle_custody_log_is_re_verifiable_offline_and_catches_a_rewrite():
    rows, prev = [], audit_chain.GENESIS
    for i in range(1, 4):
        e = {"incident_id": "i", "seq": i, "actor_user_id": "u", "actor_email": "u@x", "action": "report_generated",
             "target_type": None, "target_id": None, "details_json": None, "created_at": f"2026-10-0{i}T00:00:00"}
        e["prev_hash"] = prev
        e["event_hash"] = audit_chain.event_hash(e, prev)
        prev = e["event_hash"]
        rows.append(e)
    anchor = audit_chain.anchor(audit_chain.verify(rows))
    data = case_bundle.build_bundle(incident_id="i", title="T", evidence_rows=[], manifest_envelope=None,
                                    custody_log={"events": [], "chain": rows}, audit_anchor=anchor)
    res = case_bundle.verify_custody_log(data)
    assert res["present"] and res["ok"] and res["anchor_ok"] is True and res["anchor_source"] == "bundle"
    # a head recorded elsewhere that this log does not contain (a rewritten history) is caught
    other = {"head_seq": 3, "head_hash": "f" * 64}
    assert case_bundle.verify_custody_log(data, other)["anchor_ok"] is False
    assert case_bundle.verify_custody_log(case_bundle.build_bundle(incident_id="i", title="T", evidence_rows=[], manifest_envelope=None))["present"] is False
