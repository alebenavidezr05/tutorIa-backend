import uuid
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.enums import NivelCognitivo, OpcionRespuesta
from app.schemas.fuente import FuentePublica
from app.validators.tema import validar_tema

MAX_RESPUESTAS = 20


class CrearDiagnosticoEntrada(BaseModel):
    tema: str = Field(max_length=400)

    @field_validator("tema")
    @classmethod
    def _tema(cls, valor: str) -> str:
        return validar_tema(valor)


class OpcionesPublicas(BaseModel):
    a: str
    b: str
    c: str
    d: str


class PreguntaPublica(BaseModel):
    id_pregunta: uuid.UUID
    orden: int
    enunciado: str
    opciones: OpcionesPublicas


class CuestionarioPublico(BaseModel):
    """Nunca incluye la respuesta correcta ni la fuente que la respalda."""

    id_sesion: uuid.UUID
    tema: str
    materia: str
    preguntas: list[PreguntaPublica]


class RespuestaEntrada(BaseModel):
    id_pregunta: uuid.UUID
    respuesta: OpcionRespuesta

    @field_validator("respuesta", mode="before")
    @classmethod
    def _mayusculas(cls, valor: Any) -> Any:
        return valor.upper() if isinstance(valor, str) else valor


class RespuestasEntrada(BaseModel):
    respuestas: list[RespuestaEntrada] = Field(max_length=MAX_RESPUESTAS)


class ResultadoPregunta(BaseModel):
    id_pregunta: uuid.UUID
    respuesta_usuario: OpcionRespuesta
    es_correcta: bool
    respuesta_correcta: OpcionRespuesta
    fuente: FuentePublica | None


class ResultadoDiagnostico(BaseModel):
    id_sesion: uuid.UUID
    nivel_estimado: NivelCognitivo
    puntaje: Decimal
    aciertos: int
    total_preguntas: int
    resultados: list[ResultadoPregunta]
