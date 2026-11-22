# Backup and restore

Backup: `DATABASE_URL=... scripts/backup.sh ./backups/2026-10-07`
Restore into an empty folder: `scripts/restore.sh ./backups/2026-10-07 ./restore-test`

- The script checks checksums before restoring and refuses a non-empty target.
- Keys are **not** in the backup. Store `.file_encryption_key` and `.manifest_signing_key` in a separate, access-controlled place.
  Without the encryption key the uploads archive cannot be read.
- Test a restore every month. After restoring, start the API and call `GET /incidents/{id}/audit/verify` on a case.
- The SQLite path was tested in this repo's build. The Postgres path (pg_dump) was not run here.
