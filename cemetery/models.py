from datetime import timedelta
from decimal import Decimal
import uuid
from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("El correo es obligatorio.")
        user = self.model(email=email.strip().lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.update(is_staff=True, is_superuser=True, role="ADMIN")
        return self.create_user(email, password, **extra)


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Administrador"
        OFFICE = "OFFICE", "Administrativo"
        TREASURY = "TREASURY", "Tesorería"
        OPERATIONS = "OPERATIONS", "Operaciones"
        VIEWER = "VIEWER", "Consulta"
        FAMILY = "FAMILY", "Familiar"

    username = None
    email = models.EmailField("correo electrónico", unique=True)
    role = models.CharField(
        "perfil", max_length=12, choices=Role.choices, default=Role.VIEWER
    )
    objects = UserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="user_email_ci_unique")
        ]
        ordering = ["email"]

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.get_full_name() or self.email


class FamilyProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="family_profile")
    identification = models.CharField("identificación", max_length=40)
    phone = models.CharField("teléfono", max_length=30)
    address = models.CharField("dirección", max_length=240, blank=True)
    privacy_accepted_at = models.DateTimeField(default=timezone.now)
    verified_at = models.DateTimeField(null=True, blank=True)
    responsible = models.OneToOneField(
        "Responsible", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="family_account",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("identification"), name="family_identification_ci_unique")
        ]

    def __str__(self):
        return f"{self.user.get_full_name()} · {self.identification}"


