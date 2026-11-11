"""Comprueba DDL y restricciones en PostgreSQL aislado, sin usar sockets.

No sustituye las pruebas de ORM, migraciones de datos ni concurrencia entre
conexiones. Crea y elimina únicamente un clúster temporal nuevo.
"""

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pg-bin", help="Directorio de initdb y postgres")
    args = parser.parse_args()
    pg_config = shutil.which("pg_config")
    bindir = args.pg_bin or (
        subprocess.check_output([pg_config, "--bindir"], text=True).strip()
        if pg_config
        else None
    )
    if not bindir:
        parser.error("Instala las utilidades PostgreSQL o indica --pg-bin.")
    postgres = str(Path(bindir) / "postgres")
    initdb = str(Path(bindir) / "initdb")
    version_text = subprocess.check_output([postgres, "--version"], text=True)
    version = re.search(r"(\d+)\.(\d+)", version_text)
    if not version or int(version.group(1)) < 16:
        parser.error("Esta comprobación requiere PostgreSQL 16 o posterior.")
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()
    from django.db import connection
    from django.db.migrations.loader import MigrationLoader
    from django.db.migrations.state import ProjectState
    from psycopg.sql import quote

    if connection.vendor != "postgresql":
        parser.error("Usa la configuración PostgreSQL normal, no settings_verify.")
    # Colección de DDL sin abrir conexiones. Los literales los adapta psycopg.
    connection.pg_version = int(version.group(1)) * 10000 + int(version.group(2))
    connection.ops.compose_sql = lambda statement, params: (
        statement % tuple(quote(value) for value in params) if params else statement
    )
    loader = MigrationLoader(None, replace_migrations=False)
    plan = []
    for target in loader.graph.leaf_nodes("cemetery") + loader.graph.leaf_nodes(
        "sessions"
    ):
        for node in loader.graph.forwards_plan(target):
            if node not in plan:
                plan.append(node)
    state = ProjectState()
    with connection.schema_editor(collect_sql=True, atomic=False) as editor:
        for key in plan:
            state = loader.graph.nodes[key].apply(state, editor, collect_sql=True)
    statements = [s for s in editor.collected_sql if not s.lstrip().startswith("--")]
    preflight = (ROOT / "scripts/restore_preflight.sql").read_text().strip().rstrip(";")
    before = f"DO $$ BEGIN IF ({preflight}) <> 0 THEN RAISE EXCEPTION 'La base inicial no está vacía'; END IF; END $$;"
    after = f"DO $$ BEGIN IF ({preflight}) = 0 THEN RAISE EXCEPTION 'No se detectó el esquema existente'; END IF; END $$;"
    sql = before.replace("\n", " ") + "\n"
    sql += "\n".join(s.replace("\n", " ") for s in statements) + "\n"
    sql += after.replace("\n", " ") + "\n"
    sql += (ROOT / "cemetery/tests/postgres_schema.sql").read_text()
    with tempfile.TemporaryDirectory(prefix="cementerio-schema-") as temporary:
        cluster = str(Path(temporary) / "db")
        initialized = subprocess.run(
            [
                initdb,
                "-D",
                cluster,
                "-A",
                "trust",
                "-U",
                "cementerio",
                "--no-locale",
                "-E",
                "UTF8",
            ],
            capture_output=True,
            text=True,
        )
        if initialized.returncode:
            sys.stderr.write(initialized.stderr)
            return 1
        result = subprocess.run(
            [postgres, "--single", "-D", cluster, "postgres"],
            input=sql,
            capture_output=True,
            text=True,
        )
        output = result.stdout + result.stderr
        if (
            result.returncode
            or re.search(r"\b(?:ERROR|FATAL):", output)
            or "postgres_schema_and_constraints_ok" not in output
        ):
            sys.stderr.write(output)
            return 1
    print(
        f"PostgreSQL {version.group(0)}: {len(statements)} sentencias DDL válidas; ocupación, reservas, correo, montos, fechas e inmutabilidad comprobados."
    )
    print(
        "Pendiente independiente: ORM y concurrencia con conexiones PostgreSQL reales."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
