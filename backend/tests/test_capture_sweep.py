"""Phase E — abandoned page-capture sweep. The decision logic is pure and tested directly."""
import time

from app.services import capture_sweep as cs

HOUR = 3600
NOW = 1_000_000.0


def _c(name, age_minutes):
    return {"path": f"/data/uploads/{name}", "mtime": NOW - age_minutes * 60}


def test_old_unreferenced_capture_is_deleted():
    plan = cs.plan_sweep([_c("a.html.enc", 300)], set(), now=NOW, grace_minutes=120)
    assert plan["delete"] == ["/data/uploads/a.html.enc"]


def test_accepted_capture_is_never_deleted():
    plan = cs.plan_sweep([_c("a.html.enc", 9999)], {"/data/uploads/a.html.enc"}, now=NOW, grace_minutes=120)
    assert plan["delete"] == [] and plan["referenced_kept"] == 1


def test_recent_capture_inside_grace_is_kept():
    plan = cs.plan_sweep([_c("a.html.enc", 10), _c("b.html.enc", 119)], set(), now=NOW, grace_minutes=120)
    assert plan["delete"] == [] and plan["too_new"] == 2


def test_grace_cannot_be_configured_below_an_hour():
    assert cs.effective_grace_minutes(1) == 60
    plan = cs.plan_sweep([_c("a.html.enc", 45)], set(), now=NOW, grace_minutes=1)
    assert plan["delete"] == []  # 45 min old: inside the enforced 60-minute floor, even though 1 was configured


def test_only_html_captures_are_ever_removed():
    plan = cs.plan_sweep([_c("m.png.enc", 9999), _c("v.mp4.enc", 9999), _c("x.enc", 9999)], set(), now=NOW, grace_minutes=120)
    assert plan["delete"] == [] and plan["other_unreferenced_not_touched"] == 3


def test_mixed_batch():
    cands = [_c("old.html.enc", 500), _c("kept.html.enc", 500), _c("new.html.enc", 5), _c("img.png.enc", 500)]
    plan = cs.plan_sweep(cands, {"/data/uploads/kept.html.enc"}, now=NOW, grace_minutes=120)
    assert plan["delete"] == ["/data/uploads/old.html.enc"]
    assert (plan["too_new"], plan["referenced_kept"], plan["other_unreferenced_not_touched"]) == (1, 1, 1)


def test_local_scan_reads_mtime_and_only_enc_files():
    import tempfile, os
    from pathlib import Path
    d = Path(tempfile.mkdtemp())
    (d / "a.html.enc").write_bytes(b"x"); (d / "notes.txt").write_bytes(b"x")
    old = time.time() - 5 * HOUR
    os.utime(d / "a.html.enc", (old, old))
    found = cs._local_candidates(d)
    assert [Path(f["path"]).name for f in found] == ["a.html.enc"] and abs(found[0]["mtime"] - old) < 2
    assert cs.plan_sweep(found, set(), now=time.time(), grace_minutes=120)["delete"] == [found[0]["path"]]
