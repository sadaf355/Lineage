"""
Signed case bundle for police, platforms or a court: one zip a third party can check without access to LINEAGE.

Contents
  README_VERIFY.txt     plain-language steps to check the bundle
  manifest.json         the Ed25519-signed manifest envelope (latest), if one exists
  evidence_index.csv    every artifact with SHA-256 and recorded time
  hashes.sha256         `sha256sum -c` compatible list of the files included
  bundle_index.json     SHA-256 of every file in this zip
  custody_log.json      the case's audit events with the hash-chain check result (when available)
  verify_manifest.py    the offline verifier (when available)
  files/...             original files, ONLY when include_files=True (sensitive: the requester must opt in)
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import zipfile
from datetime import datetime
from typing import Any

README = """LINEAGE case bundle  -  how to check it
=======================================

1. Hashes. If the bundle contains a files/ folder, run in this folder:
       sha256sum -c hashes.sha256        (macOS: shasum -a 256 -c hashes.sha256)
   Every line must say OK. evidence_index.csv lists the same hashes with the time each item was recorded.

2. Signature. manifest.json is signed with an Ed25519 key. To verify it you need the PUBLIC key from the organisation that
   produced it, obtained through a channel other than this zip. Then run:
       python verify_manifest.py manifest.json --public-key <key_b64>
   A manifest verified against the key embedded in the file proves only that the file is self-consistent, not who made it.

3. Audit log. If custody_log.json is present, its `chain` list can be re-checked by anyone: each event stores the hash of the
   one before it. `audit_anchor` in bundle_index.json (and `audit_anchor` inside the signed manifest) names the head of that chain at
   export time. Compare it with a head hash you were given separately (an email, a timestamp, an earlier bundle): if the log was
   rewritten and every hash recomputed, the old head will not appear.

4. Time. If the manifest includes an RFC 3161 timestamp, the timestamp authority's certificate must be checked separately.

What this bundle does NOT prove: who created or uploaded the content, or that the content depicts real events. The detector scores
and metadata findings in the report are signals with stated limits.
"""


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def build_bundle(*, incident_id: str, title: str, evidence_rows: list[dict[str, Any]], manifest_envelope: dict | None,
                 files: list[tuple[str, bytes]] | None = None, verifier_source: str | None = None, include_report_pdf: bytes | None = None,
                 custody_log: dict | None = None, audit_anchor: dict | None = None, include_original_files: bool | None = None,
                 extra_entries: list[tuple[str, bytes]] | None = None) -> bytes:
    """evidence_rows: [{name, kind, sha256, recorded_at}]. files: [(relative_name, bytes)] already authorised by the caller."""
    out = io.BytesIO()
    entries: dict[str, bytes] = {}
    entries["README_VERIFY.txt"] = README.encode()
    csv_buf = io.StringIO()
    w = csv.writer(csv_buf)
    w.writerow(["name", "kind", "sha256", "recorded_at"])
    for r in evidence_rows:
        w.writerow([r.get("name"), r.get("kind"), r.get("sha256") or "", r.get("recorded_at") or ""])
    entries["evidence_index.csv"] = csv_buf.getvalue().encode()
    if manifest_envelope:
        entries["manifest.json"] = json.dumps(manifest_envelope, indent=2, sort_keys=True).encode()
    if verifier_source:
        entries["verify_manifest.py"] = verifier_source.encode()
    if custody_log:
        entries["custody_log.json"] = json.dumps(custody_log, indent=2, sort_keys=True, default=str).encode()
    if include_report_pdf:
        entries["report.pdf"] = include_report_pdf
    for name, data in (extra_entries or []):
        top = re.sub(r"[^A-Za-z0-9._-]", "_", name.replace("\\", "/").rsplit("/", 1)[-1]).lstrip(".")[:120] or "artifact"
        if top in entries or top in ("hashes.sha256", "bundle_index.json"):
            raise ValueError(f"extra bundle entry would overwrite {top}")
        entries[top] = data
    lines = []
    for name, data in (files or []):
        base = name.replace("\\", "/").rsplit("/", 1)[-1]           # file name only: never a path from the caller
        cleaned = "".join(c if c.isalnum() or c in "._-" else "_" for c in base).lstrip(".")
        safe = "files/" + (re.sub(r"\.{2,}", "_", cleaned)[:120] or "file")
        while safe in entries:
            safe += "_"
        entries[safe] = data
        lines.append(f"{_sha(data)}  {safe}")
    entries["hashes.sha256"] = ("\n".join(lines) + ("\n" if lines else "")).encode()
    index = {"incident_id": incident_id, "title": title, "generated_at": datetime.utcnow().isoformat() + "Z",
             "files": {k: _sha(v) for k, v in sorted(entries.items())}, "includes_original_files": bool(files) if include_original_files is None else bool(include_original_files),
             "audit_anchor": audit_anchor}
    entries["bundle_index.json"] = json.dumps(index, indent=2, sort_keys=True).encode()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in entries.items():
            z.writestr(name, data)
    return out.getvalue()


def verify_custody_log(data: bytes, trusted_anchor: dict | None = None) -> dict[str, Any]:
    """Re-run the audit hash chain on custody_log.json inside a bundle. `trusted_anchor` is a head recorded elsewhere
    ({head_seq, head_hash}); without it only the log's internal consistency is proved."""
    from app.services import audit_chain
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if "custody_log.json" not in z.namelist():
            return {"present": False}
        log = json.loads(z.read("custody_log.json"))
        index = json.loads(z.read("bundle_index.json")) if "bundle_index.json" in z.namelist() else {}
    chain = log.get("chain") or []
    own = index.get("audit_anchor")
    res = audit_chain.check_against_anchor(chain, trusted_anchor or own)
    res["present"] = True
    res["anchor_source"] = "trusted" if trusted_anchor else ("bundle" if own else None)
    return res


def verify_bundle(data: bytes) -> dict[str, Any]:
    """Check bundle_index.json against the zip's contents (and hashes.sha256 for files/). Used by tests and by recipients."""
    problems: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = set(z.namelist())
        if "bundle_index.json" not in names:
            return {"ok": False, "problems": ["bundle_index.json missing"]}
        index = json.loads(z.read("bundle_index.json"))
        for name, expected in index["files"].items():
            if name not in names:
                problems.append(f"missing: {name}")
            elif _sha(z.read(name)) != expected:
                problems.append(f"hash mismatch: {name}")
        for name in names - set(index["files"]) - {"bundle_index.json"}:
            problems.append(f"unlisted file: {name}")
        if "hashes.sha256" in names:
            for line in z.read("hashes.sha256").decode().splitlines():
                h, _, n = line.partition("  ")
                if n in names and _sha(z.read(n)) != h:
                    problems.append(f"hashes.sha256 mismatch: {n}")
    return {"ok": not problems, "problems": problems}
