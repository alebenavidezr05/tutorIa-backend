import uuid
from collections.abc import Iterable, Mapping, Sequence

from app.schemas.bloques import BLOQUES_CON_HECHOS, BloqueTutor

# Autoridad 1 = obra colaborativa: sirve de contexto, nunca respalda sola un hecho (§12.2).
AUTORIDAD_COLABORATIVA = 1
AUTORIDAD_MINIMA_RESPALDO = AUTORIDAD_COLABORATIVA + 1


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
    if max(autoridades[f] for f in bloque.fuentes) < AUTORIDAD_MINIMA_RESPALDO:
        return [f"bloque {indice}: un hecho no puede apoyarse solo en una fuente colaborativa"]
    return []


def validar_citas(
    bloques: Sequence[BloqueTutor], autoridades: Mapping[uuid.UUID, int]
) -> list[str]:
    """`autoridades` mapea cada `id_fuente` recuperado en la conversación a su autoridad."""
    return [m for i, b in enumerate(bloques) for m in _motivos_bloque(i, b, autoridades)]


def cumple_autoridad_minima(autoridades: Iterable[int], minimo: int) -> bool:
    return any(a >= minimo for a in autoridades)
