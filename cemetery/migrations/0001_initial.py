# Initial schema for CementerioC. PostgreSQL is required.
from decimal import Decimal
import uuid
import cemetery.models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import migrations, models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone


class Migration(migrations.Migration):
    initial = True
    dependencies = [("auth", "0012_alter_user_first_name_max_length")]
    operations = [
        migrations.CreateModel(
            name="User",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("password", models.CharField(max_length=128, verbose_name="password")),
                (
                    "last_login",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="last login"
                    ),
                ),
                (
                    "is_superuser",
                    models.BooleanField(
                        default=False,
                        help_text="Designates that this user has all permissions without explicitly assigning them.",
                        verbose_name="superuser status",
                    ),
                ),
                (
                    "first_name",
                    models.CharField(
                        blank=True, max_length=150, verbose_name="first name"
                    ),
                ),
                (
                    "last_name",
                    models.CharField(
                        blank=True, max_length=150, verbose_name="last name"
                    ),
                ),
                (
                    "is_staff",
                    models.BooleanField(
                        default=False,
                        help_text="Designates whether the user can log into this admin site.",
                        verbose_name="staff status",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Designates whether this user should be treated as active. Unselect this instead of deleting accounts.",
                        verbose_name="active",
                    ),
                ),
                (
                    "date_joined",
                    models.DateTimeField(
                        default=timezone.now, verbose_name="date joined"
                    ),
                ),
                (
                    "groups",
                    models.ManyToManyField(
                        blank=True,
                        help_text="The groups this user belongs to. A user will get all permissions granted to each of their groups.",
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.group",
                        verbose_name="groups",
                    ),
                ),
                (
                    "user_permissions",
                    models.ManyToManyField(
                        blank=True,
                        help_text="Specific permissions for this user.",
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.permission",
                        verbose_name="user permissions",
                    ),
                ),
                ("email", models.EmailField("correo electrónico", unique=True)),
                (
                    "role",
                    models.CharField(
                        "perfil",
                        max_length=12,
                        choices=[
                            ("ADMIN", "Administrador"),
                            ("OFFICE", "Administrativo"),
                            ("TREASURY", "Tesorería"),
                            ("OPERATIONS", "Operaciones"),
                            ("VIEWER", "Consulta"),
                        ],
                        default="VIEWER",
                    ),
                ),
            ],
            options={"ordering": ["email"]},
            managers=[("objects", cemetery.models.UserManager())],
        ),
        migrations.CreateModel(
            name="Zone",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField("nombre", max_length=80, unique=True)),
            ],
            options={"ordering": ["name", "pk"]},
        ),
        migrations.CreateModel(
            name="Block",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "zone",
                    models.ForeignKey(
                        "cemetery.zone", on_delete=models.PROTECT, verbose_name="zona"
                    ),
                ),
                ("name", models.CharField("nombre", max_length=80)),
            ],
            options={"ordering": ["zone__name", "name", "pk"]},
        ),
        migrations.CreateModel(
            name="Space",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("code", models.CharField("código", max_length=40, unique=True)),
                (
                    "block",
                    models.ForeignKey(
                        "cemetery.block",
                        on_delete=models.PROTECT,
                        verbose_name="bloque",
                    ),
                ),
                (
                    "row",
                    models.PositiveIntegerField(
                        "fila", validators=[MinValueValidator(1)]
                    ),
                ),
                (
                    "number",
                    models.PositiveIntegerField(
                        "número", validators=[MinValueValidator(1)]
                    ),
                ),
                (
                    "kind",
                    models.CharField(
                        "tipo",
                        max_length=12,
                        choices=[
                            ("GRAVE", "Sepultura"),
                            ("VAULT", "Bóveda"),
                            ("OSSUARY", "Osario"),
                            ("NICHE", "Nicho"),
                        ],
                        default="GRAVE",
                    ),
                ),
                (
                    "condition",
                    models.CharField(
                        "condición administrativa",
                        max_length=16,
                        choices=[
                            ("AVAILABLE", "Disponible"),
                            ("MAINTENANCE", "Mantenimiento"),
                            ("OUT_OF_SERVICE", "Fuera de servicio"),
                        ],
                        default="AVAILABLE",
                    ),
                ),
                ("notes", models.TextField("observaciones", blank=True)),
                ("map_x", models.PositiveIntegerField("posición X", default=0)),
                ("map_y", models.PositiveIntegerField("posición Y", default=0)),
                ("revision", models.PositiveIntegerField(default=1)),
            ],
            options={"ordering": ["code", "pk"]},
        ),
        migrations.CreateModel(
            name="Person",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("first_name", models.CharField("nombres", max_length=100)),
                ("last_name", models.CharField("apellidos", max_length=100)),
                (
                    "identification",
                    models.CharField(
                        "identificación (opcional)", max_length=40, blank=True
                    ),
                ),
                (
                    "birth_date",
                    models.DateField("fecha de nacimiento", null=True, blank=True),
                ),
                ("death_date", models.DateField("fecha de fallecimiento")),
                ("notes", models.TextField("observaciones", blank=True)),
            ],
            options={"ordering": ["last_name", "first_name", "pk"]},
        ),
        migrations.CreateModel(
            name="Responsible",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField("nombre completo", max_length=180)),
                (
                    "identification",
                    models.CharField("identificación", max_length=40, unique=True),
                ),
                ("phone", models.CharField("teléfono", max_length=30)),
                ("email", models.EmailField("correo", blank=True)),
                ("address", models.CharField("dirección", max_length=240, blank=True)),
            ],
            options={"ordering": ["name", "pk"]},
        ),
        migrations.CreateModel(
            name="PersonResponsible",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "person",
                    models.ForeignKey(
                        "cemetery.person",
                        on_delete=models.PROTECT,
                        verbose_name="persona fallecida",
                        related_name="responsible_links",
                    ),
                ),
                (
                    "responsible",
                    models.ForeignKey(
                        "cemetery.responsible",
                        on_delete=models.PROTECT,
                        verbose_name="responsable",
                    ),
                ),
                (
                    "relationship",
                    models.CharField("parentesco o relación", max_length=80),
                ),
                (
                    "principal",
                    models.BooleanField("responsable principal", default=False),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Reservation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "space",
                    models.ForeignKey(
                        "cemetery.space",
                        on_delete=models.PROTECT,
                        related_name="reservations",
                        verbose_name="sepultura",
                    ),
                ),
                (
                    "responsible",
                    models.ForeignKey(
                        "cemetery.responsible",
                        on_delete=models.PROTECT,
                        verbose_name="responsable",
                    ),
                ),
                ("expires_on", models.DateField("reservada hasta")),
                (
                    "state",
                    models.CharField(
                        max_length=12,
                        choices=[
                            ("ACTIVE", "Activa"),
                            ("CONSUMED", "Aplicada a contrato"),
                            ("CANCELLED", "Cancelada"),
                            ("EXPIRED", "Vencida"),
                        ],
                        default="ACTIVE",
                    ),
                ),
                ("reason", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(default=timezone.now)),
            ],
            options={"ordering": ["-created_at", "-pk"]},
        ),
        migrations.CreateModel(
            name="Contract",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("number", models.CharField("número", max_length=50, unique=True)),
                (
                    "space",
                    models.ForeignKey(
                        "cemetery.space",
                        on_delete=models.PROTECT,
                        related_name="contracts",
                        verbose_name="sepultura",
                    ),
                ),
                (
                    "responsible",
                    models.ForeignKey(
                        "cemetery.responsible",
                        on_delete=models.PROTECT,
                        verbose_name="responsable",
                    ),
                ),
                (
                    "reservation",
                    models.OneToOneField(
                        "cemetery.reservation",
                        null=True,
                        blank=True,
                        on_delete=models.PROTECT,
                    ),
                ),
                (
                    "amount",
                    models.DecimalField(
                        "valor total",
                        max_digits=14,
                        decimal_places=2,
                        validators=[MinValueValidator(Decimal("0.01"))],
                    ),
                ),
                ("currency", models.CharField(max_length=3, default="COP")),
                ("starts_on", models.DateField("inicio")),
                ("ends_on", models.DateField("vencimiento")),
                (
                    "state",
                    models.CharField(
                        max_length=12,
                        choices=[
                            ("ACTIVE", "Activo"),
                            ("CLOSED", "Cerrado"),
                            ("CANCELLED", "Cancelado"),
                        ],
                        default="ACTIVE",
                    ),
                ),
                ("terms", models.TextField("condiciones")),
                ("created_at", models.DateTimeField(default=timezone.now)),
            ],
            options={"ordering": ["-created_at", "-pk"]},
        ),
        migrations.CreateModel(
            name="Payment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "contract",
                    models.ForeignKey(
                        "cemetery.contract",
                        null=True,
                        blank=True,
                        on_delete=models.PROTECT,
                        related_name="payments",
                        verbose_name="contrato",
                    ),
                ),
                (
                    "reservation",
                    models.ForeignKey(
                        "cemetery.reservation",
                        null=True,
                        blank=True,
                        on_delete=models.PROTECT,
                        related_name="payments",
                    ),
                ),
                (
                    "amount",
                    models.DecimalField(
                        "valor",
                        max_digits=14,
                        decimal_places=2,
                        validators=[MinValueValidator(Decimal("0.01"))],
                    ),
                ),
                (
                    "method",
                    models.CharField(
                        "método",
                        max_length=12,
                        choices=[
                            ("CASH", "Efectivo"),
                            ("TRANSFER", "Transferencia"),
                            ("CARD", "Datáfono"),
                        ],
                    ),
                ),
                ("reference", models.CharField("referencia o recibo", max_length=100)),
                (
                    "paid_at",
                    models.DateTimeField("fecha del pago", default=timezone.now),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        settings.AUTH_USER_MODEL,
                        on_delete=models.PROTECT,
                        related_name="+",
                    ),
                ),
                ("voided_at", models.DateTimeField(null=True, blank=True)),
                ("void_reason", models.TextField(blank=True)),
            ],
            options={"ordering": ["-paid_at", "-pk"]},
        ),
        migrations.CreateModel(
            name="Occupancy",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "space",
                    models.ForeignKey(
                        "cemetery.space",
                        on_delete=models.PROTECT,
                        related_name="occupancies",
                    ),
                ),
                (
                    "person",
                    models.ForeignKey(
                        "cemetery.person",
                        on_delete=models.PROTECT,
                        related_name="occupancies",
                    ),
                ),
                (
                    "contract",
                    models.ForeignKey("cemetery.contract", on_delete=models.PROTECT),
                ),
                ("started_at", models.DateTimeField()),
                ("ended_at", models.DateTimeField(null=True, blank=True)),
            ],
        ),
        migrations.CreateModel(
            name="Movement",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "occupancy",
                    models.ForeignKey("cemetery.occupancy", on_delete=models.PROTECT),
                ),
                (
                    "kind",
                    models.CharField(
                        "tipo",
                        max_length=12,
                        choices=[
                            ("EXHUMATION", "Exhumación"),
                            ("TRANSFER", "Traslado interno"),
                        ],
                    ),
                ),
                (
                    "destination",
                    models.ForeignKey(
                        "cemetery.space",
                        null=True,
                        blank=True,
                        on_delete=models.PROTECT,
                        related_name="+",
                        verbose_name="destino interno",
                    ),
                ),
                (
                    "destination_contract",
                    models.ForeignKey(
                        "cemetery.contract",
                        null=True,
                        blank=True,
                        on_delete=models.PROTECT,
                        related_name="+",
                        verbose_name="contrato del destino",
                    ),
                ),
                (
                    "external_destination",
                    models.CharField(
                        "destino de los restos", max_length=240, blank=True
                    ),
                ),
                ("reason", models.TextField("motivo")),
                (
                    "document_reference",
                    models.CharField(
                        "referencia de autorización/documentos",
                        max_length=240,
                        blank=True,
                    ),
                ),
                ("proposed_on", models.DateField("fecha propuesta")),
                (
                    "state",
                    models.CharField(
                        max_length=12,
                        choices=[
                            ("REQUESTED", "Solicitado"),
                            ("AUTHORIZED", "Autorizado"),
                            ("EXECUTED", "Ejecutado"),
                            ("CANCELLED", "Cancelado"),
                        ],
                        default="REQUESTED",
                    ),
                ),
                (
                    "requested_by",
                    models.ForeignKey(
                        settings.AUTH_USER_MODEL,
                        on_delete=models.PROTECT,
                        related_name="+",
                    ),
                ),
                (
                    "authorized_by",
                    models.ForeignKey(
                        settings.AUTH_USER_MODEL,
                        null=True,
                        blank=True,
                        on_delete=models.PROTECT,
                        related_name="+",
                    ),
                ),
                ("authorized_at", models.DateTimeField(null=True, blank=True)),
                ("executed_at", models.DateTimeField(null=True, blank=True)),
                (
                    "executed_by",
                    models.ForeignKey(
                        settings.AUTH_USER_MODEL,
                        null=True,
                        blank=True,
                        on_delete=models.PROTECT,
                        related_name="+",
                    ),
                ),
                ("cancellation_reason", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(default=timezone.now)),
            ],
            options={"ordering": ["-created_at", "-pk"]},
        ),
        migrations.CreateModel(
            name="Event",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "space",
                    models.ForeignKey(
                        "cemetery.space",
                        on_delete=models.PROTECT,
                        related_name="events",
                    ),
                ),
                (
                    "person",
                    models.ForeignKey(
                        "cemetery.person",
                        null=True,
                        blank=True,
                        on_delete=models.PROTECT,
                    ),
                ),
                ("kind", models.CharField(max_length=40)),
                ("detail", models.TextField()),
                (
                    "actor",
                    models.ForeignKey(
                        settings.AUTH_USER_MODEL, on_delete=models.PROTECT
                    ),
                ),
                ("occurred_at", models.DateTimeField(default=timezone.now)),
            ],
            options={"ordering": ["-occurred_at", "-pk"]},
        ),
        migrations.CreateModel(
            name="Audit",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "actor",
                    models.ForeignKey(
                        settings.AUTH_USER_MODEL, on_delete=models.PROTECT
                    ),
                ),
                ("action", models.CharField(max_length=60)),
                ("target", models.CharField(max_length=120)),
                ("detail", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(default=timezone.now)),
            ],
            options={"ordering": ["-created_at", "-pk"]},
        ),
        migrations.CreateModel(
            name="Command",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("key", models.UUIDField(default=uuid.uuid4, unique=True)),
                (
                    "actor",
                    models.ForeignKey(
                        settings.AUTH_USER_MODEL, on_delete=models.PROTECT
                    ),
                ),
                ("fingerprint", models.CharField(max_length=64)),
                ("result", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(default=timezone.now)),
            ],
        ),
        migrations.CreateModel(
            name="LoginThrottle",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("key", models.CharField(max_length=64, unique=True)),
                ("failures", models.PositiveIntegerField(default=0)),
                ("window_start", models.DateTimeField(default=timezone.now)),
            ],
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                Lower("email"), name="user_email_ci_unique"
            ),
        ),
        migrations.AddConstraint(
            model_name="block",
            constraint=models.UniqueConstraint(
                fields=["zone", "name"], name="block_zone_name_unique"
            ),
        ),
        migrations.AddConstraint(
            model_name="space",
            constraint=models.UniqueConstraint(
                Lower("code"), name="space_code_ci_unique"
            ),
        ),
        migrations.AddConstraint(
            model_name="space",
            constraint=models.UniqueConstraint(
                fields=["block", "row", "number"], name="space_physical_location_unique"
            ),
        ),
        migrations.AddConstraint(
            model_name="space",
            constraint=models.CheckConstraint(
                condition=Q(row__gte=1, number__gte=1), name="space_positive_position"
            ),
        ),
        migrations.AddConstraint(
            model_name="person",
            constraint=models.UniqueConstraint(
                fields=["identification"],
                condition=~Q(identification=""),
                name="person_document_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="personresponsible",
            constraint=models.UniqueConstraint(
                fields=["person", "responsible"], name="person_responsible_unique"
            ),
        ),
        migrations.AddConstraint(
            model_name="personresponsible",
            constraint=models.UniqueConstraint(
                fields=["person"],
                condition=Q(principal=True),
                name="one_principal_responsible",
            ),
        ),
        migrations.AddConstraint(
            model_name="reservation",
            constraint=models.UniqueConstraint(
                fields=["space"],
                condition=Q(state="ACTIVE"),
                name="one_active_reservation",
            ),
        ),
        migrations.AddConstraint(
            model_name="contract",
            constraint=models.CheckConstraint(
                condition=Q(amount__gt=0), name="contract_positive_amount"
            ),
        ),
        migrations.AddConstraint(
            model_name="contract",
            constraint=models.CheckConstraint(
                condition=Q(ends_on__gte=models.F("starts_on")),
                name="contract_valid_dates",
            ),
        ),
        migrations.AddConstraint(
            model_name="contract",
            constraint=models.UniqueConstraint(
                fields=["space"],
                condition=Q(state="ACTIVE"),
                name="one_active_contract",
            ),
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.CheckConstraint(
                condition=Q(amount__gt=0), name="payment_positive_amount"
            ),
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.CheckConstraint(
                condition=Q(contract__isnull=False) | Q(reservation__isnull=False),
                name="payment_has_owner",
            ),
        ),
        migrations.AddConstraint(
            model_name="occupancy",
            constraint=models.UniqueConstraint(
                fields=["space"],
                condition=Q(ended_at__isnull=True),
                name="one_current_occupancy_per_space",
            ),
        ),
        migrations.AddConstraint(
            model_name="occupancy",
            constraint=models.UniqueConstraint(
                fields=["person"],
                condition=Q(ended_at__isnull=True),
                name="one_current_occupancy_per_person",
            ),
        ),
        migrations.AddConstraint(
            model_name="occupancy",
            constraint=models.CheckConstraint(
                condition=Q(ended_at__isnull=True)
                | Q(ended_at__gte=models.F("started_at")),
                name="occupancy_valid_dates",
            ),
        ),
        migrations.AddConstraint(
            model_name="movement",
            constraint=models.UniqueConstraint(
                fields=["occupancy"],
                condition=Q(state__in=["REQUESTED", "AUTHORIZED"]),
                name="one_pending_movement",
            ),
        ),
    ]
