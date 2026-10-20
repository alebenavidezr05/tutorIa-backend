from typing import Any

from pydantic import BaseModel

from app.llm.base import HerramientaLLM
from app.schemas.bloques import (
    ActualizacionPerfil,
    EntradaBuscarFuentes,
    EntradaBuscarVideo,
    RespuestaTutor,
)

BUSCAR_FUENTES = "buscar_fuentes"
BUSCAR_VIDEO = "buscar_video"
RESPONDER = "responder"
ACTUALIZAR_PERFIL = "actualizar_perfil"
CLAVES_DESCARTABLES = {"title", "discriminator"}
PREFIJO_REF = "#/$defs/"


def _resolver(nodo: Any, definiciones: dict[str, Any]) -> Any:
    if isinstance(nodo, list):
        return [_resolver(n, definiciones) for n in nodo]
    if not isinstance(nodo, dict):
        return nodo
    if "$ref" in nodo:
        return _resolver(definiciones[nodo["$ref"].removeprefix(PREFIJO_REF)], definiciones)
    return {
        clave: _resolver(valor, definiciones)
        for clave, valor in nodo.items()
        if clave not in CLAVES_DESCARTABLES
    }


def esquema_desde_modelo(modelo: type[BaseModel]) -> dict[str, Any]:
    """Genera el JSON Schema desde Pydantic y aplana `$defs` para no depender de referencias."""
    esquema = modelo.model_json_schema()
    definiciones = esquema.pop("$defs", {})
    resultado: dict[str, Any] = _resolver(esquema, definiciones)
    return resultado


def herramienta_buscar_fuentes() -> HerramientaLLM:
    return HerramientaLLM(
        nombre=BUSCAR_FUENTES,
        descripcion=(
            "Recupera fuentes verificables (académicas, institucionales, educativas y de "
            "referencia) sobre un concepto. Úsala antes de afirmar cualquier hecho. Devuelve "
            "id_fuente, título, sitio, categoría, autoridad (1 a 4) y un extracto."
        ),
        esquema=esquema_desde_modelo(EntradaBuscarFuentes),
    )


def herramienta_buscar_video() -> HerramientaLLM:
    return HerramientaLLM(
        nombre=BUSCAR_VIDEO,
        descripcion=(
            "Busca videos explicativos revisados (4 a 20 minutos) sobre un tema complejo. "
            "Máximo una vez por turno. Devuelve id_video, título, canal, duración y puntos clave."
        ),
        esquema=esquema_desde_modelo(EntradaBuscarVideo),
    )


def herramienta_responder() -> HerramientaLLM:
    return HerramientaLLM(
        nombre=RESPONDER,
        descripcion=(
            "Entrega la respuesta final al estudiante en bloques de texto plano y termina el "
            "turno. Es obligatorio terminar cada turno llamando a esta herramienta."
        ),
        esquema=esquema_desde_modelo(RespuestaTutor),
    )


def herramienta_actualizar_perfil() -> HerramientaLLM:
    return HerramientaLLM(
        nombre=ACTUALIZAR_PERFIL,
        descripcion=(
            "Registra la síntesis pedagógica de la conversación. Solo información de aprendizaje; "
            "nunca datos personales, de salud, emocionales ni familiares."
        ),
        esquema=esquema_desde_modelo(ActualizacionPerfil),
    )


def herramientas_tutor() -> tuple[HerramientaLLM, ...]:
    return (herramienta_buscar_fuentes(), herramienta_buscar_video(), herramienta_responder())
