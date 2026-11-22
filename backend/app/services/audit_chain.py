"""
Tamper-evident audit trail: each event stores the hash of the previous event in the same case, so editing, inserting or deleting
a past event breaks every hash after it. Pure functions (no database) so the logic is easy to test and to re-run independently.

What this gives you: anyone with read access to the rows can detect after-the-fact changes made WITHOUT also recomputing every later hash.
What it does not give you: protection against someone who can rewrite the whole table AND recompute the chain. For that, periodically
copy the latest `event_hash` somewhere the database administrator cannot write (the signed manifest, a timestamp, an email to counsel).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Iterable

GENESIS = "0" * 64
FIELDS = ("incident_id", "seq", "actor_user_id", "actor_email", "action", "target_type", "target_id", "details_json", "created_at")


def _norm(v: Any) -> Any:
    return v.isoformat() if isinstance(v, datetime) else v


def event_hash(event: dict[str, Any], prev_hash: str) -> str:
    body = {k: _norm(event.get(k)) for k in FIELDS}
    body["prev_hash"] = prev_hash
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def export_row(event: dict[str, Any]) -> dict[str, Any]:
    """The exact hashed fields plus the two hashes, JSON-safe, so a recipient can re-run `verify` on an exported log."""
    row = {k: _norm(event.get(k)) for k in FIELDS}
    row["prev_hash"] = event.get("prev_hash")
    row["event_hash"] = event.get("event_hash")
    return row


def anchor(result: dict[str, Any]) -> dict[str, Any] | None:
    """Small, signable summary of a verify() result: what to put in a signed manifest or send to counsel."""
    if result.get("ok") and result.get("head"):
        return {"chain_ok": True, "head_seq": result["head_seq"], "head_hash": result["head"], "events_chained": result["checked"],
                "legacy_unchained": result["legacy_unchained"]}
    if result.get("ok"):
        return {"chain_ok": True, "head_seq": None, "head_hash": None, "events_chained": 0, "legacy_unchained": result["legacy_unchained"]}
    return {"chain_ok": False, "first_break_seq": result.get("first_break_seq"), "reason": result.get("reason"),
            "events_chained": result.get("checked"), "legacy_unchained": result.get("legacy_unchained")}


def check_against_anchor(events: Iterable[dict[str, Any]], anchored: dict[str, Any] | None) -> dict[str, Any]:
    """Re-verify an exported log and compare it with a head hash recorded elsewhere (manifest, email, timestamp).
    A full rewrite of the table that recomputes every hash is caught here, because the anchored head no longer appears."""
    events = list(events)
    res = verify(events)
    if not anchored or not anchored.get("head_hash"):
        return {**res, "anchor_checked": False, "anchor_ok": None}
    rows = {e["seq"]: e for e in events if e.get("seq") is not None}
    at = rows.get(anchored.get("head_seq"))
    ok = bool(res["ok"] and at and at.get("event_hash") == anchored["head_hash"])
    return {**res, "anchor_checked": True, "anchor_ok": ok}


def verify(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """events: dicts (FIELDS + prev_hash + event_hash) for ONE case, any order. Legacy events without hashes are reported, not failed."""
    rows = list(events)
    chained = sorted([e for e in rows if e.get("seq") is not None and e.get("event_hash")], key=lambda e: e["seq"])
    legacy = len(rows) - len(chained)
    expected_prev = GENESIS
    expected_seq = chained[0]["seq"] if chained else 0
    for e in chained:
        if e["seq"] != expected_seq:
            return {"ok": False, "checked": len(chained), "legacy_unchained": legacy, "first_break_seq": expected_seq,
                    "reason": f"event {expected_seq} is missing (an event was deleted or never saved)", "head": None, "head_seq": None}
        if e.get("prev_hash") != expected_prev:
            return {"ok": False, "checked": len(chained), "legacy_unchained": legacy, "first_break_seq": e["seq"],
                    "reason": "previous-event link does not match", "head": None, "head_seq": None}
        if event_hash(e, expected_prev) != e["event_hash"]:
            return {"ok": False, "checked": len(chained), "legacy_unchained": legacy, "first_break_seq": e["seq"],
                    "reason": "event contents do not match their hash (the event was altered)", "head": None, "head_seq": None}
        expected_prev = e["event_hash"]
        expected_seq += 1
    return {"ok": True, "checked": len(chained), "legacy_unchained": legacy, "first_break_seq": None, "reason": None,
            "head": expected_prev if chained else None, "head_seq": chained[-1]["seq"] if chained else None,
            "note": "Record the head hash somewhere the database administrator cannot edit, to detect a full rewrite of the table."}
