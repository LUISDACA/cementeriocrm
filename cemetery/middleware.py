from django.contrib.auth import logout
from django.core.exceptions import PermissionDenied
from django.utils import timezone


class SessionLifetimeMiddleware:
    """Límite absoluto además del vencimiento por inactividad de Django."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            if not request.user.is_active:
                logout(request)
            else:
                now = int(timezone.now().timestamp())
                issued = request.session.setdefault("issued_at", now)
                if now - issued >= 8 * 60 * 60:
                    logout(request)
        response = self.get_response(request)
        # Evitar almacenamiento compartido de páginas privadas y respuestas de dominio.
        if getattr(request, "user", None) and request.user.is_authenticated:
            response["Cache-Control"] = "private, no-store"
        return response


class FamilyPortalBoundaryMiddleware:
    """A self-registered family account can only reach public auth and its portal."""

    ALLOWED_PREFIXES = (
        "/ingresar/",
        "/salir/",
        "/registro/",
        "/privacidad/",
        "/recuperar/",
        "/mi-cuenta/",
        "/static/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        path = request.path_info
        if (
            user is not None
            and user.is_authenticated
            and user.role == "FAMILY"
            and path != "/"
            and not any(path == prefix or path.startswith(prefix) for prefix in self.ALLOWED_PREFIXES)
        ):
            raise PermissionDenied("Tu cuenta familiar solo permite acceder a Mi cuenta.")
        return self.get_response(request)
