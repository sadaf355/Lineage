# What you have to do (and why I could not)

*Updated 7 Oct 2026 after reading PRD v2.0, TRD v2.0, Project Flow v2.0 and the Executive Brief. See Part G for the
requirement-by-requirement comparison, and "What changed in this update" just below.*

## Update 9 Nov 2026: Phase I (read this first)
Phase I added metadata snapshots (FR-14/52), case-deletion tombstones, a fuller bundle, upload decode limits, a responsible-use page and operational counters. It was reviewed and four defects were fixed before this zip (see `docs/FIXES.md`). **None of Phase I has run on a real stack.** Still yours:
1. New migration `e81a4b2c9d10` (head). Run `alembic upgrade head` on a copy first.
2. New settings: `MAX_VIDEO_FRAMES`, `MAX_VIDEO_DURATION_SECONDS`, `MAX_DECOMPRESSION_RATIO`, `UPLOAD_PROBE_TIMEOUT_SECONDS`, `ADMIN_EMAILS`. **Tune `MAX_DECOMPRESSION_RATIO` (default 250 pixels per byte) on real screenshots before relying on it:** a flat 1920x1080 PNG of 8 KB is 259 and would be refused.
3. Video limits need `ffprobe` or OpenCV in the image; with neither, every video is refused (fails closed).
4. Still not true in Phase I: the bundle's `c2pa_results.json` is a fixed "not_validated" placeholder, and `bundle_timestamp.json` carries no RFC 3161 token.
5. `frontend/package-lock.json` is still missing six dev packages: run `npm install` and commit it.
6. The Parts C, F and G below pre-date the 8 Oct and 9 Nov builds. Where they say the MFA secret is plain text, scanning is off by default, or the audit head is not anchored, they are out of date; FIXES.md has the current state.

## Update 8 Oct 2026 (read this first)
Problems 1-8 from your list are fixed in code; see `docs/FIXES.md`. Still yours to do, in this order:
1. Run `docs/ANTIGRAVITY_TEST_PROMPTS.md` prompts 1-9. Nothing involving FastAPI, SQLAlchemy, Docker, ClamAV, npm or the real `c2pa` library has run yet.
2. In `frontend/`: `npm install`, commit the new `package-lock.json`.
3. Set two new secrets in production: `MFA_ENCRYPTION_KEY` (Fernet key) and decide `MFA_REQUIRED` (production example sets true).
4. Run `alembic upgrade head` (new revisions `c7e1f4a9d052`, `d3b9e6a1f471`). Back up first.
5. Have counsel confirm the 3 h / 2 h / 36 h / 48 h legal figures.
Still open from your list: detector measurement, metadata snapshots (FR-14, FR-52), network depth, roles and shared cases, secrets manager, document refresh.

## What changed in this update
- **Code fix to match the PRD claims policy.** The metadata verdicts were named `possible_modification` and
  `modified_after_capture`, and the text said the metadata "appears to have been changed". The PRD and Flow say "changed" may
  only be said against a preserved earlier snapshot. Renamed to `inconsistent_single` and `inconsistent_multiple`, rewrote the
  English and Hindi wording and the panel labels. The real "changed against a snapshot" state is still not built (FR-52).
- **Custody log in the bundle.** `GET /incidents/{id}/evidence/bundle` now includes `custody_log.json` (the audit events plus
  the hash-chain check result), covering part of FR-82 and FR-85. New test added.
- **Part G** (new): which of the 71 requirements this build moves, and which still need work.
- **Part E** has new decisions taken from the TRD's open-decision list.
- The PRD/TRD/Flow baseline is the earlier PhaseDEF zip, so their status tables are now out of date for the items in Part G.
  The four documents will need a status refresh after you run Part A.

The build environment I worked in had no access to package registries (npm and pip were blocked). So I could not install
FastAPI, SQLAlchemy or the frontend packages, boot the API, or run the browser tests. Everything that is pure Python logic was
tested (see "What was verified"). Wiring, routes, the database and the frontend were checked by static analysis only.
Part A is the order I would do things in. Parts B to F are work only you (or people you hire) can do.

