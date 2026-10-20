import base64
import logging
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import openai
import pytest

from app.core.config import Settings
from app.exceptions.base import (
    GeneracionImagenError,
    LLMNoConfiguradoError,
    LLMNoDisponibleError,
    LLMRespuestaInvalidaError,
    ModeracionNoDisponibleError,
)
from app.imagenes.constantes import CALIDAD_IMAGEN_IA, construir_prompt_imagen
from app.imagenes.openai_imagenes_client import OpenAIImagenesClient
from app.llm.anthropic_client import AnthropicClient
from app.llm.base import (
    BloqueOpaco,
    BloqueResultadoHerramienta,
    BloqueSistema,
    BloqueTextoLLM,
    BloqueUsoHerramienta,
    LLMSolicitud,
    MensajeLLM,
    NivelModelo,
    TareaLLM,
)
from app.llm.herramientas import esquema_desde_modelo, herramientas_tutor
from app.llm.parser import LLMResponseParser
from app.llm.selector_modelo import SelectorModelo, SenalesComplejidad
from app.models.enums import NivelCognitivo
from app.moderacion.openai_moderacion_client import OpenAIModeracionClient
from app.moderacion.tolerante import ModeradorTolerante
from app.schemas.bloques import RespuestaTutor

LLAVE = "sk-ant-api03-SECRETO-NO-DEBE-APARECER"


def _settings(settings: Settings) -> Settings:
    return settings.model_copy(
        update={
            "llm_provider": "anthropic",
            "llm_api_key": __import__("pydantic").SecretStr(LLAVE),
            "llm_model_sencillo": "modelo-sencillo",
            "llm_model_complejo": "modelo-complejo",
            "imagenes_ia_modelo": "modelo-imagen",
        }
    )


class _Bloque(SimpleNamespace):
    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


class _Mensajes:
    def __init__(self, resultado: Any) -> None:
        self.resultado = resultado
        self.llamadas: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.llamadas.append(kwargs)
        if isinstance(self.resultado, Exception):
            raise self.resultado
        return self.resultado


def _respuesta_sdk() -> Any:
    return SimpleNamespace(
        content=[
            _Bloque(type="thinking", thinking="", signature="firma"),
            _Bloque(type="text", text="Hola"),
            _Bloque(type="tool_use", id="toolu_1", name="responder", input={"ambito": "ACADEMICO"}),
        ],
        stop_reason="tool_use",
        model="modelo-complejo",
        usage=SimpleNamespace(
            input_tokens=10,
            output_tokens=5,
            cache_read_input_tokens=7,
            cache_creation_input_tokens=3,
        ),
    )


def _solicitud() -> LLMSolicitud:
    return LLMSolicitud(
        tarea=TareaLLM.TUTOR,
        system=(BloqueSistema("estatico", cacheable=True), BloqueSistema("dinamico")),
        mensajes=(
            MensajeLLM.usuario("hola"),
            MensajeLLM(
                rol="assistant",
                contenido=(
                    BloqueOpaco({"type": "thinking", "thinking": "", "signature": "s"}),
                    BloqueUsoHerramienta("t1", "buscar_fuentes", {"consulta": "x"}),
                ),
            ),
            MensajeLLM(
                rol="user", contenido=(BloqueResultadoHerramienta("t1", "datos", es_error=False),)
            ),
        ),
        nivel_modelo=NivelModelo.COMPLEJO,
        max_tokens=100,
        herramientas=herramientas_tutor(),
        herramienta_forzada="*",
    )


