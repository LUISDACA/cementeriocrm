import uuid
from decimal import Decimal
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.forms.models import construct_instance
from django.utils import timezone
from .models import (
    Block,
    Contract,
    Invoice,
    OperatingExpense,
    Movement,
    Occupancy,
    Payment,
    Person,
    PersonResponsible,
    Responsible,
    Space,
    User,
    Zone,
)
from .map_image import InvalidPlanImage, inspect_plan_png


class StyledForm(forms.Form):
    command_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not field.widget.is_hidden:
                field.widget.attrs["class"] = (
                    "form-check-input"
                    if isinstance(field.widget, forms.CheckboxInput)
                    else "form-control"
                )


class RecordForm(forms.ModelForm):
    """Valida la entrada; el servicio valida unicidad dentro de su transacción.

    La unicidad anticipada impediría reconocer un reintento ya confirmado.
    Estas formas no guardan modelos: todas las vistas llaman a servicios que
    ejecutan full_clean() antes de escribir y conservan las restricciones SQL.
    """

    command_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not field.widget.is_hidden:
                field.widget.attrs["class"] = (
                    "form-check-input"
                    if isinstance(field.widget, forms.CheckboxInput)
                    else "form-control"
                )
            if isinstance(field, forms.DateTimeField):
                field.widget = forms.DateTimeInput(
                    format="%Y-%m-%dT%H:%M",
                    attrs={"type": "datetime-local", "class": "form-control"},
                )
                field.input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"]
            elif isinstance(field, forms.DateField):
                field.widget = forms.DateInput(
                    format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"}
                )

    def _post_clean(self):
        exclude = self._get_validation_exclusions()
        try:
            self.instance = construct_instance(
                self, self.instance, self._meta.fields, self._meta.exclude
            )
        except ValidationError as exc:
            self._update_errors(exc)
        try:
            self.instance.full_clean(
                exclude=exclude, validate_unique=False, validate_constraints=False
            )
        except ValidationError as exc:
            self._update_errors(exc)


class SignInForm(AuthenticationForm):
    username = forms.EmailField(
        label="Correo electrónico",
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "autocomplete": "username",
                "autofocus": True,
            }
        ),
    )
    password = forms.CharField(
        label="Contraseña",
        strip=False,
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "autocomplete": "current-password"}
        ),
    )
    error_messages = {
        "invalid_login": "No fue posible iniciar sesión. Comprueba tus credenciales.",
        "inactive": "No fue posible iniciar sesión. Comprueba tus credenciales.",
    }

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()


