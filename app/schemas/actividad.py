import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import EstadoActividad
from app.schemas.archivo import ArchivoPublico

MAX_RESPUESTA_ACTIVIDAD = 4000


class ActividadPublica(BaseModel):
    id_actividad: uuid.UUID
    numero_orden: int
    enunciado: str
    respuesta_usuario: str | None
    archivo: ArchivoPublico | None
    estado: EstadoActividad
    fecha_completado: datetime | None


class ActualizarActividadEntrada(BaseModel):
    estado: EstadoActividad
    respuesta_usuario: str | None = Field(default=None, max_length=MAX_RESPUESTA_ACTIVIDAD)
    id_archivo: uuid.UUID | None = None
