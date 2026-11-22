# LINEAGE — Phase 5 & 6 completion notes

## Phase 5 — production readiness

- **Database:** Alembic is now included with an initial schema migration. Production can set `REQUIRE_DATABASE_MIGRATIONS=true`; development keeps `create_all` for zero-setup startup.
- **Postgres:** production compose uses PostgreSQL 16. SQLite remains a local-development default.
- **Background jobs:** persisted `background_jobs` plus a Redis queue/worker are included. Start with `python -m app.worker` when `JOB_QUEUE_ENABLED=true`.
- **Object storage:** encrypted uploads can use local disk or S3-compatible storage via `STORAGE_BACKEND=s3`, `S3_BUCKET`, and credentials. Server-side AES256 encryption is requested for S3 objects in addition to LINEAGE encryption.
- **Retention:** optional worker scheduling is controlled by `RETENTION_PURGE_ENABLED`; purge reuses the existing incident cleanup path and deletes encrypted objects.
- **Deployment:** production compose now includes the worker, migrations, object-storage configuration, Postgres and Redis.
- **Accessibility/mobile:** existing responsive layouts, keyboard focus states and reduced-motion behavior remain; Phase 5 adds clearer report-language controls and semantic regions. Further manual screen-reader QA is still recommended.
- **Languages:** English/Hindi PDF headings and labels are available. Full application translation remains a future localization pass.

## Phase 6 — legal/trust

- **Audit trail:** investigator actions are persisted with actor and timestamp.
- **Consent:** incident-scoped consent records store purpose, policy version, grant state and timestamp.
- **BSA §63 support:** the app can generate a structured certificate draft containing record identifiers, hashes, system/device particulars and a conditions checklist. It is explicitly marked as a draft and not legal advice or a finding of admissibility. Section 63 of the Bharatiya Sakshya Adhiniyam, 2023 addresses admissibility of electronic records and requires a certificate with specified particulars when a statement is sought to be admitted under the section; qualified counsel should complete and review the certificate for the actual proceeding.
- **Victim support:** an official India cybercrime reporting resource is surfaced without automatic contact or escalation.
- **Safety:** quick exit is available in the desktop top bar; support copy warns users to use a safer device/account where appropriate.
- **Legal review status:** configurable and deliberately not represented as counsel approval.

## What still requires real-world validation

1. Run `npm ci && npm run build` and `npm test` in an environment with registry access.
2. Run Alembic against a fresh PostgreSQL instance and then against a backup copy of an existing database before production cutover.
3. Validate S3 lifecycle, IAM, backups, restore, and key rotation with the chosen cloud provider.
4. Have a lawyer review the BSA §63 certificate workflow, privacy notice, retention schedule, victim-support language and platform-specific request/takedown templates.
5. Conduct manual WCAG/screen-reader/mobile QA with representative devices.
