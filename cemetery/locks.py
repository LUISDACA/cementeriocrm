"""Bloqueos de producción y un modo serial explícito para verificación local."""

from contextlib import contextmanager
from threading import RLock
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection

_serial_locks = {43490001: RLock(), 43490002: RLock()}


@contextmanager
def transaction_lock(key):
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [key])
        yield
    elif getattr(settings, "CEMETERY_SERIAL_VERIFICATION", False):
        # Solo config.settings_verify: no acredita concurrencia entre procesos.
        with _serial_locks[key]:
            yield
    else:
        raise ImproperlyConfigured(
            "Las operaciones del cementerio requieren PostgreSQL."
        )
