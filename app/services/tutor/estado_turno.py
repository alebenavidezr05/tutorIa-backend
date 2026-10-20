import time
import uuid
from dataclasses import dataclass, field

from app.llm.base import LLMRespuesta
from app.models.fuente import Fuente
from app.models.video_curado import VideoCurado
from app.services.fuentes.fuentes_service import ContextoFuentes


@dataclass
class EstadoTurno:
    """Lo recuperado y gastado durante un turno; nada se persiste hasta el final."""

    id_usuario: uuid.UUID
    contexto_fuentes: ContextoFuentes
    fuentes: dict[uuid.UUID, Fuente] = field(default_factory=dict)
    videos: dict[uuid.UUID, VideoCurado] = field(default_factory=dict)
    busquedas_fuentes: int = 0
    busquedas_video: int = 0
    respuestas: list[LLMRespuesta] = field(default_factory=list)
    inicio: float = field(default_factory=time.monotonic)

    def segundos_transcurridos(self) -> float:
        return time.monotonic() - self.inicio

    def tokens(self) -> tuple[int, int]:
        return sum(r.tokens_entrada for r in self.respuestas), sum(
            r.tokens_salida for r in self.respuestas
        )

    def modelo(self) -> str | None:
        return self.respuestas[-1].modelo if self.respuestas else None