class MapPlan(models.Model):
    """Single private PNG basemap used by the interactive cemetery map."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    image = models.BinaryField()
    original_name = models.CharField(max_length=180)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    uploaded_at = models.DateTimeField(default=timezone.now)


class Zone(models.Model):
    name = models.CharField("nombre", max_length=80, unique=True)

    class Meta:
        ordering = ["name", "pk"]

    def __str__(self):
        return self.name


class Block(models.Model):
    zone = models.ForeignKey(Zone, on_delete=models.PROTECT, verbose_name="zona")
    name = models.CharField("nombre", max_length=80)

    class Meta:
        ordering = ["zone__name", "name", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["zone", "name"], name="block_zone_name_unique"
            )
        ]

    def __str__(self):
        return f"{self.zone} / {self.name}"


class Space(models.Model):
    class Condition(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Disponible"
        MAINTENANCE = "MAINTENANCE", "Mantenimiento"
        OUT_OF_SERVICE = "OUT_OF_SERVICE", "Fuera de servicio"

    class Kind(models.TextChoices):
        GRAVE = "GRAVE", "Sepultura"
        VAULT = "VAULT", "Bóveda"
        OSSUARY = "OSSUARY", "Osario"
        NICHE = "NICHE", "Nicho"

    code = models.CharField("código", max_length=40, unique=True)
    block = models.ForeignKey(Block, on_delete=models.PROTECT, verbose_name="bloque")
    row = models.PositiveIntegerField("fila", validators=[MinValueValidator(1)])
    number = models.PositiveIntegerField("número", validators=[MinValueValidator(1)])
    kind = models.CharField(
        "tipo", max_length=12, choices=Kind.choices, default=Kind.GRAVE
    )
    condition = models.CharField(
        "condición administrativa",
        max_length=16,
        choices=Condition.choices,
        default=Condition.AVAILABLE,
    )
    notes = models.TextField("observaciones", blank=True)
    map_x = models.PositiveIntegerField("posición X", default=0)
    map_y = models.PositiveIntegerField("posición Y", default=0)
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["code", "pk"]
        constraints = [
            models.UniqueConstraint(Lower("code"), name="space_code_ci_unique"),
            models.UniqueConstraint(
                fields=["block", "row", "number"], name="space_physical_location_unique"
            ),
            models.CheckConstraint(
                condition=Q(row__gte=1, number__gte=1), name="space_positive_position"
            ),
        ]

    @property
    def status(self):
        if hasattr(self, "has_occupancy"):
            occupied, reserved = self.has_occupancy, self.has_reservation
        else:
            occupied = self.occupancies.filter(ended_at__isnull=True).exists()
            reserved = self.reservations.filter(
                state="ACTIVE", expires_on__gte=timezone.localdate()
            ).exists()
        return "OCCUPIED" if occupied else "RESERVED" if reserved else self.condition

    @property
    def status_label(self):
        return dict(STATUS_CHOICES)[self.status]

    def __str__(self):
        return self.code


STATUS_CHOICES = [
    ("AVAILABLE", "Disponible"),
    ("OCCUPIED", "Ocupada"),
    ("RESERVED", "Reservada"),
    ("MAINTENANCE", "Mantenimiento"),
    ("OUT_OF_SERVICE", "Fuera de servicio"),
]


class Person(models.Model):
    first_name = models.CharField("nombres", max_length=100)
    last_name = models.CharField("apellidos", max_length=100)
    identification = models.CharField(
        "identificación (opcional)", max_length=40, blank=True
    )
    birth_date = models.DateField("fecha de nacimiento", null=True, blank=True)
    death_date = models.DateField("fecha de fallecimiento")
    notes = models.TextField("observaciones", blank=True)

    class Meta:
        ordering = ["last_name", "first_name", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["identification"],
                condition=~Q(identification=""),
                name="person_document_unique",
            )
        ]

    def clean(self):
        if self.death_date and self.death_date > timezone.localdate():
            raise ValidationError({"death_date": "La fecha no puede ser futura."})
        if self.birth_date and self.death_date and self.birth_date > self.death_date:
            raise ValidationError(
                {"birth_date": "El nacimiento debe ser anterior al fallecimiento."}
            )

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Responsible(models.Model):
    name = models.CharField("nombre completo", max_length=180)
    identification = models.CharField("identificación", max_length=40, unique=True)
    phone = models.CharField("teléfono", max_length=30)
    email = models.EmailField("correo", blank=True)
    address = models.CharField("dirección", max_length=240, blank=True)

    class Meta:
        ordering = ["name", "pk"]

    def __str__(self):
        return f"{self.name} · {self.identification}"


class PersonResponsible(models.Model):
    person = models.ForeignKey(
        Person,
        on_delete=models.PROTECT,
        verbose_name="persona fallecida",
        related_name="responsible_links",
    )
    responsible = models.ForeignKey(
        Responsible, on_delete=models.PROTECT, verbose_name="responsable"
    )
    relationship = models.CharField("parentesco o relación", max_length=80)
    principal = models.BooleanField("responsable principal", default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["person", "responsible"], name="person_responsible_unique"
            ),
            models.UniqueConstraint(
                fields=["person"],
                condition=Q(principal=True),
                name="one_principal_responsible",
            ),
        ]


class Reservation(models.Model):
    class State(models.TextChoices):
        ACTIVE = "ACTIVE", "Activa"
        CONSUMED = "CONSUMED", "Aplicada a contrato"
        CANCELLED = "CANCELLED", "Cancelada"
        EXPIRED = "EXPIRED", "Vencida"

    space = models.ForeignKey(
        Space,
        on_delete=models.PROTECT,
        related_name="reservations",
        verbose_name="sepultura",
    )
    responsible = models.ForeignKey(
        Responsible, on_delete=models.PROTECT, verbose_name="responsable"
    )
    expires_on = models.DateField("reservada hasta")
    state = models.CharField(max_length=12, choices=State.choices, default=State.ACTIVE)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["space"],
                condition=Q(state="ACTIVE"),
                name="one_active_reservation",
            )
        ]

    @property
    def state_label(self):
        if self.state == self.State.ACTIVE and self.expires_on < timezone.localdate():
            return "Vencida"
        return self.get_state_display()

    def __str__(self):
        return f"R-{self.pk} · {self.space}"


class Contract(models.Model):
    class State(models.TextChoices):
        ACTIVE = "ACTIVE", "Activo"
        CLOSED = "CLOSED", "Cerrado"
        CANCELLED = "CANCELLED", "Cancelado"

    number = models.CharField("número", max_length=50, unique=True)
    space = models.ForeignKey(
        Space,
        on_delete=models.PROTECT,
        related_name="contracts",
        verbose_name="sepultura",
    )
    responsible = models.ForeignKey(
        Responsible, on_delete=models.PROTECT, verbose_name="responsable"
    )
    reservation = models.OneToOneField(
        Reservation, null=True, blank=True, on_delete=models.PROTECT
    )
    amount = models.DecimalField(
        "valor total",
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    currency = models.CharField(max_length=3, default="COP")
    starts_on = models.DateField("inicio")
    ends_on = models.DateField("vencimiento")
    state = models.CharField(max_length=12, choices=State.choices, default=State.ACTIVE)
    terms = models.TextField("condiciones")
    monthly_maintenance_fee = models.DecimalField(
        "cuota mensual de mantenimiento familiar", max_digits=14, decimal_places=2,
        default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))],
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="contract_positive_amount"
            ),
            models.CheckConstraint(
                condition=Q(ends_on__gte=models.F("starts_on")),
                name="contract_valid_dates",
            ),
            models.UniqueConstraint(
                fields=["space"],
                condition=Q(state="ACTIVE"),
                name="one_active_contract",
            ),
        ]

    @property
    def paid(self):
        return self.payments.filter(voided_at__isnull=True).filter(
            Q(invoice__isnull=True) | Q(invoice__kind=Invoice.Kind.CONTRACT)
        ).aggregate(
            total=models.Sum("amount")
        )["total"] or Decimal("0.00")

    @property
    def balance(self):
        return self.amount - self.paid

    @property
    def validity(self):
        today = timezone.localdate()
        if self.state != self.State.ACTIVE:
            return self.get_state_display()
        if self.starts_on > today:
            return "Pendiente de inicio"
        if self.ends_on < today:
            return "Vencido"
        if self.ends_on <= today + timedelta(days=settings.CEMETERY_EXPIRY_DAYS):
            return "Próximo a vencer"
        return "Vigente"

    @property
    def days_remaining(self):
        if self.state != self.State.ACTIVE:
            return None
        return (self.ends_on - timezone.localdate()).days

    @property
    def expiry_label(self):
        days = self.days_remaining
        if days is None:
            return "No aplica"
        if days == 0:
            return "Vence hoy"
        value = abs(days)
        label = f"{value} {'día' if value == 1 else 'días'}"
        return f"Venció hace {label}" if days < 0 else label

    def __str__(self):
        return f"{self.number} · {self.space}"


class ContractDocument(models.Model):
    """Private, versioned evidence copy of a manually signed contract."""

    contract = models.ForeignKey(
        Contract, on_delete=models.PROTECT, related_name="documents"
    )
    version = models.PositiveIntegerField()
    file_name = models.CharField(max_length=180)
    content_type = models.CharField(max_length=40)
    content = models.BinaryField()
    sha256 = models.CharField(max_length=64)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    uploaded_at = models.DateTimeField(default=timezone.now)
    is_current = models.BooleanField(default=True)

    class Meta:
        ordering = ["-version", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["contract", "version"], name="contract_document_version_unique"
            ),
            models.UniqueConstraint(
                fields=["contract"], condition=Q(is_current=True),
                name="one_current_contract_document",
            ),
        ]

    def __str__(self):
        return f"{self.contract.number} · copia firmada v{self.version}"


class Payment(models.Model):
    class Method(models.TextChoices):
        CASH = "CASH", "Efectivo"
        TRANSFER = "TRANSFER", "Transferencia"
        CARD = "CARD", "Datáfono"

    contract = models.ForeignKey(
        Contract,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="payments",
        verbose_name="contrato",
    )
    invoice = models.ForeignKey(
        "Invoice", null=True, blank=True, on_delete=models.PROTECT,
        related_name="payments", verbose_name="factura asociada",
    )
    reservation = models.ForeignKey(
        Reservation,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    amount = models.DecimalField(
        "valor",
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    method = models.CharField("método", max_length=12, choices=Method.choices)
    reference = models.CharField("referencia o recibo", max_length=100)
    paid_at = models.DateTimeField("fecha del pago", default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-paid_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="payment_positive_amount"
            ),
            models.CheckConstraint(
                condition=Q(contract__isnull=False) | Q(reservation__isnull=False),
                name="payment_has_owner",
            ),
        ]


class Refund(models.Model):
    """Audit record of a refund already processed outside the application."""

    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="refunds")
    amount = models.DecimalField(
        "valor devuelto", max_digits=14, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    method = models.CharField("método de devolución", max_length=12, choices=Payment.Method.choices)
    reference = models.CharField("referencia de devolución", max_length=100)
    reason = models.TextField("motivo")
    refunded_at = models.DateTimeField("fecha y hora de devolución")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-refunded_at", "-pk"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="refund_positive_amount"),
        ]

    @property
    def number(self):
        return f"D-{self.pk:06d}"


class Invoice(models.Model):
    class Kind(models.TextChoices):
        CONTRACT = "CONTRACT", "Contrato de sepultura"
        MAINTENANCE = "MAINTENANCE", "Mantenimiento mensual familiar"

    number = models.CharField("número de factura interna", max_length=50, unique=True)
    contract = models.ForeignKey(Contract, on_delete=models.PROTECT, related_name="invoices")
    kind = models.CharField("concepto", max_length=16, choices=Kind.choices)
    description = models.CharField("detalle", max_length=240)
    amount = models.DecimalField("total", max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    issued_on = models.DateField("fecha de emisión", default=timezone.localdate)
    due_on = models.DateField("fecha de vencimiento")
    period = models.DateField("mes facturado", null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-issued_on", "-pk"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="invoice_positive_amount"),
            models.UniqueConstraint(fields=["contract", "kind", "period"], condition=Q(kind="MAINTENANCE"), name="one_maintenance_invoice_per_period"),
            models.UniqueConstraint(fields=["contract", "kind"], condition=Q(kind="CONTRACT"), name="one_contract_invoice"),
        ]

    @property
    def paid(self):
        return self.payments.filter(voided_at__isnull=True).aggregate(total=models.Sum("amount"))["total"] or Decimal("0.00")

    @property
    def balance(self):
        return max(Decimal("0.00"), self.amount - self.paid)

    @property
    def state_label(self):
        if self.balance == 0:
            return "Pagada"
        if self.due_on < timezone.localdate():
            return "Vencida"
        return "Pendiente"


class OperatingExpense(models.Model):
    class Category(models.TextChoices):
        TAX = "TAX", "Impuestos"
        ELECTRICITY = "ELECTRICITY", "Energía eléctrica"
        PUBLIC_CLEANING = "PUBLIC_CLEANING", "Limpieza de zonas públicas"
        WATER = "WATER", "Agua"
        SUPPLIES = "SUPPLIES", "Insumos y mantenimiento"
        OTHER = "OTHER", "Otro gasto operativo"

    number = models.CharField("consecutivo", max_length=50, unique=True)
    category = models.CharField("categoría", max_length=20, choices=Category.choices)
    description = models.CharField("descripción", max_length=240)
    supplier = models.CharField("proveedor o entidad", max_length=180, blank=True)
    amount = models.DecimalField("valor", max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    paid_on = models.DateField("fecha de pago")
    reference = models.CharField("referencia", max_length=100, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-paid_on", "-pk"]
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name="expense_positive_amount")]


class ExpenseDocument(models.Model):
    """Private, versioned invoice or payment evidence for an operating expense."""

    expense = models.ForeignKey(
        OperatingExpense, on_delete=models.PROTECT, related_name="documents"
    )
    version = models.PositiveIntegerField()
    file_name = models.CharField(max_length=180)
    content_type = models.CharField(max_length=40)
    content = models.BinaryField()
    sha256 = models.CharField(max_length=64)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    uploaded_at = models.DateTimeField(default=timezone.now)
    is_current = models.BooleanField(default=True)

    class Meta:
        ordering = ["-version", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["expense", "version"], name="expense_document_version_unique"
            ),
            models.UniqueConstraint(
                fields=["expense"], condition=Q(is_current=True),
                name="one_current_expense_document",
            ),
        ]

    def __str__(self):
        return f"{self.expense.number} · soporte v{self.version}"


class Occupancy(models.Model):
    space = models.ForeignKey(
        Space, on_delete=models.PROTECT, related_name="occupancies"
    )
    person = models.ForeignKey(
        Person, on_delete=models.PROTECT, related_name="occupancies"
    )
    contract = models.ForeignKey(Contract, on_delete=models.PROTECT)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["space"],
                condition=Q(ended_at__isnull=True),
                name="one_current_occupancy_per_space",
            ),
            models.UniqueConstraint(
                fields=["person"],
                condition=Q(ended_at__isnull=True),
                name="one_current_occupancy_per_person",
            ),
            models.CheckConstraint(
                condition=Q(ended_at__isnull=True)
                | Q(ended_at__gte=models.F("started_at")),
                name="occupancy_valid_dates",
            ),
        ]


class Movement(models.Model):
    class Kind(models.TextChoices):
        EXHUMATION = "EXHUMATION", "Exhumación"
        TRANSFER = "TRANSFER", "Traslado interno"

    class State(models.TextChoices):
        REQUESTED = "REQUESTED", "Solicitado"
        AUTHORIZED = "AUTHORIZED", "Autorizado"
        EXECUTED = "EXECUTED", "Ejecutado"
        CANCELLED = "CANCELLED", "Cancelado"

    occupancy = models.ForeignKey(Occupancy, on_delete=models.PROTECT)
    kind = models.CharField("tipo", max_length=12, choices=Kind.choices)
    destination = models.ForeignKey(
        Space,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="destino interno",
    )
    destination_contract = models.ForeignKey(
        Contract,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="contrato del destino",
    )
    external_destination = models.CharField(
        "destino de los restos", max_length=240, blank=True
    )
    reason = models.TextField("motivo")
    document_reference = models.CharField(
        "referencia de autorización/documentos", max_length=240, blank=True
    )
    proposed_on = models.DateField("fecha propuesta")
    state = models.CharField(
        max_length=12, choices=State.choices, default=State.REQUESTED
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    authorized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    authorized_at = models.DateTimeField(null=True, blank=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    executed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    cancellation_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["occupancy"],
                condition=Q(state__in=["REQUESTED", "AUTHORIZED"]),
                name="one_pending_movement",
            )
        ]


class Event(models.Model):
    class Kind(models.TextChoices):
        SPACE_CREATED = "SPACE_CREATED", "Registro de sepultura"
        SPACE_UPDATED = "SPACE_UPDATED", "Corrección de ficha"
        CONDITION_CHANGED = "CONDITION_CHANGED", "Cambio de condición"
        RESERVATION_CREATED = "RESERVATION_CREATED", "Reserva pagada"
        RESERVATION_EXPIRED = "RESERVATION_EXPIRED", "Vencimiento de reserva"
        RESERVATION_CANCELLED = "RESERVATION_CANCELLED", "Cancelación de reserva"
        CONTRACT_CREATED = "CONTRACT_CREATED", "Registro de contrato"
        CONTRACT_UPDATED = "CONTRACT_UPDATED", "Corrección de contrato"
        CONTRACT_CLOSED = "CONTRACT_CLOSED", "Cierre de contrato"
        PAYMENT_RECORDED = "PAYMENT_RECORDED", "Registro de pago"
        PAYMENT_VOIDED = "PAYMENT_VOIDED", "Anulación de pago"
        BURIAL = "BURIAL", "Inhumación"
        MOVEMENT_REQUESTED = "MOVEMENT_REQUESTED", "Solicitud de movimiento"
        MOVEMENT_AUTHORIZE = "MOVEMENT_AUTHORIZE", "Autorización de movimiento"
        MOVEMENT_CANCEL = "MOVEMENT_CANCEL", "Cancelación de movimiento"
        TRANSFER_IN = "TRANSFER_IN", "Ingreso por traslado"
        TRANSFER = "TRANSFER", "Salida por traslado"
        EXHUMATION = "EXHUMATION", "Exhumación"

    space = models.ForeignKey(Space, on_delete=models.PROTECT, related_name="events")
    person = models.ForeignKey(Person, null=True, blank=True, on_delete=models.PROTECT)
    kind = models.CharField(max_length=40, choices=Kind.choices)
    detail = models.TextField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    occurred_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-occurred_at", "-pk"]


class Audit(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=60)
    target = models.CharField(max_length=120)
    detail = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at", "-pk"]


class Command(models.Model):
    key = models.UUIDField(default=uuid.uuid4, unique=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fingerprint = models.CharField(max_length=64)
    result = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)


class LoginThrottle(models.Model):
    key = models.CharField(max_length=64, unique=True)
    failures = models.PositiveIntegerField(default=0)
    window_start = models.DateTimeField(default=timezone.now)
