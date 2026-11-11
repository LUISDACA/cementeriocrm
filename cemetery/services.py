"""Única vía de escritura del dominio: permisos, idempotencia y transacciones.

Las escrituras se serializan con un advisory lock de PostgreSQL. La lectura no
se bloquea. Esta decisión conservadora evita carreras entre reservas, contratos,
ocupaciones y pagos en el MVP; puede particionarse por agregado más adelante.
"""

from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import hmac
import uuid
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from .models import (
    Audit,
    Block,
    Command,
    Contract,
    Invoice,
    OperatingExpense,
    Event,
    Movement,
    Occupancy,
    Payment,
    Person,
    PersonResponsible,
    Reservation,
    Refund,
    Responsible,
    Space,
    User,
    Zone,
)
from .permissions import require
from .locks import transaction_lock


class DomainError(ValidationError):
    pass


def money(value):
    try:
        result = Decimal(str(value))
        if (
            not result.is_finite()
            or result <= 0
            or result != result.quantize(Decimal("0.01"))
            or result >= Decimal("1000000000000")
        ):
            raise ValueError
        return result
    except (InvalidOperation, ValueError, TypeError):
        raise DomainError(
            "El valor debe ser positivo, con máximo dos decimales y hasta doce cifras enteras."
        )


def audit(actor, action, obj, **detail):
    Audit.objects.create(
        actor=actor, action=action, target=f"{obj._meta.label}:{obj.pk}", detail=detail
    )


def audit_values(obj, fields):
    """Instantánea de campos autorizados; nunca incluye contraseñas ni tokens."""
    if not obj.pk:
        return None
    result = {}
    for name in fields:
        value = obj._meta.get_field(name).value_from_object(obj)
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        elif isinstance(value, Decimal):
            value = str(value)
        result[name] = value
    return result


def event(actor, space, kind, detail, person=None, occurred_at=None):
    Event.objects.create(
        actor=actor,
        space=space,
        kind=kind,
        detail=detail,
        person=person,
        occurred_at=occurred_at or timezone.now(),
    )


def run(actor, key, action, payload, callback):
    try:
        key = uuid.UUID(str(key))
    except (ValueError, TypeError, AttributeError):
        raise DomainError("Falta una clave de operación válida. Recarga el formulario.")

    def canonical(value):
        if hasattr(value, "_meta") and hasattr(value, "pk"):
            return {"model": value._meta.label, "id": value.pk}
        return str(value)

    serialized = json.dumps(
        {"action": action, "payload": payload}, sort_keys=True, default=canonical
    ).encode()
    digest = hmac.new(settings.SECRET_KEY.encode(), serialized, sha256).hexdigest()
    with transaction.atomic(), transaction_lock(43490001):
        # Reevaluar permisos con el usuario actual dentro de la misma transacción.
        actor.refresh_from_db(fields=["role", "is_active"])
        if not actor.is_active:
            raise DomainError("Tu cuenta ya no está activa.")
        capability = {
            "catalog": "spaces",
            "space": "spaces",
            "person": "people",
            "responsible": "contacts",
            "reservation": "finance",
            "contract": "contracts",
            "payment": "finance",
            "burial": "operations",
            "movement": "operations",
            "user": "users",
            "expense": "finance",
        }[action.split(".")[0]]
        require(actor, "authorize" if action == "movement.authorize" else capability)
        previous = Command.objects.filter(key=key).first()
        if previous:
            if previous.actor_id != actor.pk or previous.fingerprint != digest:
                raise DomainError("Esta clave ya pertenece a otra operación.")
            return previous.result
        try:
            result = callback()
        except ObjectDoesNotExist:
            raise DomainError("El registro ya no existe o la referencia no es válida.")
        Command.objects.create(key=key, actor=actor, fingerprint=digest, result=result)
        return result


def checked_save(obj):
    obj.full_clean()
    obj.save()
    return obj


