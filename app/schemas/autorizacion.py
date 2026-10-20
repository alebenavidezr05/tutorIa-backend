from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import EstadoAutorizacion
from app.validators.usuario import normalizar_correo

LONGITUD_MIN_TOKEN = 20
LONGITUD_MAX_TOKEN = 100


class SolicitudAutorizacionEntrada(BaseModel):
    correo_acudiente: EmailStr
    correo_estudiante: EmailStr
    declara_representante_legal: bool = False
    version_politica: str = Field(min_length=1, max_length=20)
    acepta_tratamiento: bool = False
    acepta_transferencia_internacional: bool = False
    permite_compras: bool = False

    @field_validator("correo_acudiente", "correo_estudiante")
    @classmethod
    def _correo(cls, valor: str) -> str:
        return normalizar_correo(valor)


class TokenAutorizacionEntrada(BaseModel):
    token: str = Field(min_length=LONGITUD_MIN_TOKEN, max_length=LONGITUD_MAX_TOKEN)


class RevocarAutorizacionEntrada(TokenAutorizacionEntrada):
    eliminar_datos: bool = False


class AutorizacionPublica(BaseModel):
    estado: EstadoAutorizacion
    correo_estudiante_enmascarado: str
    permite_compras: bool
    fecha_expiracion_token: datetime


class MensajeGenerico(BaseModel):
    mensaje: str