## What was verified, and what was not
- **Ran and passed here:** 245 tests across the pure-logic modules (metadata forensics, provenance, hosting parsing, origin
  report, legal packs, case bundle, audit chain, TOTP with RFC 6238 vectors, prompt safety, upload scan, envelope helper,
  threat-model references, evaluation tooling and others). Backup and restore round-trip on SQLite.
- **Not run here (needs your machine):** 17 test files that import FastAPI (the API tests), `test_integrity_and_limits.py`
  (imports FastAPI), the whole frontend build and tests, Playwright, axe, Docker, Postgres, Neo4j, Redis, the ML models.
- **Checked statically only:** the new routes in `routers/origin.py`, MFA endpoints in `routers/auth.py`, upload scan wiring,
  model columns, Alembic migrations, `OriginPanel.tsx`, `MfaPanel.tsx`, Login changes. No syntax or undefined-name problems were
  found, but I cannot promise they run until you do Part A.

## Part A. First run on a real machine (about 1 to 2 hours)
1. Install Python 3.12 (3.13 has no torch wheels, so ML needs 3.12) and Node 20.
2. `python scripts/first_run.py` and read what it reports. Start with the core install (no ML); add ML later with
   `pip install -r backend/requirements-ml.txt`.
3. Backend tests: `cd backend && pip install -r requirements-dev.txt && pytest -q`.
   **If anything fails, send me the full output and I will fix it.** This is the most important step: it is the first time the
   API-level tests of the new routes will run.
4. Run the migrations on a copy of any existing database: `alembic upgrade head`. Five new revisions
   (`9c2e5f1a7d33`, `b4d8a60e2c19`, `c7e1f4a9d052`, `d3b9e6a1f471`, `e81a4b2c9d10` = head) follow the existing ones. Then start the API and open `/docs`.
5. Frontend: `cd frontend && npm install && npm run build && npm test`. **Commit the regenerated `package-lock.json`**; the
   lock shipped here may not match `package.json` (`scripts/check_lock_sync.py` checks this).
6. Click through: register, log in, create a case, upload an image, open the Evidence Locker, open the Origin panel,
   switch to Hindi, download a legal pack and a case bundle, open the bundle and run its verifier, then turn on two-factor
   in Settings and log in again with a code.
7. Browser tests: `npx playwright install` then the Playwright suite and the axe accessibility run.
8. Run `scripts/demo.sh`, `scripts/demo_check.py`, `scripts/trial_feature_match.py`, `scripts/load_test.py`.

## Part B. Legal and policy (a lawyer must do these)
- Review all four legal packs and their wording, including the section reference for BSA s.63 evidence certificates, the
  IT Rules and TAKE IT DOWN timelines, and the NCRP summary. Until they sign off, every PDF says DRAFT. When they approve,
  set `LEGAL_REVIEW_STATUS` in the backend environment (see `app/core/config.py` for the allowed values).
- Have a Hindi-fluent translator review the Hindi wording of the metadata and origin reports (it is draft). The legal packs themselves are English only; decide whether you need Hindi or other-language packs.
- Confirm what the "inconsistent" language may say in a court filing. The tool says leads, not proof, and never says "changed" without a preserved snapshot.
- Finish the DPIA (`docs/runbooks/DPIA_TEMPLATE.md`), retention periods, consent text and your privacy notice.
- Decide how you handle images of minors and who you escalate to.
- Confirm the StopNCII partnership terms and scope before claiming any integration.
- Dataset licences for anything you train or evaluate on, then `phase_b.sh` and the detector model card.

## Part C. Security work that needs real infrastructure
- Choose a key manager (cloud KMS or a secrets manager). Today the encryption key is a file on disk.
- Decide whether to wire the envelope helper (`services/envelope.py`) into `file_storage`. It is built and tested but is
  **not connected** (the old `ENVELOPE_ENCRYPTION_ENABLED` setting was removed so nobody thinks it does something), because switching storage encryption on a live system needs a migration plan and a rollback. I did not
  want to change how evidence is stored without a way for you to test it.