class FamilyRegistrationForm(forms.Form):
    first_name = forms.CharField(label="Nombres", max_length=150)
    last_name = forms.CharField(label="Apellidos", max_length=150)
    email = forms.EmailField(label="Correo electrónico")
    identification = forms.CharField(label="Documento de identidad", max_length=40)
    phone = forms.CharField(label="Teléfono", max_length=30)
    address = forms.CharField(label="Dirección", max_length=240, required=False)
    privacy_consent = forms.BooleanField(
        label="Autorizo el uso de estos datos para administrar y verificar mi cuenta familiar.",
        required=True,
    )
    password1 = forms.CharField(label="Contraseña", widget=forms.PasswordInput, strip=False)
    password2 = forms.CharField(label="Repite la contraseña", widget=forms.PasswordInput, strip=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
        self.fields["password1"].widget.attrs["autocomplete"] = "new-password"
        self.fields["password2"].widget.attrs["autocomplete"] = "new-password"

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean_identification(self):
        return self.cleaned_data["identification"].strip().upper()

    def clean_phone(self):
        return self.cleaned_data["phone"].strip()

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password1")
        confirmation = cleaned.get("password2")
        if password and confirmation and password != confirmation:
            self.add_error("password2", "Las contraseñas no coinciden.")
        if password and cleaned.get("email"):
            candidate = User(email=cleaned["email"], first_name=cleaned.get("first_name", ""), last_name=cleaned.get("last_name", ""))
            try:
                validate_password(password, candidate)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned


class FamilyResendForm(forms.Form):
    email = forms.EmailField(label="Correo electrónico")

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class MapImportForm(forms.Form):
    file = forms.FileField(label="Archivo CSV de coordenadas")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["file"].widget.attrs.update({"class": "form-control", "accept": ".csv,text/csv"})

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        if uploaded.size > 2 * 1024 * 1024:
            raise ValidationError("El CSV no puede superar 2 MB.")
        if not uploaded.name.lower().endswith(".csv"):
            raise ValidationError("Carga un archivo con extensión .csv.")
        return uploaded


class SpaceImportForm(MapImportForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["file"].label = "Archivo CSV de sepulturas"


class MapPlanForm(forms.Form):
    image_file = forms.FileField(label="Plano o imagen aérea en PNG")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["image_file"].widget.attrs.update(
            {"class": "form-control", "accept": ".png,image/png"}
        )
        self.image_bytes = None
        self.image_width = None
        self.image_height = None

    def clean_image_file(self):
        uploaded = self.cleaned_data["image_file"]
        if not uploaded.name.lower().endswith(".png"):
            raise ValidationError("El archivo debe tener extensión .png.")
        self.image_bytes = uploaded.read()
        try:
            self.image_width, self.image_height = inspect_plan_png(self.image_bytes)
        except InvalidPlanImage as exc:
            raise ValidationError(str(exc)) from exc
        return uploaded


class SpaceForm(RecordForm):
    revision = forms.IntegerField(widget=forms.HiddenInput, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        obj = self.instance
        if obj.pk and (
            obj.occupancies.exists()
            or obj.contracts.exists()
            or obj.reservations.exists()
        ):
            for name in ("code", "block", "row", "number", "kind"):
                self.fields[name].disabled = True
                self.fields[
                    name
                ].help_text = (
                    "Se conserva porque el espacio ya tiene registros asociados."
                )

    class Meta:
        model = Space
        fields = ["code", "block", "row", "number", "kind", "map_x", "map_y", "notes"]

    def clean_code(self):
        return self.cleaned_data["code"].strip().upper()


class PersonForm(RecordForm):
    class Meta:
        model = Person
        fields = [
            "first_name",
            "last_name",
            "identification",
            "birth_date",
            "death_date",
            "notes",
        ]


class ResponsibleForm(RecordForm):
    class Meta:
        model = Responsible
        fields = ["name", "identification", "phone", "email", "address"]


class LinkForm(RecordForm):
    class Meta:
        model = PersonResponsible
        fields = ["person", "responsible", "relationship", "principal"]


class ContractForm(RecordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields["terms"].initial = (
                "1. OBJETO. La administración asigna el uso de la sepultura identificada en este contrato durante su vigencia.\n\n"
                "2. VALOR Y PAGOS. El valor contractual y los abonos se registran en la factura y los recibos asociados. Cada abono reduce el saldo de la factura correspondiente.\n\n"
                "3. CUIDADO DE LA SEPULTURA. La familia responsable se compromete a conservar limpia y en buen estado la sepultura y sus elementos particulares, respetando las reglas de seguridad y convivencia del cementerio.\n\n"
                "4. MANTENIMIENTO COMÚN. La cuota mensual familiar, cuando se pacte, corresponde al servicio de mantenimiento de zonas comunes indicado por la administración. No sustituye la obligación familiar de cuidar la sepultura individual.\n\n"
                "5. VIGENCIA Y RENOVACIÓN. La vigencia es la indicada en el contrato. Toda renovación, cambio de tarifa o modificación deberá quedar registrada y aceptada por las partes.\n\n"
                "6. FIRMAS. Las partes revisarán este documento, completarán lugar y fecha, y firmarán cada ejemplar. Las condiciones particulares acordadas se consignan en este espacio.\n\n"
                "Condiciones particulares: ______________________________________________"
            )

    class Meta:
        model = Contract
        fields = [
            "number",
            "space",
            "responsible",
            "amount",
            "starts_on",
            "ends_on",
            "terms",
            "monthly_maintenance_fee",
        ]

    def clean_number(self):
        return self.cleaned_data["number"].strip().upper()


class ContractEditForm(RecordForm):
    class Meta:
        model = Contract
        fields = ["ends_on", "terms"]


class ContractDocumentForm(StyledForm):
    signed_copy = forms.FileField(
        label="Copia firmada escaneada",
        help_text="PDF, PNG o JPEG; máximo 8 MB. No es una firma electrónica.",
    )

    def clean_signed_copy(self):
        uploaded = self.cleaned_data["signed_copy"]
        content = uploaded.read()
        if len(content) > 8 * 1024 * 1024:
            raise ValidationError("El archivo no puede superar 8 MB.")
        if content.startswith(b"%PDF-") and b"%%EOF" in content[-2048:]:
            content_type = "application/pdf"
            extension = ".pdf"
        elif content.startswith(b"\xff\xd8\xff") and content.endswith(b"\xff\xd9"):
            content_type = "image/jpeg"
            extension = ".jpg"
        elif content.startswith(b"\x89PNG\r\n\x1a\n"):
            try:
                inspect_plan_png(content)
            except InvalidPlanImage as exc:
                raise ValidationError("El archivo PNG no es válido o supera los límites permitidos.") from exc
            content_type = "image/png"
            extension = ".png"
        else:
            raise ValidationError("Carga una copia escaneada en formato PDF, PNG o JPEG válido.")
        self.cleaned_data["signed_copy_bytes"] = content
        self.cleaned_data["signed_copy_type"] = content_type
        self.cleaned_data["signed_copy_extension"] = extension
        return uploaded


class ExpenseDocumentForm(ContractDocumentForm):
    signed_copy = forms.FileField(
        label="Factura o soporte del gasto",
        help_text="PDF, PNG o JPEG; máximo 8 MB. Se guarda de forma privada.",
    )


class ReservationForm(StyledForm):
    space = forms.ModelChoiceField(label="Sepultura", queryset=Space.objects.all())
    responsible = forms.ModelChoiceField(
        label="Responsable", queryset=Responsible.objects.all()
    )
    expires_on = forms.DateField(
        label="Reservada hasta", widget=forms.DateInput(attrs={"type": "date"})
    )
    amount = forms.DecimalField(
        label="Anticipo recibido",
        min_value=Decimal("0.01"),
        max_digits=14,
        decimal_places=2,
    )
    method = forms.ChoiceField(label="Método de pago", choices=Payment.Method.choices)
    reference = forms.CharField(label="Referencia o recibo", max_length=100)


class PaymentForm(RecordForm):
    class Meta:
        model = Payment
        fields = ["contract", "invoice", "amount", "method", "reference", "paid_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["contract"].required = True
        self.fields["contract"].queryset = Contract.objects.filter(state="ACTIVE")
        self.fields["invoice"].queryset = Invoice.objects.filter(contract__state="ACTIVE").select_related("contract")
        self.fields["invoice"].required = True
        self.fields["invoice"].label_from_instance = lambda invoice: (
            f"{invoice.number} · {invoice.get_kind_display()} · saldo {invoice.balance} {invoice.contract.currency}"
        )

    def clean(self):
        cleaned = super().clean()
        invoice, contract = cleaned.get("invoice"), cleaned.get("contract")
        if invoice and contract and invoice.contract_id != contract.pk:
            self.add_error("invoice", "Selecciona una factura del contrato elegido.")
        return cleaned


class ReservationRefundForm(StyledForm):
    amount = forms.DecimalField(
        label="Valor efectivamente devuelto", min_value=Decimal("0.01"),
        max_digits=14, decimal_places=2,
    )
    method = forms.ChoiceField(label="Método de devolución", choices=Payment.Method.choices)
    reference = forms.CharField(label="Referencia de transferencia, recibo o reversión", max_length=100)
    refunded_at = forms.DateTimeField(
        label="Fecha y hora de devolución",
        initial=timezone.now,
        widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local", "class": "form-control"}),
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"],
    )
    reason = forms.CharField(label="Motivo y autorización", widget=forms.Textarea)

    def clean_reference(self):
        return self.cleaned_data["reference"].strip()

    def clean_reason(self):
        return self.cleaned_data["reason"].strip()


class ExpenseForm(RecordForm):
    class Meta:
        model = OperatingExpense
        fields = ["category", "description", "supplier", "amount", "paid_on", "reference"]


class BurialForm(StyledForm):
    person = forms.ModelChoiceField(
        label="Persona fallecida", queryset=Person.objects.all()
    )
    space = forms.ModelChoiceField(label="Sepultura", queryset=Space.objects.all())
    contract = forms.ModelChoiceField(
        label="Contrato vigente", queryset=Contract.objects.filter(state="ACTIVE")
    )
    occurred_at = forms.DateTimeField(
        label="Fecha y hora de inhumación",
        initial=timezone.now,
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}
        ),
    )
    notes = forms.CharField(
        label="Responsable operativo y observaciones", widget=forms.Textarea
    )


class MovementForm(RecordForm):
    class Meta:
        model = Movement
        fields = [
            "occupancy",
            "kind",
            "destination",
            "destination_contract",
            "external_destination",
            "reason",
            "proposed_on",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["occupancy"].label = "Ocupación vigente"
        self.fields["occupancy"].queryset = Occupancy.objects.filter(
            ended_at__isnull=True
        ).select_related("person", "space")
        self.fields["occupancy"].label_from_instance = lambda o: (
            f"{o.space.code} · {o.person}"
        )
        self.fields["destination_contract"].queryset = Contract.objects.filter(
            state="ACTIVE"
        )


class UserForm(RecordForm):
    password = forms.CharField(
        label="Nueva contraseña",
        strip=False,
        required=False,
        widget=forms.PasswordInput,
        help_text="Mínimo 12 caracteres. Obligatoria al crear; vacía conserva la actual.",
    )

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "role", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = [
            choice for choice in User.Role.choices if choice[0] != User.Role.FAMILY
        ]

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class ZoneForm(RecordForm):
    class Meta:
        model = Zone
        fields = ["name"]


class BlockForm(RecordForm):
    class Meta:
        model = Block
        fields = ["zone", "name"]


class ActionForm(StyledForm):
    reason = forms.CharField(label="Motivo", widget=forms.Textarea, required=False)
    document_reference = forms.CharField(
        label="Referencia documental de autorización", required=False, max_length=240
    )
    occurred_at = forms.DateTimeField(
        label="Fecha y hora real de ejecución",
        required=False,
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}
        ),
    )


class ConditionForm(StyledForm):
    condition = forms.ChoiceField(
        label="Nueva condición", choices=Space.Condition.choices
    )
    reason = forms.CharField(label="Motivo", widget=forms.Textarea)
    revision = forms.IntegerField(widget=forms.HiddenInput)
