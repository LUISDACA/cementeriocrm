from django.conf import settings
from .permissions import can, may_read_contacts, may_read_finance


def navigation(request):
    user = request.user
    return {
        "academic_mode": getattr(settings, "ACADEMIC_MODE", False),
        "bootstrap_css": (
            settings.BASE_DIR / "static/vendor/bootstrap.min.css"
        ).exists(),
        "cemetery_name": settings.CEMETERY_NAME,
        "currency": settings.CEMETERY_CURRENCY,
        "access": {
            cap: can(user, cap)
            for cap in [
                "spaces",
                "people",
                "contacts",
                "contracts",
                "finance",
                "operations",
                "authorize",
                "users",
                "audit",
            ]
        },
        "read_contacts": may_read_contacts(user),
        "read_finance": may_read_finance(user),
        "movements_approved": settings.CEMETERY_MOVEMENTS_APPROVED,
    }
