from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal

HERRAMIENTA_CUALQUIERA = "*"


class TareaLLM(StrEnum):
    CUESTIONARIO = "CUESTIONARIO"
    PLAN = "PLAN"
    TUTOR = "TUTOR"
    CONSOLIDACION = "CONSOLIDACION"


class NivelModelo(StrEnum):
    SENCILLO = "SENCILLO"
    COMPLEJO = "COMPLEJO"


@dataclass(frozen=True)
class BloqueSistema:
    texto: str
    cacheable: bool = False


@dataclass(frozen=True)
class BloqueTextoLLM:
    texto: str


@dataclass(frozen=True)
class BloqueImagenLLM:
    media_type: str
    datos_base64: str


@dataclass(frozen=True)
class BloqueDocumentoLLM:
    media_type: str
    datos_base64: str


@dataclass(frozen=True)
class BloqueUsoHerramienta:
    id: str
    nombre: str
    entrada: dict[str, Any]


@dataclass(frozen=True)
class BloqueResultadoHerramienta:
    id_uso: str
    contenido: str
    es_error: bool = False


@dataclass(frozen=True)
class BloqueOpaco:
    """Bloque del proveedor (p. ej. razonamiento) que se reenvía sin cambios en el bucle."""

    datos: dict[str, Any]


BloqueLLM = (
    BloqueTextoLLM
    | BloqueImagenLLM
    | BloqueDocumentoLLM
    | BloqueUsoHerramienta
    | BloqueResultadoHerramienta
    | BloqueOpaco
)


@dataclass(frozen=True)
class MensajeLLM:
    rol: Literal["user", "assistant"]
    contenido: tuple[BloqueLLM, ...]

    @classmethod
    def usuario(cls, texto: str) -> "MensajeLLM":
        return cls(rol="user", contenido=(BloqueTextoLLM(texto),))

    @classmethod
    def asistente(cls, texto: str) -> "MensajeLLM":
        return cls(rol="assistant", contenido=(BloqueTextoLLM(texto),))


@dataclass(frozen=True)
class HerramientaLLM:
    nombre: str
    descripcion: str
    esquema: dict[str, Any]


@dataclass(frozen=True)
class LLMSolicitud:
    tarea: TareaLLM
    system: tuple[BloqueSistema, ...]
    mensajes: tuple[MensajeLLM, ...]
    nivel_modelo: NivelModelo
    max_tokens: int
    herramientas: tuple[HerramientaLLM, ...] = ()
    herramienta_forzada: str | None = None

    @classmethod
    def simple(
        cls,
        tarea: TareaLLM,
        system: tuple[BloqueSistema, ...],
        texto_usuario: str,
        nivel_modelo: NivelModelo,
        max_tokens: int,
    ) -> "LLMSolicitud":
        return cls(
            tarea=tarea,
            system=system,
            mensajes=(MensajeLLM.usuario(texto_usuario),),
            nivel_modelo=nivel_modelo,
            max_tokens=max_tokens,
        )

    def texto_usuario(self) -> str:
        """Texto del último mensaje del usuario (lo usa el cliente simulado)."""
        ultimos = [m for m in self.mensajes if m.rol == "user"]
        bloques = ultimos[-1].contenido if ultimos else ()
        return " ".join(b.texto for b in bloques if isinstance(b, BloqueTextoLLM))


@dataclass(frozen=True)
class LLMRespuesta:
    bloques: tuple[BloqueLLM, ...]
    razon_parada: str
    modelo: str
    tokens_entrada: int
    tokens_salida: int
    tokens_cache_lectura: int = 0
    tokens_cache_escritura: int = 0
    metadatos: dict[str, Any] = field(default_factory=dict)

    def texto(self) -> str:
        return "".join(b.texto for b in self.bloques if isinstance(b, BloqueTextoLLM))

    def usos_herramienta(self) -> list[BloqueUsoHerramienta]:
        return [b for b in self.bloques if isinstance(b, BloqueUsoHerramienta)]

    @property
    def fue_rechazada(self) -> bool:
        return self.razon_parada == "refusal"


class LLMClient(ABC):
    @abstractmethod
    def completar(self, solicitud: LLMSolicitud) -> LLMRespuesta: ...

    def cerrar(self) -> None:
        """Libera conexiones; los adaptadores sin recursos no hacen nada."""
