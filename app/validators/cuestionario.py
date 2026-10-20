import uuid
from collections.abc import Set

from app.exceptions.base import LLMRespuestaInvalidaError, TemaNoPermitidoError
from app.schemas.bloques import CuestionarioGenerado, PreguntaGenerada


class CuestionarioValidator:
    """Exige tema académico y descarta preguntas sin una fuente entregada que las respalde."""

    def __init__(self, minimo: int, maximo: int) -> None:
        self._minimo = minimo
        self._maximo = maximo

    def validar(
        self, cuestionario: CuestionarioGenerado, ids_fuentes: Set[uuid.UUID]
    ) -> list[PreguntaGenerada]:
        if not cuestionario.tema_academico:
            raise TemaNoPermitidoError("Ese tema no es académico. Escribe un tema de estudio.")
        respaldadas = [p for p in cuestionario.preguntas if p.id_fuente in ids_fuentes]
        if len(respaldadas) < self._minimo:
            raise LLMRespuestaInvalidaError(
                "No fue posible crear un cuestionario respaldado por fuentes. Intenta de nuevo."
            )
        return respaldadas[: self._maximo]
