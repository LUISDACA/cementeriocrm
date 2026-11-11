"""Arranque del contenedor, con migraciones y estáticos reproducibles."""

import os
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
os.chdir(root)
for command in (
    [sys.executable, "manage.py", "check"],
    [sys.executable, "manage.py", "migrate", "--noinput"],
    [sys.executable, "manage.py", "collectstatic", "--noinput"],
):
    subprocess.run(command, check=True)
os.execvp(
    "gunicorn",
    [
        "gunicorn",
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
