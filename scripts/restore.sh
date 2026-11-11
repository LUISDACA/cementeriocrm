#!/usr/bin/env bash
set -euo pipefail
: "${RESTORE_DATABASE_URL:?Indica una base de restauración nueva, distinta de producción}"
: "${1:?Indica la ruta del respaldo}"
if [ ! -f "$1" ] || [ ! -r "$1" ]; then
  printf 'El respaldo no existe o no se puede leer.\n' >&2
  exit 1
fi
if [ "${DATABASE_URL:-}" = "$RESTORE_DATABASE_URL" ]; then
  printf 'La base de restauración debe ser distinta de la base de origen.\n' >&2
  exit 1
fi
pg_restore --list "$1" >/dev/null
objects=$(PGDATABASE="$RESTORE_DATABASE_URL" psql --no-psqlrc --tuples-only --no-align --set=ON_ERROR_STOP=1 --file="$(dirname "$0")/restore_preflight.sql")
if [ "$objects" != "0" ]; then
  printf 'La base de destino contiene objetos. Usa una base nueva y vacía.\n' >&2
  exit 1
fi
# No usa --clean: no borra tablas de una base existente.
PGDATABASE="$RESTORE_DATABASE_URL" pg_restore --single-transaction --exit-on-error --no-owner --no-privileges "$1"
printf 'Restauración finalizada en la base indicada. Ejecuta las verificaciones de la guía.\n'
