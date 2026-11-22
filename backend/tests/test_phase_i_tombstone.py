from pathlib import Path


def test_tombstone_uses_the_anchor_head_hash_not_a_guessed_key():
    src = (Path(__file__).resolve().parents[1] / "app" / "routers" / "incidents.py").read_text(encoding="utf-8")
    assert 'audit.anchor(db, incident.id)' in src and '"head_hash"' in src
    assert "head_event_hash" not in src


def test_tombstone_route_requires_login_and_owner():
    src = (Path(__file__).resolve().parents[1] / "app" / "routers" / "operations.py").read_text(encoding="utf-8")
    block = src.split("def get_tombstone", 1)[1]
    assert "Depends(get_current_user)" in block.split("\n", 1)[0] and "owner_user_id" in block