def expire_reservation(actor, space):
    for reservation in space.reservations.select_for_update().filter(
        state="ACTIVE", expires_on__lt=timezone.localdate()
    ):
        reservation.state = "EXPIRED"
        reservation.save(update_fields=["state"])
        event(
            actor,
            space,
            "RESERVATION_EXPIRED",
            f"Reserva R-{reservation.pk} vencida. Su pago se conserva para conciliación.",
        )
        audit(actor, "reservation.expire", reservation)


def available_for(actor, space, responsible_id=None):
    expire_reservation(actor, space)
    if (
        space.condition != Space.Condition.AVAILABLE
        or space.occupancies.filter(ended_at__isnull=True).exists()
    ):
        raise DomainError("La sepultura no está disponible.")
    reservation = space.reservations.filter(state="ACTIVE").first()
    if reservation and reservation.responsible_id != responsible_id:
        raise DomainError("La sepultura está reservada por otro responsable.")


def valid_contract(contract, space, on_date):
    if (
        contract.space_id != space.pk
        or contract.state != "ACTIVE"
        or not contract.starts_on <= on_date <= contract.ends_on
    ):
        raise DomainError(
            "Se exige un contrato activo y vigente para esa sepultura y fecha."
        )


def save_catalog(actor, key, model, data):
    def operation():
        require(actor, "spaces")
        if model not in (Zone, Block):
            raise DomainError("Catálogo no admitido.")
        obj = checked_save(model(**data))
        audit(actor, "catalog.create", obj)
        return {"id": obj.pk}

    return run(actor, key, f"catalog.{model.__name__}", data, operation)


def save_space(actor, key, data, pk=None, revision=None):
    def operation():
        require(actor, "spaces")
        values = {
            k: v
            for k, v in data.items()
            if k
            in {"code", "block", "row", "number", "kind", "condition", "notes", "map_x", "map_y"}
        }
        values["code"] = values["code"].strip().upper()
        if pk:
            obj = Space.objects.select_for_update().get(pk=pk)
            if revision != obj.revision:
                raise DomainError(
                    "El registro cambió desde que lo abriste. Recarga antes de editar."
                )
            previous = audit_values(obj, values)
            identity = ("code", "block", "row", "number", "kind")
            changed_identity = any(
                previous[name] != (getattr(values[name], "pk", values[name]))
                for name in identity
                if name in values
            )
            if changed_identity and (
                obj.occupancies.exists()
                or obj.contracts.exists()
                or obj.reservations.exists()
            ):
                raise DomainError(
                    "Este espacio tiene registros asociados. Su código, tipo y ubicación física deben conservarse para no alterar la historia. Puedes corregir observaciones y posición del plano."
                )
            for field, value in values.items():
                setattr(obj, field, value)
            obj.revision += 1
        else:
            obj = Space(**values)
            previous = None
        checked_save(obj)
        event(
            actor,
            obj,
            "SPACE_UPDATED" if pk else "SPACE_CREATED",
            "Ficha del espacio actualizada." if pk else "Espacio registrado.",
        )
        audit(
            actor,
            "space.update" if pk else "space.create",
            obj,
            previous=previous,
            new=audit_values(obj, values),
        )
        return {"id": obj.pk}

    return run(
        actor, key, "space.save", {"id": pk, "revision": revision, **data}, operation
    )


def change_condition(actor, key, pk, condition, reason, revision):
    def operation():
        require(actor, "spaces")
        space = Space.objects.select_for_update().get(pk=pk)
        if revision != space.revision:
            raise DomainError("Otro usuario actualizó el espacio. Recarga su ficha.")
        if condition not in Space.Condition.values or not reason.strip():
            raise DomainError("Selecciona una condición válida y registra el motivo.")
        expire_reservation(actor, space)
        if (
            space.occupancies.filter(ended_at__isnull=True).exists()
            or space.reservations.filter(state="ACTIVE").exists()
        ):
            raise DomainError(
                "Un cambio administrativo no puede modificar una ocupación o reserva vigente."
            )
        old = space.get_condition_display()
        space.condition = condition
        space.revision += 1
        space.save(update_fields=["condition", "revision"])
        event(
            actor,
            space,
            "CONDITION_CHANGED",
            f"{old} → {space.get_condition_display()}. Motivo: {reason}",
        )
        audit(actor, "space.condition", space, previous=old, new=condition)
        return {"id": space.pk}

    return run(
        actor,
        key,
        "space.condition",
        locals_payload(pk=pk, condition=condition, reason=reason, revision=revision),
        operation,
    )


