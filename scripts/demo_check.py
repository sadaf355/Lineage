#!/usr/bin/env python3
"""End-to-end API check for the demo path. Run it before every rehearsal and before presenting.

    python scripts/demo_check.py                                   # core path
    python scripts/demo_check.py --trace-url https://you.github.io/lineage-trace-demo/

Steps: health + security headers, CSRF guard, account, case, upload, content-sniffing (a renamed executable is refused),
detect, fingerprint, integrity, signed manifest (sign -> verify), safety check (private URL refused), and with --trace-url:
trace -> accept, then trace again -> reject. Finally report generation (inline job) and the BSA draft.
Exit code 0 only if every step passed. A WARN is not a failure but should be read before demoing.

Needs: pip install requests. Uses a throwaway account unless --demo-account is given.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_IMAGE = ROOT / "backend" / "demo_assets" / "sample_case_image.jpg"

results: list[tuple[str, str, str]] = []  # (status, step, detail)


def record(status: str, step: str, detail: str = "") -> None:
    results.append((status, step, detail))
    colour = {"PASS": "32", "FAIL": "31", "WARN": "33"}[status]
    print(f"\033[{colour}m{status}\033[0m  {step}" + (f"  ({detail})" if detail else ""))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--image", default=str(DEFAULT_IMAGE))
    ap.add_argument("--trace-url", default=None, help="public page containing a copy of the case image")
    ap.add_argument("--demo-account", action="store_true", help="use demo@lineage.app instead of a throwaway account")
    args = ap.parse_args()
    api = args.api.rstrip("/")
    s = requests.Session()
    s.headers["User-Agent"] = "lineage-demo-check"
    from urllib.parse import urlparse
    if (urlparse(api).hostname or "") in ("localhost", "127.0.0.1", "::1"):
        s.trust_env = False  # a system or corporate proxy must not intercept calls to this machine

    def call(method: str, path: str, **kw):
        kw.setdefault("timeout", 180)
        return s.request(method, f"{api}{path}", **kw)

    # 1. health
    try:
        h = call("GET", "/health", timeout=10).json()
    except Exception as exc:
        record("FAIL", "API reachable", str(exc))
        return finish()
    record("PASS", "API reachable", f"env={h.get('env')}")
    det = h.get("detector", {})
    if det.get("loaded"):
        record("PASS", "Detector model loaded", det.get("model_id", ""))
    else:
        record("WARN", "Detector model NOT loaded", "detections will use the labelled pixel-heuristic fallback")
    if h.get("offline_demo"):
        record("WARN", "Offline demo mode is on", "expected only when running without Wi-Fi")

    # 1b. security headers and CSRF guard (cheap regression checks for the hardening work)
    hr = call("GET", "/health", timeout=10)
    missing = [k for k in ("X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy") if k not in hr.headers]
    record("PASS" if not missing else "FAIL", "Security headers present", "" if not missing else "missing: " + ", ".join(missing))
    r = call("POST", "/auth/refresh", timeout=10)
    record("PASS" if r.status_code == 403 else "FAIL", "Refresh without CSRF header is refused", f"status {r.status_code}")

    # 2. account
    if args.demo_account:
        email, password = "demo@lineage.app", "demo-access"
    else:
        email, password = f"check-{int(time.time())}@lineage.app", "Check-Pass-12345"
        r = call("POST", "/auth/register", json={"email": email, "password": password, "display_name": "Demo check"})
        if r.status_code != 201:
            record("FAIL", "Register throwaway account", f"{r.status_code} {r.text[:120]}")
            return finish()
    r = call("POST", "/auth/login", data={"username": email, "password": password})
    if r.status_code != 200:
        record("FAIL", "Login", f"{r.status_code} {r.text[:120]}")
        return finish()
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    record("PASS", "Login", email)

    # 3. case
    r = call("POST", "/incidents", json={"title": "Demo check case", "description": "Automated check", "victim_ref": "V-CHECK"})
    if r.status_code != 201:
        record("FAIL", "Create case", f"{r.status_code} {r.text[:120]}")
        return finish()
    iid = r.json()["id"]
    record("PASS", "Create case", iid)

    # 4. upload
    img = Path(args.image)
    if not img.is_file():
        record("FAIL", "Sample image present", str(img))
        return finish()
    r = call("POST", f"/incidents/{iid}/media", files={"file": (img.name, img.read_bytes(), "image/jpeg")})
    if r.status_code != 201:
        record("FAIL", "Upload image", f"{r.status_code} {r.text[:160]}")
        return finish()
    mid = r.json()["id"]
    record("PASS", "Upload image", img.name)

    # 4b. a Windows executable renamed to .png must be refused (content sniffing), and must not be stored
    r = call("POST", f"/incidents/{iid}/media", files={"file": ("holiday.png", b"MZ\x90\x00" + b"\x00" * 256, "image/png")})
    record("PASS" if r.status_code in (400, 415, 422) else "FAIL", "Renamed executable refused at upload", f"status {r.status_code}")

    # 5. detect
    r = call("POST", f"/incidents/{iid}/media/{mid}/detect")
    if r.status_code == 200:
        d = r.json()
        name = d.get("model_name", "")
        if "fallback" in name:
            record("WARN", "Detection ran on FALLBACK heuristic", name)
        else:
            record("PASS", "Detection ran on real model", f"{name}, score {d.get('manipulation_likelihood')}% (synthetic image: score is not meaningful)")
    else:
        record("FAIL", "Detection", f"{r.status_code} {r.text[:160]}")

    # 6. fingerprint (a synthetic image has no face; the endpoint should still succeed)
    r = call("POST", f"/incidents/{iid}/media/{mid}/fingerprint")
    record("PASS" if r.status_code == 200 else "FAIL", "Fingerprint", "" if r.status_code == 200 else f"{r.status_code} {r.text[:160]}")

    # 7. integrity
    r = call("GET", f"/incidents/{iid}/media/{mid}/integrity")
    record("PASS" if r.status_code == 200 else "FAIL", "Integrity verification", "" if r.status_code == 200 else f"{r.status_code} {r.text[:160]}")

    # 7b. signed manifest: sign the evidence hashes, then verify the signature
    r = call("POST", f"/incidents/{iid}/evidence/manifest")
    if r.status_code == 503:
        record("FAIL", "Sign evidence manifest", "signing key not configured (set MANIFEST_SIGNING_KEY, or ENV=development to auto-create one)")
    elif r.status_code != 201:
        record("FAIL", "Sign evidence manifest", f"{r.status_code} {r.text[:160]}")
    else:
        mf = r.json()
        mf_id = mf.get("id")
        record("PASS", "Sign evidence manifest", f"key {mf.get('key_id', '?')}")
        r = call("POST", f"/incidents/{iid}/evidence/manifests/{mf_id}/verify")
        v = (r.json().get("verification") or {}) if r.status_code == 200 else {}
        good = r.status_code == 200 and v.get("signature_valid") and v.get("manifest_sha256_matches") and v.get("entries_digest_matches")
        record("PASS" if good else "FAIL", "Manifest signature verifies", "" if good else f"{r.status_code} {r.text[:200]}")
        drift = (r.json().get("case_drift_since_signing") or {}) if r.status_code == 200 else {}
        record("PASS" if drift.get("unchanged") else "WARN", "No drift since signing", "" if drift.get("unchanged") else str(drift)[:140])

    # 8. safety: a private address must be refused, never fetched
    r = call("POST", f"/incidents/{iid}/sources/trace-url", json={"url": "http://127.0.0.1:8000/health"})
    record("PASS" if r.status_code in (400, 422) else "FAIL", "Private URL refused by tracer", f"status {r.status_code}")

    # 9. trace accept / reject on a real public page
    if args.trace_url:
        trace_flow(call, iid, args.trace_url)
    else:
        record("WARN", "Trace accept/reject skipped", "pass --trace-url with your hosted demo page (see backend/demo_assets/README.md)")

    # 10. report
    r = call("POST", f"/incidents/{iid}/report")
    record("PASS" if r.status_code in (200, 201) else "FAIL", "Generate report", "" if r.status_code in (200, 201) else f"{r.status_code} {r.text[:160]}")

    # 10b. the report job must finish without a worker (this was the two-minute hang), and the BSA certificate stays a draft
    t0 = time.time()
    r = call("POST", f"/incidents/{iid}/jobs/report")
    if r.status_code in (200, 202):
        j = r.json()
        took = time.time() - t0
        done = j.get("status") == "succeeded"
        record("PASS" if done else ("WARN" if j.get("worker_required") else "FAIL"), "Report job completes",
               f"status {j.get('status')}, {'inline' if j.get('ran_inline') else 'queued for worker'}, {took:.1f}s")
    else:
        record("FAIL", "Report job", f"{r.status_code} {r.text[:160]}")
    r = call("POST", f"/incidents/{iid}/evidence/bsa63-certificate")
    body = r.text.lower()
    record("PASS" if r.status_code == 200 and "draft" in body else "FAIL", "BSA section 63 certificate is marked draft",
           "" if r.status_code == 200 else f"{r.status_code} {r.text[:120]}")

    # tidy up the throwaway case
    if not args.demo_account:
        call("DELETE", f"/incidents/{iid}")
    return finish()


def trace_flow(call, iid: str, url: str) -> None:
    r = call("POST", f"/incidents/{iid}/sources/trace-url", json={"url": url})
    if r.status_code != 200 or not r.json().get("matched"):
        record("FAIL", "Trace finds the case image on the page", f"{r.status_code} {r.text[:200]}")
        return
    pending = r.json()["pending_match"]
    record("PASS", "Trace finds the case image on the page", f"similarity {pending['similarity_score']}%, hashes {pending['agreeing_hashes']}/3")
    if "unrelated" in str(pending.get("matched_image_url", "")):
        record("FAIL", "Trace picked the wrong (decoy) image", pending["matched_image_url"])
    r = call("POST", f"/incidents/{iid}/sources/trace-url/accept", json=pending)
    record("PASS" if r.status_code == 201 else "FAIL", "Accept match becomes a source", "" if r.status_code == 201 else f"{r.status_code} {r.text[:200]}")
    tampered = dict(pending, similarity_score=100.0, url="https://evil.example/forged")
    r = call("POST", f"/incidents/{iid}/sources/trace-url/accept", json=tampered)
    record("PASS" if r.status_code == 400 else "FAIL", "Tampered match is refused", f"status {r.status_code}")
    # Second trace -> reject path
    r = call("POST", f"/incidents/{iid}/sources/trace-url", json={"url": url})
    if r.status_code == 200 and r.json().get("matched"):
        r2 = call("POST", f"/incidents/{iid}/sources/trace-url/reject", json=r.json()["pending_match"])
        record("PASS" if r2.status_code == 204 else "FAIL", "Reject deletes the pending capture", f"status {r2.status_code}")
    else:
        record("FAIL", "Second trace for the reject path", f"{r.status_code} {r.text[:160]}")


def finish() -> int:
    fails = [x for x in results if x[0] == "FAIL"]
    warns = [x for x in results if x[0] == "WARN"]
    print(f"\n{len(results) - len(fails) - len(warns)} passed, {len(warns)} warnings, {len(fails)} failed.")
    if warns:
        print("Read the warnings before presenting.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
