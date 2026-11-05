from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import EstadoAutorizacion, EstadoAutorizacionEstudiante

LONGITUD_MIN_TOKEN = 20
LONGITUD_MAX_TOKEN = 100


class TokenAutorizacionEntrada(BaseModel):
    token: str = Field(min_length=LONGITUD_MIN_TOKEN, max_length=LONGITUD_MAX_TOKEN)


class ConfirmarAutorizacionEntrada(TokenAutorizacionEntrada):
    """La versión debe ser la vigente: garantiza que el adulto confirmó el texto que se registra."""

    version_politica: str = Field(min_length=1, max_length=20)


class RevocarAutorizacionEntrada(TokenAutorizacionEntrada):
    eliminar_datos: bool = False


class ReenviarAutorizacionEntrada(BaseModel):
    # Sin correo: se reenvía al mismo acudiente. Se valida en el service (CORREO_ACUDIENTE_*).
    correo_acudiente: str | None = Field(default=None, max_length=254)


class AutorizacionPublica(BaseModel):
    estado: EstadoAutorizacion
    nombre_estudiante: str
    correo_estudiante_enmascarado: str
    texto_consentimiento: str
    version_politica: str
    # Siempre false: la autorización ya no pregunta por compras (un menor no puede pagar).
    permite_compras: bool
    fecha_expiracion_token: datetime


class MiAutorizacion(BaseModel):
    estado: EstadoAutorizacionEstudiante
    correo_acudiente_enmascarado: str | None
    puede_reenviar_en_segundos: int


class MensajeGenerico(BaseModel):
    mensaje: str
