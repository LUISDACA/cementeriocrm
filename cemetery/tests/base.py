from datetime import timedelta
from decimal import Decimal
import uuid
from django.utils import timezone
from cemetery.models import (
    Block,
    Contract,
    Person,
    PersonResponsible,
    Responsible,
    Space,
    User,
    Zone,
)


class DomainFixtures:
    def create_domain_fixtures(self):
        self.today = timezone.localdate()
        self.admin = User.objects.create_user(
            "admin@example.test",
            "Example-password-2026!",
            role="ADMIN",
            first_name="Admin",
        )
        self.office = User.objects.create_user(
            "office@example.test", "Example-password-2026!", role="OFFICE"
        )
        self.treasury = User.objects.create_user(
            "treasury@example.test", "Example-password-2026!", role="TREASURY"
        )
        self.operator = User.objects.create_user(
            "operator@example.test", "Example-password-2026!", role="OPERATIONS"
        )
        self.viewer = User.objects.create_user(
            "viewer@example.test", "Example-password-2026!", role="VIEWER"
        )
        self.zone = Zone.objects.create(name="Zona prueba")
        self.block = Block.objects.create(zone=self.zone, name="Bloque prueba")
        self.space = Space.objects.create(
            code="A-001", block=self.block, row=1, number=1
        )
        self.destination = Space.objects.create(
            code="A-002", block=self.block, row=1, number=2, map_x=120
        )
        self.person = Person.objects.create(
            first_name="María",
            last_name="Prueba",
            death_date=self.today - timedelta(days=60),
        )
        self.other_person = Person.objects.create(
            first_name="María",
            last_name="Prueba",
            death_date=self.today - timedelta(days=40),
        )
        self.responsible = Responsible.objects.create(
            name="Contacto de prueba", identification="R001", phone="3000000000"
        )
        self.other_responsible = Responsible.objects.create(
            name="Otro contacto", identification="R002", phone="3000000001"
        )
        PersonResponsible.objects.create(
            person=self.person,
            responsible=self.responsible,
            relationship="Familiar",
            principal=True,
        )
        self.contract = Contract.objects.create(
            number="C001",
            space=self.space,
            responsible=self.responsible,
            amount=Decimal("1000.00"),
            starts_on=self.today - timedelta(days=90),
            ends_on=self.today + timedelta(days=90),
            terms="Condiciones de prueba",
        )

    def key(self):
        return uuid.uuid4()

    def burial_data(self, **overrides):
        return {
            "person": self.person,
            "space": self.space,
            "contract": self.contract,
            "occurred_at": timezone.now() - timedelta(days=10),
            "notes": "Responsable operativo de prueba.",
            **overrides,
        }

    def payment_data(self, **overrides):
        return {
            "contract": self.contract,
            "amount": Decimal("300.00"),
            "method": "CASH",
            "reference": "RECIBO-001",
            "paid_at": timezone.now(),
            **overrides,
        }

    def reservation_data(self, **overrides):
        return {
            "space": self.destination,
            "responsible": self.responsible,
            "expires_on": self.today + timedelta(days=7),
            "amount": Decimal("100.00"),
            "method": "TRANSFER",
            "reference": "ANTICIPO-001",
            **overrides,
        }
