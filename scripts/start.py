"""Arranque del contenedor, con migraciones y estáticos reproducibles."""

import os
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
os.chdir(root)
existing_python_path = os.environ.get("PYTHONPATH", "")
python_path_entries = existing_python_path.split(os.pathsep) if existing_python_path else []
if str(root) not in python_path_entries:
    os.environ["PYTHONPATH"] = os.pathsep.join([str(root), *python_path_entries])
for command in (
    [sys.executable, "manage.py", "check"],
    [sys.executable, "manage.py", "migrate", "--noinput"],
    [sys.executable, "manage.py", "collectstatic", "--noinput"],
):
    subprocess.run(command, check=True, cwd=root)

# Free-hosted academic demos cannot use an interactive shell for initial setup.
# Seed only when the academic settings profile explicitly enables this flag.
if os.environ.get("CEMETERY_AUTO_SEED_DEMO") == "1":
    from django.conf import settings

    if not getattr(settings, "ACADEMIC_MODE", False):
        raise RuntimeError("Demo seeding requires the academic settings profile.")
    from cemetery.models import Space

    if not Space.objects.exists():
        subprocess.run(
            [sys.executable, "manage.py", "seed_demo"], check=True, cwd=root
        )
    for command in ("expand_demo_map", "generate_monthly_invoices"):
        subprocess.run([sys.executable, "manage.py", command], check=True, cwd=root)

os.execvp(
    "gunicorn",
    [
        "gunicorn",
        "--chdir",
        str(root),
        "config.wsgi:application",
        "--bind",
        f"0.0.0.0:{os.environ.get('PORT', '8000')}",
        "--workers",
        "2",
        "--timeout",
        "60",
        "--access-logfile",
        "/dev/null",
        "--error-logfile",
        "-",
    ],
)
