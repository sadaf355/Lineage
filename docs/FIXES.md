# Fixes in this build (on top of Lineage-Release)

1. **Traced matches can no longer be forged.** The server signs every pending match (HMAC, bound to the case and a 30 minute expiry). `trace-url/accept` rejects unsigned, edited, replayed or expired matches.
2. **Temporary page captures are cleaned up.** New `POST /incidents/{id}/sources/trace-url/reject` deletes the capture; the Add Source dialog has a "Dismiss and delete capture" button.
3. **Test tools are real devDependencies** (vitest, jsdom, Testing Library, Playwright). CI, preflight and the frontend Dockerfile use `npm install`.
   After your first `npm install`, commit the regenerated `frontend/package-lock.json`, then you can switch back to `npm ci`.
4. **`delete_encrypted` refuses any path outside the uploads folder.**
5. New tests: signature round trip and tamper detection, accept rejects unsigned/tampered/replayed/expired, reject deletes the capture, delete refuses outside paths.

Not run in the build environment (no network): `pytest`, `npm run build`. Run `./scripts/preflight.sh` before presenting.

---

# Final build fixes

1. **Report generation no longer hangs by default.** `POST /incidents/{id}/jobs/report` now runs the job inline when no worker/Redis queue is configured (local and demo use). With `JOB_QUEUE_ENABLED=true` and `REDIS_URL` set (production compose) it is queued for `python -m app.worker`. The response includes `ran_inline` and `worker_required`.
2. **CSRF protection on cookie endpoints.** `/auth/refresh` and `/auth/logout` require the header `X-Lineage-CSRF: 1`, and a browser `Origin`, if sent, must be in `CORS_ORIGINS`. The frontend sends the header automatically.
3. **Security headers.** The API adds `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, a framing-only CSP and HSTS over HTTPS (docs pages exempt). The production Caddyfile adds the same plus a strict app CSP.
4. **BSA §63 draft is now `POST`**, because it records a certificate row. A GET returns 405.
5. **3D scene respects `prefers-reduced-motion`** (draws one still frame).
6. **Unused Google Fonts removed** from `index.html` (no third-party font requests).
7. **Zip hygiene:** no `__pycache__`, `.pytest_cache` or build info; `.pytest_cache/` added to `.gitignore`.
8. New tests: `tests/test_final_fixes.py`. Existing refresh/logout test updated for the CSRF header.

Still to do (needs your machine): run `./scripts/preflight.sh`, run the detector evaluation (`backend/eval/README.md`) and paste the numbers into `docs/DETECTOR_MODEL_CARD.md`.

---

# Review fixes after the Phase D/E/F build

1. **Removed `backend/data` from the package** (it held a `.file_encryption_key` and test `.enc` files). New `scripts/make_release_zip.sh` builds a clean zip and aborts if a key or data file slips in. If you ever ran with that shipped key, do not reuse it.
2. **Signed manifest now has a UI.** `components/ManifestPanel.tsx` (mounted in the Evidence Locker): sign current evidence, list manifests, verify against this deployment's key, show drift since signing, copy the public key. API methods added to `lib/api.ts`.
3. **Production compose supplied no `MANIFEST_SIGNING_KEY`**, so manifest endpoints would have returned 503 in production. It is now required (`deploy/docker-compose.prod.yml`), documented in `deploy/.env.production.example` with a generation command. `LEGAL_REVIEW_STATUS` defaults to `pending`.
4. **Capture sweep is scheduled in production** (`CAPTURE_SWEEP_ENABLED=true` on the worker).
5. **`TRACE_FEATURE_MATCH_ENABLED` documented** in `backend/.env.example` with a reminder to trial it on your own sample.
6. **Lock-file guard:** `scripts/check_lock_sync.py` (run by preflight and the release script). It currently reports the lock is out of sync.
7. New tests: `tests/test_release_hygiene.py`.

## Still open (needs your machine)
* `cd frontend && npm install`, then commit the regenerated `package-lock.json` (6 dev dependencies are missing from the lock). Until then `scripts/make_release_zip.sh` refuses to build, by design.
* `./scripts/preflight.sh`, `npm run test:e2e` (axe), real-browser check of the scanner, palette, rail and the new manifest panel.
* Detector evaluation on a licensed dataset (`backend/eval/phase_b.sh`), then fill the model card.
* Lawyer review of the BSA certificate (`docs/LEGAL_REVIEW.md`).
* No `hero.glb` ships; the procedural 3D scene is used.

---

# Phase B and C build

See `docs/PHASE_B_C_DONE.md`. Highlights: leakage-safe evaluation protocol with confidence intervals and a near-duplicate check,
a self-test for the evaluation tooling, an in-app panel that never shows a smoke test as measured, a feature-match trial script, a
broader demo check, an offline readiness check wired into `demo.sh --offline`, and a rehearsal timer. New tests:
`test_eval_stats.py`, `test_eval_protocol_harness.py`, `test_eval_leakage.py`, `test_demo_check_script.py`,
`test_rehearsal_timer.py`, `test_phase_bc_wiring.py`.



---

# Run-first build

See `docs/RUN_FIRST.md`: core/ML requirements split (fixes the Python 3.13 install failure), `scripts/first_run.py`, `PRELOAD_MODELS=false` default, Dockerfile `INSTALL_ML` argument, one wrong test assertion corrected.


---

# Complete build

Read `docs/YOUR_TODO.md` first: it says what was verified, what was not, and what you must do.

Added: metadata tamper report (9 checks, 4 verdicts, never "stripped = tampered"), content-origin report (no creator-IP field),
structural C2PA detection, opt-in RDAP hosting lookup, four draft legal packs, signed case bundle with verifier, tamper-evident
audit chain (+ `GET /incidents/{id}/audit/verify`), optional TOTP two-factor, prompt-injection and PII handling for LLM calls,
upload scan (EICAR, clamd, pixel limit; `MALWARE_SCAN_MODE`), envelope-encryption helper (not wired), SBOM script, CI security
workflow, backup/restore scripts, runbooks, 14 new threat-model rows, two Alembic migrations, frontend Origin panel and MFA panel.

Removed: an earlier orphaned set of duplicate modules (`origin_report`, `c2pa_read`, `hosting_intel`, `egress_guard`,
`exif_factory` and their two tests). Nothing imported them; their job is done by `origin`, `provenance`, `hosting_enrich` (which
reuses the DNS-pinned fetcher in `source_tracing`) and `exif_builder`.

Known limits: see "Part F" of `docs/YOUR_TODO.md`.

## Update after PRD/TRD v2.0 review
Renamed the metadata verdicts to `inconsistent_single` / `inconsistent_multiple` and rewrote their wording (PRD claims policy:
never "changed" without a preserved snapshot). Added `custody_log.json` to the case bundle. Updated `docs/YOUR_TODO.md` (Part G).

## Update: the eight reported problems (8 Oct 2026)
1. **Audit chain fork.** `audit.record` now locks the case row (`SELECT ... FOR UPDATE`), inserts inside a SAVEPOINT, and retries up to 8 times on a conflict. New unique index `ux_audit_incident_seq` on `(incident_id, seq)` (legacy NULL seqs allowed). Migration `c7e1f4a9d052`. New `tests/test_audit_db.py` (record -> verify_chain, edited row, index, retry, give-up, parallel writers on Postgres via `TEST_POSTGRES_URL`). **Not run here: needs SQLAlchemy.**
2. **Anchor.** Head hash (`audit_anchor`) is in every signed manifest, in `bundle_index.json`, and the bundle carries `custody_log.json` with the chain, re-checkable offline (`case_bundle.verify_custody_log`). The manifest verify route returns `audit_anchor_check`.
3. **Malware scan.** Streaming scan (64 KB chunks, clamd INSTREAM, size cap). `clamav` service added to the production compose (enforce, MFA on) and as an optional `scan` profile in the demo. Default mode is now `log`. `deploy/clamd.conf` is untested.
4. **MFA.** TOTP secret encrypted at rest (`MFA_ENCRYPTION_KEY`), 10 one-time recovery codes (HMAC-hashed), replay refused (`mfa_last_step`), `MFA_REQUIRED` enforcement (403 `mfa_setup_required`). Migration `d3b9e6a1f471`. Routes unrun.
5. **Legal packs.** IT Rules split into `order` 3 h, `high_risk_complaint` 2 h (default), `individual_complaint` 36 h; counsel caveat kept. TAKE IT DOWN stays 48 h and says it covers intimate imagery only. Figures come from the summaries you cited; counsel must confirm.
6. **Dead setting.** `ENVELOPE_ENCRYPTION_ENABLED` and `MASTER_KEY` removed; `envelope.py` docstring says it is not wired.
7. **C2PA.** Optional `requirements-c2pa.txt` (version range unverified), `INSTALL_C2PA` Docker arg, `first_run.py --c2pa`, and 7 tests of the validator-present path using a fake module. The real library is untested.
8. **Packaging.** Caches removed from the zip. `package-lock.json` could NOT be regenerated (no registry): run `npm install` in `frontend/` (Antigravity prompt 3).

## Phase I review (9 Nov 2026)
Added in Phase I: `MetadataSnapshot` (taken at upload from the first 4 MB), compare route `POST /incidents/{id}/media/{mid}/metadata/compare`, `CaseTombstone` written on case delete, bundle now lists snapshot JSON, `c2pa_results.json`, `report.pdf` and `bundle_timestamp.json`, image and video decode limits, `/responsible-use` page (EN/HI), `OperationalEvent` counters with admin summary, migration `e81a4b2c9d10`.
Defects found in review and fixed here:
1. `routers/sources.py` imported `abuse_guard` from `services.operations`, which does not define it: the API would not start. Fixed.
2. `frontend/src/data/roadmapContent.ts` was missing from the zip while `Roadmap.tsx` imports it: the frontend build would fail. Restored.
3. The tombstone read a key (`head_hash`) that `audit.verify_chain` does not return, so `final_audit_head_hash` was always empty. It now uses `audit.anchor`.
4. `GET /custody/tombstones/{case_id}` needed no login. It now requires login and the case owner (new `owner_user_id` column, in the same migration).
5. Video probing accepted a file OpenCV could not open (it returns -1 frames). Now refused.
6. The snapshot step loaded the whole upload into memory; it now reads 4 MB. On snapshot failure the stored file is deleted and the half-added row rolled back. The compare route no longer reads an unbounded upload.
7. New tests: `test_import_names.py` (every `from app... import` must resolve) and `test_phase_i_tombstone.py`.
Not changed, needs your call: the decompression-ratio default (see YOUR_TODO), and `c2pa_results.json` is still a placeholder.

## Phase I follow-up (9 Nov 2026, second pass)
- Decompression-ratio rule now applies only at or above `DECOMPRESSION_RATIO_MIN_PIXELS` (default 20 million), so normal flat screenshots are accepted while a 64 MP image from 50 KB is still refused. Two tests added.
- `c2pa_results.json` in the bundle is now a real `provenance.inspect_c2pa` result per image (50 MB cap; "not_validated" or "error" when it cannot be read; real signature checks only with the optional `c2pa` package).
- Origin panel: a "Compare a later copy with the preserved snapshot" control calls the compare route (`api.compareMetadata`).
- `YOUR_TODO.md` Parts C, F and G corrected to match the code (ClamAV, MFA, anchor, snapshots, migration count).
Still open: `bundle_timestamp.json` has no timestamp-authority token; `package-lock.json` needs `npm install`; the four Word documents are not refreshed.
