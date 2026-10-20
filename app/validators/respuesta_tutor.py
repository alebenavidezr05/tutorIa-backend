import re
import uuid
from collections.abc import Iterator, Mapping, Set

from app.models.enums import AmbitoMensaje
from app.schemas.bloques import (
    MAX_BLOQUES,
    BloqueEjemplo,
    BloquePreguntaResumen,
    BloqueTutor,
    BloqueVideo,
    RespuestaTutor,
    SolicitudVisual,
)
from app.validators.diagrama import validar_diagrama
from app.validators.entrega_directa import contiene_entrega_directa
from app.validators.fuentes import validar_citas
from app.validators.resultado import ResultadoValidacion
from app.validators.texto import (
    contiene_html,
    contiene_markdown,
    contiene_url,
    normalizar_para_comparar,
)

ROTULO_ILUSTRATIVO = "ejemplo ilustrativo"
CAMPOS_DE_TEXTO = ("contenido", "titulo", "enunciado", "descripcion")
_PATRON_DIGITO = re.compile(r"\d")


def _textos(bloque: BloqueTutor) -> Iterator[str]:
    for campo in CAMPOS_DE_TEXTO:
        valor = getattr(bloque, campo, None)
        if isinstance(valor, str):
            yield valor
    yield from getattr(bloque, "pasos", [])


def _motivos_formato(bloques: list[BloqueTutor]) -> list[str]:
    textos = [t for b in bloques for t in _textos(b)]
    motivos = []
    if any(contiene_html(t) or contiene_markdown(t) for t in textos):
        motivos.append("los bloques deben ser texto plano, sin HTML ni Markdown")
    if any(contiene_url(t) for t in textos):
        motivos.append("los bloques no pueden incluir URLs")
    if any(contiene_entrega_directa(t) for t in textos):
        motivos.append("entrega la respuesta directa de un ejercicio")
    return motivos


def _motivos_ejemplos(bloques: list[BloqueTutor]) -> list[str]:
    sin_rotulo = [
        b
        for b in bloques
        if isinstance(b, BloqueEjemplo)
        and _PATRON_DIGITO.search(b.contenido)
        and ROTULO_ILUSTRATIVO not in normalizar_para_comparar(b.contenido)
    ]
    return ["los números de práctica deben rotularse '(ejemplo ilustrativo)'"] if sin_rotulo else []


def _motivos_videos(bloques: list[BloqueTutor], ids_videos: Set[uuid.UUID]) -> list[str]:
    citados = [b.id_video for b in bloques if isinstance(b, BloqueVideo | BloquePreguntaResumen)]
    return ["cita videos que no devolvió la herramienta"] if set(citados) - ids_videos else []


def _motivos_visual(solicitud: SolicitudVisual | None) -> list[str]:
    if solicitud is None or solicitud.diagrama is None:
        return []
    return validar_diagrama(solicitud.diagrama)


class RespuestaTutorValidator:
    """Capa 3 del chat: estructura, formato, citas, videos, recurso visual y entrega directa."""

    def validar(
        self,
        respuesta: RespuestaTutor,
        autoridades_fuentes: Mapping[uuid.UUID, int],
        ids_videos: Set[uuid.UUID],
    ) -> ResultadoValidacion:
        if respuesta.ambito != AmbitoMensaje.ACADEMICO:
            return ResultadoValidacion(valido=True)
        bloques = respuesta.bloques
        motivos = [] if 1 <= len(bloques) <= MAX_BLOQUES else ["debe tener entre 1 y 8 bloques"]
        motivos += _motivos_formato(bloques) + _motivos_ejemplos(bloques)
        motivos += validar_citas(bloques, autoridades_fuentes)
        motivos += _motivos_videos(bloques, ids_videos) + _motivos_visual(
            respuesta.solicitud_visual
        )
        return ResultadoValidacion.desde_motivos(motivos)
