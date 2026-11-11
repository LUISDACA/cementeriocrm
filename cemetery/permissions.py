from django.core.exceptions import PermissionDenied

CAPABILITIES = {
    "ADMIN": {
        "spaces",
        "people",
        "contacts",
        "contracts",
        "finance",
        "operations",
        "authorize",
        "users",
        "audit",
    },
    "OFFICE": {"spaces", "people", "contacts", "contracts"},
    "TREASURY": {"contacts", "contracts", "finance"},
    "OPERATIONS": {"people", "contacts", "operations"},
    "VIEWER": set(),
    "FAMILY": set(),
}


def can(user, capability):
    return bool(
        user.is_authenticated
        and user.is_active
        and capability in CAPABILITIES.get(user.role, set())
    )


def require(user, capability):
    if not can(user, capability):
        raise PermissionDenied("Tu perfil no permite realizar esta acción.")


def may_read_contacts(user):
    return can(user, "contacts")


def may_read_finance(user):
    return can(user, "finance") or can(user, "contracts")
