import logging
import smtplib
from email.message import EmailMessage
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import Settings
from app.correo.base import Correo, CorreoClient
from app.exceptions.base import CorreoNoEnviadoError

logger = logging.getLogger(__name__)

CODIFICACION = "UTF-8"


class SesCorreoClient(CorreoClient):
    def __init__(self, settings: Settings, cliente: Any | None = None) -> None:
        self._remitente = settings.correo_remitente
        self._ses = cliente or boto3.client("sesv2", region_name=settings.ses_region)

    def enviar(self, correo: Correo) -> None:
        contenido = {
            "Simple": {
                "Subject": {"Data": correo.asunto, "Charset": CODIFICACION},
                "Body": {"Text": {"Data": correo.texto, "Charset": CODIFICACION}},
            }
        }
        try:
            self._ses.send_email(
                FromEmailAddress=self._remitente,
                Destination={"ToAddresses": [correo.destinatario]},
                Content=contenido,
            )
        except (BotoCoreError, ClientError) as exc:
            logger.warning("correo_error proveedor=ses tipo=%s", type(exc).__name__)
            raise CorreoNoEnviadoError() from exc


class SmtpCorreoClient(CorreoClient):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def enviar(self, correo: Correo) -> None:
        mensaje = EmailMessage()
        mensaje["From"] = self._settings.correo_remitente
        mensaje["To"] = correo.destinatario
        mensaje["Subject"] = correo.asunto
        mensaje.set_content(correo.texto)
        try:
            self._entregar(mensaje)
        except (smtplib.SMTPException, OSError) as exc:
            logger.warning("correo_error proveedor=smtp tipo=%s", type(exc).__name__)
            raise CorreoNoEnviadoError() from exc

    def _entregar(self, mensaje: EmailMessage) -> None:
        s = self._settings
        with smtplib.SMTP(s.smtp_host, s.smtp_puerto, timeout=s.imagenes_timeout_segundos) as smtp:
            if s.smtp_tls:
                smtp.starttls()
            if s.smtp_usuario:
                smtp.login(s.smtp_usuario, s.smtp_contrasena.get_secret_value())
            smtp.send_message(mensaje)
