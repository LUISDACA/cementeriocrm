from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from cemetery.models import Contract, Invoice


class Command(BaseCommand):
    help = "Emite las facturas internas de mantenimiento familiar del mes indicado."

    def add_arguments(self, parser):
        parser.add_argument("--month", help="Mes a facturar en formato AAAA-MM; por defecto el mes actual.")

    def handle(self, *args, **options):
        if not settings.DEBUG or not getattr(settings, "ACADEMIC_MODE", False):
            raise CommandError("La emisión masiva está habilitada solo en el modo académico.")
        raw = options.get("month") or timezone.localdate().strftime("%Y-%m")
        try:
            year, month = map(int, raw.split("-"))
            period = date(year, month, 1)
        except (ValueError, TypeError):
            raise CommandError("Usa --month AAAA-MM, por ejemplo --month 2026-11.")
        due = date(year, month, monthrange(year, month)[1]) + timedelta(days=10)
        created = skipped = 0
        with transaction.atomic():
            contracts = Contract.objects.filter(
                state=Contract.State.ACTIVE,
                monthly_maintenance_fee__gt=Decimal("0.00"),
                starts_on__lte=date(year, month, monthrange(year, month)[1]),
                ends_on__gte=period,
            )
            for contract in contracts.select_related("space"):
                invoice, was_created = Invoice.objects.get_or_create(
                    contract=contract, kind=Invoice.Kind.MAINTENANCE, period=period,
                    defaults={
                        "number": f"M-{contract.pk:06d}-{year}{month:02d}",
                        "description": f"Cuota familiar de mantenimiento · {period.strftime('%m/%Y')} · {contract.space.code}",
                        "amount": contract.monthly_maintenance_fee,
                        "issued_on": timezone.localdate(), "due_on": due,
                    },
                )
                created += int(was_created)
                skipped += int(not was_created)
        self.stdout.write(self.style.SUCCESS(f"Facturas de mantenimiento emitidas: {created}; ya existentes omitidas: {skipped}."))
