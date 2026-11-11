from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256
import csv
import io
import json
import uuid
from email import policy
from email.parser import BytesParser
from pathlib import Path
from django.conf import settings
from django.apps import apps
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import PasswordResetView
from django.core.exceptions import FieldDoesNotExist, PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import DecimalField, Exists, F, OuterRef, Prefetch, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.http import Http404, HttpResponse, JsonResponse
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.encoding import force_bytes, force_str
from django.utils.http import content_disposition_header
from django.utils.http import url_has_allowed_host_and_scheme, urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from . import forms, services
from .map_coordinates import MARKER_HEIGHT, MARKER_WIDTH, PositionIndex
from .models import (
    Audit,
    Block,
    Contract,
    ContractDocument,
    Event,
    ExpenseDocument,
    FamilyProfile,
    Invoice,
    MapPlan,
    LoginThrottle,
    Movement,
    Occupancy,
    OperatingExpense,
    Payment,
    Person,
    Reservation,
    Refund,
    Responsible,
    Space,
    User,
    Zone,
    STATUS_CHOICES,
)
from .permissions import can, may_read_contacts, may_read_finance, require
from .queries import (
    filter_spaces,
    person_query,
    reference_id,
    search_term,
    space_counts,
    spaces,
    text_query,
)
from .locks import transaction_lock


def data_only(form):
    return {
        key: value
        for key, value in form.cleaned_data.items()
        if key not in ("command_key", "revision")
    }


def form_error(form, exc):
    if isinstance(exc, IntegrityError):
        form.add_error(
            None,
            "La operación entra en conflicto con un registro existente. Recarga y verifica los datos.",
        )
    elif hasattr(exc, "error_dict"):
        for name, errors in exc.error_dict.items():
            form.add_error(name if name in form.fields else None, errors)
    else:
        form.add_error(None, exc)


@never_cache
@require_http_methods(["GET", "POST"])
def sign_in(request):
    if request.user.is_authenticated:
        return redirect("family_portal" if request.user.role == User.Role.FAMILY else "dashboard")
    form = forms.SignInForm(request, data=request.POST or None)
    if request.method == "POST":
        email = request.POST.get("username", "").strip().lower()
        keys = [
            sha256(f"{scope}:{value}".encode()).hexdigest()
            for scope, value in [
                ("email", email),
                ("ip", request.META.get("REMOTE_ADDR", "")),
            ]
        ]
        now = timezone.now()
        with transaction.atomic(), transaction_lock(43490002):
            entries = [LoginThrottle.objects.get_or_create(key=key)[0] for key in keys]
            for entry in entries:
                if now - entry.window_start >= timedelta(minutes=15):
                    entry.failures, entry.window_start = 0, now
                    entry.save()
            blocked = any(
                entry.failures >= limit for entry, limit in zip(entries, [5, 30])
            )
            if not blocked and form.is_valid():
                for entry in entries[:1]:
                    entry.delete()
                login(request, form.get_user())
                request.session["issued_at"] = int(now.timestamp())
                if request.user.role == User.Role.FAMILY:
                    return redirect("family_portal")
                target = request.POST.get("next", "")
                return redirect(
                    target
                    if url_has_allowed_host_and_scheme(
                        target, {request.get_host()}, require_https=request.is_secure()
                    )
                    else "dashboard"
                )
            for entry in entries:
                entry.failures += 1
                entry.save(update_fields=["failures"])
            if blocked:
                form.add_error(
                    None,
                    "No fue posible iniciar sesión. Espera 15 minutos antes de intentarlo nuevamente.",
                )
    return render(
        request,
        "registration/login.html",
        {"form": form, "next": request.GET.get("next", "")},
    )


