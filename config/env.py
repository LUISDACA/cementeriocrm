"""Carga .env local como datos; nunca lo ejecuta como código shell."""

import os
from pathlib import Path
import shlex


def load_env(path: Path):
    if not path.exists():
        return
    for number, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Línea {number} inválida en .env.")
        name, value = line.split("=", 1)
        name = name.strip()
        if not name or not name.replace("_", "").isalnum() or name[0].isdigit():
            raise ValueError(f"Nombre de variable inválido en .env, línea {number}.")
        parsed = shlex.split(value.strip(), comments=True)
        os.environ.setdefault(name, " ".join(parsed))
