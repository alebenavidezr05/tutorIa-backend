from dataclasses import dataclass
from datetime import date

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models.enums import TipoNivel
from app.schemas.usuario import UsuarioPublico
from app.validators.usuario import (
    normalizar_correo,
    validar_contrasena,
    validar_nivel_educativo,
    validar_nombre,
)

LONGITUD_MAX_CONTRASENA_LOGIN = 128


class RegistroEntrada(BaseModel):
    nombre: str
    correo: EmailStr
    contrasena: str
    fecha_nacimiento: date
    tipo_nivel: TipoNivel
    nivel_educativo: str
    version_politica: str = Field(min_length=1, max_length=20)
    acepta_tratamiento: bool = False
    acepta_transferencia_internacional: bool = False
    acepta_personalizacion: bool = False
    acepta_comunicaciones: bool = False
    entiende_datos_menor: bool = False
    # Obligatorio de 13 a 17 años (lo decide el servidor); se valida en el service para responder
    # con un código estable (CORREO_ACUDIENTE_*). Mayor de edad: se ignora.
    correo_acudiente: str | None = Field(default=None, max_length=254)

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor: str) -> str:
        return validar_nombre(valor)

    @field_validator("correo")
    @classmethod
    def _correo(cls, valor: str) -> str:
        return normalizar_correo(valor)

    @field_validator("contrasena")
    @classmethod
    def _contrasena(cls, valor: str) -> str:
        return validar_contrasena(valor)

    @model_validator(mode="after")
    def _nivel(self) -> "RegistroEntrada":
        self.nivel_educativo = validar_nivel_educativo(self.tipo_nivel, self.nivel_educativo)
        return self


class LoginEntrada(BaseModel):
    correo: str = Field(min_length=3, max_length=254)
    contrasena: str = Field(min_length=1, max_length=LONGITUD_MAX_CONTRASENA_LOGIN)

    @field_validator("correo")
    @classmethod
    def _correo(cls, valor: str) -> str:
        return normalizar_correo(valor)


@dataclass(frozen=True)
class SesionAutenticada:
    usuario: UsuarioPublico
    token: str


@dataclass(frozen=True)
class ContextoSolicitud:
    """Datos de la petición que los services necesitan como evidencia (nunca se guardan en claro)."""

    ip: str | None
