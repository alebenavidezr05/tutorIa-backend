import uuid
from dataclasses import dataclass

from pydantic import BaseModel

from app.models.enums import ContextoArchivo

__all__ = ["ArchivoDescarga", "ArchivoPublico", "ContextoArchivo", "EntradaArchivo"]


class ArchivoPublico(BaseModel):
    id_archivo: uuid.UUID
    nombre: str
    mime: str
    tamano_bytes: int


@dataclass(frozen=True)
class EntradaArchivo:
    nombre: str
    contenido: bytes


@dataclass(frozen=True)
class ArchivoDescarga:
    nombre: str
    contenido: bytes
    mime: str
