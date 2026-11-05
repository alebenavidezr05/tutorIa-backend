"""Frontera tolerante del correo: validar una dirección y enviar sin propagar fallos."""

import logging

from pydantic.networks import validate_email
from pydantic_core import PydanticCustomError

from app.correo.base import Correo, CorreoClient

logger = logging.getLogger(__name__)


def correo_valido(texto: str) -> str | None:
    """Devuelve la dirección si tiene formato válido; None si no."""
    try:
        _, correo = validate_email(texto)
    except PydanticCustomError:
        return None
    return correo


def enviar_sin_fallar(cliente: CorreoClient, correo: Correo, evento: str) -> bool:
    """El llamador ya confirmó su transacción: un fallo de envío solo se registra (sin datos
    personales) y el usuario puede reintentar."""
    try:
        cliente.enviar(correo)
    except Exception as exc:
        logger.warning("%s tipo=%s", evento, type(exc).__name__)
        return False
    return True
