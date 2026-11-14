#!/bin/sh
# Database backups for the production stack (the `backup` service in
# docker-compose.prod.yml): a pg_dump in custom format (-Fc, compressed,
# restorable with pg_restore) into $BACKUP_DIR, once at start and then every
# day at $BACKUP_HOUR UTC. Dumps older than $BACKUP_KEEP_DAYS days are deleted.
# BACKUP_ONCE=1 takes one dump and exits (a backup on demand).
#
# Connection: the standard PGHOST / PGUSER / PGPASSWORD / PGDATABASE variables.
# Restore: docs/implementation-docs/deployment-runbook.md, "Database backups".
set -eu

BACKUP_DIR="${BACKUP_DIR:-/backups}"
BACKUP_HOUR="${BACKUP_HOUR:-3}"
BACKUP_KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"

dump() {
    stamp=$(date -u +%Y%m%d-%H%M%S)
    file="$BACKUP_DIR/${PGDATABASE}-$stamp.dump"
    # Write under a temporary name so a failed or interrupted dump never looks complete.
    if pg_dump -Fc -f "$file.partial"; then
        mv "$file.partial" "$file"
        echo "backup: wrote $(basename "$file") ($(du -h "$file" | cut -f1))"
    else
        rm -f "$file.partial"
        echo "backup: pg_dump failed; keeping the older dumps" >&2
        return 1
    fi
    find "$BACKUP_DIR" -maxdepth 1 -name "${PGDATABASE}-*.dump" -mtime +"$BACKUP_KEEP_DAYS" -print -delete \
        | sed 's|^.*/|backup: removed |'
}

mkdir -p "$BACKUP_DIR"

if [ "${BACKUP_ONCE:-0}" = "1" ]; then
    dump
    exit
fi

dump || true
while true; do
    # Seconds until the next BACKUP_HOUR:00 UTC (a full day if that is now).
    now=$(date -u +%s)
    wait=$(( (BACKUP_HOUR * 3600 - now % 86400 + 86400) % 86400 ))
    [ "$wait" -eq 0 ] && wait=86400
    sleep "$wait"
    dump || true
done