@require_http_methods(["GET", "POST"])
def family_register(request):
    if request.user.is_authenticated:
        return redirect("family_portal" if request.user.role == User.Role.FAMILY else "dashboard")
    form = forms.FamilyRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        now = timezone.now()
        throttle_key = sha256(
            f"family-register:{request.META.get('REMOTE_ADDR', '')}".encode()
        ).hexdigest()
        with transaction.atomic(), transaction_lock(43490002):
            throttle, _ = LoginThrottle.objects.get_or_create(key=throttle_key)
            if now - throttle.window_start >= timedelta(minutes=15):
                throttle.failures, throttle.window_start = 0, now
            blocked = throttle.failures >= 8
            if not blocked:
                throttle.failures += 1
                throttle.save(update_fields=["failures", "window_start"])
        if blocked:
            form.add_error(None, "Por seguridad, espera 15 minutos antes de intentar registrarte de nuevo.")
        else:
            data = form.cleaned_data
            try:
                with transaction.atomic():
                    user = User(
                        email=data["email"],
                        first_name=data["first_name"].strip(),
                        last_name=data["last_name"].strip(),
                        role=User.Role.FAMILY,
                        is_active=False,
                    )
                    user.set_password(data["password1"])
                    user.save()
                    FamilyProfile.objects.create(
                        user=user,
                        identification=data["identification"],
                        phone=data["phone"],
                        address=data["address"].strip(),
                    )
            except IntegrityError:
                form.add_error(None, "No pudimos completar el registro con esos datos. Revisa el correo y el documento o contacta a la administración.")
            else:
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                verification_url = request.build_absolute_uri(
                    reverse("family_verify", kwargs={"uidb64": uid, "token": token})
                )
                try:
                    sent = send_mail(
                        subject="Confirma tu cuenta familiar · CementerioERP",
                        message=render_to_string(
                            "registration/family_verify.txt",
                            {"name": user.first_name, "verification_url": verification_url},
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[user.email],
                        fail_silently=False,
                    )
                    if not sent:
                        raise RuntimeError("El servidor de correo no aceptó el mensaje.")
                except Exception:
                    form.add_error(None, "Tu cuenta quedó pendiente de confirmación, pero no pudimos enviar el correo. Usa «Solicitar otro enlace» cuando el servicio de correo esté disponible.")
                else:
                    return render(request, "registration/family_register_sent.html", {"email": data["email"]})
    return render(request, "registration/family_register.html", {"form": form})


@require_GET
def family_privacy_notice(request):
    return render(request, "registration/family_privacy.html")


@require_http_methods(["GET", "POST"])
def family_resend_verification(request):
    if request.user.is_authenticated:
        return redirect("family_portal" if request.user.role == User.Role.FAMILY else "dashboard")
    form = forms.FamilyResendForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        ip = request.META.get("REMOTE_ADDR", "")
        throttle_key = sha256(f"family-resend:{ip}".encode()).hexdigest()
        now = timezone.now()
        with transaction.atomic(), transaction_lock(43490002):
            throttle, _ = LoginThrottle.objects.get_or_create(key=throttle_key)
            if now - throttle.window_start >= timedelta(minutes=15):
                throttle.failures, throttle.window_start = 0, now
            allowed = throttle.failures < 5
            if allowed:
                throttle.failures += 1
                throttle.save(update_fields=["failures", "window_start"])
        if allowed:
            user = User.objects.filter(
                email=form.cleaned_data["email"], role=User.Role.FAMILY, is_active=False
            ).first()
            profile = FamilyProfile.objects.filter(user=user, verified_at__isnull=True).first() if user else None
            if user and profile:
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                verification_url = request.build_absolute_uri(
                    reverse("family_verify", kwargs={"uidb64": uid, "token": token})
                )
                try:
                    send_mail(
                        subject="Confirma tu cuenta familiar · CementerioERP",
                        message=render_to_string(
                            "registration/family_verify.txt",
                            {"name": user.first_name, "verification_url": verification_url},
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[user.email],
                        fail_silently=False,
                    )
                except Exception:
                    pass
        return render(request, "registration/family_resend_result.html")
    return render(request, "registration/family_resend.html", {"form": form})


@require_http_methods(["GET", "POST"])
def family_verify(request, uidb64, token):
    try:
        user_id = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=user_id, role=User.Role.FAMILY)
        profile = FamilyProfile.objects.get(user=user)
    except (ValueError, TypeError, OverflowError, User.DoesNotExist, FamilyProfile.DoesNotExist):
        user = profile = None
    if user is None:
        return render(request, "registration/family_verify_result.html", {"result": "invalid"})
    if profile.verified_at:
        return render(request, "registration/family_verify_result.html", {"result": "verified"})
    if not default_token_generator.check_token(user, token):
        return render(request, "registration/family_verify_result.html", {"result": "invalid"})
    if request.method == "GET":
        return render(request, "registration/family_verify_result.html", {"result": "pending"})
    profile.verified_at = timezone.now()
    profile.save(update_fields=["verified_at"])
    user.is_active = True
    user.save(update_fields=["is_active"])
    return render(request, "registration/family_verify_result.html", {"result": "success"})


@login_required
def family_portal(request):
    if request.user.role != User.Role.FAMILY:
        return redirect("dashboard")
    profile = get_object_or_404(FamilyProfile.objects.select_related("responsible"), user=request.user)
    responsible = profile.responsible
    contracts = (
        Contract.objects.filter(responsible=responsible).select_related("space").annotate(
            family_paid=Coalesce(
                Sum(
                    "payments__amount",
                    filter=Q(payments__voided_at__isnull=True)
                    & (Q(payments__invoice__isnull=True) | Q(payments__invoice__kind=Invoice.Kind.CONTRACT)),
                ),
                Value(Decimal("0.00"), output_field=DecimalField(max_digits=14, decimal_places=2)),
            )
        ).prefetch_related(Prefetch(
            "documents",
            queryset=ContractDocument.objects.filter(is_current=True).defer("content"),
            to_attr="family_documents",
        ))
        if responsible else Contract.objects.none()
    )
    invoices = (
        Invoice.objects.filter(contract__responsible=responsible).select_related("contract", "contract__space").annotate(
            paid_total=Coalesce(
                Sum("payments__amount", filter=Q(payments__voided_at__isnull=True)),
                Value(Decimal("0.00"), output_field=DecimalField(max_digits=14, decimal_places=2)),
            )
        ).prefetch_related(Prefetch(
            "payments",
            queryset=Payment.objects.filter(voided_at__isnull=True).order_by("paid_at", "pk"),
        ))
        if responsible else Invoice.objects.none()
    )
    contract_rows = [
        {"contract": contract, "balance": contract.amount - contract.family_paid,
         "document": contract.family_documents[0] if contract.family_documents else None}
        for contract in contracts
    ]
    invoice_rows = [
        {"invoice": invoice, "balance": max(Decimal("0.00"), invoice.amount - invoice.paid_total),
         "state": "Pagada" if invoice.amount <= invoice.paid_total else "Vencida" if invoice.due_on < timezone.localdate() else "Pendiente",
         "payments": invoice.payments.all()}
        for invoice in invoices
    ]
    return render(request, "cemetery/family_portal.html", {
        "profile": profile, "contract_rows": contract_rows, "invoice_rows": invoice_rows,
    })


@login_required
def family_document_download(request, document_pk):
    if request.user.role != User.Role.FAMILY:
        raise Http404
    profile = get_object_or_404(FamilyProfile, user=request.user)
    document = get_object_or_404(
        ContractDocument.objects.select_related("contract"), pk=document_pk
    )
    if not profile.responsible_id or document.contract.responsible_id != profile.responsible_id:
        raise Http404
    response = HttpResponse(bytes(document.content), content_type=document.content_type)
    response["Content-Disposition"] = content_disposition_header(True, document.file_name)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
def family_receipt(request, pk):
    if request.user.role != User.Role.FAMILY:
        raise Http404
    profile = get_object_or_404(FamilyProfile, user=request.user)
    payment = get_object_or_404(
        Payment.objects.select_related("invoice__contract__space", "invoice__contract__responsible"),
        pk=pk,
        invoice__contract__responsible_id=profile.responsible_id,
    )
    return render(request, "cemetery/family_receipt.html", {"payment": payment})


@login_required
@require_http_methods(["GET", "POST"])
def family_accounts(request):
    require(request.user, "users")
    if request.method == "POST":
        try:
            profile_id = int(request.POST.get("profile_id", ""))
        except (TypeError, ValueError):
            profile_id = None
        if request.POST.get("action") in ("deactivate", "activate") and profile_id:
            account_action = request.POST["action"]
            confirmation_name = "confirm_deactivation" if account_action == "deactivate" else "confirm_activation"
            if request.POST.get(confirmation_name) != "yes":
                messages.error(request, "Confirma el cambio de acceso de la cuenta.")
                return redirect("family_accounts")
            with transaction.atomic(), transaction_lock(43490001):
                profile = FamilyProfile.objects.select_for_update().select_related("user").filter(pk=profile_id).first()
                desired_active = account_action == "activate"
                if profile and profile.user.is_active != desired_active and (not desired_active or profile.verified_at):
                    profile.user.is_active = desired_active
                    profile.user.save(update_fields=["is_active"])
                    Audit.objects.create(
                        actor=request.user,
                        action=f"family.{account_action}",
                        target=f"cemetery.FamilyProfile:{profile.pk}",
                        detail={"account_email": profile.user.email},
                    )
                    messages.success(request, "Acceso familiar actualizado.")
                else:
                    messages.error(request, "La cuenta no existe, ya tiene ese estado o aún no confirmó su correo.")
            return redirect("family_accounts")
        if not profile_id or request.POST.get("confirm_identity") != "yes":
            messages.error(request, "Confirma que cotejaste el documento de identidad antes de vincular.")
        else:
            with transaction.atomic(), transaction_lock(43490001):
                profile = FamilyProfile.objects.select_for_update().filter(pk=profile_id).first()
                responsible = Responsible.objects.filter(
                    identification__iexact=profile.identification
                ).first() if profile and profile.verified_at else None
                if not profile or not profile.verified_at:
                    messages.error(request, "La cuenta debe verificar su correo antes de vincularse.")
                elif profile.responsible_id:
                    messages.error(request, "La cuenta ya está vinculada a un responsable.")
                elif not responsible:
                    messages.error(request, "No existe un responsable con ese documento. Revisa el registro antes de vincular.")
                elif FamilyProfile.objects.filter(responsible=responsible).exists():
                    messages.error(request, "Ese responsable ya está vinculado a otra cuenta.")
                else:
                    profile.responsible = responsible
                    profile.save(update_fields=["responsible"])
                    Audit.objects.create(
                        actor=request.user,
                        action="family.link",
                        target=f"cemetery.FamilyProfile:{profile.pk}",
                        detail={"responsible_id": responsible.pk, "identification_checked": True},
                    )
                    messages.success(request, "Cuenta familiar vinculada. Ahora puede consultar sus propios contratos y facturas.")
        return redirect("family_accounts")
    profiles = FamilyProfile.objects.select_related("user", "responsible").order_by("-created_at")
    for profile in profiles:
        profile.matching_responsible = Responsible.objects.filter(
            identification__iexact=profile.identification
        ).first()
    return render(request, "cemetery/family_accounts.html", {"profiles": profiles})


@require_POST
def sign_out(request):
    logout(request)
    return redirect("login")


@login_required
def dashboard(request):
    if request.user.role == User.Role.FAMILY:
        return redirect("family_portal")
    counts = space_counts()
    today = timezone.localdate()
    context = {
        "counts": counts,
        "today": today,
        "map_plan": MapPlan.objects.defer("image").filter(pk=1).first(),
        "recent": Event.objects.select_related("space").order_by("-occurred_at", "-pk")[
            :6
        ],
    }
    if may_read_finance(request.user):
        month_start = today.replace(day=1)
        income = Payment.objects.filter(
            voided_at__isnull=True, paid_at__date__gte=month_start, paid_at__date__lte=today
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        refunds = Refund.objects.filter(
            refunded_at__date__gte=month_start, refunded_at__date__lte=today
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        expenses = OperatingExpense.objects.filter(
            paid_on__gte=month_start, paid_on__lte=today
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        unpaid_invoices = Invoice.objects.annotate(
            paid_total=Coalesce(
                Sum("payments__amount", filter=Q(payments__voided_at__isnull=True)),
                Value(Decimal("0.00"), output_field=DecimalField(max_digits=14, decimal_places=2)),
            )
        ).filter(amount__gt=F("paid_total"))
        context["finance_summary"] = {
            "month_start": month_start,
            "income": income,
            "refunds": refunds,
            "expenses": expenses,
            "net": income - refunds - expenses,
            "overdue_count": unpaid_invoices.filter(due_on__lt=today).count(),
            "open_count": unpaid_invoices.count(),
        }
        context["expiring"] = Contract.objects.filter(
            state="ACTIVE",
            ends_on__lte=today + timedelta(days=settings.CEMETERY_EXPIRY_DAYS),
        ).select_related("space")[:8]
    return render(request, "cemetery/dashboard.html", context)


class RecoverAccessView(PasswordResetView):
    """Límite persistente con la misma respuesta para todas las cuentas."""

    def form_valid(self, form):
        now = timezone.now()
        values = [
            ("reset-email", form.cleaned_data["email"].strip().lower(), 3),
            ("reset-ip", self.request.META.get("REMOTE_ADDR", ""), 12),
        ]
        with transaction.atomic(), transaction_lock(43490002):
            entries = []
            for scope, value, limit in values:
                key = sha256(f"{scope}:{value}".encode()).hexdigest()
                entry, _ = LoginThrottle.objects.get_or_create(key=key)
                if now - entry.window_start >= timedelta(minutes=15):
                    entry.failures, entry.window_start = 0, now
                entries.append((entry, limit))
            blocked = any(entry.failures >= limit for entry, limit in entries)
            for entry, _ in entries:
                entry.failures += 1
                entry.save()
        if blocked:
            return redirect(self.get_success_url())
        self.extra_email_context = {
            **(self.extra_email_context or {}),
            "cemetery_name": settings.CEMETERY_NAME,
        }
        return super().form_valid(form)


LISTS = {
    "sepulturas": (Space, "Sepulturas", "spaces"),
    "personas": (Person, "Personas fallecidas", "people"),
    "responsables": (Responsible, "Familiares y responsables", "contacts"),
    "contratos": (Contract, "Contratos", "contracts"),
    "reservas": (Reservation, "Reservas pagadas", "finance"),
    "pagos": (Payment, "Pagos y recibos", "finance"),
    "facturas": (Invoice, "Facturas", "finance"),
    "gastos": (OperatingExpense, "Gastos operativos", "finance"),
    "movimientos": (Movement, "Exhumaciones y traslados", "operations"),
    "usuarios": (User, "Usuarios y permisos", "users"),
    "zonas": (Zone, "Zonas", "spaces"),
    "bloques": (Block, "Bloques", "spaces"),
    "auditoria": (Audit, "Auditoría", "audit"),
}


def read_access(user, kind):
    if kind == "sepulturas":
        return
    if kind == "personas" and (can(user, "people") or may_read_contacts(user)):
        return
    if kind in ("contratos", "pagos", "reservas", "facturas", "gastos") and may_read_finance(user):
        return
    require(user, LISTS[kind][2])


@login_required
def listing(request, kind):
    if kind not in LISTS:
        from django.http import Http404

        raise Http404
    model, title, capability = LISTS[kind]
    read_access(request.user, kind)
    invalid_search = False
    try:
        q = search_term(request.GET.get("q", ""))
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
        q, invalid_search = "", True
    qs = model.objects.all()
    headers = []
    if kind == "sepulturas":
        try:
            qs = filter_spaces(spaces(), request.GET)
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
            qs = spaces().none()
        headers = ["Código", "Ubicación", "Tipo", "Estado"]
    elif kind == "personas":
        qs = qs.filter(person_query(q)) if q else qs
        headers = ["Persona", "Fallecimiento", "Identificación"]
    elif kind == "responsables":
        qs = qs.filter(text_query(q, "name", "identification", "phone", "email"))
        headers = ["Responsable", "Identificación", "Teléfono", "Correo"]
    elif kind == "contratos":
        qs = qs.select_related("space", "responsible").filter(
            text_query(q, "number", "space__code", "responsible__name")
        )
        if request.GET.get("state") in Contract.State.values:
            qs = qs.filter(state=request.GET["state"])
        if request.GET.get("validity") == "expired":
            qs = qs.filter(state="ACTIVE", ends_on__lt=timezone.localdate())
        elif request.GET.get("validity") == "soon":
            qs = qs.filter(
                state="ACTIVE",
                starts_on__lte=timezone.localdate(),
                ends_on__gte=timezone.localdate(),
                ends_on__lte=timezone.localdate()
                + timedelta(days=settings.CEMETERY_EXPIRY_DAYS),
            )
        headers = [
            "Contrato",
            "Sepultura",
            "Responsable",
            "Inicio",
            "Vencimiento",
            "Plazo restante",
            "Vigencia",
        ]
    elif kind == "reservas":
        qs = qs.select_related("space", "responsible").filter(
            text_query(q, "space__code", "responsible__name")
        )
        headers = ["Reserva", "Sepultura", "Responsable", "Hasta", "Estado"]
    elif kind == "pagos":
        qs = qs.select_related("contract", "reservation").filter(
            Q(reference__icontains=q) | Q(contract__number__icontains=q)
        )
        headers = ["Recibo", "Contrato / reserva", "Valor", "Fecha", "Estado"]
    elif kind == "facturas":
        qs = qs.select_related("contract", "contract__responsible").filter(
            Q(number__icontains=q) | Q(contract__number__icontains=q) | Q(description__icontains=q)
        )
        headers = ["Factura", "Contrato", "Concepto", "Total", "Estado"]
    elif kind == "gastos":
        qs = qs.filter(Q(number__icontains=q) | Q(description__icontains=q) | Q(supplier__icontains=q))
        headers = ["Consecutivo", "Categoría", "Descripción", "Valor", "Fecha"]
    elif kind == "movimientos":
        qs = qs.select_related("occupancy__person", "occupancy__space").filter(
            text_query(
                q,
                "occupancy__space__code",
                "occupancy__person__first_name",
                "occupancy__person__last_name",
                "occupancy__person__identification",
            )
        )
        headers = ["Solicitud", "Persona", "Origen", "Tipo", "Estado"]
    elif kind == "usuarios":
        qs = qs.exclude(role=User.Role.FAMILY).filter(
            text_query(q, "email", "first_name", "last_name")
        )
        headers = ["Usuario", "Correo", "Perfil", "Acceso"]
    elif kind == "zonas":
        qs = qs.filter(text_query(q, "name"))
        headers = ["Nombre"]
    elif kind == "bloques":
        qs = qs.select_related("zone").filter(text_query(q, "name", "zone__name"))
        headers = ["Zona", "Bloque"]
    elif kind == "auditoria":
        qs = qs.select_related("actor").filter(
            Q(action__icontains=q) | Q(target__icontains=q)
        )
        headers = ["Fecha", "Acción", "Registro", "Usuario"]
    if invalid_search:
        qs = qs.none()
    page = Paginator(qs, 20).get_page(request.GET.get("page"))
    rows = []
    for obj in page:
        detail_url = None
        if kind == "sepulturas":
            values = [
                obj.code,
                f"{obj.block} · F{obj.row} / {obj.number}",
                obj.get_kind_display(),
                obj.status_label,
            ]
            detail_url = reverse("space_detail", args=[obj.pk])
        elif kind == "personas":
            values = [str(obj), obj.death_date, obj.identification or "Sin documento"]
            detail_url = reverse("person_detail", args=[obj.pk])
        elif kind == "responsables":
            values = [obj.name, obj.identification, obj.phone, obj.email or "—"]
        elif kind == "contratos":
            values = [
                obj.number,
                obj.space.code,
                obj.responsible.name,
                obj.starts_on,
                obj.ends_on,
                obj.expiry_label,
                obj.validity,
            ]
            detail_url = reverse("contract_detail", args=[obj.pk])
        elif kind == "reservas":
            values = [
                f"R-{obj.pk}",
                obj.space.code,
                obj.responsible.name,
                obj.expires_on,
                obj.state_label,
            ]
            detail_url = reverse("reservation_detail", args=[obj.pk])
        elif kind == "pagos":
            values = [
                f"P-{obj.pk}",
                obj.contract.number if obj.contract else f"R-{obj.reservation_id}",
                obj.amount,
                obj.paid_at,
                "Anulado" if obj.voided_at else "Válido",
            ]
            detail_url = reverse("payment_detail", args=[obj.pk])
        elif kind == "facturas":
            values = [obj.number, obj.contract.number, obj.get_kind_display(), obj.amount, obj.state_label]
            detail_url = reverse("invoice_detail", args=[obj.pk])
        elif kind == "gastos":
            values = [obj.number, obj.get_category_display(), obj.description, obj.amount, obj.paid_on]
            detail_url = reverse("expense_detail", args=[obj.pk])
        elif kind == "movimientos":
            values = [
                f"M-{obj.pk}",
                str(obj.occupancy.person),
                obj.occupancy.space.code,
                obj.get_kind_display(),
                obj.get_state_display(),
            ]
            detail_url = reverse("movement_detail", args=[obj.pk])
        elif kind == "usuarios":
            values = [
                str(obj),
                obj.email,
                obj.get_role_display(),
                "Activo" if obj.is_active else "Inactivo",
            ]
        elif kind == "zonas":
            values = [obj.name]
        elif kind == "bloques":
            values = [obj.zone.name, obj.name]
        else:
            values = [obj.created_at, obj.action, obj.target, str(obj.actor)]
            detail_url = reverse("audit_detail", args=[obj.pk])
        edit_url = (
            reverse("edit_record", args=[kind, obj.pk])
            if kind in ("responsables", "usuarios") and can(request.user, capability)
            else None
        )
        rows.append({"values": values, "url": detail_url or edit_url})
    params = request.GET.copy()
    params.pop("page", None)
    return render(
        request,
        "cemetery/list.html",
        {
            "title": title,
            "kind": kind,
            "page": page,
            "rows": rows,
            "headers": headers,
            "querystring": params.urlencode(),
            "create_url": reverse("new_record", args=[kind])
            if kind not in ("auditoria", "facturas") and can(request.user, capability)
            else None,
            "zones": Zone.objects.all() if kind == "sepulturas" else [],
            "blocks": Block.objects.select_related("zone")
            if kind == "sepulturas"
            else [],
            "status_choices": STATUS_CHOICES,
            "kind_choices": Space.Kind.choices,
        },
    )


FORM_MAP = {
    "sepulturas": (forms.SpaceForm, services.save_space),
    "personas": (forms.PersonForm, services.save_person),
    "responsables": (forms.ResponsibleForm, services.save_responsible),
    "contratos": (forms.ContractForm, services.create_contract),
    "reservas": (forms.ReservationForm, services.create_reservation),
    "pagos": (forms.PaymentForm, services.record_payment),
    "gastos": (forms.ExpenseForm, services.record_expense),
    "movimientos": (forms.MovementForm, services.request_movement),
    "usuarios": (forms.UserForm, services.save_user),
    "zonas": (forms.ZoneForm, None),
    "bloques": (forms.BlockForm, None),
}


@login_required
@require_http_methods(["GET", "POST"])
def edit_record(request, kind, pk=None):
    if kind not in FORM_MAP:
        raise PermissionDenied
    model, title, capability = LISTS[kind]
    require(request.user, capability)
    if pk and kind not in (
        "sepulturas",
        "personas",
        "responsables",
        "usuarios",
        "contratos",
    ):
        raise PermissionDenied
    obj = get_object_or_404(model, pk=pk) if pk else None
    form_class, service = FORM_MAP[kind]
    if pk and kind == "contratos":
        form_class, service = forms.ContractEditForm, services.update_contract
    kwargs = {"instance": obj} if issubclass(form_class, forms.RecordForm) else {}
    initial = {"revision": obj.revision} if kind == "sepulturas" and obj else {}
    for field in ("space", "person", "contract", "invoice"):
        try:
            key = reference_id(request.GET.get(field, ""))
        except ValidationError:
            messages.error(request, "El registro indicado en el enlace no es válido.")
            continue
        if key is not None:
            initial[field] = key
            if field == "invoice" and kind == "pagos":
                invoice = Invoice.objects.filter(pk=key).first()
                if invoice:
                    initial["contract"] = invoice.contract_id
    form = form_class(request.POST or None, initial=initial, **kwargs)
    if request.method == "POST" and form.is_valid():
        try:
            data = data_only(form)
            key = form.cleaned_data["command_key"]
            if kind in ("zonas", "bloques"):
                result = services.save_catalog(request.user, key, model, data)
            elif pk and kind == "contratos":
                result = service(request.user, key, pk, data)
            elif kind == "sepulturas":
                result = service(
                    request.user,
                    key,
                    data,
                    pk=pk,
                    revision=form.cleaned_data.get("revision"),
                )
            elif pk:
                result = service(request.user, key, data, pk=pk)
            else:
                result = service(request.user, key, data)
            messages.success(request, "Operación registrada correctamente.")
            details = {
                "sepulturas": "space_detail",
                "personas": "person_detail",
                "contratos": "contract_detail",
                "reservas": "reservation_detail",
                "pagos": "payment_detail",
                "movimientos": "movement_detail",
            }
            if kind in details:
                return redirect(details[kind], pk=result["id"])
            return redirect("listing", kind=kind)
        except (ValidationError, IntegrityError) as exc:
            form_error(form, exc)
    return render(
        request,
        "cemetery/form.html",
        {
            "form": form,
            "title": f"{'Editar' if pk else 'Registrar'} · {title}",
            "back_url": reverse("listing", args=[kind]),
        },
    )


@login_required
def space_detail(request, pk):
    space = get_object_or_404(spaces(), pk=pk)
    events = space.events.select_related("person", "actor")
    if request.GET.get("type"):
        events = events.filter(kind=request.GET["type"])
    if may_read_contacts(request.user) and request.GET.get("person"):
        try:
            events = events.filter(person_query(request.GET["person"], "person__"))
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
            events = events.none()
    dates = {}
    for field, lookup in [
        ("from", "occurred_at__date__gte"),
        ("to", "occurred_at__date__lte"),
    ]:
        raw_date = request.GET.get(field, "")
        try:
            date = parse_date(raw_date)
        except ValueError:
            date = None
        if raw_date and date is None:
            messages.error(
                request,
                "Revisa las fechas del filtro: usa fechas válidas en formato año-mes-día.",
            )
            events = events.none()
        elif date:
            dates[field] = date
            events = events.filter(**{lookup: date})
    if dates.get("from") and dates.get("to") and dates["from"] > dates["to"]:
        messages.error(
            request, "La fecha inicial del filtro no puede ser posterior a la final."
        )
        events = events.none()
    if not may_read_contacts(request.user):
        # La consulta básica no recibe personas, motivos, autores ni datos financieros.
        events = events.filter(
            kind__in=["SPACE_CREATED", "SPACE_UPDATED", "CONDITION_CHANGED"]
        )
    page = Paginator(events, 20).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    occupancy = (
        space.occupancies.select_related("person", "contract")
        .filter(ended_at__isnull=True)
        .first()
        if may_read_contacts(request.user)
        else None
    )
    return render(
        request,
        "cemetery/space.html",
        {
            "space": space,
            "occupancy": occupancy,
            "page": page,
            "querystring": params.urlencode(),
            "contracts": space.contracts.select_related("responsible")
            if may_read_finance(request.user)
            else [],
            "event_types": [
                (code, dict(Event.Kind.choices).get(code, "Otro evento"))
                for code in space.events.values_list("kind", flat=True)
                .distinct()
                .order_by("kind")
            ]
            if may_read_contacts(request.user)
            else [],
        },
    )


@login_required
def person_detail(request, pk):
    read_access(request.user, "personas")
    person = get_object_or_404(Person, pk=pk)
    return render(
        request,
        "cemetery/person.html",
        {
            "person": person,
            "occupancies": person.occupancies.select_related("space").order_by(
                "-started_at", "-pk"
            ),
            "links": person.responsible_links.select_related("responsible")
            if may_read_contacts(request.user)
            else [],
        },
    )


@login_required
@require_GET
def audit_detail(request, pk):
    require(request.user, "audit")
    entry = get_object_or_404(Audit.objects.select_related("actor"), pk=pk)
    previous, current = (
        entry.detail.get("previous") or {},
        entry.detail.get("new") or {},
    )
    try:
        model = apps.get_model(entry.target.split(":", 1)[0])
    except (LookupError, ValueError):
        model = None
    changes = []
    for name in sorted(set(previous) | set(current)):
        if previous.get(name) == current.get(name):
            continue
        try:
            field = model._meta.get_field(name) if model else None
        except FieldDoesNotExist:
            field = None

        def display(value):
            if value is None:
                return "—"
            if isinstance(value, bool):
                return "Sí" if value else "No"
            if field is not None and field.choices:
                return dict(field.flatchoices).get(value, value)
            return "(vacío)" if value == "" else value

        changes.append(
            {
                "label": field.verbose_name if field else name,
                "previous": display(previous.get(name)),
                "new": display(current.get(name)),
            }
        )
    extra = {
        key: value
        for key, value in entry.detail.items()
        if key not in ("previous", "new")
    }
    return render(
        request,
        "cemetery/audit.html",
        {
            "entry": entry,
            "changes": changes,
            "extra": json.dumps(extra, ensure_ascii=False, indent=2) if extra else "",
        },
    )


@login_required
@require_GET
def academic_mailbox(request):
    require(request.user, "users")
    if not getattr(settings, "ACADEMIC_MODE", False):
        from django.http import Http404

        raise Http404
    directory = Path(settings.ACADEMIC_MAIL_ROOT)
    files = sorted(
        directory.glob("*.eml"), key=lambda path: path.stat().st_mtime, reverse=True
    )[:20]
    mailbox = []
    for path in files:
        message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
        body = message.get_body(preferencelist=("plain",))
        mailbox.append(
            {
                "subject": str(message.get("Subject", "")),
                "to": str(message.get("To", "")),
                "date": str(message.get("Date", "")),
                "body": body.get_content() if body else "Sin cuerpo de texto.",
            }
        )
    return render(request, "cemetery/academic_mail.html", {"mailbox": mailbox})


@login_required
@require_http_methods(["GET", "POST"])
def link_person(request):
    require(request.user, "contacts")
    form = forms.LinkForm(
        request.POST or None, initial={"person": request.GET.get("person")}
    )
    if request.method == "POST" and form.is_valid():
        try:
            result = services.link_responsible(
                request.user, form.cleaned_data["command_key"], data_only(form)
            )
            messages.success(request, "Responsable vinculado.")
            return redirect("person_detail", pk=result["id"])
        except (ValidationError, IntegrityError) as exc:
            form_error(form, exc)
    return render(
        request,
        "cemetery/form.html",
        {
            "form": form,
            "title": "Vincular responsable",
            "back_url": reverse("listing", args=["personas"]),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def burial(request):
    require(request.user, "operations")
    initial = {
        field: request.GET[field]
        for field in ("person", "space")
        if request.GET.get(field, "").isdigit()
    }
    form = forms.BurialForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            result = services.bury(
                request.user, form.cleaned_data["command_key"], data_only(form)
            )
            messages.success(
                request, "Inhumación confirmada. Ubicación e historial actualizados."
            )
            return redirect("space_detail", pk=result["space_id"])
        except (ValidationError, IntegrityError) as exc:
            form_error(form, exc)
    return render(
        request,
        "cemetery/form.html",
        {
            "form": form,
            "title": "Registrar inhumación",
            "back_url": reverse("listing", args=["sepulturas"]),
        },
    )


@login_required
def contract_detail(request, pk):
    read_access(request.user, "contratos")
    obj = get_object_or_404(
        Contract.objects.select_related("space", "responsible").prefetch_related(
            Prefetch(
                "payments",
                queryset=Payment.objects.select_related("created_by"),
                to_attr="payment_rows",
            )
        ),
        pk=pk,
    )
    paid = sum(
        (payment.amount for payment in obj.payment_rows if payment.voided_at is None),
        Decimal("0.00"),
    )
    return render(
        request,
        "cemetery/contract.html",
        {
            "contract": obj,
            "payments": obj.payment_rows,
            "invoices": obj.invoices.all(),
            "documents": obj.documents.select_related("uploaded_by").all(),
            "current_document": obj.documents.filter(is_current=True).select_related("uploaded_by").first(),
            "document_form": forms.ContractDocumentForm(),
            "paid": paid,
            "balance": obj.amount - paid,
            "command_key": uuid.uuid4(),
        },
    )


@login_required
def contract_print(request, pk):
    read_access(request.user, "contratos")
    obj = get_object_or_404(Contract.objects.select_related("space", "responsible"), pk=pk)
    return render(request, "cemetery/contract_print.html", {"contract": obj})


@login_required
@require_POST
def contract_document_upload(request, pk):
    require(request.user, "contracts")
    get_object_or_404(Contract, pk=pk)
    form = forms.ContractDocumentForm(request.POST, request.FILES)
    if not form.is_valid():
        errors = " ".join(str(error) for error in form.errors.get("signed_copy", []))
        messages.error(request, errors or "No se pudo validar el archivo.")
        return redirect("contract_detail", pk=pk)

    uploaded = form.cleaned_data["signed_copy"]
    safe_name = uploaded.name.replace("\\", "/").split("/")[-1]
    stem = Path(safe_name).stem.strip()
    stem = "".join(char for char in stem if char.isalnum() or char in " ._-").strip(" .")
    stored_name = f"{(stem or 'copia-firmada')[:170]}{form.cleaned_data['signed_copy_extension']}"
    content = form.cleaned_data["signed_copy_bytes"]
    try:
        with transaction.atomic(), transaction_lock(43490001):
            contract = Contract.objects.select_for_update().get(pk=pk)
            previous = contract.documents.filter(is_current=True).first()
            version = (
                contract.documents.order_by("-version").values_list("version", flat=True).first() or 0
            ) + 1
            contract.documents.filter(is_current=True).update(is_current=False)
            document = ContractDocument.objects.create(
                contract=contract,
                version=version,
                file_name=stored_name,
                content_type=form.cleaned_data["signed_copy_type"],
                content=content,
                sha256=sha256(content).hexdigest(),
                uploaded_by=request.user,
            )
            services.audit(
                request.user,
                "contract.document.upload",
                document,
                contract=contract.number,
                version=version,
                replaced_document_id=previous.pk if previous else None,
                sha256=document.sha256,
            )
    except (Contract.DoesNotExist, IntegrityError):
        messages.error(request, "No se guardó la copia. Recarga el contrato e inténtalo de nuevo.")
        return redirect("contract_detail", pk=pk)
    messages.success(request, f"Copia firmada v{version} guardada en el expediente.")
    return redirect("contract_detail", pk=pk)


@login_required
@require_GET
def contract_document_download(request, pk, document_pk):
    read_access(request.user, "contratos")
    document = get_object_or_404(
        ContractDocument.objects.select_related("contract"),
        pk=document_pk,
        contract_id=pk,
    )
    response = HttpResponse(bytes(document.content), content_type=document.content_type)
    response["Content-Disposition"] = content_disposition_header(True, document.file_name)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
def expense_detail(request, pk):
    read_access(request.user, "gastos")
    expense = get_object_or_404(OperatingExpense.objects.select_related("created_by"), pk=pk)
    return render(
        request,
        "cemetery/expense.html",
        {
            "expense": expense,
            "documents": expense.documents.select_related("uploaded_by").all(),
            "current_document": expense.documents.filter(is_current=True).select_related("uploaded_by").first(),
            "document_form": forms.ExpenseDocumentForm(),
        },
    )


@login_required
@require_POST
def expense_document_upload(request, pk):
    require(request.user, "finance")
    get_object_or_404(OperatingExpense, pk=pk)
    form = forms.ExpenseDocumentForm(request.POST, request.FILES)
    if not form.is_valid():
        errors = " ".join(str(error) for error in form.errors.get("signed_copy", []))
        messages.error(request, errors or "No se pudo validar el archivo.")
        return redirect("expense_detail", pk=pk)

    uploaded = form.cleaned_data["signed_copy"]
    safe_name = uploaded.name.replace("\\", "/").split("/")[-1]
    stem = Path(safe_name).stem.strip()
    stem = "".join(char for char in stem if char.isalnum() or char in " ._-").strip(" .")
    stored_name = f"{(stem or 'soporte-gasto')[:170]}{form.cleaned_data['signed_copy_extension']}"
    content = form.cleaned_data["signed_copy_bytes"]
    try:
        with transaction.atomic(), transaction_lock(43490001):
            expense = OperatingExpense.objects.select_for_update().get(pk=pk)
            previous = expense.documents.filter(is_current=True).first()
            version = (
                expense.documents.order_by("-version").values_list("version", flat=True).first() or 0
            ) + 1
            expense.documents.filter(is_current=True).update(is_current=False)
            document = ExpenseDocument.objects.create(
                expense=expense,
                version=version,
                file_name=stored_name,
                content_type=form.cleaned_data["signed_copy_type"],
                content=content,
                sha256=sha256(content).hexdigest(),
                uploaded_by=request.user,
            )
            services.audit(
                request.user,
                "expense.document.upload",
                document,
                expense=expense.number,
                version=version,
                replaced_document_id=previous.pk if previous else None,
                sha256=document.sha256,
            )
    except (OperatingExpense.DoesNotExist, IntegrityError):
        messages.error(request, "No se guardó el soporte. Recarga el gasto e inténtalo de nuevo.")
        return redirect("expense_detail", pk=pk)
    messages.success(request, f"Soporte del gasto v{version} guardado en el expediente.")
    return redirect("expense_detail", pk=pk)


@login_required
@require_GET
def expense_document_download(request, pk, document_pk):
    read_access(request.user, "gastos")
    document = get_object_or_404(
        ExpenseDocument.objects.select_related("expense"),
        pk=document_pk,
        expense_id=pk,
    )
    response = HttpResponse(bytes(document.content), content_type=document.content_type)
    response["Content-Disposition"] = content_disposition_header(True, document.file_name)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
def invoice_detail(request, pk):
    read_access(request.user, "facturas")
    obj = get_object_or_404(Invoice.objects.select_related("contract", "contract__space", "contract__responsible"), pk=pk)
    return render(request, "cemetery/invoice.html", {"invoice": obj, "payments": obj.payments.select_related("created_by")})


@login_required
@require_GET
def finance_portfolio(request):
    read_access(request.user, "facturas")
    today = timezone.localdate()
    unpaid = Invoice.objects.select_related(
        "contract", "contract__space", "contract__responsible"
    ).annotate(
        paid_total=Coalesce(
            Sum("payments__amount", filter=Q(payments__voided_at__isnull=True)),
            Value(Decimal("0.00"), output_field=DecimalField(max_digits=14, decimal_places=2)),
        )
    ).filter(amount__gt=F("paid_total")).order_by("due_on", "number")

    buckets = {
        "current": {"label": "Por vencer", "count": 0, "balance": Decimal("0.00")},
        "days_1_30": {"label": "Vencida · 1–30 días", "count": 0, "balance": Decimal("0.00")},
        "days_31_60": {"label": "Vencida · 31–60 días", "count": 0, "balance": Decimal("0.00")},
        "days_61_90": {"label": "Vencida · 61–90 días", "count": 0, "balance": Decimal("0.00")},
        "days_over_90": {"label": "Vencida · más de 90 días", "count": 0, "balance": Decimal("0.00")},
    }
    rows = []
    total_balance = Decimal("0.00")
    for invoice in unpaid:
        balance = invoice.amount - invoice.paid_total
        days_late = max(0, (today - invoice.due_on).days)
        if days_late == 0:
            bucket_key = "current"
        elif days_late <= 30:
            bucket_key = "days_1_30"
        elif days_late <= 60:
            bucket_key = "days_31_60"
        elif days_late <= 90:
            bucket_key = "days_61_90"
        else:
            bucket_key = "days_over_90"
        buckets[bucket_key]["count"] += 1
        buckets[bucket_key]["balance"] += balance
        total_balance += balance
        rows.append({
            "invoice": invoice,
            "balance": balance,
            "days_late": days_late,
            "bucket": buckets[bucket_key]["label"],
        })

    if request.GET.get("format") == "csv":
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="cartera-cementerio.csv"'
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow(["Factura", "Contrato", "Responsable", "Sepultura", "Concepto", "Vence", "Total", "Abonado", "Saldo", "Días de mora"])
        def safe_cell(value):
            value = str(value)
            return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value
        for row in rows:
            invoice = row["invoice"]
            writer.writerow([
                safe_cell(invoice.number), safe_cell(invoice.contract.number),
                safe_cell(invoice.contract.responsible.name), safe_cell(invoice.contract.space.code),
                safe_cell(invoice.description), invoice.due_on.isoformat(),
                invoice.amount, invoice.paid_total, row["balance"], row["days_late"],
            ])
        return response

    page = Paginator(rows, 50).get_page(request.GET.get("page"))
    return render(request, "cemetery/finance_portfolio.html", {
        "buckets": buckets.values(),
        "total_balance": total_balance,
        "open_count": len(rows),
        "page": page,
        "today": today,
    })


@login_required
def reservation_detail(request, pk):
    read_access(request.user, "reservas")
    obj = get_object_or_404(
        Reservation.objects.select_related("space", "responsible"), pk=pk
    )
    payments = obj.payments.prefetch_related(
        Prefetch("refunds", queryset=Refund.objects.select_related("created_by"), to_attr="refund_rows")
    )
    payment_rows = []
    for payment in payments:
        refunded = sum((item.amount for item in payment.refund_rows), Decimal("0.00"))
        remaining = payment.amount - refunded
        payment_rows.append({
            "payment": payment,
            "refunds": payment.refund_rows,
            "refunded": refunded,
            "remaining": remaining,
            "can_refund": (
                obj.state in (Reservation.State.CANCELLED, Reservation.State.EXPIRED)
                and not payment.contract_id and not payment.invoice_id and not payment.voided_at
                and remaining > 0
            ),
            "form": forms.ReservationRefundForm(initial={"method": payment.method}),
        })
    return render(
        request,
        "cemetery/reservation.html",
        {
            "reservation": obj,
            "payment_rows": payment_rows,
            "command_key": uuid.uuid4(),
        },
    )


@login_required
@require_POST
def reservation_refund(request, reservation_pk, payment_pk):
    require(request.user, "finance")
    reservation = get_object_or_404(Reservation, pk=reservation_pk)
    get_object_or_404(Payment, pk=payment_pk, reservation_id=reservation.pk)
    form = forms.ReservationRefundForm(request.POST)
    if form.is_valid():
        try:
            result = services.record_reservation_refund(
                request.user,
                form.cleaned_data["command_key"],
                payment_pk,
                {key: value for key, value in form.cleaned_data.items() if key != "command_key"},
            )
            messages.success(request, "Devolución registrada en el historial; no se ejecutó ningún movimiento de dinero.")
            return redirect("reservation_detail", pk=result["reservation_id"])
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
    else:
        errors = [str(error) for error in form.errors.values()]
        messages.error(request, " ".join(errors) or "Revisa los datos de la devolución.")
    return redirect("reservation_detail", pk=reservation.pk)


@login_required
def payment_detail(request, pk):
    read_access(request.user, "pagos")
    obj = get_object_or_404(
        Payment.objects.select_related("contract", "reservation", "created_by").prefetch_related(
            Prefetch("refunds", queryset=Refund.objects.select_related("created_by"), to_attr="refund_rows")
        ), pk=pk
    )
    return render(
        request, "cemetery/payment.html", {"payment": obj, "command_key": uuid.uuid4()}
    )


@login_required
def refund_detail(request, pk):
    read_access(request.user, "pagos")
    refund = get_object_or_404(
        Refund.objects.select_related(
            "payment__reservation__space", "payment__reservation__responsible",
            "payment__invoice", "payment__contract", "created_by",
        ),
        pk=pk,
    )
    return render(request, "cemetery/refund.html", {"refund": refund})


@login_required
def movement_detail(request, pk):
    require(request.user, "operations")
    obj = get_object_or_404(
        Movement.objects.select_related(
            "occupancy__space", "occupancy__person", "destination", "authorized_by"
        ),
        pk=pk,
    )
    return render(
        request,
        "cemetery/movement.html",
        {"movement": obj, "form": forms.ActionForm(), "command_key": uuid.uuid4()},
    )


@login_required
@require_http_methods(["GET", "POST"])
def condition(request, pk):
    require(request.user, "spaces")
    space = get_object_or_404(Space, pk=pk)
    form = forms.ConditionForm(
        request.POST or None,
        initial={"condition": space.condition, "revision": space.revision},
    )
    if request.method == "POST" and form.is_valid():
        try:
            services.change_condition(
                request.user,
                form.cleaned_data["command_key"],
                pk,
                form.cleaned_data["condition"],
                form.cleaned_data["reason"],
                form.cleaned_data["revision"],
            )
            messages.success(request, "Condición actualizada y auditada.")
            return redirect("space_detail", pk=pk)
        except (ValidationError, IntegrityError) as exc:
            form_error(form, exc)
    return render(
        request,
        "cemetery/form.html",
        {
            "form": form,
            "title": f"Cambiar condición · {space.code}",
            "back_url": reverse("space_detail", args=[pk]),
        },
    )


@login_required
@require_POST
def action(request, kind, pk, action_name):
    form = forms.ActionForm(request.POST)
    if not form.is_valid():
        return render(
            request,
            "cemetery/form.html",
            {
                "form": form,
                "title": "Revisar operación",
                "back_url": reverse("dashboard"),
            },
            status=400,
        )
    data = form.cleaned_data
    try:
        if kind == "movimientos" and action_name in ("authorize", "execute", "cancel"):
            services.movement_action(
                request.user,
                data["command_key"],
                pk,
                action_name,
                reason=data["reason"],
                document_reference=data["document_reference"],
                occurred_at=data["occurred_at"],
            )
        elif kind == "pagos" and action_name == "void":
            services.void_payment(request.user, data["command_key"], pk, data["reason"])
        elif kind == "reservas" and action_name == "cancel":
            services.cancel_reservation(
                request.user, data["command_key"], pk, data["reason"]
            )
        elif kind == "contratos" and action_name == "close":
            services.close_contract(
                request.user, data["command_key"], pk, data["reason"]
            )
        else:
            raise PermissionDenied
        messages.success(request, "Operación registrada.")
    except (ValidationError, IntegrityError) as exc:
        form_error(form, exc)
        return render(
            request,
            "cemetery/form.html",
            {
                "form": form,
                "title": "Revisar operación",
                "back_url": reverse("dashboard"),
            },
            status=400,
        )
    return redirect(
        {
            "movimientos": "movement_detail",
            "pagos": "payment_detail",
            "reservas": "reservation_detail",
            "contratos": "contract_detail",
        }[kind],
        pk=pk,
    )


@login_required
def cemetery_map(request):
    return render(
        request,
        "cemetery/map.html",
        {
            "blocks": Block.objects.select_related("zone"),
            "status_choices": STATUS_CHOICES,
            "plan": MapPlan.objects.defer("image").filter(pk=1).first(),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def map_plan_manage(request):
    require(request.user, "spaces")
    current = MapPlan.objects.defer("image").filter(pk=1).first()
    form = forms.MapPlanForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        name = request.FILES["image_file"].name.replace("\\", "/").split("/")[-1][:180]
        with transaction.atomic(), transaction_lock(43490001):
            old_name = current.original_name if current else ""
            plan, _ = MapPlan.objects.update_or_create(
                pk=1,
                defaults={
                    "image": form.image_bytes,
                    "original_name": name or "plano.png",
                    "width": form.image_width,
                    "height": form.image_height,
                    "uploaded_by": request.user,
                    "uploaded_at": timezone.now(),
                },
            )
            services.audit(
                request.user,
                "map.plan.replace",
                plan,
                previous={"original_name": old_name} if old_name else {},
                new={"original_name": plan.original_name, "width": plan.width, "height": plan.height},
            )
        messages.success(request, "Fondo del plano actualizado. Ajusta después las coordenadas para que coincidan con la imagen.")
        return redirect("map_plan_manage")
    return render(request, "cemetery/map_plan.html", {"form": form, "plan": current})


@login_required
@require_GET
def map_plan_image(request):
    plan = MapPlan.objects.filter(pk=1).only("image").first()
    if not plan:
        raise Http404
    response = HttpResponse(bytes(plan.image), content_type="image/png")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
@require_http_methods(["GET", "POST"])
def map_coordinates(request):
    require(request.user, "spaces")
    if request.method == "POST" and request.POST.get("action") == "cancel":
        request.session.pop("map_import_preview", None)
        messages.info(request, "Vista previa descartada; no se modificó el plano.")
        return redirect("map_coordinates")
    if request.method == "POST" and request.POST.get("action") == "apply":
        preview = request.session.get("map_import_preview")
        if not preview or preview.get("user_id") != request.user.pk:
            messages.error(request, "La vista previa venció. Carga el CSV nuevamente.")
            return redirect("map_coordinates")
        if request.POST.get("confirm") != "yes":
            messages.error(request, "Confirma que revisaste las coordenadas antes de aplicarlas.")
            return redirect("map_coordinates")
        changed = 0
        try:
            with transaction.atomic(), transaction_lock(43490001):
                active_plan = MapPlan.objects.only("uploaded_at").filter(pk=1).first()
                plan_version = active_plan.uploaded_at.isoformat() if active_plan else None
                if preview.get("plan_version") != plan_version:
                    raise ValidationError("El fondo del plano cambió desde la vista previa. Vuelve a cargar el CSV.")
                imported_ids = [item["id"] for item in preview["rows"]]
                existing_positions = list(
                    Space.objects.exclude(pk__in=imported_ids).values_list("map_x", "map_y")
                )
                active_plan = MapPlan.objects.filter(pk=1).exists()
                if active_plan:
                    position_index = PositionIndex(existing_positions)
                    for item in preview["rows"]:
                        conflict = position_index.overlap(item["x"], item["y"])
                        if conflict:
                            raise ValidationError(
                                f"La posición de {item['code']} se cruza con otra sepultura cerca de ({conflict[0]}, {conflict[1]}). Recarga el CSV."
                            )
                        position_index.add(item["x"], item["y"])
                else:
                    target_positions = [(item["x"], item["y"]) for item in preview["rows"]]
                    if len(target_positions) != len(set(target_positions)):
                        raise ValidationError("La vista previa contiene coordenadas repetidas.")
                    existing_position_set = set(existing_positions)
                    conflict = next((position for position in target_positions if position in existing_position_set), None)
                    if conflict:
                        raise ValidationError(
                            f"La posición ({conflict[0]}, {conflict[1]}) fue ocupada por otra sepultura después de la vista previa."
                        )
                for item in preview["rows"]:
                    space = Space.objects.select_for_update().filter(pk=item["id"]).first()
                    if (
                        not space
                        or space.code.casefold() != item["code"].casefold()
                        or space.map_x != item["old_x"]
                        or space.map_y != item["old_y"]
                    ):
                        raise ValidationError(
                            f"La sepultura {item['code']} cambió después de la vista previa. Recarga el archivo."
                        )
                    if (space.map_x, space.map_y) == (item["x"], item["y"]):
                        continue
                    previous = {"map_x": space.map_x, "map_y": space.map_y}
                    space.map_x, space.map_y = item["x"], item["y"]
                    space.revision += 1
                    space.save(update_fields=["map_x", "map_y", "revision"])
                    services.audit(
                        request.user, "map.coordinates.import", space,
                        previous=previous, new={"map_x": space.map_x, "map_y": space.map_y},
                    )
                    services.event(
                        request.user, space, "SPACE_UPDATED",
                        f"Posición del plano actualizada por importación CSV para {space.code}.",
                    )
                    changed += 1
            request.session.pop("map_import_preview", None)
            messages.success(request, f"Coordenadas aplicadas: {changed} sepulturas actualizadas.")
            return redirect("map")
        except (ValidationError, IntegrityError) as exc:
            messages.error(request, exc.messages[0] if hasattr(exc, "messages") else "No se aplicaron cambios porque hubo un conflicto. Vuelve a cargar el archivo.")
            return redirect("map_coordinates")

    form = forms.MapImportForm(request.POST or None, request.FILES or None)
    active_plan = MapPlan.objects.only("width", "height", "uploaded_at").filter(pk=1).first()
    errors, preview_rows = [], []
    if request.method == "POST" and request.POST.get("action") != "apply":
        request.session.pop("map_import_preview", None)
    if request.method == "POST" and request.POST.get("action") != "apply" and form.is_valid():
        try:
            uploaded = form.cleaned_data["file"]
            content = uploaded.read().decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(content))
            headers = {str(header).strip().lower(): header for header in (reader.fieldnames or [])}
            if not {"codigo", "x", "y"}.issubset(headers):
                raise ValidationError("El CSV debe incluir las columnas codigo,x,y. Descarga la plantilla para ver el formato.")
            catalog = {
                space.code.casefold(): space
                for space in Space.objects.only("pk", "code", "map_x", "map_y")
            }
            seen_codes, seen_positions = set(), set()
            marker_positions = PositionIndex()
            for line, raw in enumerate(reader, start=2):
                if not any((value or "").strip() for value in raw.values() if value is not None):
                    continue
                if None in raw:
                    raise ValidationError(f"La fila {line} tiene más columnas que el encabezado.")
                code = (raw.get(headers["codigo"]) or "").strip().upper()
                if not code:
                    raise ValidationError(f"Falta el código en la fila {line}.")
                normalized = code.casefold()
                if normalized in seen_codes:
                    raise ValidationError(f"El código {code} aparece más de una vez en el CSV.")
                seen_codes.add(normalized)
                space = catalog.get(normalized)
                if not space:
                    raise ValidationError(f"No existe la sepultura {code}. El archivo no crea ni renumera espacios.")
                try:
                    x, y = int(raw[headers["x"]]), int(raw[headers["y"]])
                except (TypeError, ValueError):
                    raise ValidationError(f"Las coordenadas de {code} deben ser números enteros.")
                if not 0 <= x <= 20000 or not 0 <= y <= 20000:
                    raise ValidationError(f"Las coordenadas de {code} deben estar entre 0 y 20.000.")
                if active_plan and (x + 58 > active_plan.width or y + 50 > active_plan.height):
                    raise ValidationError(
                        f"La lápida {code} sale del fondo de {active_plan.width} × {active_plan.height} px. Usa su esquina superior izquierda."
                    )
                if (x, y) in seen_positions:
                    raise ValidationError(f"La coordenada ({x}, {y}) está repetida en el archivo.")
                if active_plan and marker_positions.overlaps(x, y):
                    raise ValidationError(f"La lápida {code} se cruza con otra lápida del archivo.")
                seen_positions.add((x, y))
                marker_positions.add(x, y)
                preview_rows.append({
                    "id": space.pk, "code": space.code,
                    "old_x": space.map_x, "old_y": space.map_y, "x": x, "y": y,
                })
                if len(preview_rows) > 5000:
                    raise ValidationError("Un archivo puede contener hasta 5.000 sepulturas.")
            if not preview_rows:
                raise ValidationError("El archivo no contiene filas de coordenadas.")
            imported_ids = {row["id"] for row in preview_rows}
            existing_spaces = [space for space in catalog.values() if space.pk not in imported_ids]
            if active_plan:
                position_index = PositionIndex((space.map_x, space.map_y) for space in existing_spaces)
                for row in preview_rows:
                    conflict = position_index.overlap(row["x"], row["y"])
                    if conflict:
                        raise ValidationError(
                            f"La posición de {row['code']} se cruza con una sepultura no incluida en el CSV cerca de ({conflict[0]}, {conflict[1]})."
                        )
                    position_index.add(row["x"], row["y"])
            else:
                existing_positions = {(space.map_x, space.map_y): space.code for space in existing_spaces}
                for row in preview_rows:
                    conflict = existing_positions.get((row["x"], row["y"]))
                    if conflict:
                        raise ValidationError(
                            f"La posición de {row['code']} coincide con la sepultura no incluida {conflict}."
                        )
            request.session["map_import_preview"] = {
                "user_id": request.user.pk,
                "plan_version": active_plan.uploaded_at.isoformat() if active_plan else None,
                "rows": preview_rows,
            }
        except (UnicodeDecodeError, csv.Error, ValidationError) as exc:
            errors.append(exc.messages[0] if hasattr(exc, "messages") else "No se pudo leer el CSV. Guárdalo como CSV UTF-8 y vuelve a intentarlo.")
    elif request.method == "POST" and request.POST.get("action") != "apply":
        errors.extend(str(error) for error in form.non_field_errors())
        for field_errors in form.errors.values():
            errors.extend(str(error) for error in field_errors)
    session_preview = request.session.get("map_import_preview")
    if session_preview and session_preview.get("user_id") == request.user.pk:
        preview_rows = session_preview["rows"]
    return render(request, "cemetery/map_import.html", {
        "form": form, "errors": errors, "preview_rows": preview_rows,
        "preview_count": len(preview_rows),
        "plan": active_plan,
    })


@login_required
def map_coordinates_csv(request):
    require(request.user, "spaces")
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="cementerio-coordenadas.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["codigo", "x", "y"])
    for space in Space.objects.order_by("code").iterator():
        writer.writerow([space.code, space.map_x, space.map_y])
    return response


def _space_choice(raw, choices, default):
    value = (raw or "").strip().casefold()
    if not value:
        return default
    lookup = {}
    for key, label in choices:
        lookup[key.casefold()] = key
        lookup[label.casefold()] = key
    return lookup.get(value)


@login_required
@require_http_methods(["GET", "POST"])
def space_import(request):
    require(request.user, "spaces")
    if request.method == "POST" and request.POST.get("action") == "cancel":
        request.session.pop("space_import_preview", None)
        messages.info(request, "Vista previa descartada; no se crearon sepulturas.")
        return redirect("space_import")

    if request.method == "POST" and request.POST.get("action") == "apply":
        preview = request.session.get("space_import_preview")
        if not preview or preview.get("user_id") != request.user.pk:
            messages.error(request, "La vista previa venció. Carga el CSV de nuevo.")
            return redirect("space_import")
        if request.POST.get("confirm") != "yes":
            messages.error(request, "Confirma que revisaste códigos y ubicaciones antes de importar.")
            return redirect("space_import")
        created = 0
        try:
            with transaction.atomic(), transaction_lock(43490001):
                plan = MapPlan.objects.only("width", "height", "uploaded_at").filter(pk=1).first()
                plan_version = plan.uploaded_at.isoformat() if plan else None
                if preview.get("plan_version") != plan_version:
                    raise ValidationError("El plano cambió desde la vista previa. Carga el CSV nuevamente.")
                codes = {code.casefold() for code in Space.objects.values_list("code", flat=True)}
                locations = set(Space.objects.values_list("block_id", "row", "number"))
                position_index = PositionIndex(
                    Space.objects.exclude(map_x=0, map_y=0).values_list("map_x", "map_y")
                )
                for row in preview["rows"]:
                    if row["code"].casefold() in codes:
                        raise ValidationError(f"El código {row['code']} ya existe. No se modificó ningún registro.")
                    location = (row["block_id"], row["row"], row["number"])
                    if location in locations:
                        raise ValidationError(f"La ubicación {row['zone']} / {row['block']} · fila {row['row']}, número {row['number']} ya existe.")
                    block = Block.objects.select_for_update().filter(
                        pk=row["block_id"], zone__name__iexact=row["zone"], name__iexact=row["block"]
                    ).first()
                    if not block:
                        raise ValidationError(f"El bloque {row['zone']} / {row['block']} cambió después de la vista previa.")
                    if position_index.overlaps(row["x"], row["y"]):
                        raise ValidationError(f"La posición de {row['code']} se cruza con otra sepultura. No se creó ningún registro.")
                    position_index.add(row["x"], row["y"])
                    codes.add(row["code"].casefold())
                    locations.add(location)
                block_cache = {block.pk: block for block in Block.objects.filter(pk__in={row["block_id"] for row in preview["rows"]}).select_related("zone")}
                for row in preview["rows"]:
                    values = {
                        "code": row["code"], "block": block_cache[row["block_id"]],
                        "row": row["row"], "number": row["number"], "kind": row["kind"],
                        "condition": row["condition"], "map_x": row["x"], "map_y": row["y"],
                        "notes": row["notes"],
                    }
                    services.save_space(request.user, uuid.uuid4(), values)
                    created += 1
            request.session.pop("space_import_preview", None)
            messages.success(request, f"Importación completada: {created} sepulturas nuevas.")
            return redirect("listing", kind="sepulturas")
        except (ValidationError, IntegrityError) as exc:
            detail = exc.messages[0] if hasattr(exc, "messages") else "No se aplicó la importación por un conflicto. Vuelve a cargar el CSV."
            request.session.pop("space_import_preview", None)
            messages.error(request, detail)
            return redirect("space_import")

    form = forms.SpaceImportForm(request.POST or None, request.FILES or None)
    errors, preview_rows = [], []
    active_plan = MapPlan.objects.only("width", "height", "uploaded_at").filter(pk=1).first()
    if request.method == "POST" and request.POST.get("action") != "apply":
        request.session.pop("space_import_preview", None)
    if request.method == "POST" and request.POST.get("action") not in ("apply", "cancel") and form.is_valid():
        try:
            content = form.cleaned_data["file"].read().decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(content))
            raw_headers = reader.fieldnames or []
            headers = {str(header).strip().casefold(): header for header in raw_headers if header is not None}
            if len(headers) != len(raw_headers):
                raise ValidationError("El CSV tiene encabezados vacíos o repetidos.")
            required = {"codigo", "zona", "bloque", "fila", "numero"}
            if not required.issubset(headers):
                raise ValidationError("El CSV debe incluir codigo,zona,bloque,fila,numero. Descarga la plantilla.")

            blocks = list(Block.objects.select_related("zone").order_by("zone__name", "name", "pk"))
            block_lookup = {}
            ambiguous = set()
            for block in blocks:
                key = (block.zone.name.casefold(), block.name.casefold())
                if key in block_lookup:
                    ambiguous.add(key)
                block_lookup[key] = block
            block_positions = {block.pk: index for index, block in enumerate(blocks)}
            existing_codes = {code.casefold() for code in Space.objects.values_list("code", flat=True)}
            existing_locations = set(Space.objects.values_list("block_id", "row", "number"))
            existing_map_positions = PositionIndex(
                Space.objects.exclude(map_x=0, map_y=0).values_list("map_x", "map_y")
            )
            seen_codes, seen_locations, marker_positions = set(), set(), PositionIndex()
            preview_rows = []
            for line, raw in enumerate(reader, start=2):
                if not any((value or "").strip() for value in raw.values() if value is not None):
                    continue
                if None in raw:
                    raise ValidationError(f"La fila {line} tiene más columnas que el encabezado.")
                code = (raw.get(headers["codigo"]) or "").strip().upper()
                zone_name = (raw.get(headers["zona"]) or "").strip()
                block_name = (raw.get(headers["bloque"]) or "").strip()
                if not code or len(code) > 40 or not code[0].isalnum() or any(not (char.isalnum() or char in "._/-") for char in code):
                    raise ValidationError(f"El código de la fila {line} no es válido (máximo 40 letras, números, punto, guion o barra).")
                if not zone_name or len(zone_name) > 80 or not block_name or len(block_name) > 80:
                    raise ValidationError(f"Indica una zona y un bloque existente en la fila {line}.")
                code_key = code.casefold()
                if code_key in existing_codes or code_key in seen_codes:
                    raise ValidationError(f"El código {code} ya existe o aparece duplicado en el CSV.")
                block_key = (zone_name.casefold(), block_name.casefold())
                if block_key in ambiguous:
                    raise ValidationError(f"La zona y bloque {zone_name} / {block_name} son ambiguos. Corrige el catálogo antes de importar.")
                block = block_lookup.get(block_key)
                if not block:
                    raise ValidationError(f"No existe el bloque {zone_name} / {block_name}. Créalo en el catálogo antes de importar.")
                try:
                    row_number = int(raw[headers["fila"]])
                    number = int(raw[headers["numero"]])
                except (TypeError, ValueError):
                    raise ValidationError(f"Fila y número deben ser enteros positivos en la fila {line}.")
                if not 1 <= row_number <= 100000 or not 1 <= number <= 100000:
                    raise ValidationError(f"Fila y número deben estar entre 1 y 100.000 en la fila {line}.")
                location = (block.pk, row_number, number)
                if location in existing_locations or location in seen_locations:
                    raise ValidationError(f"La ubicación de {zone_name} / {block_name}, fila {row_number}, número {number} ya existe o está repetida.")
                kind = _space_choice(raw.get(headers.get("tipo", ""), ""), Space.Kind.choices, Space.Kind.GRAVE)
                condition = _space_choice(raw.get(headers.get("condicion", ""), ""), Space.Condition.choices, Space.Condition.AVAILABLE)
                if not kind or not condition:
                    raise ValidationError(f"Tipo o condición no válidos en la fila {line}. Usa GRAVE/VAULT/OSSUARY/NICHE y AVAILABLE/MAINTENANCE/OUT_OF_SERVICE, o sus etiquetas en español.")
                x_raw, y_raw = (raw.get(headers.get("x", ""), "") or "").strip(), (raw.get(headers.get("y", ""), "") or "").strip()
                if bool(x_raw) != bool(y_raw):
                    raise ValidationError(f"La fila {line} debe incluir x e y, o dejar ambos vacíos.")
                if active_plan and not x_raw:
                    raise ValidationError(f"El plano ya tiene fondo. Indica coordenadas x,y en píxeles para {code}.")
                if x_raw:
                    try:
                        x, y = int(x_raw), int(y_raw)
                    except ValueError:
                        raise ValidationError(f"Las coordenadas x,y de {code} deben ser enteros.")
                    if not 0 <= x <= 20000 or not 0 <= y <= 20000:
                        raise ValidationError(f"Las coordenadas de {code} deben estar entre 0 y 20.000.")
                else:
                    block_index = block_positions[block.pk]
                    x = 1500 + (block_index % 3) * 1000 + (number - 1) * 90
                    y = (block_index // 3) * 1000 + (row_number - 1) * 88
                if active_plan:
                    if x + MARKER_WIDTH > active_plan.width or y + MARKER_HEIGHT > active_plan.height:
                        raise ValidationError(f"La lápida {code} sale del fondo de {active_plan.width} × {active_plan.height} px.")
                if existing_map_positions.overlaps(x, y) or marker_positions.overlaps(x, y):
                    raise ValidationError(f"La posición de {code} se cruza con otra sepultura.")
                marker_positions.add(x, y)
                notes = raw.get(headers.get("observaciones", ""), "") or ""
                if len(notes) > 5000:
                    raise ValidationError(f"Las observaciones de {code} superan 5.000 caracteres.")
                seen_codes.add(code_key)
                seen_locations.add(location)
                preview_rows.append({
                    "code": code, "zone": block.zone.name, "block": block.name,
                    "block_id": block.pk, "row": row_number, "number": number,
                    "kind": kind, "condition": condition, "x": x, "y": y, "notes": notes,
                })
                if len(preview_rows) > 5000:
                    raise ValidationError("Un archivo puede contener hasta 5.000 sepulturas.")
            if not preview_rows:
                raise ValidationError("El archivo no contiene sepulturas.")
            request.session["space_import_preview"] = {
                "user_id": request.user.pk,
                "plan_version": active_plan.uploaded_at.isoformat() if active_plan else None,
                "rows": preview_rows,
            }
        except (UnicodeDecodeError, csv.Error, ValidationError) as exc:
            errors.append(exc.messages[0] if hasattr(exc, "messages") else "No se pudo leer el CSV UTF-8.")
    elif request.method == "POST" and request.POST.get("action") not in ("apply", "cancel"):
        errors.extend(str(error) for error in form.non_field_errors())
        for field_errors in form.errors.values():
            errors.extend(str(error) for error in field_errors)

    stored_preview = request.session.get("space_import_preview")
    if stored_preview and stored_preview.get("user_id") == request.user.pk:
        preview_rows = stored_preview["rows"]
    return render(request, "cemetery/space_import.html", {
        "form": form,
        "errors": errors,
        "preview_rows": preview_rows[:100],
        "preview_count": len(stored_preview["rows"]) if stored_preview and stored_preview.get("user_id") == request.user.pk else len(preview_rows),
        "plan": active_plan,
    })


@login_required
@require_GET
def space_import_csv(request):
    require(request.user, "spaces")
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="plantilla-sepulturas.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["codigo", "zona", "bloque", "fila", "numero", "tipo", "condicion", "x", "y", "observaciones"])
    return response


@login_required
@require_GET
def space_export_csv(request):
    require(request.user, "spaces")
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="inventario-sepulturas.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["codigo", "zona", "bloque", "fila", "numero", "tipo", "condicion", "x", "y", "observaciones"])
    def safe_cell(value):
        value = str(value)
        return "'" + value if value.lstrip(" \t\r\n")[:1] in ("=", "+", "-", "@") else value
    for space in Space.objects.select_related("block__zone").order_by("block__zone__name", "block__name", "row", "number"):
        writer.writerow([
            safe_cell(space.code), safe_cell(space.block.zone.name), safe_cell(space.block.name),
            space.row, space.number, space.kind, space.condition, space.map_x, space.map_y,
            safe_cell(space.notes),
        ])
    return response


@login_required
@require_GET
def space_capacity_report(request):
    require(request.user, "spaces")
    today = timezone.localdate()
    occupied_query = Occupancy.objects.filter(space_id=OuterRef("pk"), ended_at__isnull=True)
    reservation_query = Reservation.objects.filter(
        space_id=OuterRef("pk"), state="ACTIVE", expires_on__gte=today
    )
    grouped = {}
    for block_id, condition, occupied, reserved in Space.objects.annotate(
        has_current_occupancy=Exists(occupied_query),
        has_active_reservation=Exists(reservation_query),
    ).values_list("block_id", "condition", "has_current_occupancy", "has_active_reservation").iterator():
        row = grouped.setdefault(block_id, {
            "total": 0, "occupied": 0, "reserved": 0, "available": 0,
            "maintenance": 0, "out_of_service": 0,
        })
        row["total"] += 1
        if occupied:
            row["occupied"] += 1
        elif reserved:
            row["reserved"] += 1
        elif condition == Space.Condition.MAINTENANCE:
            row["maintenance"] += 1
        elif condition == Space.Condition.OUT_OF_SERVICE:
            row["out_of_service"] += 1
        else:
            row["available"] += 1

    blocks = []
    totals = {key: 0 for key in ("total", "occupied", "reserved", "available", "maintenance", "out_of_service")}
    for block in Block.objects.select_related("zone").order_by("zone__name", "name"):
        metrics = grouped.get(block.pk, {key: 0 for key in totals})
        for key in totals:
            totals[key] += metrics[key]
        blocks.append({
            "zone": block.zone.name,
            "block": block.name,
            **metrics,
            "occupancy_rate": round(metrics["occupied"] * 100 / metrics["total"]) if metrics["total"] else 0,
        })

    if request.GET.get("format") == "csv":
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="capacidad-cementerio.csv"'
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow(["zona", "bloque", "total", "ocupadas", "reservadas", "disponibles", "mantenimiento", "fuera_de_servicio", "ocupacion_porcentaje"])
        def safe_cell(value):
            value = str(value)
            return "'" + value if value.lstrip(" \t\r\n")[:1] in ("=", "+", "-", "@") else value
        for row in blocks:
            writer.writerow([safe_cell(row["zone"]), safe_cell(row["block"]), row["total"], row["occupied"], row["reserved"], row["available"], row["maintenance"], row["out_of_service"], row["occupancy_rate"]])
        return response

    return render(request, "cemetery/space_capacity.html", {
        "blocks": blocks, "totals": totals, "today": today,
    })


@login_required
@require_GET
def finance_cashbook(request):
    read_access(request.user, "facturas")
    today = timezone.localdate()
    month_key = request.GET.get("month", "").strip()
    error = ""
    try:
        if month_key:
            if len(month_key) != 7 or month_key[4] != "-":
                raise ValueError
            month_start = date.fromisoformat(f"{month_key}-01")
        else:
            month_start = today.replace(day=1)
            month_key = month_start.strftime("%Y-%m")
    except ValueError:
        month_start = today.replace(day=1)
        month_key = month_start.strftime("%Y-%m")
        error = "El mes debe tener formato AAAA-MM. Se muestra el mes actual."
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    month_end = next_month - timedelta(days=1)

    rows = []
    income = refunds_total = expenses_total = Decimal("0.00")
    payments = Payment.objects.filter(
        voided_at__isnull=True,
        paid_at__date__gte=month_start,
        paid_at__date__lte=month_end,
    ).select_related("invoice", "contract", "reservation")
    for payment in payments:
        source = (
            payment.invoice.number if payment.invoice_id
            else payment.contract.number if payment.contract_id
            else f"Reserva R-{payment.reservation_id}"
        )
        income += payment.amount
        rows.append({
            "date": timezone.localtime(payment.paid_at).date(),
            "kind": "Cobro",
            "reference": payment.reference,
            "source": source,
            "description": f"{payment.get_method_display()} · Recibo P-{payment.pk}",
            "inflow": payment.amount,
            "outflow": Decimal("0.00"),
            "url": reverse("payment_detail", args=[payment.pk]),
            "sort": 0,
        })

    refunds = Refund.objects.filter(
        refunded_at__date__gte=month_start,
        refunded_at__date__lte=month_end,
    ).select_related("payment__reservation", "payment__invoice", "payment__contract")
    for refund in refunds:
        payment = refund.payment
        if payment.reservation_id:
            source = f"Reserva R-{payment.reservation_id}"
        elif payment.invoice_id:
            source = payment.invoice.number
        elif payment.contract_id:
            source = payment.contract.number
        else:
            source = f"Pago P-{payment.pk}"
        refunds_total += refund.amount
        rows.append({
            "date": timezone.localtime(refund.refunded_at).date(),
            "kind": "Devolución",
            "reference": refund.reference,
            "source": source,
            "description": refund.reason,
            "inflow": Decimal("0.00"),
            "outflow": refund.amount,
            "url": reverse("refund_detail", args=[refund.pk]),
            "sort": 1,
        })

    expenses = OperatingExpense.objects.filter(paid_on__gte=month_start, paid_on__lte=month_end)
    for expense in expenses:
        expenses_total += expense.amount
        rows.append({
            "date": expense.paid_on,
            "kind": "Gasto",
            "reference": expense.reference or expense.number,
            "source": expense.supplier,
            "description": f"{expense.get_category_display()} · {expense.description}",
            "inflow": Decimal("0.00"),
            "outflow": expense.amount,
            "url": reverse("expense_detail", args=[expense.pk]),
            "sort": 2,
        })
    rows.sort(key=lambda row: (row["date"], row["sort"], row["reference"]))
    net = income - refunds_total - expenses_total

    if request.GET.get("format") == "csv":
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="libro-caja-{month_key}.csv"'
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow(["fecha", "tipo", "referencia", "origen", "detalle", "entrada", "salida", "neto"])
        def safe_cell(value):
            value = str(value)
            return "'" + value if value.lstrip(" \t\r\n")[:1] in ("=", "+", "-", "@") else value
        for row in rows:
            writer.writerow([
                row["date"].isoformat(), safe_cell(row["kind"]), safe_cell(row["reference"]),
                safe_cell(row["source"]), safe_cell(row["description"]), row["inflow"],
                row["outflow"], row["inflow"] - row["outflow"],
            ])
        return response

    page = Paginator(rows, 50).get_page(request.GET.get("page"))
    return render(request, "cemetery/finance_cashbook.html", {
        "month_key": month_key, "month_start": month_start, "month_end": month_end,
        "income": income, "refunds_total": refunds_total, "expenses_total": expenses_total,
        "net": net, "page": page, "row_count": len(rows), "error": error,
    })


@login_required
@require_POST
def map_coordinate_update(request, pk):
    require(request.user, "spaces")
    try:
        payload = json.loads(request.body)
        x, y, revision = payload.get("x"), payload.get("y"), payload.get("revision")
        plan_version = payload.get("plan_version")
        if any(isinstance(value, bool) or not isinstance(value, int) for value in (x, y, revision)):
            raise ValueError
    except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
        return JsonResponse({"error": "Envía coordenadas enteras válidas."}, status=400)

    try:
        with transaction.atomic(), transaction_lock(43490001):
            space = Space.objects.select_for_update().select_related("block").filter(pk=pk).first()
            if not space:
                raise Http404
            plan = MapPlan.objects.only("width", "height", "uploaded_at").filter(pk=1).first()
            current_version = plan.uploaded_at.isoformat() if plan else None
            if not plan or plan_version != current_version:
                return JsonResponse({"error": "El plano cambió. Recarga el mapa antes de editar."}, status=409)
            if space.revision != revision:
                return JsonResponse({"error": "La sepultura cambió desde que abriste el mapa. Recarga para evitar sobrescribir cambios."}, status=409)
            if x < 0 or y < 0 or x + MARKER_WIDTH > plan.width or y + MARKER_HEIGHT > plan.height:
                return JsonResponse({"error": "La sepultura debe quedar dentro de los límites del plano."}, status=400)
            conflict = Space.objects.exclude(pk=space.pk).filter(
                map_x__gt=x - MARKER_WIDTH,
                map_x__lt=x + MARKER_WIDTH,
                map_y__gt=y - MARKER_HEIGHT,
                map_y__lt=y + MARKER_HEIGHT,
            ).values_list("code", flat=True).first()
            if conflict:
                return JsonResponse({"error": f"La posición se cruza con la lápida {conflict}."}, status=409)
            previous = {"map_x": space.map_x, "map_y": space.map_y}
            if previous != {"map_x": x, "map_y": y}:
                space.map_x, space.map_y = x, y
                space.revision += 1
                space.save(update_fields=["map_x", "map_y", "revision"])
                services.audit(
                    request.user,
                    "map.coordinates.drag",
                    space,
                    previous=previous,
                    new={"map_x": x, "map_y": y},
                )
                services.event(
                    request.user,
                    space,
                    "SPACE_UPDATED",
                    f"Ubicación de {space.code} ajustada desde el mapa interactivo.",
                )
    except IntegrityError:
        return JsonResponse({"error": "Otra sepultura ocupó esa posición. Recarga el mapa e inténtalo de nuevo."}, status=409)
    return JsonResponse({"ok": True, "revision": space.revision, "x": space.map_x, "y": space.map_y})


@login_required
@never_cache
def map_data(request):
    try:
        qs = filter_spaces(spaces(), request.GET)
        term = (
            search_term(request.GET.get("person", ""))
            if may_read_contacts(request.user)
            else ""
        )
    except ValidationError as exc:
        return JsonResponse({"error": exc.messages[0]}, status=400)
    matched_people = []
    people_truncated = False
    if term:
        current = Occupancy.objects.filter(
            person_id=OuterRef("pk"), ended_at__isnull=True
        ).values("space_id")[:1]
        people = list(
            Person.objects.filter(person_query(term))
            .annotate(current_space_id=Subquery(current))
            .order_by("last_name", "first_name", "pk")[:21]
        )
        people_truncated = len(people) > 20
        for person in people[:20]:
            matched_people.append(
                {
                    "id": person.pk,
                    "name": str(person),
                    "space_id": person.current_space_id,
                    "url": reverse("person_detail", args=[person.pk]),
                }
            )
    result = [
        {
            "id": s.pk,
            "code": s.code,
            "block": str(s.block),
            "status": s.status,
            "label": s.status_label,
            "x": s.map_x,
            "y": s.map_y,
            "revision": s.revision,
            "url": reverse("space_detail", args=[s.pk]),
        }
        for s in qs[:1001]
    ]
    plan = MapPlan.objects.filter(pk=1).values("original_name", "width", "height", "uploaded_at").first()
    if plan:
        plan["url"] = reverse("map_plan_image")
        plan["version"] = plan["uploaded_at"].isoformat()
        del plan["uploaded_at"]
    return JsonResponse(
        {
            "spaces": result[:1000],
            "truncated": len(result) > 1000,
            "people": matched_people,
            "people_truncated": people_truncated,
            "plan": plan,
            "updated_at": timezone.now().isoformat(),
        }
    )


def health(request):
    from django.db import connection

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