def locals_payload(**kwargs):
    return kwargs


def save_person(actor, key, data, pk=None):
    def operation():
        require(actor, "people")
        obj = Person.objects.get(pk=pk) if pk else Person()
        fields = (
            "first_name",
            "last_name",
            "identification",
            "birth_date",
            "death_date",
            "notes",
        )
        previous = audit_values(obj, fields)
        for field in (
            "first_name",
            "last_name",
            "identification",
            "birth_date",
            "death_date",
            "notes",
        ):
            if field in data:
                setattr(
                    obj,
                    field,
                    data[field].strip()
                    if isinstance(data[field], str)
                    else data[field],
                )
        if pk:
            first_burial = obj.occupancies.order_by("started_at").first()
            if (
                first_burial
                and obj.death_date > timezone.localtime(first_burial.started_at).date()
            ):
                raise DomainError(
                    "El fallecimiento no puede ser posterior a una inhumación registrada."
                )
        checked_save(obj)
        audit(
            actor,
            "person.update" if pk else "person.create",
            obj,
            previous=previous,
            new=audit_values(obj, fields),
        )
        return {"id": obj.pk}

    return run(actor, key, "person.save", {"id": pk, **data}, operation)


def save_responsible(actor, key, data, pk=None):
    def operation():
        require(actor, "contacts")
        obj = Responsible.objects.get(pk=pk) if pk else Responsible()
        fields = ("name", "identification", "phone", "email", "address")
        previous = audit_values(obj, fields)
        for field in ("name", "identification", "phone", "email", "address"):
            if field in data:
                setattr(obj, field, data[field].strip())
        checked_save(obj)
        audit(
            actor,
            "responsible.update" if pk else "responsible.create",
            obj,
            previous=previous,
            new=audit_values(obj, fields),
        )
        return {"id": obj.pk}

    return run(actor, key, "responsible.save", {"id": pk, **data}, operation)


def link_responsible(actor, key, data):
    def operation():
        require(actor, "contacts")
        obj = (
            PersonResponsible.objects.filter(
                person=data["person"], responsible=data["responsible"]
            ).first()
            or PersonResponsible()
        )
        previous_principals = list(
            PersonResponsible.objects.filter(
                person=data["person"], principal=True
            ).values_list("pk", flat=True)
        )
        if data.get("principal"):
            PersonResponsible.objects.filter(
                person=data["person"], principal=True
            ).exclude(pk=obj.pk).update(principal=False)
        for field in ("person", "responsible", "relationship", "principal"):
            setattr(obj, field, data[field])
        checked_save(obj)
        audit(
            actor,
            "responsible.link",
            obj,
            previous_principal_ids=previous_principals,
            principal=obj.principal,
        )
        return {"id": obj.person_id}

    return run(actor, key, "responsible.link", data, operation)


def create_reservation(actor, key, data):
    def operation():
        require(actor, "finance")
        space = Space.objects.select_for_update().get(pk=data["space"].pk)
        available_for(actor, space)
        if space.contracts.filter(state="ACTIVE").exists():
            raise DomainError(
                "Este espacio ya tiene contrato activo. No se puede reservar."
            )
        if data["expires_on"] < timezone.localdate():
            raise DomainError("La fecha de reserva no puede estar vencida.")
        reservation = checked_save(
            Reservation(
                space=space,
                responsible=data["responsible"],
                expires_on=data["expires_on"],
            )
        )
        payment = checked_save(
            Payment(
                reservation=reservation,
                amount=money(data["amount"]),
                method=data["method"],
                reference=data["reference"],
                created_by=actor,
            )
        )
        event(
            actor,
            space,
            "RESERVATION_CREATED",
            f"Reserva pagada R-{reservation.pk}, hasta {reservation.expires_on}.",
        )
        audit(actor, "reservation.create", reservation, payment_id=payment.pk)
        return {"id": reservation.pk}

    return run(actor, key, "reservation.create", data, operation)