class TestAnthropicClient:
    def test_traduce_solicitud_y_respuesta(self, settings: Settings) -> None:
        mensajes = _Mensajes(_respuesta_sdk())
        cliente = AnthropicClient(
            _settings(settings), cliente=SimpleNamespace(messages=mensajes, close=lambda: None)
        )  # type: ignore[arg-type]
        respuesta = cliente.completar(_solicitud())
        llamada = mensajes.llamadas[0]
        assert llamada["model"] == "modelo-complejo"
        assert llamada["tool_choice"] == {"type": "auto"}
        assert (
            llamada["system"][0]["cache_control"] == {"type": "ephemeral"}
            and "cache_control" not in llamada["system"][1]
        )
        assert llamada["messages"][1]["content"][0] == {
            "type": "thinking",
            "thinking": "",
            "signature": "s",
        }
        assert llamada["messages"][2]["content"][0]["type"] == "tool_result"
        assert {t["name"] for t in llamada["tools"]} == {
            "buscar_fuentes",
            "buscar_video",
            "responder",
        }
        assert isinstance(respuesta.bloques[0], BloqueOpaco) and respuesta.texto() == "Hola"
        assert respuesta.usos_herramienta()[0].nombre == "responder"
        assert (respuesta.tokens_cache_lectura, respuesta.tokens_cache_escritura) == (7, 3)

    @pytest.mark.parametrize(
        ("error", "esperado"),
        [
            (
                anthropic.AuthenticationError(
                    "x",
                    response=httpx2.Response(401, request=httpx2.Request("POST", "https://a.b")),
                    body=None,
                ),
                LLMNoConfiguradoError,
            ),
            (
                anthropic.NotFoundError(
                    "x",
                    response=httpx2.Response(404, request=httpx2.Request("POST", "https://a.b")),
                    body=None,
                ),
                LLMNoConfiguradoError,
            ),
            (
                anthropic.RateLimitError(
                    "x",
                    response=httpx2.Response(429, request=httpx2.Request("POST", "https://a.b")),
                    body=None,
                ),
                LLMNoDisponibleError,
            ),
            (
                anthropic.InternalServerError(
                    "x",
                    response=httpx2.Response(529, request=httpx2.Request("POST", "https://a.b")),
                    body=None,
                ),
                LLMNoDisponibleError,
            ),
            (
                anthropic.APIConnectionError(request=httpx2.Request("POST", "https://a.b")),
                LLMNoDisponibleError,
            ),
        ],
    )
    def test_traduce_errores_sin_filtrar_la_llave(
        self,
        settings: Settings,
        error: Exception,
        esperado: type[Exception],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        cliente = AnthropicClient(
            _settings(settings),
            cliente=SimpleNamespace(messages=_Mensajes(error), close=lambda: None),
        )  # type: ignore[arg-type]
        caplog.set_level(logging.DEBUG)
        with pytest.raises(esperado) as capturado:
            cliente.completar(_solicitud())
        assert LLAVE not in str(capturado.value) and LLAVE not in caplog.text
        assert LLAVE not in repr(_settings(settings))

    def test_validacion_de_configuracion(self, settings: Settings) -> None:
        with pytest.raises(ValueError, match="LLM_API_KEY"):
            Settings(**{**settings.model_dump(), "llm_provider": "anthropic"})


class TestOpenAI:
    def test_imagen_siempre_en_calidad_baja(self, settings: Settings) -> None:
        llamadas: list[dict[str, Any]] = []

        def generar(**kwargs: Any) -> Any:
            llamadas.append(kwargs)
            return SimpleNamespace(
                data=[SimpleNamespace(b64_json=base64.b64encode(b"img").decode())],
                usage=SimpleNamespace(input_tokens=5, output_tokens=9),
            )

        cliente = OpenAIImagenesClient(
            _settings(settings), cliente=SimpleNamespace(images=SimpleNamespace(generate=generar))
        )  # type: ignore[arg-type]
        imagen = cliente.generar("una célula", "hmac-seudonimo")
        assert llamadas[0]["quality"] == CALIDAD_IMAGEN_IA == "low"
        assert (
            llamadas[0]["safety_identifier"] == "hmac-seudonimo"
            and llamadas[0]["model"] == "modelo-imagen"
        )
        assert imagen.contenido == b"img" and imagen.tokens_salida == 9

    def test_imagen_error(self, settings: Settings) -> None:
        def fallar(**_: Any) -> Any:
            raise openai.APIConnectionError(
                request=__import__("httpx2").Request("POST", "https://o.a")
            )

        cliente = OpenAIImagenesClient(
            _settings(settings), cliente=SimpleNamespace(images=SimpleNamespace(generate=fallar))
        )  # type: ignore[arg-type]
        with pytest.raises(GeneracionImagenError):
            cliente.generar("x", "y")

    def test_prompt_de_imagen_solo_con_descripcion(self) -> None:
        prompt = construir_prompt_imagen("el ciclo del agua", "ADOLESCENTE")
        assert "el ciclo del agua" in prompt and "Sin texto" in prompt and "15 a 17" in prompt

    def test_moderacion(self, settings: Settings) -> None:
        puntajes = SimpleNamespace(model_dump=lambda by_alias: {"self-harm": 0.9, "sexual": None})
        resultado = SimpleNamespace(
            results=[SimpleNamespace(flagged=True, category_scores=puntajes)]
        )
        cliente = OpenAIModeracionClient(
            settings,
            cliente=SimpleNamespace(moderations=SimpleNamespace(create=lambda **_: resultado)),
        )  # type: ignore[arg-type]
        assert cliente.moderar_texto("x").categorias == {"self-harm": 0.9}

        def fallar(**_: Any) -> Any:
            raise openai.APIConnectionError(
                request=__import__("httpx2").Request("POST", "https://o.a")
            )

        caido = OpenAIModeracionClient(
            settings, cliente=SimpleNamespace(moderations=SimpleNamespace(create=fallar))
        )  # type: ignore[arg-type]
        with pytest.raises(ModeracionNoDisponibleError):
            caido.moderar_imagen(b"x", "image/png")
        assert ModeradorTolerante(caido).moderar_texto("x").disponible is False


class TestHerramientasYParser:
    def test_esquema_sin_referencias(self) -> None:
        esquema = esquema_desde_modelo(RespuestaTutor)
        assert "$ref" not in str(esquema) and "$defs" not in esquema
        assert esquema["properties"]["bloques"]["maxItems"] == 8

    def test_parser_quita_cercas_y_falla_limpio(self) -> None:
        parser = LLMResponseParser()
        plan = parser.parse_plan('```json\n{"titulo": "T", "actividades": ["a"]}\n```')
        assert plan.titulo == "T"
        with pytest.raises(LLMRespuestaInvalidaError):
            parser.parse_cuestionario("no es json")
        with pytest.raises(LLMRespuestaInvalidaError):
            parser.parse_respuesta_tutor({"ambito": "OTRO"})
        assert parser.intentar_parse_plan("{") is None


class TestSelector:
    selector = SelectorModelo(umbral=3, palabras_largo=60)

    def _nivel(
        self, mensaje: str, nivel: NivelCognitivo, no_entendi: int = 0, archivo: bool = False
    ) -> str:
        return self.selector.elegir(SenalesComplejidad(mensaje, nivel, no_entendi, archivo)).value

    def test_casos_obligatorios(self) -> None:
        assert self._nivel("¿qué es la fotosíntesis?", NivelCognitivo.BASICO) == "SENCILLO"
        assert (
            self._nivel("compara y justifica las dos posturas", NivelCognitivo.AVANZADO)
            == "COMPLEJO"
        )
        assert self._nivel("hola " * 80 + "¿qué es un átomo?", NivelCognitivo.BASICO) == "SENCILLO"
        assert self._nivel("demuestra esto", NivelCognitivo.AVANZADO) == "COMPLEJO"
        assert self._nivel("no entiendo", NivelCognitivo.INTERMEDIO, no_entendi=5) == "COMPLEJO"
        assert self._nivel("revisa", NivelCognitivo.INTERMEDIO, archivo=True) == "COMPLEJO"

    def test_tareas_fijas(self) -> None:
        assert self.selector.para_tarea(TareaLLM.CUESTIONARIO) == NivelModelo.SENCILLO
        assert self.selector.para_tarea(TareaLLM.CONSOLIDACION) == NivelModelo.SENCILLO
        assert self.selector.para_tarea(TareaLLM.PLAN) == NivelModelo.COMPLEJO


def test_bloque_texto_en_mensaje() -> None:
    assert MensajeLLM.usuario("x").contenido == (BloqueTextoLLM("x"),)
