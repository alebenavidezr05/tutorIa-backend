import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.exceptions.base import LLMRespuestaInvalidaError
from app.schemas.bloques import (
    ActualizacionPerfil,
    CuestionarioGenerado,
    PlanGenerado,
    RespuestaTutor,
)

ModeloT = TypeVar("ModeloT", bound=BaseModel)
_PATRON_CERCA = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)
_PATRON_OBJETO = re.compile(r"\{.*\}", re.DOTALL)


def _quitar_cercas(texto: str) -> str:
    sin_cercas = _PATRON_CERCA.sub("", texto.strip())
    coincidencia = _PATRON_OBJETO.search(sin_cercas)
    return coincidencia.group(0) if coincidencia else sin_cercas


class LLMResponseParser:
    """Convierte la salida del modelo en modelos validados; cualquier fallo es una excepción propia."""

    def parse_cuestionario(self, texto: str) -> CuestionarioGenerado:
        return self._desde_texto(texto, CuestionarioGenerado)

    def parse_plan(self, texto: str) -> PlanGenerado:
        return self._desde_texto(texto, PlanGenerado)

    def intentar_parse_plan(self, texto: str) -> PlanGenerado | None:
        """Para el bucle de regeneración: un intento ilegible no es un error, se reintenta."""
        try:
            return self.parse_plan(texto)
        except LLMRespuestaInvalidaError:
            return None

    def intentar_validar(self, datos: Any, modelo: type[ModeloT]) -> ModeloT | None:
        """Entradas de herramientas auxiliares: si no validan, se devuelve un error al modelo."""
        try:
            return self._desde_dict(datos, modelo)
        except LLMRespuestaInvalidaError:
            return None

    def parse_respuesta_tutor(self, entrada: dict[str, Any]) -> RespuestaTutor:
        return self._desde_dict(entrada, RespuestaTutor)

    def parse_actualizacion_perfil(self, entrada: dict[str, Any]) -> ActualizacionPerfil:
        return self._desde_dict(entrada, ActualizacionPerfil)

    def _desde_texto(self, texto: str, modelo: type[ModeloT]) -> ModeloT:
        try:
            datos = json.loads(_quitar_cercas(texto))
        except json.JSONDecodeError as exc:
            raise LLMRespuestaInvalidaError() from exc
        return self._desde_dict(datos, modelo)

    def _desde_dict(self, datos: Any, modelo: type[ModeloT]) -> ModeloT:
        try:
            return modelo.model_validate(datos)
        except ValidationError as exc:
            raise LLMRespuestaInvalidaError() from exc
