from app.core.config import Settings
from app.correo.base import CorreoClient
from app.correo.fake_client import FakeCorreoClient
from app.correo.ses_correo_client import SesCorreoClient, SmtpCorreoClient


def crear_correo_client(settings: Settings) -> CorreoClient:
    if settings.correo_proveedor == "ses":
        return SesCorreoClient(settings)
    if settings.correo_proveedor == "smtp":
        return SmtpCorreoClient(settings)
    return FakeCorreoClient()
