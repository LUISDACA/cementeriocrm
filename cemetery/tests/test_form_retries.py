from decimal import Decimal
import uuid
from django.test import TestCase
from django.utils import timezone
from cemetery.models import (
    Audit,
    Command,
    Contract,
    Event,
    Payment,
    Responsible,
    Space,
    User,
)
from .base import DomainFixtures


class FormRetryTests(DomainFixtures, TestCase):
    def setUp(self):
        self.create_domain_fixtures()
        self.client.force_login(self.admin)

    def contact_data(self, **changes):
        return {
            "command_key": str(uuid.uuid4()),
            "name": "Contacto del reintento",
            "identification": "RETRY-R",
            "phone": "3001234567",
            "email": "",
            "address": "",
            **changes,
        }

    def assert_replay(self, url, data):
        first = self.client.post(url, data)
        self.assertEqual(first.status_code, 302, getattr(first, "context", None))
        second = self.client.post(url, data)
        errors = second.context["form"].errors if second.context else None
        self.assertEqual(second.status_code, 302, str(errors))
        self.assertEqual(first.url, second.url)
        self.assertEqual(Command.objects.filter(key=data["command_key"]).count(), 1)

    def test_contact_creation_retry_recovers_original_result(self):
        self.assert_replay("/gestion/responsables/nuevo/", self.contact_data())
        self.assertEqual(
            Responsible.objects.filter(identification="RETRY-R").count(), 1
        )
        self.assertEqual(Audit.objects.filter(action="responsible.create").count(), 1)

    def test_space_creation_retry_does_not_repeat_event(self):
        data = {
            "command_key": str(uuid.uuid4()),
            "code": "RETRY-SPACE",
            "block": self.block.pk,
            "row": 2,
            "number": 1,
            "kind": "GRAVE",
            "map_x": 200,
            "map_y": 100,
            "notes": "Demo",
        }
        self.assert_replay("/gestion/sepulturas/nuevo/", data)
        space = Space.objects.get(code="RETRY-SPACE")
        self.assertEqual(
            Event.objects.filter(space=space, kind="SPACE_CREATED").count(), 1
        )

    def test_contract_creation_retry_returns_original_contract(self):
        data = {
            "command_key": str(uuid.uuid4()),
            "number": "RETRY-C",
            "space": self.destination.pk,
            "responsible": self.responsible.pk,
            "amount": "200.00",
            "starts_on": str(self.today),
            "ends_on": str(self.today),
            "terms": "Condiciones ficticias",
        }
        self.assert_replay("/gestion/contratos/nuevo/", data)
        self.assertEqual(Contract.objects.filter(number="RETRY-C").count(), 1)

    def test_user_creation_retry_does_not_rehash_or_duplicate_account(self):
        data = {
            "command_key": str(uuid.uuid4()),
            "email": "retry@example.test",
            "first_name": "Cuenta",
            "last_name": "Demo",
            "role": "VIEWER",
            "is_active": "on",
            "password": "Synthetic-retry-password-741!",
        }
        self.assert_replay("/gestion/usuarios/nuevo/", data)
        self.assertEqual(User.objects.filter(email="retry@example.test").count(), 1)
        self.assertEqual(Audit.objects.filter(action="user.create").count(), 1)

    def test_new_operation_with_duplicate_identity_is_still_rejected(self):
        data = self.contact_data()
        self.assertEqual(
            self.client.post("/gestion/responsables/nuevo/", data).status_code, 302
        )
        data["command_key"] = str(uuid.uuid4())
        response = self.client.post("/gestion/responsables/nuevo/", data)
        self.assertEqual(response.status_code, 200)
        self.assertIn("identification", response.context["form"].errors)
        self.assertEqual(
            Responsible.objects.filter(identification="RETRY-R").count(), 1
        )
        self.assertFalse(Command.objects.filter(key=data["command_key"]).exists())

    def test_reusing_key_with_changed_content_is_rejected(self):
        data = self.contact_data()
        self.client.post("/gestion/responsables/nuevo/", data)
        data["phone"] = "3009999999"
        response = self.client.post("/gestion/responsables/nuevo/", data)
        self.assertContains(response, "Esta clave ya pertenece a otra operación")
        self.assertEqual(
            Responsible.objects.get(identification="RETRY-R").phone, "3001234567"
        )

    def test_operation_result_is_not_shared_with_another_actor(self):
        data = self.contact_data()
        self.client.post("/gestion/responsables/nuevo/", data)
        self.client.force_login(self.office)
        response = self.client.post("/gestion/responsables/nuevo/", data)
        self.assertContains(response, "Esta clave ya pertenece a otra operación")

    def test_failed_payment_preserves_fields_and_can_be_corrected(self):
        data = {
            "command_key": str(uuid.uuid4()),
            "contract": self.contract.pk,
            "amount": "1001.00",
            "method": "TRANSFER",
            "reference": "RETRY-PAGO",
            "paid_at": timezone.localtime().strftime("%Y-%m-%dT%H:%M:%S"),
        }
        response = self.client.post("/gestion/pagos/nuevo/", data)
        self.assertContains(response, "el pago no puede superar el saldo")
        self.assertEqual(response.context["form"]["reference"].value(), "RETRY-PAGO")
        self.assertEqual(
            response.context["form"]["command_key"].value(), data["command_key"]
        )
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(Command.objects.filter(key=data["command_key"]).exists())
        data["amount"] = "500.00"
        self.assert_replay("/gestion/pagos/nuevo/", data)
        self.assertEqual(self.contract.balance, Decimal("500.00"))
