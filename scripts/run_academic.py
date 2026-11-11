"""Prepara la demostración académica y sirve únicamente en localhost."""

import argparse
from getpass import getpass
import os
from pathlib import Path
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root))
    os.chdir(root)
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings_academic"
    import django

    django.setup()
    from django.conf import settings
    from django.core.management import call_command
    from django.core.management.base import CommandError
    from django.db import connection
    from django.db.utils import OperationalError
    from cemetery.models import Space, User

    if not settings.DEBUG:
        raise CommandError("La demostración requiere DJANGO_DEBUG=1 en .env.")
    call_command("check")
    deadline = time.monotonic() + 30
    waiting_message_shown = False
    while True:
        try:
            connection.ensure_connection()
            connection.close()
            break
        except OperationalError:
            if time.monotonic() >= deadline:
                raise
            if not waiting_message_shown:
                print("Esperando a que PostgreSQL termine de iniciar…", flush=True)
                waiting_message_shown = True
            time.sleep(1)
    call_command("migrate", interactive=False)
    call_command("collectstatic", interactive=False, verbosity=0)
    addresses = [
        f"{name}@example.test"
        for name in ("admin", "oficina", "tesoreria", "operaciones", "consulta")
    ]
    if (
        not Space.objects.exists()
        or User.objects.filter(email__in=addresses).count() < 5
    ):
        previous = os.environ.get("DEMO_ADMIN_PASSWORD")
        password = previous
        if not password:
            password = getpass(
                "Contraseña para los perfiles nuevos (mínimo 12 caracteres): "
            )
            if password != getpass("Repite la contraseña: "):
                raise CommandError("Las contraseñas no coinciden.")
        os.environ["DEMO_ADMIN_PASSWORD"] = password
        try:
            call_command("seed_demo")
        finally:
            if previous is None:
                os.environ.pop("DEMO_ADMIN_PASSWORD", None)
            else:
                os.environ["DEMO_ADMIN_PASSWORD"] = previous
    # Mantiene el plano amplio como parte del arranque normal de la demo.
    # El comando es idempotente y conserva cualquier sepultura existente.
    call_command("expand_demo_map")
    call_command("generate_monthly_invoices")
    call_command("collectstatic", interactive=False, verbosity=0)
    print("Perfil académico preparado. Las contraseñas existentes se conservan.")
    print("Cuentas: " + ", ".join(addresses))
    if not args.prepare_only:
        call_command("runserver", "127.0.0.1:8000", use_reloader=False)


if __name__ == "__main__":
    from django.core.exceptions import ValidationError
    from django.core.management.base import CommandError
    from django.db import OperationalError

    try:
        main()
    except OperationalError:
        print(
            "No se pudo conectar a PostgreSQL después de 30 segundos. Comprueba "
            "docker compose ps, los registros con docker compose logs db y que "
            "DATABASE_URL en .env coincida con la base configurada. "
            "La demostración no se ha iniciado.",
            file=sys.stderr,
        )
        sys.exit(1)
    except (CommandError, ValidationError) as error:
        print(f"No se pudo preparar la demostración: {error}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
