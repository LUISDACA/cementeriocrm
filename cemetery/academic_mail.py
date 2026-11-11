"""Entrega local de mensajes de demostración; no utiliza SMTP ni registra cuerpos en logs."""

import os
from pathlib import Path
import uuid
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend


class AcademicMailboxBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        if not getattr(settings, "ACADEMIC_MODE", False):
            raise ImproperlyConfigured(
                "El buzón simulado requiere el perfil académico."
            )
        directory = Path(settings.ACADEMIC_MAIL_ROOT)
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        delivered = 0
        for message in email_messages:
            if not message.recipients():
                continue
            payload = message.message().as_bytes(linesep="\r\n")
            path = directory / f"{uuid.uuid4()}.eml"
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
            delivered += 1
        return delivered
