"""Construye una entrega local del código y verifica su manifiesto SHA-256."""

import argparse
from hashlib import sha256
from pathlib import Path
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

TOP_FILES = (
    ".env.example",
    ".gitignore",
    ".dockerignore",
    "Dockerfile",
    "Makefile",
    "README.md",
    "manage.py",
    "requirements.txt",
    "requirements.lock",
    "package.json",
    "package-lock.json",
    "compose.yaml",
    "compose.academic.yaml",
)
SOURCE_DIRS = (
    ".github",
    "cemetery",
    "config",
    "docs",
    "scripts",
    "static",
    "templates",
    "tests-js",
)
EXTENSIONS = {
    ".py",
    ".md",
    ".html",
    ".txt",
    ".css",
    ".js",
    ".cjs",
    ".json",
    ".map",
    ".png",
    ".svg",
    ".sql",
    ".sh",
    ".yml",
    ".yaml",
}


def release_files(root):
    root = Path(root)
    candidates = [root / name for name in TOP_FILES if (root / name).exists()]
    for name in SOURCE_DIRS:
        directory = root / name
        if directory.is_symlink():
            raise ValueError(f"No se admiten enlaces simbólicos: {name}")
        if not directory.exists():
            continue
        candidates.extend(directory.rglob("*"))
    files = {}
    for path in sorted(candidates):
        relative = path.relative_to(root)
        if any(
            part
            in {
                "__pycache__",
                "node_modules",
                ".venv",
                ".academic-mail",
                "backups",
                "media",
                "dist",
            }
            for part in relative.parts
        ):
            continue
        if path.is_symlink():
            raise ValueError(f"No se admiten enlaces simbólicos: {relative}")
        if not path.is_file() or (
            relative.as_posix() not in TOP_FILES and path.suffix not in EXTENSIONS
        ):
            continue
        if path.name.startswith(".env") and path.name != ".env.example":
            continue
        files[relative.as_posix()] = path.read_bytes()
    if not files:
        raise ValueError("No hay archivos de entrega.")
    return files


def build_archive(root, output):
    files = release_files(root)
    manifest = "".join(
        f"{sha256(content).hexdigest()}  {name}\n" for name, content in files.items()
    )
    files["MANIFEST.sha256"] = manifest.encode()
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=output.parent, suffix=".partial", delete=False
    ) as stream:
        temporary = Path(stream.name)
    try:
        with ZipFile(
            temporary, "w", compression=ZIP_DEFLATED, compresslevel=9
        ) as archive:
            for name, content in sorted(files.items()):
                entry = ZipInfo(
                    f"CementerioERP/{name}", date_time=(1980, 1, 1, 0, 0, 0)
                )
                entry.compress_type = ZIP_DEFLATED
                entry.create_system = 3
                entry.external_attr = 0o100644 << 16
                archive.writestr(entry, content)
        with ZipFile(temporary) as archive:
            if archive.testzip() is not None:
                raise ValueError("El ZIP no superó su comprobación de integridad.")
            for name, content in files.items():
                if archive.read(f"CementerioERP/{name}") != content:
                    raise ValueError(f"El contenido no coincide: {name}")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    digest = sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{digest}  {output.name}\n"
    )
    return len(files) - 1, digest


def main():
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=root / "dist/CementerioERP-academico.zip"
    )
    args = parser.parse_args()
    count, digest = build_archive(root, args.output)
    print(f"Entrega local creada: {args.output} ({count} archivos y manifiesto)")
    print(f"SHA-256: {digest}")


if __name__ == "__main__":
    main()