def cancel_reservation(actor, key, pk, reason):
    def operation():
        require(actor, "finance")
        obj = Reservation.objects.select_for_update().get(pk=pk)
        if obj.state not in ("ACTIVE", "EXPIRED") or not reason.strip():
            raise DomainError(
                "Solo se cancela una reserva activa o vencida, con motivo."
            )
        obj.state, obj.reason = "CANCELLED", reason
        obj.save(update_fields=["state", "reason"])
        event(
            actor,
            obj.space,
            "RESERVATION_CANCELLED",
            f"Reserva R-{pk} cancelada. Motivo: {reason}. El pago se conserva; no implica devolución.",
        )
        audit(actor, "reservation.cancel", obj)
        return {"id": obj.pk}

    return run(
        actor, key, "reservation.cancel", {"id": pk, "reason": reason}, operation
    )


def create_contract(actor, key, data):
    def operation():
        require(actor, "contracts")
        space = Space.objects.select_for_update().get(pk=data["space"].pk)
        available_for(actor, space, data["responsible"].pk)
        if data["ends_on"] < data["starts_on"]:
            raise DomainError("El vencimiento debe ser posterior o igual al inicio.")
        reservation = space.reservations.filter(
            state="ACTIVE", responsible=data["responsible"]
        ).first()
        if reservation and not (actor.role == "ADMIN" or actor.role == "TREASURY"):
            raise DomainError(
                "Tesorería o administración deben aplicar el anticipo de esta reserva al contrato."
            )
        amount = money(data["amount"])
        if reservation:
            paid = sum(
                (p.amount for p in reservation.payments.filter(voided_at__isnull=True)),
                Decimal("0.00"),
            )
            if paid > amount:
                raise DomainError(
                    "El anticipo supera el valor contractual. Debe conciliarse antes de contratar."
                )
        contract = checked_save(
            Contract(
                number=data["number"].strip().upper(),
                space=space,
                responsible=data["responsible"],
                reservation=reservation,
                amount=amount,
                currency=settings.CEMETERY_CURRENCY,
                starts_on=data["starts_on"],
                ends_on=data["ends_on"],
                terms=data["terms"],
                monthly_maintenance_fee=data.get("monthly_maintenance_fee", Decimal("0.00")),
            )
        )
        invoice = checked_save(Invoice(
            number=f"F-{contract.pk:06d}-{contract.number[:35]}", contract=contract,
            kind=Invoice.Kind.CONTRACT,
            description=f"Contrato de uso de sepultura {space.code}",
            amount=amount, issued_on=timezone.localdate(), due_on=data["ends_on"],
        ))
        if reservation:
            reservation.state = "CONSUMED"
            reservation.save(update_fields=["state"])
            reservation.payments.update(contract=contract, invoice=invoice)
        event(
            actor, space, "CONTRACT_CREATED", f"Contrato {contract.number} registrado."
        )
        audit(
            actor,
            "contract.create",
            contract,
            reservation_id=reservation.pk if reservation else None,
        )
        return {"id": contract.pk}

    return run(actor, key, "contract.create", data, operation)


