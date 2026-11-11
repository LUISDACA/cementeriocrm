#!/usr/bin/env bash
set -euo pipefail
umask 077
: "${DATABASE_URL:?Exporta DATABASE_URL para respaldar la base}"
backup_dir="${1:-backups}"
mkdir -p "$backup_dir"
backup_temp=$(mktemp "$backup_dir/.cementerio-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX.partial")
trap 'rm -f -- "$backup_temp"' EXIT
backup_name=${backup_temp##*/}
backup_name=${backup_name#.}
backup_path="$backup_dir/${backup_name%.partial}.dump"
PGDATABASE="$DATABASE_URL" pg_dump --format=custom --file="$backup_temp"
pg_restore --list "$backup_temp" >/dev/null
mv -- "$backup_temp" "$backup_path"
printf 'Respaldo creado: %s\n' "$backup_path"
