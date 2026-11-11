"""Perfil exclusivo de comprobación serial: no es configuración de despliegue.

Permite probar reglas, formularios y HTTP cuando el sandbox prohíbe sockets.
No verifica migraciones PostgreSQL, advisory locks ni concurrencia real.
"""

from .settings import *  # noqa: F403

DEBUG = True
SECURE_SSL_REDIRECT = False
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
MIGRATION_MODULES = {"cemetery": None}
CEMETERY_SERIAL_VERIFICATION = True
PASSWORD_HASHERS = ["django.contrib.auth.hashers.PBKDF2PasswordHasher"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