def update_contract(actor, key, pk, data):
    def operation():
        require(actor, "contracts")
        contract = Contract.objects.select_for_update().get(pk=pk)
        # El contrato es histórico: el valor y sus relaciones no se reescriben.
        if contract.state != "ACTIVE":
            raise DomainError("El contrato ya está cerrado o cancelado.")
        previous = {"ends_on": str(contract.ends_on), "terms": contract.terms}
        contract.ends_on, contract.terms = data["ends_on"], data["terms"]
        if contract.ends_on < contract.starts_on:
            raise DomainError("El vencimiento no puede preceder al inicio.")
        latest = contract.occupancy_set.order_by("-started_at").first()
        if latest and contract.ends_on < timezone.localtime(latest.started_at).date():
            raise DomainError(
                "La vigencia debe conservar la cobertura de las inhumaciones ya registradas."
            )
        checked_save(contract)
        event(
            actor,
            contract.space,
            "CONTRACT_UPDATED",
            f"Contrato {contract.number}: condiciones/vencimiento actualizados.",
        )
        audit(
            actor,
            "contract.update",
            contract,
            previous=previous,
            new={"ends_on": str(contract.ends_on), "terms": contract.terms},
        )
        return {"id": contract.pk}

    return run(actor, key, "contract.update", {"id": pk, **data}, operation)


def close_contract(actor, key, pk, reason):
    def operation():
        require(actor, "contracts")
        contract = Contract.objects.select_for_update().get(pk=pk)
        if contract.state != "ACTIVE" or not reason.strip():
            raise DomainError("Indica un motivo para cerrar un contrato activo.")
        if contract.occupancy_set.filter(ended_at__isnull=True).exists():
            raise DomainError(
                "No se puede cerrar mientras exista una ocupación vigente."
            )
        if contract.balance != Decimal("0.00"):
            raise DomainError("El contrato debe tener saldo cero antes del cierre.")
        contract.state = "CLOSED"
        contract.save(update_fields=["state"])
        event(
            actor,
            contract.space,
            "CONTRACT_CLOSED",
            f"Contrato {contract.number} cerrado. Motivo: {reason}",
        )
        audit(actor, "contract.close", contract)
        return {"id": contract.pk}

    return run(actor, key, "contract.close", {"id": pk, "reason": reason}, operation)


def record_payment(actor, key, data):
    def operation():
        require(actor, "finance")
        contract = Contract.objects.select_for_update().get(pk=data["contract"].pk)
        amount = money(data["amount"])
        invoice = data.get("invoice")
        if invoice:
            invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
            if invoice.contract_id != contract.pk or invoice.balance < amount:
                raise DomainError("La factura no corresponde al contrato o el pago supera su saldo.")
        if contract.state != "ACTIVE" or (not invoice and amount > contract.balance):
            raise DomainError(
                "El contrato debe estar activo y el pago no puede superar el saldo."
            )
        if data["paid_at"] > timezone.now():
            raise DomainError("El pago no puede tener fecha futura.")
        obj = checked_save(
            Payment(
                contract=contract,
                invoice=invoice,
                amount=amount,
                method=data["method"],
                reference=data["reference"],
                paid_at=data["paid_at"],
                created_by=actor,
            )
        )
        audit(actor, "payment.create", obj, contract_id=contract.pk)
        event(
            actor,
            contract.space,
            "PAYMENT_RECORDED",
            f"Pago P-{obj.pk} registrado para contrato {contract.number}.",
        )
        return {"id": obj.pk, "contract_id": contract.pk}

    return run(actor, key, "payment.create", data, operation)


