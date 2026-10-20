import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import NivelCognitivo


class ItemHistorial(BaseModel):
    id_sesion: uuid.UUID
    id_plan: uuid.UUID
    tema: str
    nivel_estimado: NivelCognitivo | None
    fecha: datetime


class HistorialPagina(BaseModel):
    items: list[ItemHistorial]
    total: int
    pagina: int
    tamano: int
    limitado: bool
