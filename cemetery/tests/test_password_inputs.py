import uuid
from django.test import TestCase
from cemetery.models import User


class PasswordInputTests(TestCase):
    password = "  Synthetic-password-with-spaces-208!  "

    def setUp(self):
        self.admin = User.objects.create_user(
            "admin@example.test", self.password, role="ADMIN"
        )

    def test_login_preserves_leading_and_trailing_password_spaces(self):
        response = self.client.post(
            "/ingresar/", {"username": self.admin.email, "password": self.password}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.admin.pk)

    def test_user_form_does_not_silently_change_password(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            "/gestion/usuarios/nuevo/",
            {
                "command_key": str(uuid.uuid4()),
                "email": "new@example.test",
                "first_name": "Ejemplo",
                "last_name": "",
                "role": "VIEWER",
                "is_active": "on",
                "password": self.password,
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email="new@example.test")
        self.assertTrue(user.check_password(self.password))
        self.assertFalse(user.check_password(self.password.strip()))
