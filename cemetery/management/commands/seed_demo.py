from datetime import timedelta
from decimal import Decimal
import os
import uuid
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from cemetery import services
from cemetery.demo_data import synthetic_name
from cemetery.models import Block, Contract, Person, Responsible, Space, User, Zone


class Command(BaseCommand):
    help = "Carga datos sintéticos únicamente en desarrollo. No borra información existente."

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "La demostración solo puede cargarse con DJANGO_DEBUG=1."
            )
        password = os.environ.get("DEMO_ADMIN_PASSWORD")
        if not password or len(password) < 12:
            raise CommandError(
                "Define DEMO_ADMIN_PASSWORD con al menos 12 caracteres. No se imprimirá."
            )
        from django.contrib.auth.password_validation import validate_password

        for address, role, name in (
            ("admin", "ADMIN", "Administración"),
            ("oficina", "OFFICE", "Oficina"),
            ("tesoreria", "TREASURY", "Tesorería"),
            ("operaciones", "OPERATIONS", "Operaciones"),
            ("consulta", "VIEWER", "Consulta"),
        ):
            user, created = User.objects.get_or_create(
                email=f"{address}@example.test",
                defaults={"role": role, "first_name": name, "last_name": "Demo"},
            )
            if created:
                validate_password(password, user)
                user.set_password(password)
                user.save()
            if address == "admin":
                admin = user
        if Space.objects.exists():
            self.stdout.write(
                "Perfiles de demostración disponibles. Se conservan las cuentas y espacios existentes."
            )
            return
        zone = Zone.objects.create(name="Jardín de demostración")
        block_a = Block.objects.create(zone=zone, name="Bloque A")
        block_b = Block.objects.create(zone=zone, name="Bloque B")
        key = uuid.uuid4
        all_spaces = []
        for bi, block in enumerate((block_a, block_b)):
            for row in range(1, 5):
                for number in range(1, 7):
                    code = f"{'AB'[bi]}-{row}{number:02d}"
                    result = services.save_space(
                        admin,
                        key(),
                        {
                            "code": code,
                            "block": block,
                            "row": row,
                            "number": number,
                            "kind": "GRAVE",
                            "notes": "Dato sintético para demostración.",
                            "map_x": bi * 750 + (number - 1) * 105,
                            "map_y": (row - 1) * 90,
                        },
                    )
                    all_spaces.append(Space.objects.get(pk=result["id"]))
        today = timezone.localdate()
        for index in range(8):
            responsible = Responsible.objects.create(
                name=f"Responsable de ejemplo {index + 1}",
                identification=f"DEMO-R-{index + 1}",
                phone="0000000000",
                email=f"contacto{index + 1}@example.test",
            )
            first_name, last_name = synthetic_name(index)
            person = Person.objects.create(
                first_name=first_name,
                last_name=last_name,
                identification=f"DEMO-ERP-{index + 1:04d}",
                death_date=today - timedelta(days=60 + index),
                notes="Identidad ficticia de la demostración académica.",
            )
            services.link_responsible(
                admin,
                key(),
                {
                    "person": person,
                    "responsible": responsible,
                    "relationship": "Familiar de demostración",
                    "principal": True,
                },
            )
            cid = services.create_contract(
                admin,
                key(),
                {
                    "number": f"DEMO-C-{index + 1:03d}",
                    "space": all_spaces[index],
                    "responsible": responsible,
                    "amount": Decimal("1500000.00"),
                    "monthly_maintenance_fee": Decimal("25000.00"),
                    "starts_on": today - timedelta(days=90),
                    "ends_on": today + timedelta(days=15 + index * 30),
                    "terms": "Contrato sintético de demostración.",
                },
            )["id"]
            contract = Contract.objects.get(pk=cid)
            services.record_payment(
                admin,
                key(),
                {
                    "contract": contract,
                    "invoice": contract.invoices.get(kind="CONTRACT"),
                    "amount": Decimal("350000.00"),
                    "method": "TRANSFER",
                    "reference": f"DEMO-PAGO-{index + 1}",
                    "paid_at": timezone.now(),
                },
            )
            services.bury(
                admin,
                key(),
                {
                    "person": person,
                    "space": all_spaces[index],
                    "contract": contract,
                    "occurred_at": timezone.now() - timedelta(days=30),
                    "notes": "Registro histórico sintético de demostración.",
                },
            )
        for index in range(8, 12):
            responsible = Responsible.objects.create(
                name=f"Responsable reserva demo {index}",
                identification=f"DEMO-R-{index + 1}",
                phone="0000000000",
            )
            services.create_reservation(
                admin,
                key(),
                {
                    "space": all_spaces[index],
                    "responsible": responsible,
                    "expires_on": today + timedelta(days=15),
                    "amount": Decimal("100000.00"),
                    "method": "CASH",
                    "reference": f"DEMO-ANTICIPO-{index}",
                },
            )
        for index in (15, 16, 17):
            space = all_spaces[index]
            services.change_condition(
                admin,
                key(),
                space.pk,
                "MAINTENANCE" if index != 17 else "OUT_OF_SERVICE",
                "Condición sintética de demostración.",
                space.revision,
            )
        self.stdout.write(
            self.style.SUCCESS(
                "Demostración creada: 48 espacios, 8 ocupaciones, 4 reservas y cinco perfiles. Administración: admin@example.test."
            )
        )
