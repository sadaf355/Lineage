"""Phase E: scheduled sweep for abandoned page captures.

``POST /sources/trace-url`` stores the fetched page as an encrypted ``*.html.enc`` file BEFORE the investigator decides.
If they accept, an EvidenceItem references it. If they reject, the reject endpoint deletes it. If they do nothing
(close the tab, session expires, browser crashes) the file is orphaned forever — still encrypted, but personal
data we have no reason to keep. This sweep removes those.

Safety rules (each is covered by a test):
* Only ``*.html.enc`` files are ever deleted: the shape traced page captures have. Other unreferenced files are
  counted and reported, never removed.
* A file is deleted only if NO MediaItem/EvidenceItem references it and it is older than the grace period.
* The grace period can never be configured below 60 minutes, and always exceeds the 30-minute pending-match life.
* ``dry_run`` reports what would be removed without touching anything.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from urllib.parse import urlparse


log = logging.getLogger("lineage.capture_sweep")
CAPTURE_SUFFIX = ".html.enc"
MIN_GRACE_MINUTES = 60


def effective_grace_minutes(configured: int) -> int:
    return max(MIN_GRACE_MINUTES, int(configured))


def plan_sweep(candidates: list[dict], referenced: set[str], *, now: float, grace_minutes: int) -> dict:
    """Pure decision step. ``candidates`` = [{"path": str, "mtime": epoch_seconds}]."""
    cutoff = now - effective_grace_minutes(grace_minutes) * 60
    delete, too_new, referenced_kept, other_unreferenced = [], 0, 0, 0
    for c in candidates:
        is_capture = c["path"].endswith(CAPTURE_SUFFIX)
        if c["path"] in referenced:
            referenced_kept += 1
        elif not is_capture:
            other_unreferenced += 1
        elif c["mtime"] > cutoff:
            too_new += 1
        else:
            delete.append(c["path"])
    return {"delete": delete, "too_new": too_new, "referenced_kept": referenced_kept, "other_unreferenced_not_touched": other_unreferenced}


def _local_candidates(uploads_dir: Path) -> list[dict]:
    out = []
    if uploads_dir.is_dir():
        for p in uploads_dir.iterdir():
            if p.is_file() and p.name.endswith(".enc"):
                out.append({"path": str(p.resolve()), "mtime": p.stat().st_mtime})
    return out


def _s3_candidates(settings) -> list[dict]:  # pragma: no cover - needs a real bucket; exercised in staging only
    from app.services import object_storage
    client = object_storage._s3()
    prefix = (settings.S3_PREFIX.strip("/") + "/") if settings.S3_PREFIX else ""
    out, token = [], None
    while True:
        kw = {"Bucket": settings.S3_BUCKET, "Prefix": prefix}
        if token:
            kw["ContinuationToken"] = token
        page = client.list_objects_v2(**kw)
        for obj in page.get("Contents", []):
            out.append({"path": f"s3://{settings.S3_BUCKET}/{obj['Key']}", "mtime": obj["LastModified"].timestamp()})
        if not page.get("IsTruncated"):
            return out
        token = page.get("NextContinuationToken")


def _normalise(path: str) -> str:
    return path if path.startswith("s3://") else str(Path(path).resolve())


def sweep_abandoned_captures(db, *, dry_run: bool = False, now: float | None = None, delete_fn=None) -> dict:
    from app.core.config import get_settings
    from app.models.media import MediaItem
    from app.models.source import EvidenceItem
    from app.services import file_storage, object_storage

    s = get_settings()
    now = time.time() if now is None else now
    referenced = {_normalise(p) for (p,) in db.query(MediaItem.storage_path).all() if p}
    referenced |= {_normalise(p) for (p,) in db.query(EvidenceItem.storage_path).all() if p}
    candidates = _s3_candidates(s) if object_storage.enabled() else _local_candidates(Path(s.UPLOADS_DIR))
    plan = plan_sweep(candidates, referenced, now=now, grace_minutes=s.CAPTURE_SWEEP_GRACE_MINUTES)
    removed, failed = [], []
    if not dry_run:
        remove = delete_fn or file_storage.delete_encrypted
        for path in plan["delete"]:
            try:
                remove(path)
                removed.append(path)
            except Exception:  # noqa: BLE001 - one bad object must not stop the sweep
                log.exception("Could not delete abandoned capture")
                failed.append(path)
    summary = {
        "dry_run": dry_run, "scanned": len(candidates), "abandoned_found": len(plan["delete"]),
        "deleted": len(removed), "failed": len(failed), "skipped_too_new": plan["too_new"],
        "skipped_referenced": plan["referenced_kept"], "other_unreferenced_not_touched": plan["other_unreferenced_not_touched"],
        "grace_minutes": effective_grace_minutes(s.CAPTURE_SWEEP_GRACE_MINUTES),
    }
    # Filenames are random UUIDs, but never write the paths to logs: counts are enough for operations.
    log.info("capture sweep: %s", summary)
    return summary


if __name__ == "__main__":  # python -m app.services.capture_sweep [--dry-run]
    import json
    import sys
    from app.db.session import SessionLocal

    _db = SessionLocal()
    try:
        print(json.dumps(sweep_abandoned_captures(_db, dry_run="--dry-run" in sys.argv), indent=2))
    finally:
        _db.close()
