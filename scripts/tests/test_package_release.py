from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from zipfile import ZipFile
from scripts.package_release import build_archive


class ReleasePackageTests(TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "README.md").write_text("Contenido de ejemplo")
        (self.root / ".env.example").write_text(
            "DJANGO_SECRET_KEY=replace-with-a-random-secret"
        )
        for relative in (
            ".env",
            "private.dump",
            ".venv/private.py",
            "node_modules/private.js",
            "cemetery/.env",
            "cemetery/__pycache__/private.pyc",
            "docs/.academic-mail/private.eml",
        ):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("SECRET-SYNTHETIC-DO-NOT-PACK")
        self.output = self.root / "dist/release.zip"

    def test_only_deliverable_files_are_included(self):
        count, digest = build_archive(self.root, self.output)
        self.assertEqual(count, 2)
        with ZipFile(self.output) as archive:
            self.assertSetEqual(
                set(archive.namelist()),
                {
                    "CementerioERP/README.md",
                    "CementerioERP/.env.example",
                    "CementerioERP/MANIFEST.sha256",
                },
            )
            for name in archive.namelist():
                self.assertNotIn(b"SECRET-SYNTHETIC-DO-NOT-PACK", archive.read(name))
        self.assertEqual(digest, sha256(self.output.read_bytes()).hexdigest())

    def test_manifest_matches_bytes_and_repeated_builds_are_identical(self):
        build_archive(self.root, self.output)
        original = self.output.read_bytes()
        with ZipFile(self.output) as archive:
            manifest = archive.read("CementerioERP/MANIFEST.sha256").decode()
            for line in manifest.splitlines():
                digest, name = line.split("  ", 1)
                self.assertEqual(
                    digest, sha256(archive.read(f"CementerioERP/{name}")).hexdigest()
                )
        build_archive(self.root, self.output)
        self.assertEqual(original, self.output.read_bytes())

    def test_symbolic_link_cannot_import_an_external_file(self):
        (self.root / "docs").mkdir(exist_ok=True)
        (self.root / "docs/external.md").symlink_to(self.root / ".env")
        with self.assertRaisesRegex(ValueError, "enlaces simbólicos"):
            build_archive(self.root, self.output)
        self.assertFalse(self.output.exists())
