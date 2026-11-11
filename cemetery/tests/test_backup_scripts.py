"""Pruebas del control de errores del shell; no simulan una restauración real."""

import os
from pathlib import Path
import subprocess
import tempfile
from django.conf import settings
from django.test import SimpleTestCase


class BackupScriptControlTests(SimpleTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="cementerio-backup-test-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        binaries = self.root / "bin"
        binaries.mkdir()
        self.log = self.root / "restore-args.txt"
        self.environment = {
            **os.environ,
            "PATH": str(binaries) + os.pathsep + os.environ["PATH"],
            "DATABASE_URL": "postgresql://synthetic:secret@source.invalid/db",
            "RESTORE_DATABASE_URL": "postgresql://synthetic:secret@restore.invalid/db",
            "TEST_RESTORE_LOG": str(self.log),
            "TEST_DESTINATION_OBJECTS": "0",
        }
        for name, content in {
            "pg_dump": '#!/bin/bash\nfor arg in "$@"; do case "$arg" in --file=*) file=${arg#--file=};; esac; done\nprintf "synthetic dump" > "$file"\nexit "${TEST_DUMP_FAIL:-0}"\n',
            "pg_restore": '#!/bin/bash\nif [ "$1" = "--list" ]; then exit "${TEST_LIST_FAIL:-0}"; fi\nprintf "%s\\n" "$@" > "$TEST_RESTORE_LOG"\nexit "${TEST_RESTORE_FAIL:-0}"\n',
            "psql": '#!/bin/bash\nprintf "%s\\n" "$TEST_DESTINATION_OBJECTS"\n',
        }.items():
            path = binaries / name
            path.write_text(content)
            path.chmod(0o700)
        self.archive = self.root / "input.dump"
        self.archive.write_text("synthetic archive")

    def execute(self, name, argument, **environment):
        return subprocess.run(
            ["bash", str(settings.BASE_DIR / "scripts" / name), str(argument)],
            env={**self.environment, **environment},
            capture_output=True,
            text=True,
        )

    def test_backup_failure_does_not_publish_incomplete_file(self):
        target = self.root / "failed backups"
        result = self.execute("backup.sh", target, TEST_DUMP_FAIL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(target.iterdir()), [])

    def test_archive_validation_failure_cleans_temporary_file(self):
        target = self.root / "invalid backups"
        result = self.execute("backup.sh", target, TEST_LIST_FAIL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(target.iterdir()), [])

    def test_two_backups_do_not_overwrite_each_other(self):
        target = self.root / "valid backups"
        for _ in range(2):
            self.assertEqual(self.execute("backup.sh", target).returncode, 0)
        self.assertEqual(len(list(target.glob("*.dump"))), 2)
        self.assertFalse(list(target.glob("*.partial")))

    def test_restore_refuses_nonempty_destination(self):
        result = self.execute("restore.sh", self.archive, TEST_DESTINATION_OBJECTS="2")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("contiene objetos", result.stderr)
        self.assertFalse(self.log.exists())

    def test_restore_uses_single_transaction_without_exposing_credentials(self):
        result = self.execute("restore.sh", self.archive)
        self.assertEqual(result.returncode, 0)
        args = self.log.read_text()
        self.assertIn("--single-transaction", args)
        self.assertNotIn("--clean", args)
        self.assertNotIn("secret", args)

    def test_failed_restore_does_not_report_success(self):
        result = self.execute("restore.sh", self.archive, TEST_RESTORE_FAIL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Restauración finalizada", result.stdout)

    def test_restore_refuses_source_database(self):
        result = self.execute(
            "restore.sh",
            self.archive,
            RESTORE_DATABASE_URL=self.environment["DATABASE_URL"],
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())
