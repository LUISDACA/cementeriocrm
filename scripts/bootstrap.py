"""Instala las dependencias locales, migra y comprueba la aplicación."""

import os
from pathlib import Path
import secrets
import subprocess
from urllib.parse import quote
import venv

root = Path(__file__).resolve().parent.parent
os.chdir(root)
environment = root / ".venv"
if not environment.exists():
    venv.EnvBuilder(with_pip=True).create(environment)
python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
if not (root / ".env").exists():
    secret = secrets.token_urlsafe(48)
    content = (
        (root / ".env.example")
        .read_text()
        .replace("replace-with-a-random-secret", secret)
    )
    postgres_password = secrets.token_urlsafe(30)
    content = content.replace("change-me@127.0.0.1:55432", quote(postgres_password, safe="") + "@127.0.0.1:55432")
    content += "\nPOSTGRES_PASSWORD=" + postgres_password + "\n"
    fd = os.open(root / ".env", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as file:
        file.write(content)
    print("Se creó .env con secretos locales. Revisa DATABASE_URL antes de continuar.")
for command in (
    [
        str(python),
        "-m",
        "pip",
        "install",
        "-r",
        "requirements.txt",
        "-c",
        "requirements.lock",
    ],
    [str(python), "scripts/vendor_bootstrap.py"],
    [str(python), "manage.py", "check"],
    [str(python), "manage.py", "migrate", "--noinput"],
    [str(python), "manage.py", "collectstatic", "--noinput"],
):
    subprocess.run(command, check=True)
print("Base preparada. Crea tu cuenta: .venv/bin/python manage.py createsuperuser")
