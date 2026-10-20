import logging
from dataclasses import dataclass

from app.core.config import Settings
from app.exceptions.base import ContenidoNoPermitidoError
from app.models.enums import AccionModeracion, CategoriaAlerta
from app.moderacion.base import ModeradorClient, ResultadoModeracion

logger = logging.getLogger(__name__)

PREFIJO_AUTOLESION = "self-harm"
CATEGORIA_ABUSO_MENORES = "sexual/minors"
UMBRAL_POR_DEFECTO = 0.5
# Prefijo de la categoría de OpenAI -> categoría propia de la alerta.
CATEGORIAS_RECHAZO = {
    "sexual": CategoriaAlerta.SEXUAL,
    "violence": CategoriaAlerta.VIOLENCIA,
    "harassment": CategoriaAlerta.ACOSO,
    "hate": CategoriaAlerta.ACOSO,
    "illicit": CategoriaAlerta.ILICITO,
}


@dataclass(frozen=True)
class DecisionModeracion:
    accion: AccionModeracion
    categoria: CategoriaAlerta | None = None
    # En abuso sexual infantil la alerta guarda solo la categoría, nunca el texto.
    guardar_detalle: bool = True
    moderador_disponible: bool = True


def _base(categoria: str) -> str:
    return categoria.split("/")[0]


class ModeracionService:
    def __init__(self, moderador: ModeradorClient, settings: Settings) -> None:
        self._moderador = moderador
        self._umbrales = settings.moderacion_umbrales

    def evaluar_entrada(self, texto: str) -> DecisionModeracion:
        return self._decidir(self._moderador.moderar_texto(texto))

    def evaluar_archivo(self, contenido: bytes, mime: str, texto: str | None) -> None:
        resultado = (
            self._moderador.moderar_texto(texto)
            if texto is not None
            else self._moderador.moderar_imagen(contenido, mime)
        )
        if self._decidir(resultado).accion != AccionModeracion.CONTINUAR:
            raise ContenidoNoPermitidoError()

    def imagen_es_apropiada(self, contenido: bytes, mime: str) -> bool:
        resultado = self._moderador.moderar_imagen(contenido, mime)
        return (
            resultado.disponible and self._decidir(resultado).accion == AccionModeracion.CONTINUAR
        )

    def texto_es_apropiado(self, texto: str) -> bool:
        resultado = self._moderador.moderar_texto(texto)
        return (
            resultado.disponible and self._decidir(resultado).accion == AccionModeracion.CONTINUAR
        )

    def _decidir(self, resultado: ResultadoModeracion) -> DecisionModeracion:
        if not resultado.disponible:
            logger.warning("moderacion_omitida motivo=no_disponible")
            return DecisionModeracion(AccionModeracion.CONTINUAR, moderador_disponible=False)
        superadas = {c for c, puntaje in resultado.categorias.items() if puntaje >= self._umbral(c)}
        if any(c.startswith(PREFIJO_AUTOLESION) for c in superadas):
            return DecisionModeracion(AccionModeracion.APOYO, CategoriaAlerta.AUTOLESION)
        rechazo = next(
            (
                CATEGORIAS_RECHAZO[_base(c)]
                for c in sorted(superadas)
                if _base(c) in CATEGORIAS_RECHAZO
            ),
            None,
        )
        if rechazo is not None:
            return DecisionModeracion(
                AccionModeracion.RECHAZAR,
                rechazo,
                guardar_detalle=CATEGORIA_ABUSO_MENORES not in superadas,
            )
        return DecisionModeracion(AccionModeracion.CONTINUAR)

    def _umbral(self, categoria: str) -> float:
        return self._umbrales.get(
            categoria, self._umbrales.get(_base(categoria), UMBRAL_POR_DEFECTO)
        )
