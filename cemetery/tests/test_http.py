from django.test import Client, TestCase, override_settings
from cemetery.models import (
    Contract,
    Movement,
    Occupancy,
    Person,
    PersonResponsible,
    Reservation,
    Responsible,
    User,
)
from .base import DomainFixtures


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage",
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    },
    PASSWORD_HASHERS=["django.contrib.auth.hashers.PBKDF2PasswordHasher"],
)
class HttpTests(DomainFixtures, TestCase):
    def setUp(self):
        self.create_domain_fixtures()

    def test_all_authenticated_pages_render(self):
        self.client.force_login(self.admin)
        urls = [
            "/",
            "/mapa/",
            f"/sepultura/{self.space.pk}/",
            f"/persona/{self.person.pk}/",
            f"/contrato/{self.contract.pk}/",
            "/inhumacion/",
            "/vincular-responsable/",
        ]
        for kind in (
            "sepulturas",
            "personas",
            "responsables",
            "contratos",
            "reservas",
            "pagos",
            "movimientos",
            "usuarios",
            "zonas",
            "bloques",
            "auditoria",
        ):
            urls.append(f"/gestion/{kind}/")
            if kind != "auditoria":
                urls.append(f"/gestion/{kind}/nuevo/")
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_anonymous_requires_login(self):
        for url in ("/", "/mapa/datos/", "/gestion/usuarios/", "/inhumacion/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)

    def test_viewer_cannot_read_personal_financial_or_user_records(self):
        self.client.force_login(self.viewer)
        for url in (
            "/gestion/personas/",
            "/gestion/responsables/",
            "/gestion/contratos/",
            "/gestion/pagos/",
            "/gestion/usuarios/",
            "/gestion/auditoria/",
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_viewer_cannot_post_directly_to_operations(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.post("/inhumacion/", {}).status_code, 403)
        self.assertEqual(
            self.client.post("/gestion/usuarios/nuevo/", {}).status_code, 403
        )

    def test_csrf_is_enforced(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        response = client.post("/gestion/sepulturas/nuevo/", {"code": "ATTEMPT"})
        self.assertEqual(response.status_code, 403)

    def test_map_does_not_expose_personal_data_to_viewer(self):
        self.client.force_login(self.viewer)
        response = self.client.get("/mapa/datos/?person=María")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["people"], [])
        self.assertNotContains(response, self.responsible.identification)

    def test_map_distinguishes_homonyms_without_current_location(self):
        self.client.force_login(self.admin)
        response = self.client.get("/mapa/datos/?person=María")
        people = response.json()["people"]
        self.assertEqual(len(people), 2)
        self.assertTrue(all(person["space_id"] is None for person in people))

    def test_pagination_preserves_search_filters(self):
        self.client.force_login(self.admin)
        response = self.client.get("/gestion/sepulturas/?q=A&status=AVAILABLE&page=2")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="A"')

    def test_login_accepts_normalized_email(self):
        response = self.client.post(
            "/ingresar/",
            {"username": "ADMIN@EXAMPLE.TEST", "password": "Example-password-2026!"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_login_errors_do_not_reveal_account_existence(self):
        existing = self.client.post(
            "/ingresar/", {"username": "admin@example.test", "password": "wrong"}
        )
        missing = self.client.post(
            "/ingresar/", {"username": "missing@example.test", "password": "wrong"}
        )
        message = "No fue posible iniciar sesión. Comprueba tus credenciales."
        self.assertContains(existing, message)
        self.assertContains(missing, message)

    def test_login_throttles_repeated_attempts(self):
        for _ in range(5):
            self.client.post(
                "/ingresar/", {"username": "admin@example.test", "password": "wrong"}
            )
        response = self.client.post(
            "/ingresar/",
            {"username": "admin@example.test", "password": "Example-password-2026!"},
        )
        self.assertContains(response, "Espera 15 minutos")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_disabled_user_loses_access_on_next_request(self):
        self.client.force_login(self.office)
        User.objects.filter(pk=self.office.pk).update(is_active=False)
        self.assertEqual(self.client.get("/").status_code, 302)

    def test_role_change_applies_without_relogin(self):
        self.client.force_login(self.office)
        self.assertEqual(self.client.get("/gestion/responsables/").status_code, 200)
        User.objects.filter(pk=self.office.pk).update(role="VIEWER")
        self.assertEqual(self.client.get("/gestion/responsables/").status_code, 403)

    def test_logout_requires_post_and_invalidates_session(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get("/salir/").status_code, 405)
        self.assertEqual(self.client.post("/salir/").status_code, 302)
        self.assertEqual(self.client.get("/").status_code, 302)

    def test_login_prevents_external_redirect(self):
        response = self.client.post(
            "/ingresar/",
            {
                "username": "admin@example.test",
                "password": "Example-password-2026!",
                "next": "https://outside.invalid/",
            },
        )
        self.assertEqual(response["Location"], "/")

    def test_clear_empty_state_and_login_render(self):
        self.assertEqual(self.client.get("/ingresar/").status_code, 200)
        self.client.force_login(self.admin)
        self.assertContains(
            self.client.get("/gestion/sepulturas/?q=missing"),
            "No hay registros para mostrar",
        )

    def test_invalid_history_dates_are_reported_without_server_error(self):
        self.client.force_login(self.admin)
        response = self.client.get(f"/sepultura/{self.space.pk}/?from=2026-02-30")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Revisa las fechas")

    def test_absolute_session_expiry(self):
        from django.utils import timezone

        self.client.force_login(self.admin)
        session = self.client.session
        session["issued_at"] = int(timezone.now().timestamp()) - 8 * 60 * 60 - 1
        session.save()
        self.assertEqual(self.client.get("/").status_code, 302)

    def test_authenticated_responses_are_not_cached(self):
        self.client.force_login(self.admin)
        self.assertIn("no-store", self.client.get("/")["Cache-Control"])

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_recovery_rate_limit_has_generic_response(self):
        from django.core import mail

        for _ in range(4):
            response = self.client.post("/recuperar/", {"email": self.admin.email})
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response["Location"], "/recuperar/enviado/")
        self.assertEqual(len(mail.outbox), 3)

    @override_settings(CEMETERY_MOVEMENTS_APPROVED=True)
    def test_full_workflow_through_real_forms(self):
        from decimal import Decimal
        from django.utils import timezone
        import uuid

        self.client.force_login(self.admin)

        def submit(url, **data):
            response = self.client.post(url, {"command_key": str(uuid.uuid4()), **data})
            errors = (
                response.context["form"].errors
                if response.context and "form" in response.context
                else None
            )
            self.assertEqual(response.status_code, 302, str(errors))
            return response

        submit(
            "/gestion/responsables/nuevo/",
            name="Contacto del recorrido",
            identification="FLOW-R",
            phone="3001234567",
            email="",
            address="",
        )
        responsible = Responsible.objects.get(identification="FLOW-R")
        submit(
            "/gestion/personas/nuevo/",
            first_name="Persona",
            last_name="Recorrido completo",
            identification="FLOW-P",
            birth_date="",
            death_date=str(self.today),
            notes="Datos sintéticos",
        )
        person = Person.objects.get(identification="FLOW-P")
        submit(
            "/vincular-responsable/",
            person=person.pk,
            responsible=responsible.pk,
            relationship="Familiar",
            principal="on",
        )
        self.assertTrue(PersonResponsible.objects.get(person=person).principal)
        submit(
            "/gestion/reservas/nuevo/",
            space=self.destination.pk,
            responsible=responsible.pk,
            expires_on=str(self.today),
            amount="0.01",
            method="CASH",
            reference="FLOW-ANTICIPO",
        )
        reservation = Reservation.objects.get(space=self.destination)
        submit(
            "/gestion/contratos/nuevo/",
            number="FLOW-C",
            space=self.destination.pk,
            responsible=responsible.pk,
            amount="100.00",
            starts_on=str(self.today),
            ends_on=str(self.today),
            terms="Condiciones sintéticas",
        )
        contract = Contract.objects.get(number="FLOW-C")
        self.assertEqual(contract.paid, Decimal("0.01"))
        reservation.refresh_from_db()
        self.assertEqual(reservation.state, "CONSUMED")
        timestamp = timezone.localtime().strftime("%Y-%m-%dT%H:%M:%S")
        submit(
            "/inhumacion/",
            person=person.pk,
            space=self.destination.pk,
            contract=contract.pk,
            occurred_at=timestamp,
            notes="Operación sintética",
        )
        occupancy = Occupancy.objects.get(person=person, ended_at__isnull=True)
        submit(
            "/gestion/pagos/nuevo/",
            contract=contract.pk,
            amount="99.99",
            method="TRANSFER",
            reference="FLOW-PAGO",
            paid_at=timestamp,
        )
        self.assertEqual(contract.balance, Decimal("0.00"))
        self.assertContains(
            self.client.get(f"/sepultura/{self.destination.pk}/"), str(person)
        )
        map_data = self.client.get("/mapa/datos/").json()
        self.assertEqual(
            next(
                s["status"]
                for s in map_data["spaces"]
                if s["id"] == self.destination.pk
            ),
            "OCCUPIED",
        )
        submit(
            "/gestion/movimientos/nuevo/",
            occupancy=occupancy.pk,
            kind="EXHUMATION",
            destination="",
            destination_contract="",
            external_destination="Destino validado",
            reason="Solicitud sintética",
            proposed_on=str(self.today),
        )
        movement = Movement.objects.get(occupancy=occupancy)
        submit(
            f"/accion/movimientos/{movement.pk}/authorize/",
            document_reference="FLOW-DOC",
        )
        submit(f"/accion/movimientos/{movement.pk}/execute/")
        occupancy.refresh_from_db()
        self.assertIsNotNone(occupancy.ended_at)
        submit(
            f"/accion/contratos/{contract.pk}/close/",
            reason="Operación completada y saldo liquidado",
        )
        contract.refresh_from_db()
        self.assertEqual(contract.state, "CLOSED")

    def test_recovery_pages_render_with_an_existing_session(self):
        self.client.force_login(self.admin)
        for url, text in [
            ("/recuperar/", "Restablecer contraseña"),
            ("/recuperar/enviado/", "Revisa tu correo"),
            ("/recuperar/completado/", "Contraseña actualizada"),
        ]:
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), text)
