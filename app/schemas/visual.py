from pydantic import BaseModel

from app.models.enums import EstadoTrabajoVisual, TipoRecursoVisual
from app.schemas.bloques import Diagrama


class ImagenPublica(BaseModel):
    url: str
    texto_alternativo: str
    pie: str
    autor: str | None
    licencia: str | None
    url_licencia: str | None
    url_origen: str | None
    proveedor: str | None


class VisualPublico(BaseModel):
    estado: EstadoTrabajoVisual
    tipo: TipoRecursoVisual | None
    imagen: ImagenPublica | None
    diagrama: Diagrama | None
    generado_por_ia: bool
    aviso_ia: str | None
