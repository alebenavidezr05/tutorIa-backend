from datetime import datetime

from app.schemas.perfil_aprendizaje import (
    MAX_CLAVE_TEMA,
    MAX_ITEMS_TEMA,
    MAX_TEMAS,
    MAX_TEXTO_ITEM,
    PreferenciasAprendizaje,
    TemaPerfil,
)
from app.validators.texto import normalizar_para_comparar, normalizar_texto, truncar


def normalizar_tema(tema: str) -> str:
    return normalizar_para_comparar(tema)[:MAX_CLAVE_TEMA]


def _limpiar_item(item: str) -> str:
    return truncar(normalizar_texto(item), MAX_TEXTO_ITEM)


def agregar_fifo(actuales: list[str], nuevos: list[str], maximo: int = MAX_ITEMS_TEMA) -> list[str]:
    """Agrega sin duplicar y conserva los más recientes: los más viejos salen primero."""
    resultado = list(actuales)
    for item in (_limpiar_item(n) for n in nuevos if n.strip()):
        if item in resultado:
            resultado.remove(item)
        resultado.append(item)
    return resultado[-maximo:]


def _podar_temas(temas: dict[str, TemaPerfil]) -> dict[str, TemaPerfil]:
    recientes = sorted(temas.items(), key=lambda par: par[1].ultima_vez, reverse=True)
    return dict(recientes[:MAX_TEMAS])


def fusionar_tema(
    preferencias: PreferenciasAprendizaje,
    tema: str,
    dificultades: list[str],
    fortalezas: list[str],
    ahora: datetime,
) -> PreferenciasAprendizaje:
    clave = normalizar_tema(tema)
    actual = preferencias.temas.get(clave, TemaPerfil(ultima_vez=ahora))
    fusionado = TemaPerfil(
        dificultades=agregar_fifo(actual.dificultades, dificultades),
        fortalezas=agregar_fifo(actual.fortalezas, fortalezas),
        ultima_vez=ahora,
    )
    temas = _podar_temas({**preferencias.temas, clave: fusionado})
    return preferencias.model_copy(update={"temas": temas})
