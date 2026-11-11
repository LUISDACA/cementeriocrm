from django.core.exceptions import ValidationError
from django.db.models import Count, Exists, OuterRef, Q
from django.utils import timezone
from .models import Occupancy, Reservation, Space


def search_term(value):
    value = (value or "").strip()
    if len(value) > 200:
        raise ValidationError("La búsqueda admite hasta 200 caracteres.")
    return value


def reference_id(value, label="registro"):
    value = str(value or "").strip()
    if not value:
        return None
    if len(value) > 19 or not value.isascii() or not value.isdigit():
        raise ValidationError(f"El filtro de {label} no es válido.")
    number = int(value)
    if not 0 < number <= 9223372036854775807:
        raise ValidationError(f"El filtro de {label} no es válido.")
    return number


def text_query(term, *fields):
    result = Q()
    for part in search_term(term).split():
        match = Q()
        for field in fields:
            match |= Q(**{field + "__icontains": part})
        result &= match
    return result


def person_query(term, prefix=""):
    return text_query(
        term,
        *(prefix + field for field in ("first_name", "last_name", "identification")),
    )


def spaces():
    return Space.objects.select_related("block__zone").annotate(
        has_occupancy=Exists(
            Occupancy.objects.filter(space_id=OuterRef("pk"), ended_at__isnull=True)
        ),
        has_reservation=Exists(
            Reservation.objects.filter(
                space_id=OuterRef("pk"),
                state="ACTIVE",
                expires_on__gte=timezone.localdate(),
            )
        ),
    )


def filter_spaces(queryset, params):
    term = search_term(params.get("q", ""))
    if term:
        queryset = queryset.filter(code__icontains=term)
    for field in ("block", "block__zone"):
        value = params.get("block" if field == "block" else "zone", "")
        key = reference_id(value, "bloque" if field == "block" else "zona")
        if key is not None:
            queryset = queryset.filter(**{field + "_id": key})
    if params.get("kind"):
        if params["kind"] not in Space.Kind.values:
            raise ValidationError("El tipo de espacio no es válido.")
        queryset = queryset.filter(kind=params["kind"])
    status = params.get("status")
    if status == "OCCUPIED":
        queryset = queryset.filter(has_occupancy=True)
    elif status == "RESERVED":
        queryset = queryset.filter(has_occupancy=False, has_reservation=True)
    elif status in Space.Condition.values:
        queryset = queryset.filter(
            has_occupancy=False, has_reservation=False, condition=status
        )
    elif status:
        raise ValidationError("El estado del espacio no es válido.")
    return queryset


def space_counts():
    result = {
        "OCCUPIED": Count("pk", filter=Q(has_occupancy=True)),
        "RESERVED": Count("pk", filter=Q(has_occupancy=False, has_reservation=True)),
    }
    for condition in Space.Condition.values:
        result[condition] = Count(
            "pk",
            filter=Q(has_occupancy=False, has_reservation=False, condition=condition),
        )
    return spaces().aggregate(**result)