- Put a WAF and TLS in front, set `AUTH_COOKIE_SECURE=true`, restrict CORS to your domain, and set a strong `SECRET_KEY`.
- ClamAV is now a service in `deploy/docker-compose.prod.yml` (production runs `MALWARE_SCAN_MODE=enforce`; demo defaults to `log`).
  `deploy/clamd.conf` is untested: bring it up, check it becomes healthy, and confirm EICAR is refused (Antigravity prompt 4).
- Commission a penetration test. Fix the findings; add rows to `docs/THREAT_MODEL.md`.
- Enable GitHub code scanning (the workflow `security.yml` is included) and Dependabot.
- Practise the runbooks once: backup, restore, key rotation, incident response.
- Real timestamp authority: get an account with a TSA, test a real stamp, and add CMS signature verification of the reply.
  Today the stamp is recorded but its signature is not verified.

## Part D. People work
- Usability test with an NGO or helpline team and at least a few survivors' advocates. Their feedback decides the tone of
  every screen, so do this before launch.
- Rehearse the demo (`scripts/rehearsal_timer.py`).
- Decide who may see a case beyond the owner (see "Not built" below) and write the access policy.

## Part E. Decisions I need from you
- Do you want hosting lookups (RDAP) on? They contact public registries with a domain or IP, nothing about the victim.
  Default is off.
- Which platforms get a custom preservation template first?
- Do you want anonymous intake (no account)? It changes the risk model, so it should be a deliberate choice.

- C2PA: which open-source implementation (the TRD suggests the Content Authenticity Initiative SDK or its CLI) and which signer
  trust list. Check licence and format support first.
- GeoIP and ASN provider and its licence for this use (FR-61, FR-62). Nothing is built until you choose.
- Antivirus engine and sandbox profile to run next to the API (FR-13). ClamAV is the only engine wired in.
- Which timestamp authority, and whether production can reach it.
- First RBAC release: single-tenant roles, or per-case membership (the TRD leaves this open).
- Which datasets form the detector evaluation set, and their licences (FR-22).

## Part F. Not built (be honest about these when you present)
- Roles and sharing: any teammate access, NGO case handoff, role-based access control.
- Real C2PA signature validation (needs the optional `c2pa` library and testing with real signed files).
- TSA reply signature verification.
- Envelope encryption wired into storage (helper only).
- Hindi in PDFs: the legal packs are English only, and the PDF code uses a built-in Latin font. If you add Hindi packs you
  must bundle a Devanagari font and test shaping.
- Anonymous intake; watching for re-uploads of removed content; platform-specific automation of takedown submission.
- Re-encoding uploaded images to strip hostile content (a helper idea; originals must stay untouched as evidence anyway).
- A QR code in the MFA screen: it shows the key and a link, which works with most authenticator apps.
- MFA: the secret is now encrypted at rest (`MFA_ENCRYPTION_KEY`), with recovery codes and replay protection. Still missing: passkeys and a session inventory.
- Metadata snapshots exist (Phase I), but the Origin panel's older "inconsistent" report and the new snapshot compare are separate checks; a provenance timeline view (FR-53) does not exist.

## Part G. Comparison with PRD v2.0 / TRD v2.0 (71 requirements)
The PRD counts 30 implemented, 21 partial, 20 to implement for the earlier zip. Below is what this build changes. "Built, unrun"
means the code and its pure-logic tests exist but the API route or screen has not been run (Part A).

