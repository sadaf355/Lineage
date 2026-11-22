from datetime import datetime

from app.services import audit_chain as ac


def _chain(n=5):
    rows, prev = [], ac.GENESIS
    for i in range(1, n + 1):
        e = {"incident_id": "i1", "seq": i, "actor_user_id": "u", "actor_email": "a@b.c", "action": "evidence_reviewed",
             "target_type": "evidence", "target_id": f"e{i}", "details_json": '{"k":1}', "created_at": datetime(2026, 10, 6, 10, 0, i)}
        e["prev_hash"] = prev
        e["event_hash"] = ac.event_hash(e, prev)
        prev = e["event_hash"]
        rows.append(e)
    return rows


def test_intact_chain_verifies_and_reports_head():
    r = ac.verify(_chain())
    assert r["ok"] and r["checked"] == 5 and len(r["head"]) == 64


def test_edited_event_is_detected_at_that_event():
    rows = _chain()
    rows[2]["details_json"] = '{"k":2}'
    r = ac.verify(rows)
    assert not r["ok"] and r["first_break_seq"] == 3 and "altered" in r["reason"]


def test_deleted_event_is_detected():
    rows = _chain()
    del rows[2]
    r = ac.verify(rows)
    assert not r["ok"] and r["first_break_seq"] == 3


def test_deleted_last_event_cannot_be_seen_from_rows_alone_but_head_changes():
    rows = _chain()
    head_full = ac.verify(rows)["head"]
    head_short = ac.verify(rows[:-1])["head"]
    assert head_full != head_short           # which is why the head hash should be recorded somewhere the DB admin cannot edit


def test_swapped_order_and_forged_link_detected():
    rows = _chain()
    rows[3]["prev_hash"] = ac.GENESIS
    assert not ac.verify(rows)["ok"]


def test_legacy_unchained_events_are_counted_not_failed():
    rows = _chain(3) + [{"incident_id": "i1", "seq": None, "action": "old", "event_hash": None}]
    r = ac.verify(rows)
    assert r["ok"] and r["legacy_unchained"] == 1


def test_empty_is_ok():
    assert ac.verify([])["ok"] is True


# ---- anchoring (pure) ----
def _log(n):
    rows, prev = [], ac.GENESIS
    for i in range(1, n + 1):
        e = {"incident_id": "c", "seq": i, "actor_user_id": "u", "actor_email": "u@x", "action": "report_generated",
             "target_type": None, "target_id": None, "details_json": None, "created_at": f"2026-10-0{i}T00:00:00"}
        e["prev_hash"] = prev
        e["event_hash"] = ac.event_hash(e, prev)
        prev = e["event_hash"]
        rows.append(e)
    return rows


def test_anchor_summarises_head_and_break():
    rows = _log(3)
    a = ac.anchor(ac.verify(rows))
    assert a["chain_ok"] and a["head_seq"] == 3 and a["head_hash"] == rows[-1]["event_hash"] and a["events_chained"] == 3
    rows[1]["details_json"] = "{}"
    b = ac.anchor(ac.verify(rows))
    assert b["chain_ok"] is False and b["first_break_seq"] == 2


def test_full_rewrite_with_recomputed_hashes_is_caught_by_the_anchor():
    original = _log(4)
    anchor = ac.anchor(ac.verify(original))
    # an attacker edits event 2 and recomputes every later hash: the chain is internally consistent again
    forged, prev = [], ac.GENESIS
    for e in original:
        e = dict(e)
        if e["seq"] == 2:
            e["action"] = "evidence_deleted"
        e["prev_hash"] = prev
        e["event_hash"] = ac.event_hash(e, prev)
        prev = e["event_hash"]
        forged.append(e)
    assert ac.verify(forged)["ok"] is True                       # chain alone cannot see it
    res = ac.check_against_anchor(forged, anchor)
    assert res["anchor_checked"] and res["anchor_ok"] is False            # the anchored head no longer matches
    assert ac.check_against_anchor(original, anchor)["anchor_ok"] is True


def test_anchor_survives_later_events_but_not_a_truncated_tail():
    rows = _log(5)
    anchor = ac.anchor(ac.verify(rows[:3]))
    assert ac.check_against_anchor(rows, anchor)["anchor_ok"] is True      # more events were added later: fine
    assert ac.check_against_anchor(rows[:2], anchor)["anchor_ok"] is False  # tail deleted: head is gone


def test_export_row_round_trips_through_json():
    import json
    rows = _log(3)
    exported = json.loads(json.dumps([ac.export_row(r) for r in rows]))
    assert ac.verify(exported)["ok"] is True
