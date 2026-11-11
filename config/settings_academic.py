"""Demostración académica con PostgreSQL y operaciones completamente simuladas."""

from .settings import *  # noqa: F403

ACADEMIC_MODE = True
CEMETERY_MOVEMENTS_APPROVED = True
EMAIL_BACKEND = "cemetery.academic_mail.AcademicMailboxBackend"
ACADEMIC_MAIL_ROOT = BASE_DIR / ".academic-mail"  # noqa: F405