def record_reservation_refund(actor, key, payment_id, data):
    def operation():
        require(actor, "finance")
        payment = Payment.objects.select_for_update().select_related("reservation").filter(pk=payment_id).first()
        if not payment or not payment.reservation_id:
            raise DomainError("El pago no corresponde a un anticipo de reserva.")
        reservation = Reservation.objects.select_for_update().get(pk=payment.reservation_id)
        if reservation.state not in (Reservation.State.CANCELLED, Reservation.State.EXPIRED):
            raise DomainError("Solo se registran devoluciones de reservas canceladas o vencidas.")
        if payment.invoice_id or payment.contract_id or payment.voided_at:
            raise DomainError("El anticipo fue aplicado o anulado y no admite devolución desde la reserva.")
        amount = money(data["amount"])
        refunded = payment.refunds.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        remaining = payment.amount - refunded
        if amount > remaining:
            raise DomainError(f"El importe supera el anticipo aún no devuelto ({remaining}).")
        if data["refunded_at"] > timezone.now():
            raise DomainError("La fecha de devolución no puede ser futura.")
        reference, reason = data["reference"].strip(), data["reason"].strip()
        if not reference or not reason:
            raise DomainError("Indica una referencia y el motivo/autorización de la devolución.")
        refund = checked_save(Refund(
            payment=payment,
            amount=amount,
            method=data["method"],
            reference=reference,
            reason=reason,
            refunded_at=data["refunded_at"],
            created_by=actor,
        ))
        audit(
            actor,
            "reservation.refund.record",
            refund,
            reservation_id=reservation.pk,
            payment_id=payment.pk,
            amount=str(amount),
            reference=reference,
        )
        return {"id": refund.pk, "reservation_id": reservation.pk}

    return run(actor, key, "reservation.refund.record", {"payment_id": payment_id, **data}, operation)


def record_expense(actor, key, data):
    def operation():
        require(actor, "finance")
        if data["paid_on"] > timezone.localdate():
            raise DomainError("La fecha del gasto no puede ser futura.")
        last_id = OperatingExpense.objects.order_by("-pk").values_list("pk", flat=True).first() or 0
        obj = checked_save(OperatingExpense(number=f"G-{last_id + 1:08d}", **data, created_by=actor))
        audit(actor, "expense.create", obj, category=obj.category, amount=str(obj.amount))
        return {"id": obj.pk}

    return run(actor, key, "expense.create", data, operation)


def void_payment(actor, key, pk, reason):
    def operation():
        require(actor, "finance")
        payment = Payment.objects.select_for_update().get(pk=pk)
        if payment.voided_at or not reason.strip():
            raise DomainError("Indica un motivo para anular un pago válido.")
        if payment.reservation_id:
            raise DomainError(
                "Los anticipos de reserva requieren conciliación y no se anulan desde este formulario."
            )
        if payment.contract and payment.contract.state != "ACTIVE":
            raise DomainError("No se anulan pagos de un contrato cerrado.")
        payment.voided_at, payment.void_reason = timezone.now(), reason
        payment.save(update_fields=["voided_at", "void_reason"])
        audit(actor, "payment.void", payment)
        event(
            actor,
            payment.contract.space,
            "PAYMENT_VOIDED",
            f"Pago P-{pk} anulado. Motivo: {reason}",
        )
        return {"id": pk, "contract_id": payment.contract_id}

    return run(actor, key, "payment.void", {"id": pk, "reason": reason}, operation)


def bury(actor, key, data):
    def operation():
        require(actor, "operations")
        person = Person.objects.select_for_update().get(pk=data["person"].pk)
        space = Space.objects.select_for_update().get(pk=data["space"].pk)
        contract = Contract.objects.select_for_update().get(pk=data["contract"].pk)
        available_for(actor, space, contract.responsible_id)
        when = data["occurred_at"]
        day = timezone.localtime(when).date()
        valid_contract(contract, space, day)
        if day < person.death_date or when > timezone.now():
            raise DomainError(
                "La inhumación debe estar entre el fallecimiento y la fecha actual."
            )
        if person.occupancies.filter(ended_at__isnull=True).exists():
            raise DomainError("La persona ya tiene una ocupación vigente.")
        if not person.responsible_links.filter(
            responsible=contract.responsible
        ).exists():
            raise DomainError(
                "El responsable del contrato debe estar vinculado a la persona fallecida."
            )
        if not data["notes"].strip():
            raise DomainError(
                "Registra el responsable operativo y las observaciones de la inhumación."
            )
        occupancy = checked_save(
            Occupancy(space=space, person=person, contract=contract, started_at=when)
        )
        space.revision += 1
        space.save(update_fields=["revision"])
        event(
            actor,
            space,
            "BURIAL",
            f"Inhumación registrada. {data['notes']}",
            person=person,
            occurred_at=when,
        )
        audit(actor, "occupancy.create", occupancy)
        return {"id": occupancy.pk, "space_id": space.pk}

    return run(actor, key, "burial.create", data, operation)


