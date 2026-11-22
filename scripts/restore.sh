#!/usr/bin/env bash
# Restore a backup made by scripts/backup.sh into a NEW location, then verify. Never overwrites a live database.
set -euo pipefail
SRC="${1:?usage: restore.sh <backup-dir> <target-dir>}"
DST="${2:?usage: restore.sh <backup-dir> <target-dir>}"
[ -e "$DST" ] && [ -n "$(ls -A "$DST" 2>/dev/null)" ] && { echo "Target $DST is not empty; refusing."; exit 1; }
mkdir -p "$DST"
( cd "$SRC" && sha256sum -c SHA256SUMS )
[ -f "$SRC/lineage.db" ] && cp "$SRC/lineage.db" "$DST/lineage.db"
[ -f "$SRC/uploads.tgz" ] && tar -C "$DST" -xzf "$SRC/uploads.tgz"
[ -f "$SRC/lineage.pgdump" ] && echo "Postgres dump: restore with: pg_restore --create -d postgres $SRC/lineage.pgdump"
echo "Restored into $DST. Point DATABASE_URL/DATA_DIR at it, start the API, then call GET /incidents/{id}/audit/verify on a case."
