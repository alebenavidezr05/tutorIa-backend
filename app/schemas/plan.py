import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import EstadoPlan, NivelCognitivo
from app.schemas.actividad import ActividadPublica
from app.schemas.fuente import FuentePublica


class GenerarPlanEntrada(BaseModel):
    id_sesion: uuid.UUID


class PlanDetalle(BaseModel):
    id_plan: uuid.UUID
    id_sesion: uuid.UUID
    titulo: str
    explicacion: str
    tecnicas_estudio: list[str]
    nivel_bloom: NivelCognitivo
    validado: bool
    estado: EstadoPlan
    fecha_generacion: datetime
    actividades: list[ActividadPublica]
    fuentes: list[FuentePublica]
    acepta_archivos: bool
