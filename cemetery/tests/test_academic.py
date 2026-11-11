from io import StringIO
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import TestCase, override_settings
from cemetery.models import Space, User


@override_settings(
    ACADEMIC_MODE=True,
    EMAIL_BACKEND="cemetery.academic_mail.AcademicMailboxBackend",
)
class AcademicMailTests(TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        override = override_settings(ACADEMIC_MAIL_ROOT=self.directory.name)
        override.enable()
        self.addCleanup(override.disable)
        self.admin = User.objects.create_user(
            "admin@example.test", "Synthetic-initial-password-41!", role="ADMIN"
        )
        self.viewer = User.objects.create_user(
            "viewer@example.test", "Synthetic-initial-password-41!", role="VIEWER"
        )

    def test_local_delivery_uses_private_file(self):
        self.assertEqual(
            mail.send_mail("Asunto", "Contenido ficticio", None, [self.viewer.email]), 1
        )
        paths = list(Path(self.directory.name).glob("*.eml"))
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0].stat().st_mode & 0o777, 0o600)
        self.client.force_login(self.admin)
        response = self.client.get("/demostracion/correos/")
        self.assertContains(response, "Contenido ficticio")
        self.assertContains(response, "Asunto")

    @override_settings(ACADEMIC_MODE=False)
    def test_backend_refuses_normal_profile(self):
        with self.assertRaises(ImproperlyConfigured):
            mail.send_mail("Prueba", "Prueba", None, [self.viewer.email])
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get("/demostracion/correos/").status_code, 404)

    def test_mailbox_requires_administration(self):
        self.assertEqual(self.client.get("/demostracion/correos/").status_code, 302)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get("/demostracion/correos/").status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post("/demostracion/correos/").status_code, 405)

    def test_password_recovery_via_simulated_mailbox(self):
        response = self.client.post("/recuperar/", {"email": self.viewer.email})
        self.assertEqual(response.status_code, 302)
        self.client.force_login(self.admin)
        response = self.client.get("/demostracion/correos/")
        self.assertEqual(
            response.context["mailbox"][0]["subject"],
            "Recuperación de acceso a CementerioERP",
        )
        body = response.context["mailbox"][0]["body"]
        link = re.search(r"http://testserver(/recuperar/[^\s]+)", body).group(1)
        self.client.logout()
        response = self.client.get(link)
        self.assertEqual(response.status_code, 302)
        password = "  Synthetic-replacement-password-92!  "
        response = self.client.post(
            response.url, {"new_password1": password, "new_password2": password}
        )
        self.assertRedirects(response, "/recuperar/completado/")
        self.viewer.refresh_from_db()
        self.assertTrue(self.viewer.check_password(password))
        self.assertNotContains(
            self.client.get(link, follow=True), 'name="new_password1"'
        )
        response = self.client.post(
            "/ingresar/", {"username": self.viewer.email, "password": password}
        )
        self.assertEqual(response.status_code, 302)


@override_settings(DEBUG=True)
class AcademicSeedTests(TestCase):
    def test_five_profiles_and_synthetic_plan_are_repeatable(self):
        output = StringIO()
        with patch.dict(
            os.environ, {"DEMO_ADMIN_PASSWORD": "Synthetic-demo-password-792!"}
        ):
            call_command("seed_demo", stdout=output)
            initial = User.objects.get(email="admin@example.test").password
            call_command("seed_demo", stdout=output)
        self.assertEqual(Space.objects.count(), 48)
        self.assertSetEqual(
            set(User.objects.values_list("role", flat=True)),
            {"ADMIN", "OFFICE", "TREASURY", "OPERATIONS", "VIEWER"},
        )
        self.assertEqual(User.objects.get(email="admin@example.test").password, initial)
        self.assertNotIn("Synthetic-demo-password", output.getvalue())

    def test_academic_profile_retains_postgresql(self):
        from config import settings_academic

        self.assertEqual(
            settings_academic.DATABASES["default"]["ENGINE"],
            "django.db.backends.postgresql",
        )
        self.assertTrue(settings_academic.CEMETERY_MOVEMENTS_APPROVED)
