from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from cemetery.models import Reservation, User
from cemetery.services import expire_reservation, run
import uuid


class Command(BaseCommand):
    help = "Registra vencimientos de reservas; conserva los pagos para conciliación."

    def add_arguments(self, parser):
        parser.add_argument(
            "--actor",
            required=True,
            help="Correo de una cuenta de tesorería o administración.",
        )

    def handle(self, *args, **options):
        try:
            actor = User.objects.get(
                email=options["actor"].strip().lower(),
                is_active=True,
                role__in=["ADMIN", "TREASURY"],
            )
        except User.DoesNotExist:
            raise CommandError(
                "Se requiere un actor activo de tesorería o administración."
            )
        reservations = list(
            Reservation.objects.filter(
                state="ACTIVE", expires_on__lt=timezone.localdate()
            ).select_related("space")
        )
        for obj in reservations:
            run(
                actor,
                uuid.uuid4(),
                "reservation.expire",
                {"space_id": obj.space_id},
                lambda: (expire_reservation(actor, obj.space), {"id": obj.pk})[1],
            )
        self.stdout.write(
            f"Reservas revisadas: {len(reservations)}. Ningún pago fue eliminado."
        )
