#!/usr/bin/env python3
"""Fail CI on known vulnerabilities in backend/requirements.txt, except reviewed and dated exceptions.

    python scripts/audit_python.py            # needs: pip install pip-audit

Why a wrapper instead of plain `pip-audit`: the ML stack (torch, transformers, Pillow) is pinned to a narrow
window that facenet-pytorch 2.6.0 requires (see the comments in backend/requirements.txt), so a blanket upgrade
is not currently possible. Those packages are listed below with the reason and a review-by date. The audit
fails if (a) any OTHER package has an advisory, or (b) an exception has passed its review-by date, so the
exception cannot be forgotten.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

REQ = Path(__file__).resolve().parent.parent / "backend" / "requirements.txt"

# package (lowercase) -> (reason, review_by)
ACCEPTED: dict[str, tuple[str, str]] = {
    "torch": ("Pinned to 2.2.x by facenet-pytorch 2.6.0; used only for local inference on files already in the case, "
              "never to load untrusted model files (models come from the configured Hugging Face ids).", "2026-12-31"),
    "transformers": ("Pinned to 4.46.x to match torch 2.2.x. Only pretrained weights from the configured model ids are "
                     "loaded; no user-supplied checkpoints.", "2026-12-31"),
    "pillow": ("Pinned <10.3 by facenet-pytorch 2.6.0. Mitigated by upload sniffing, size limits and decoding in a "
               "worker context; replace facenet-pytorch or fork its pin to upgrade.", "2026-12-31"),
}


def main() -> int:
    lines = []
    for raw in REQ.read_text().splitlines():
        m = re.match(r"^([A-Za-z0-9_.\-]+(?:\[[^\]]+\])?)==([^\s#;]+)", raw.strip())
        if m:
            lines.append(f"{m.group(1)}=={m.group(2).split('+')[0]}")   # drop local '+cpu' suffixes
    with tempfile.TemporaryDirectory() as tmp:
        req = Path(tmp) / "req.txt"
        req.write_text("\n".join(lines) + "\n")
        proc = subprocess.run(["pip-audit", "-r", str(req), "--no-deps", "--disable-pip", "-f", "json"],
                              capture_output=True, text=True)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        print("pip-audit produced no JSON (is it installed, and is pypi.org reachable?):", proc.stderr[-800:])
        return 2

    today, failures, accepted = date.today(), [], []
    for dep in data.get("dependencies", []):
        vulns = dep.get("vulns") or []
        if not vulns:
            continue
        name = dep["name"].lower()
        ids = sorted({v["id"] for v in vulns})
        if name in ACCEPTED:
            reason, review_by = ACCEPTED[name]
            if date.fromisoformat(review_by) < today:
                failures.append(f"{dep['name']}=={dep['version']}: exception expired on {review_by} ({len(ids)} advisories)")
            else:
                accepted.append(f"{dep['name']}=={dep['version']}: {len(ids)} advisories accepted until {review_by}")
        else:
            fixes = sorted({f for v in vulns for f in v.get("fix_versions", [])})
            failures.append(f"{dep['name']}=={dep['version']}: {', '.join(ids)}; fixed in {', '.join(fixes) or 'no fix listed'}")
    for a in accepted:
        print("ACCEPTED (documented in docs/THREAT_MODEL.md):", a)
    for f in failures:
        print("FAIL:", f)
    print("pip-audit:", "FAILED" if failures else "ok")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
