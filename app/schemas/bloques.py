"""Modelos de lo que produce el LLM: bloques del tutor, entradas de herramientas y JSON generados.

Son la fuente única del esquema: de aquí salen el `input_schema` de las herramientas y la
validación de lo que devuelve el modelo.
"""

import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AmbitoMensaje, NivelDetalle, Ritmo, TipoVisualPreferido

MAX_BLOQUES = 8
MAX_FUENTES_POR_BLOQUE = 4
MAX_CONTENIDO_TEXTO = 1200
MIN_PASOS = 2
MAX_PASOS = 8
MIN_NODOS = 2
MAX_NODOS = 12
MAX_ARISTAS = 30
MAX_TEXTO_NODO = 60
MAX_CONCEPTO = 100
MAX_DESCRIPCION_VISUAL = 300


class _Estricto(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _BloqueConHechos(_Estricto):
    afirma_hechos: bool = False
    fuentes: list[uuid.UUID] = Field(default_factory=list, max_length=MAX_FUENTES_POR_BLOQUE)


class BloqueTexto(_BloqueConHechos):
    tipo: Literal["texto"]
    contenido: str = Field(min_length=1, max_length=MAX_CONTENIDO_TEXTO)


class BloquePasos(_BloqueConHechos):
    tipo: Literal["pasos"]
    titulo: str = Field(min_length=1, max_length=120)
    pasos: list[Annotated[str, Field(min_length=1, max_length=300)]] = Field(
        min_length=MIN_PASOS, max_length=MAX_PASOS
    )


class BloqueEjemplo(_BloqueConHechos):
    tipo: Literal["ejemplo"]
    titulo: str = Field(min_length=1, max_length=120)
    contenido: str = Field(min_length=1, max_length=MAX_CONTENIDO_TEXTO)


class BloqueAnalogia(_BloqueConHechos):
    tipo: Literal["analogia"]
    contenido: str = Field(min_length=1, max_length=800)


class BloqueFormula(_BloqueConHechos):
    tipo: Literal["formula"]
    latex: str = Field(min_length=1, max_length=300)
    descripcion: str = Field(min_length=1, max_length=400)


class BloquePreguntaComprension(_Estricto):
    tipo: Literal["pregunta_comprension"]
    enunciado: str = Field(min_length=1, max_length=400)


class BloqueVideo(_Estricto):
    tipo: Literal["video"]
    id_video: uuid.UUID


class BloquePreguntaResumen(_Estricto):
    tipo: Literal["pregunta_resumen"]
    enunciado: str = Field(min_length=1, max_length=400)
    id_video: uuid.UUID


BloqueTutor = Annotated[
    BloqueTexto
    | BloquePasos
    | BloqueEjemplo
    | BloqueAnalogia
    | BloqueFormula
    | BloquePreguntaComprension
    | BloqueVideo
    | BloquePreguntaResumen,
    Field(discriminator="tipo"),
]

BLOQUES_CON_HECHOS = (BloqueTexto, BloquePasos, BloqueEjemplo, BloqueAnalogia, BloqueFormula)


class NodoDiagrama(_Estricto):
    id: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    texto: str = Field(min_length=1, max_length=MAX_TEXTO_NODO)


class AristaDiagrama(_Estricto):
    desde: str = Field(min_length=1, max_length=20)
    hasta: str = Field(min_length=1, max_length=20)
    etiqueta: str | None = Field(default=None, max_length=40)


class Diagrama(_Estricto):
    tipo_diagrama: Literal["flujo", "mapa_conceptual"]
    titulo: str = Field(min_length=1, max_length=120)
    nodos: list[NodoDiagrama] = Field(min_length=MIN_NODOS, max_length=MAX_NODOS)
    aristas: list[AristaDiagrama] = Field(default_factory=list, max_length=MAX_ARISTAS)


class SolicitudVisual(_Estricto):
    concepto_canonico: str = Field(min_length=3, max_length=MAX_CONCEPTO)
    tipo_preferido: TipoVisualPreferido
    descripcion_visual: str = Field(min_length=3, max_length=MAX_DESCRIPCION_VISUAL)
    exige_exactitud: bool
    diagrama: Diagrama | None = None


class RespuestaTutor(_Estricto):
    """Entrada de la herramienta `responder`."""

    ambito: AmbitoMensaje
    bloques: list[BloqueTutor] = Field(default_factory=list, max_length=MAX_BLOQUES)
    solicitud_visual: SolicitudVisual | None = None


class EntradaBuscarFuentes(_Estricto):
    consulta: str = Field(min_length=3, max_length=100)
    motivo: str = Field(default="", max_length=200)


class EntradaBuscarVideo(_Estricto):
    tema: str = Field(min_length=3, max_length=100)
    motivo: str = Field(default="", max_length=200)


class OpcionesGeneradas(_Estricto):
    a: str = Field(min_length=1, max_length=400)
    b: str = Field(min_length=1, max_length=400)
    c: str = Field(min_length=1, max_length=400)
    d: str = Field(min_length=1, max_length=400)


class PreguntaGenerada(_Estricto):
    enunciado: str = Field(min_length=5, max_length=600)
    opciones: OpcionesGeneradas
    respuesta_correcta: Literal["a", "b", "c", "d"]
    id_fuente: uuid.UUID | None = None


class CuestionarioGenerado(_Estricto):
    tema_academico: bool
    materia: str = Field(default="", max_length=100)
    preguntas: list[PreguntaGenerada] = Field(default_factory=list, max_length=20)


class PlanGenerado(_Estricto):
    titulo: str = Field(default="", max_length=200)
    explicacion: str = Field(default="", max_length=6000)
    tecnicas_estudio: list[Annotated[str, Field(max_length=300)]] = Field(default_factory=list)
    actividades: list[Annotated[str, Field(max_length=800)]] = Field(default_factory=list)
    fuentes_usadas: list[uuid.UUID] = Field(default_factory=list)


class ActualizacionPerfil(_Estricto):
    """Entrada de la herramienta `actualizar_perfil` (consolidación con el modelo sencillo)."""

    resumen_conversacion: str = Field(max_length=600)
    dificultades: list[Annotated[str, Field(max_length=120)]] = Field(max_length=5)
    fortalezas: list[Annotated[str, Field(max_length=120)]] = Field(max_length=5)
    detalle: NivelDetalle
    ritmo: Ritmo
    resumen_perfil: str = Field(max_length=600)
