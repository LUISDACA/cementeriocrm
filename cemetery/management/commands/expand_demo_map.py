"""Añade un plano amplio y registros con identidades claramente ficticias."""

from datetime import datetime, time, timedelta
from decimal import Decimal
import uuid

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from cemetery import services
from cemetery.demo_data import synthetic_name
from cemetery.models import Block, Contract, Person, Responsible, Space, User, Zone


class Command(BaseCommand):
    help = "Añade seis bloques y cientos de registros sintéticos; no modifica registros existentes."

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG or not getattr(settings, "ACADEMIC_MODE", False):
            raise CommandError(
                "El plano ampliado solo está disponible en el perfil académico."
            )
        admin = User.objects.filter(
            email="admin@example.test", role="ADMIN", is_active=True
        ).first()
        if admin is None:
            raise CommandError("Carga primero la demostración con `make demo`.")

        key = uuid.uuid4
        for index, old_document in enumerate(
            f"DEMO-P-{number}" for number in range(1, 9)
        ):
            old_person = Person.objects.filter(
                identification=old_document,
                first_name="Persona de ejemplo",
                last_name="Registro sintético",
            ).first()
            if old_person is not None:
                first, last = synthetic_name(index)
                services.save_person(
                    admin,
                    key(),
                    {
                        "first_name": first,
                        "last_name": last,
                        "identification": f"DEMO-ERP-{index + 1:04d}",
                        "notes": "Identidad ficticia de la demostración académica.",
                    },
                    pk=old_person.pk,
                )
        zone, _ = Zone.objects.get_or_create(name="Jardín de demostración")
        blocks = []
        for letter in "CDEFGH":
            block, _ = Block.objects.get_or_create(zone=zone, name=f"Bloque {letter}")
            blocks.append(block)

        today = timezone.localdate()
        created = 0
        skipped = 0
        occupied = 0
        reserved = 0
        maintenance = 0
        out_of_service = 0
        for block_index, block in enumerate(blocks):
            group_x = 1500 + (block_index % 3) * 1000
            group_y = (block_index // 3) * 1000
            for row in range(1, 9):
                for number in range(1, 9):
                    index = block_index * 64 + (row - 1) * 8 + number - 1
                    code = f"{block.name[-1]}-{row}{number:02d}"
                    if Space.objects.filter(code=code).exists():
                        skipped += 1
                        continue
                    position = {
                        "code": code,
                        "block": block,
                        "row": row,
                        "number": number,
                        "kind": "GRAVE",
                        "notes": "Sepultura ficticia de un lote ilustrativo.",
                        "map_x": group_x + (number - 1) * 90,
                        "map_y": group_y + (row - 1) * 88,
                    }
                    result = services.save_space(admin, key(), position)
                    space = Space.objects.get(pk=result["id"])
                    created += 1

                    if index < 64:
                        first, last = synthetic_name(index + 8)
                        identification = f"DEMO-ERP-{index + 101:04d}"
                        responsible = Responsible.objects.create(
                            name=f"Familiar ficticio de {first} {last}",
                            identification=f"DEMO-ERP-R-{index + 101:04d}",
                            phone="0000000000",
                            email=f"contacto{index + 1:03d}@example.test",
                        )
                        death_date = today - timedelta(days=360 + index * 19)
                        person = Person.objects.create(
                            first_name=first,
                            last_name=last,
                            identification=identification,
                            death_date=death_date,
                            notes="Identidad y datos ficticios para una demostración académica.",
                        )
                        services.link_responsible(
                            admin,
                            key(),
                            {
                                "person": person,
                                "responsible": responsible,
                                "relationship": "Familiar (registro ficticio)",
                                "principal": True,
                            },
                        )
                        contract_id = services.create_contract(
                            admin,
                            key(),
                            {
                                "number": f"DEMO-MAPA-{code}",
                                "space": space,
                                "responsible": responsible,
                                "amount": Decimal("1500000.00"),
                                "monthly_maintenance_fee": Decimal("25000.00"),
                                "starts_on": death_date - timedelta(days=60),
                                "ends_on": today + timedelta(days=90 + (index % 270)),
                                "terms": "Contrato ficticio para demostración académica.",
                            },
                        )["id"]
                        contract = Contract.objects.get(pk=contract_id)
                        services.record_payment(
                            admin,
                            key(),
                            {
                                "contract": contract,
                                "invoice": contract.invoices.get(kind="CONTRACT"),
                                "amount": Decimal("350000.00"),
                                "method": "TRANSFER",
                                "reference": f"DEMO-MAPA-PAGO-{index + 1:04d}",
                                "paid_at": timezone.now(),
                            },
                        )
                        burial_at = timezone.make_aware(
                            datetime.combine(
                                death_date + timedelta(days=2), time(10, 30)
                            )
                        )
                        services.bury(
                            admin,
                            key(),
                            {
                                "person": person,
                                "space": space,
                                "contract": contract,
                                "occurred_at": burial_at,
                                "notes": "Registro histórico ficticio del plano académico.",
                            },
                        )
                        occupied += 1
                    elif index < 88:
                        responsible = Responsible.objects.create(
                            name=f"Responsable ficticio {synthetic_name(index + 8)[0]} {synthetic_name(index + 8)[1]}",
                            identification=f"DEMO-ERP-R-{index + 101:04d}",
                            phone="0000000000",
                            email=f"reserva{index + 1:03d}@example.test",
                        )
                        services.create_reservation(
                            admin,
                            key(),
                            {
                                "space": space,
                                "responsible": responsible,
                                "expires_on": today + timedelta(days=30 + index % 60),
                                "amount": Decimal("100000.00"),
                                "method": "CASH",
                                "reference": f"DEMO-MAPA-ANTICIPO-{index + 1:04d}",
                            },
                        )
                        reserved += 1
                    elif index in (120, 121, 122, 200, 201, 202):
                        services.change_condition(
                            admin,
                            key(),
                            space.pk,
                            "MAINTENANCE",
                            "Área ajardinada de mantenimiento (dato ficticio).",
                            space.revision,
                        )
                        maintenance += 1
                    elif index in (123, 203, 330):
                        services.change_condition(
                            admin,
                            key(),
                            space.pk,
                            "OUT_OF_SERVICE",
                            "Lote retirado del plano de asignación (dato ficticio).",
                            space.revision,
                        )
                        out_of_service += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Lote académico listo: {created} sepulturas añadidas, {skipped} ya estaban. "
                f"{occupied} ocupaciones con nombres ficticios, {reserved} reservas y "
                f"{maintenance} espacios en mantenimiento / {out_of_service} fuera de servicio. "
                "Ejecuta de nuevo el comando para completar si una carga previa encontró códigos existentes."
            )
        )
