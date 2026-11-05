from typing import Literal

from pydantic import BaseModel

from app.schemas.autorizacion import TokenAutorizacionEntrada


class VerificarCorreoEntrada(TokenAutorizacionEntrada):
    """Mismo formato de token que el enlace del acudiente."""


class VerificacionCorreoResultado(BaseModel):
    estado: Literal["VERIFICADO"] = "VERIFICADO"


class EstadoVerificacionCorreo(BaseModel):
    correo_verificado: bool
    correo_enmascarado: str
    puede_reenviar_en_segundos: int
