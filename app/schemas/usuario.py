import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.models.enums import EstadoCuenta, TipoNivel
from app.validators.usuario import validar_nivel_educativo, validar_nombre


class UsuarioPublico(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_usuario: uuid.UUID
    nombre: str
    correo: str
    tipo_nivel: TipoNivel
    nivel_educativo: str
    estado_cuenta: EstadoCuenta
    es_menor: bool
    fecha_registro: datetime


class ActualizarPerfilEntrada(BaseModel):
    nombre: str
    tipo_nivel: TipoNivel
    nivel_educativo: str

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor: str) -> str:
        return validar_nombre(valor)

    @model_validator(mode="after")
    def _nivel(self) -> "ActualizarPerfilEntrada":
        self.nivel_educativo = validar_nivel_educativo(self.tipo_nivel, self.nivel_educativo)
        return self
