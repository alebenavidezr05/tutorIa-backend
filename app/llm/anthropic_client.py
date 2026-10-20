import logging
import time
from dataclasses import dataclass
from typing import Any

import anthropic

from app.core.config import Settings
from app.exceptions.base import LLMNoConfiguradoError, LLMNoDisponibleError
from app.llm.base import (
    BloqueDocumentoLLM,
    BloqueImagenLLM,
    BloqueLLM,
    BloqueOpaco,
    BloqueResultadoHerramienta,
    BloqueSistema,
    BloqueTextoLLM,
    BloqueUsoHerramienta,
    HerramientaLLM,
    LLMClient,
    LLMRespuesta,
    LLMSolicitud,
    MensajeLLM,
    NivelModelo,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResultadoPrueba:
    modelo: str
    exito: bool
    latencia_ms: int = 0
    tokens_entrada: int = 0
    tokens_salida: int = 0
    error: str = ""


MS_POR_SEGUNDO = 1000
CACHE_EFIMERA = {"type": "ephemeral"}
# Los modelos vigentes (p. ej. Sonnet 5.5) rechazan tool_choice "any"/"tool" con un 400: se usa
# "auto" y el prompt exige terminar con `responder`; el bucle del tutor comprueba que lo haga.
ELECCION_HERRAMIENTA = {"type": "auto"}


def _bloque_sistema(bloque: BloqueSistema) -> dict[str, Any]:
    datos: dict[str, Any] = {"type": "text", "text": bloque.texto}
    if bloque.cacheable:
        datos["cache_control"] = CACHE_EFIMERA
    return datos


def _fuente_base64(media_type: str, datos: str) -> dict[str, str]:
    return {"type": "base64", "media_type": media_type, "data": datos}


def _bloque_api(bloque: BloqueLLM) -> dict[str, Any]:
    match bloque:
        case BloqueTextoLLM(texto=texto):
            return {"type": "text", "text": texto}
        case BloqueImagenLLM(media_type=media_type, datos_base64=datos):
            return {"type": "image", "source": _fuente_base64(media_type, datos)}
        case BloqueDocumentoLLM(media_type=media_type, datos_base64=datos):
            return {"type": "document", "source": _fuente_base64(media_type, datos)}
        case BloqueUsoHerramienta(id=id_uso, nombre=nombre, entrada=entrada):
            return {"type": "tool_use", "id": id_uso, "name": nombre, "input": entrada}
        case BloqueResultadoHerramienta(id_uso=id_uso, contenido=contenido, es_error=es_error):
            return {
                "type": "tool_result",
                "tool_use_id": id_uso,
                "content": contenido,
                "is_error": es_error,
            }
        case BloqueOpaco(datos=datos):
            return datos
    raise TypeError(f"bloque no soportado: {type(bloque).__name__}")


def _mensaje_api(mensaje: MensajeLLM) -> dict[str, Any]:
    return {"role": mensaje.rol, "content": [_bloque_api(b) for b in mensaje.contenido]}


def _herramienta_api(herramienta: HerramientaLLM) -> dict[str, Any]:
    return {
        "name": herramienta.nombre,
        "description": herramienta.descripcion,
        "input_schema": herramienta.esquema,
    }


def _bloque_respuesta(bloque: Any) -> BloqueLLM:
    if bloque.type == "text":
        return BloqueTextoLLM(bloque.text)
    if bloque.type == "tool_use":
        return BloqueUsoHerramienta(id=bloque.id, nombre=bloque.name, entrada=dict(bloque.input))
    # Razonamiento y otros bloques se devuelven intactos: la API exige reenviarlos sin cambios.
    return BloqueOpaco(bloque.to_dict())


class AnthropicClient(LLMClient):
    """Único lugar que conoce el SDK de Anthropic y traduce sus errores a excepciones propias."""

    def __init__(self, settings: Settings, cliente: anthropic.Anthropic | None = None) -> None:
        self._modelos = {
            NivelModelo.SENCILLO: settings.llm_model_sencillo,
            NivelModelo.COMPLEJO: settings.llm_model_complejo,
        }
        clave = settings.llm_api_key.get_secret_value() if settings.llm_api_key else None
        self._cliente = cliente or anthropic.Anthropic(
            api_key=clave,
            timeout=settings.llm_timeout_segundos,
            max_retries=settings.llm_reintentos_red,
        )

    def completar(self, solicitud: LLMSolicitud) -> LLMRespuesta:
        modelo = self._modelos[solicitud.nivel_modelo]
        inicio = time.perf_counter()
        respuesta = self._invocar(modelo, self._parametros(solicitud))
        latencia_ms = int((time.perf_counter() - inicio) * MS_POR_SEGUNDO)
        resultado = self._traducir(respuesta)
        logger.info(
            "llm_ok modelo=%s tarea=%s latencia_ms=%s tokens_entrada=%s tokens_salida=%s",
            resultado.modelo,
            solicitud.tarea,
            latencia_ms,
            resultado.tokens_entrada,
            resultado.tokens_salida,
        )
        return resultado

    def probar_conexion(self, solicitud: LLMSolicitud) -> ResultadoPrueba:
        """Para `probar_llm`: distingue llave/modelo inválidos de falta de conexión."""
        modelo = self._modelos[solicitud.nivel_modelo]
        inicio = time.perf_counter()
        try:
            respuesta = self.completar(solicitud)
        except LLMNoConfiguradoError as exc:
            return ResultadoPrueba(modelo, False, error=exc.mensaje)
        except LLMNoDisponibleError:
            return ResultadoPrueba(
                modelo, False, error="Sin conexión con la API de Claude o servicio saturado."
            )
        latencia = int((time.perf_counter() - inicio) * MS_POR_SEGUNDO)
        return ResultadoPrueba(
            respuesta.modelo, True, latencia, respuesta.tokens_entrada, respuesta.tokens_salida
        )

    def cerrar(self) -> None:
        self._cliente.close()

    def _parametros(self, solicitud: LLMSolicitud) -> dict[str, Any]:
        parametros: dict[str, Any] = {
            "max_tokens": solicitud.max_tokens,
            "system": [_bloque_sistema(b) for b in solicitud.system],
            "messages": [_mensaje_api(m) for m in solicitud.mensajes],
        }
        if solicitud.herramientas:
            parametros["tools"] = [_herramienta_api(h) for h in solicitud.herramientas]
            parametros["tool_choice"] = ELECCION_HERRAMIENTA
        return parametros

    def _invocar(self, modelo: str, parametros: dict[str, Any]) -> Any:
        try:
            return self._cliente.messages.create(model=modelo, **parametros)
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
            self._registrar_fallo(modelo, exc)
            raise LLMNoConfiguradoError("La llave de la API de Claude no es válida.") from exc
        except anthropic.NotFoundError as exc:
            self._registrar_fallo(modelo, exc)
            raise LLMNoConfiguradoError("El modelo configurado no está disponible.") from exc
        except (anthropic.APIConnectionError, anthropic.APIStatusError) as exc:
            self._registrar_fallo(modelo, exc)
            raise LLMNoDisponibleError() from exc

    def _registrar_fallo(self, modelo: str, exc: Exception) -> None:
        estado = getattr(exc, "status_code", None)
        logger.warning("llm_error modelo=%s tipo=%s estado=%s", modelo, type(exc).__name__, estado)

    def _traducir(self, respuesta: Any) -> LLMRespuesta:
        uso = respuesta.usage
        return LLMRespuesta(
            bloques=tuple(_bloque_respuesta(b) for b in respuesta.content),
            razon_parada=respuesta.stop_reason or "",
            modelo=respuesta.model,
            tokens_entrada=uso.input_tokens,
            tokens_salida=uso.output_tokens,
            tokens_cache_lectura=getattr(uso, "cache_read_input_tokens", 0) or 0,
            tokens_cache_escritura=getattr(uso, "cache_creation_input_tokens", 0) or 0,
        )
