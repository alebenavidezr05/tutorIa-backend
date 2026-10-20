from app.core.config import Settings
from app.moderacion.base import ModeradorClient
from app.moderacion.fake_client import FakeModeradorClient
from app.moderacion.openai_moderacion_client import OpenAIModeracionClient
from app.moderacion.tolerante import ModeradorTolerante


def crear_moderador(settings: Settings) -> ModeradorClient:
    if settings.moderacion_proveedor == "openai":
        return ModeradorTolerante(OpenAIModeracionClient(settings))
    return ModeradorTolerante(FakeModeradorClient())
