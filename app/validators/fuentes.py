import re
import uuid
from collections.abc import Collection, Iterable, Mapping, Sequence

from app.fuentes.bloqueo import es_dominio_bloqueado
from app.schemas.bloques import BLOQUES_CON_HECHOS, BloqueTutor
from app.validators.texto import compilar, contiene_alguno, normalizar_para_comparar

# Algo con forma de dominio o URL dentro del texto (p. ej. sitio.org/ruta).
_PATRON_DOMINIO = re.compile(r"(?:https?://)?(?:[a-z0-9-]+\.)+[a-z]{2,}(?:[/?#]\S*)?")
_VERBOS_ATRIBUCION = r"(dice|dicen|indica|afirma|explica|senala|define|menciona|sostiene|establece)"
# Atribuir un dato a Wikipedia; mencionarla para explicar por qué no se usa sí se permite.
_PATRONES_ATRIBUCION = compilar(
    r"\bsegun\b[^.;:!?]{0,40}\bwikipedia\b",
    r"\bde acuerdo (con|a)\b[^.;:!?]{0,40}\bwikipedia\b",
    rf"\bwikipedia\s+(nos\s+|te\s+|lo\s+)?{_VERBOS_ATRIBUCION}\b",
    rf"\ben\b[^.;:!?,]{{0,40}}\bwikipedia\b,?\s+(se\s+|nos\s+)?({_VERBOS_ATRIBUCION}|lee|aparece)\b",
    r"(^|[.!?]\s*)en\b[^.;:!?,]{0,40}\bwikipedia\b\s*,",
)


def _motivos_bloque(
    indice: int, bloque: BloqueTutor, autoridades: Mapping[uuid.UUID, int]
) -> list[str]:
    if not isinstance(bloque, BLOQUES_CON_HECHOS):
        return []
    inexistentes = [f for f in bloque.fuentes if f not in autoridades]
    if inexistentes:
        return [f"bloque {indice}: cita fuentes que no se recuperaron en esta conversación"]
    if not bloque.afirma_hechos:
        return []
    if not bloque.fuentes:
        return [f"bloque {indice}: afirma hechos sin citar fuentes"]
    return []


def validar_citas(
    bloques: Sequence[BloqueTutor], autoridades: Mapping[uuid.UUID, int]
) -> list[str]:
    """`autoridades` mapea cada `id_fuente` recuperado en la conversación a su autoridad; las
    fuentes de dominio bloqueado no figuran en él, así que citarlas invalida la respuesta."""
    return [m for i, b in enumerate(bloques) for m in _motivos_bloque(i, b, autoridades)]


def contiene_url_bloqueada(texto: str, adicionales: Collection[str] = ()) -> bool:
    return any(
        es_dominio_bloqueado(m.group(0), adicionales)
        for m in _PATRON_DOMINIO.finditer(texto.lower())
    )


def atribuye_a_fuente_bloqueada(texto: str) -> bool:
    return contiene_alguno(normalizar_para_comparar(texto), _PATRONES_ATRIBUCION)


def cumple_autoridad_minima(autoridades: Iterable[int], minimo: int) -> bool:
    return any(a >= minimo for a in autoridades)