**Moved forward in this build**
| FR | Requirement | PRD v2.0 status | This build | What is still missing |
|---|---|---|---|---|
| 13 | Malware scan and decode limits | To implement | Mostly built, unrun | Streaming EICAR and ClamAV scan, pixel limit, decompression-ratio (large images only), video frame and duration limits, production enforce with a ClamAV service. Missing: YARA, sandboxed subprocess decoding, no-network scan container. |
| 51 | C2PA validation | To implement | Partial | Detects Content Credentials and AI markers (structure only). Missing: signature validation, signer trust list, ingredients, valid/invalid/untrusted states. |
| 60 | Hosting footprint | Partial | Partial, improved | Opt-in RDAP adds network name, handle, CIDR, registry country, domain registrar and dates. Still missing: collection inside the pinned fetch at capture time. |
| 61 | ASN, CDN, TLS, DNS observations | To implement | Barely started | RDAP network owner only. No ASN, CDN detection, TLS certificate details or DNS observations. |
| 82 | Chain-of-custody ledger | To implement | Partial, built, unrun | Per-case hash chain, `audit/verify`, export inside the bundle. Built: row lock, unique index, head-hash anchor in manifests and bundles, and a tombstone kept when a case is deleted. Missing: events from before the chain are unchained; the anchor is only as external as the signed manifest you hand out. |
| 85 | Evidence package | Partial | Partial, improved | Signed bundle with hashes, index, manifest, verifier, custody log. Missing: C2PA results, report PDF and timestamp are not placed in the bundle by the route. |
| 90 | Request packs and drafts | Implemented | Extended | Four draft legal packs (preservation, IT Rules, TAKE IT DOWN, NCRP). Draft until counsel signs off. Human approval gate is the download itself, which is audited; nothing is sent. |
| 104 | MFA | To implement | Partial, built, unrun | TOTP with RFC 6238 test vectors, enrol/enable/disable, login code. Built: encrypted secret, 10 recovery codes, replay protection, `MFA_REQUIRED`. Missing: passkeys, session inventory, per-role enforcement. |
| 106 | Supply-chain checks | Partial | Partial, improved | SBOM script (tested here), CodeQL and gitleaks workflow (unrun). Missing: container scan, signed releases. |
| 108 | Threat model tied to tests | Implemented | Extended | 14 new rows, each with a real test reference. |
| 124 | Backup and restore drill | To implement | Partial | `backup.sh` / `restore.sh` tested on SQLite, runbooks. Missing: the drill itself, Postgres path untested, key escrow process. |
| 134 | Provenance and network screens | To implement | Partial | Origin panel inside the Evidence Locker. Missing: a provenance timeline view and a network footprint screen. |
| – | Prompt-injection and PII redaction for LLM calls | not in PRD | Built, unrun | Copilot context is delimited and redacted. The one-sentence report summary uses only numbers and labels. Worth adding to the PRD. |

**Not touched, still on you (or a later build)**
- FR-14 and FR-52 **metadata snapshot at ingest and "changed against a snapshot"**: built in Phase I (table, migration, capture at upload, compare route and a button in the Origin panel), unrun. Missing: an automatic compare when a later copy is ingested, and a provenance timeline (FR-53).
- FR-53 provenance timeline, FR-54 generator hypothesis (P2), FR-73 IOC extraction, FR-62 GeoIP, FR-63 capture telemetry.
- FR-103 RBAC and case membership (`CaseMember`, `Role`). Needs your Part E decision, then a careful change to every route.
- FR-121 detection and fingerprinting in the worker queue. FR-122 S3 provider validation. FR-123 observability and alerts.
- FR-25 calibrated score bands, FR-21/22 second model and the benchmark run (needs a licensed dataset).
- FR-81 real timestamp reply. FR-83 counsel review. FR-92/93 connectors and watchlists.
- FR-131 axe run, FR-132 mobile check, FR-133 state audit, FR-135 responsible-use page, FR-136 `.glb` asset.
- FR-84/94: Hindi PDF needs a Devanagari font packaged in the image (TRD says so). The new legal packs are English only.
- TRD data model: `ProvenanceEvent`, `C2paResult`, `NetworkObservation`, `CaseMember`, `CustodyEvent` tables. The audit chain
  reuses `AuditEvent` instead of a separate `CustodyEvent` table; decide whether you want the separate table.

**Corrections the four documents need after this build**
- Alembic migrations: four, not two (`9c2e5f1a7d33` audit chain, `b4d8a60e2c19` MFA).
- The TRD repository layout and API tables should list the new routes: `/incidents/{id}/origin`, `/media/{id}/metadata-report`,
  `/automation/legal-pack`, `/audit/verify`, `/evidence/bundle`, and `/auth/mfa/*`.
- The "To add" list for the upload gate should say the scan exists but is off by default.
- The test counts in the TRD (about 282 backend tests) are now higher; re-count after Part A.
- Check that "Implemented" in the PRD still means "built, not run" until Part A passes. I kept that definition.