def request_movement(actor, key, data):
    def operation():
        require(actor, "operations")
        occupancy = Occupancy.objects.select_for_update().get(pk=data["occupancy"].pk)
        if occupancy.ended_at:
            raise DomainError("Esta ocupación ya finalizó.")
        if data["proposed_on"] < timezone.localtime(occupancy.started_at).date():
            raise DomainError("La fecha propuesta no puede preceder a la inhumación.")
        if data["kind"] == "TRANSFER":
            if not data.get("destination") or not data.get("destination_contract"):
                raise DomainError(
                    "El traslado requiere sepultura y contrato de destino."
                )
            if data["destination"].pk == occupancy.space_id:
                raise DomainError("El destino debe ser distinto del origen.")
            data["destination"] = Space.objects.select_for_update().get(
                pk=data["destination"].pk
            )
            data["destination_contract"] = Contract.objects.select_for_update().get(
                pk=data["destination_contract"].pk
            )
            available_for(
                actor, data["destination"], data["destination_contract"].responsible_id
            )
            valid_contract(
                data["destination_contract"], data["destination"], data["proposed_on"]
            )
        elif data["kind"] == "EXHUMATION":
            if not data.get("external_destination", "").strip():
                raise DomainError("Registra el destino de los restos.")
            data["destination"], data["destination_contract"] = None, None
        else:
            raise DomainError("Tipo de movimiento inválido.")
        obj = checked_save(Movement(**data, requested_by=actor))
        event(
            actor,
            occupancy.space,
            "MOVEMENT_REQUESTED",
            f"Solicitud M-{obj.pk}: {obj.get_kind_display()}. El espacio sigue ocupado.",
            person=occupancy.person,
        )
        audit(actor, "movement.request", obj)
        return {"id": obj.pk}

    return run(actor, key, "movement.request", data.copy(), operation)


