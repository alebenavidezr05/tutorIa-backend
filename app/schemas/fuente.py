import uuid

from pydantic import BaseModel, ConfigDict

from app.models.enums import CategoriaFuente, TipoFuente


class FuentePublica(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_fuente: uuid.UUID
    tipo: TipoFuente
    categoria: CategoriaFuente
    titulo: str
    sitio: str
    url: str
    autor: str | None
    doi: str | None
    licencia: str | None


class ReferenciaPublica(BaseModel):
    id_fuente: uuid.UUID | None = None
    id_recurso: uuid.UUID | None = None
    id_video: uuid.UUID | None = None
    tipo: str
    texto_apa: str
    url: str | None
