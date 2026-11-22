#!/usr/bin/env bash
# Back up the database and the encrypted evidence store. Run from the repo root.
# SQLite:   DATABASE_URL=sqlite:///backend/data/lineage.db  -> file copy via Python sqlite3 backup API
# Postgres: DATABASE_URL=postgresql://...                   -> pg_dump
# Keys are NOT included on purpose. Back up .file_encryption_key, the manifest signing key and MFA_ENCRYPTION_KEY separately (see docs/runbooks/BACKUP_RESTORE.md).
set -euo pipefail
OUT="${1:-backup-$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$OUT"
URL="${DATABASE_URL:-sqlite:///backend/data/lineage.db}"
case "$URL" in
  sqlite:///*) DB="${URL#sqlite:///}"; python3 -c "import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.close(); s.close()" "$DB" "$OUT/lineage.db" ;;
  postgres*)   pg_dump --format=custom --file "$OUT/lineage.pgdump" "$URL" ;;
  *) echo "Unsupported DATABASE_URL"; exit 1 ;;
esac
DATA="${DATA_DIR:-backend/data}"
if [ -d "$DATA/uploads" ]; then tar -C "$DATA" -czf "$OUT/uploads.tgz" uploads; fi
( cd "$OUT" && sha256sum * > SHA256SUMS )
echo "Backup written to $OUT (no keys included)."