def movement_action(
    actor, key, pk, action, reason="", document_reference="", occurred_at=None
):
    def operation():
        require(actor, "authorize" if action == "authorize" else "operations")
        movement = Movement.objects.select_for_update().get(pk=pk)
        occupancy = Occupancy.objects.select_for_update().get(pk=movement.occupancy_id)
        if action == "cancel":
            if movement.state not in ("REQUESTED", "AUTHORIZED") or not reason.strip():
                raise DomainError(
                    "Solo se cancela una solicitud pendiente y con motivo."
                )
            movement.state, movement.cancellation_reason = "CANCELLED", reason
            movement.save(update_fields=["state", "cancellation_reason"])
        elif action == "authorize":
            if not settings.CEMETERY_MOVEMENTS_APPROVED:
                raise DomainError(
                    "Primero deben validarse las condiciones operativas de exhumación/traslado. Consulta la configuración y documentación."
                )
            if (
                movement.state != "REQUESTED"
                or not document_reference.strip()
                or occupancy.ended_at
            ):
                raise DomainError(
                    "Se exige solicitud vigente y referencia documental para autorizar."
                )
            movement.state, movement.document_reference = (
                "AUTHORIZED",
                document_reference,
            )
            movement.authorized_by, movement.authorized_at = actor, timezone.now()
            movement.save()
        elif action == "execute":
            if (
                not settings.CEMETERY_MOVEMENTS_APPROVED
                or movement.state != "AUTHORIZED"
                or occupancy.ended_at
            ):
                raise DomainError(
                    "Solo se ejecutan movimientos autorizados de ocupaciones vigentes."
                )
            when = occurred_at or timezone.now()
            if (
                when > timezone.now()
                or when < occupancy.started_at
                or when < movement.authorized_at
            ):
                raise DomainError(
                    "La ejecución debe ser posterior a la inhumación y autorización, y no futura."
                )
            origin = Space.objects.select_for_update().get(pk=occupancy.space_id)
            if movement.kind == "TRANSFER":
                destination = Space.objects.select_for_update().get(
                    pk=movement.destination_id
                )
                contract = Contract.objects.select_for_update().get(
                    pk=movement.destination_contract_id
                )
                available_for(actor, destination, contract.responsible_id)
                valid_contract(contract, destination, timezone.localtime(when).date())
                if not occupancy.person.responsible_links.filter(
                    responsible=contract.responsible
                ).exists():
                    raise DomainError(
                        "El responsable del contrato de destino debe estar vinculado a la persona."
                    )
            occupancy.ended_at = when
            occupancy.save(update_fields=["ended_at"])
            if movement.kind == "TRANSFER":
                checked_save(
                    Occupancy(
                        space=destination,
                        person=occupancy.person,
                        contract=contract,
                        started_at=when,
                    )
                )
                destination.revision += 1
                destination.save(update_fields=["revision"])
                event(
                    actor,
                    destination,
                    "TRANSFER_IN",
                    f"Traslado M-{pk} desde {origin.code}.",
                    person=occupancy.person,
                    occurred_at=when,
                )
            origin.revision += 1
            origin.save(update_fields=["revision"])
            movement.state, movement.executed_at, movement.executed_by = (
                "EXECUTED",
                when,
                actor,
            )
            movement.save()
            destination_label = (
                movement.destination.code
                if movement.destination_id
                else movement.external_destination
            )
            event(
                actor,
                origin,
                movement.kind,
                f"Movimiento M-{pk} ejecutado. Destino: {destination_label}.",
                person=occupancy.person,
                occurred_at=when,
            )
        else:
            raise DomainError("Acción inválida.")
        audit(actor, f"movement.{action}", movement)
        if action != "execute":
            event(
                actor,
                occupancy.space,
                f"MOVEMENT_{action.upper()}",
                f"Solicitud M-{pk}: {movement.get_state_display()}.",
                person=occupancy.person,
            )
        return {"id": movement.pk, "space_id": occupancy.space_id}

    return run(
        actor,
        key,
        f"movement.{action}",
        {
            "id": pk,
            "reason": reason,
            "document_reference": document_reference,
            "occurred_at": occurred_at,
        },
        operation,
    )


def save_user(actor, key, data, pk=None):
    def operation():
        require(actor, "users")
        user = User.objects.select_for_update().get(pk=pk) if pk else User()
        if data["role"] == User.Role.FAMILY or (pk and user.role == User.Role.FAMILY):
            raise DomainError("Las cuentas familiares se crean por registro público y se gestionan desde Cuentas familiares.")
        public_fields = ("email", "first_name", "last_name", "role", "is_active")
        previous = audit_values(user, public_fields)
        if (
            pk
            and user.role == "ADMIN"
            and user.is_active
            and (data["role"] != "ADMIN" or not data["is_active"])
        ):
            if (
                not User.objects.filter(role="ADMIN", is_active=True)
                .exclude(pk=pk)
                .exists()
            ):
                raise DomainError("Debe conservarse al menos un administrador activo.")
        for field in ("email", "first_name", "last_name", "role", "is_active"):
            setattr(user, field, data[field])
        password = data.get("password")
        if not pk and not password:
            raise DomainError("La contraseña inicial es obligatoria.")
        if password:
            validate_password(password, user)
            user.set_password(password)
        checked_save(user)
        audit(
            actor,
            "user.update" if pk else "user.create",
            user,
            role=user.role,
            active=user.is_active,
            previous=previous,
            new=audit_values(user, public_fields),
        )
        return {"id": user.pk}

    return run(actor, key, "user.save", {"id": pk, **data}, operation)
