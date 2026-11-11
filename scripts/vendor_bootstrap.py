"""Instala CSS y source map fijados; verifica integridad antes de escribir."""

import base64
import hashlib
from pathlib import Path
from urllib.request import urlopen

VERSION = "5.3.8"
FILES = {
    "bootstrap.min.css": "sRIl4kxILFvY47J16cr9ZwB07vP4J8+LH7qKQnuqkuIAvNWLzeN8tE5YBujZqJLB",
    "bootstrap.min.css.map": "IGzRD4jINKs2iSsOq2MORajTvAmIsb5zZ1DXovbJoJdvmiCcdj9KLJocCj0TS60/",
}


def verified(content, expected):
    return base64.b64encode(hashlib.sha384(content).digest()).decode() == expected


def main():
    directory = Path(__file__).resolve().parent.parent / "static/vendor"
    directory.mkdir(parents=True, exist_ok=True)
    for name, expected in FILES.items():
        target = directory / name
        if target.exists() and verified(target.read_bytes(), expected):
            print(f"Bootstrap {VERSION}: {name} verificado.")
            continue
        url = f"https://cdn.jsdelivr.net/npm/bootstrap@{VERSION}/dist/css/{name}"
        with urlopen(url, timeout=30) as response:
            content = response.read(2_000_000)
        if not verified(content, expected):
            raise RuntimeError(
                f"La integridad de {name} no coincide con la versión fijada."
            )
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_bytes(content)
        temporary.replace(target)
        print(f"Bootstrap {VERSION}: {name} instalado y verificado.")


if __name__ == "__main__":
    main()
