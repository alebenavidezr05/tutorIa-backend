from pydantic import BaseModel

from app.repositories.salud import SaludRepository

ESTADO_OK = "ok"


class EstadoSalud(BaseModel):
    estado: str


class SaludService:
    def __init__(self, salud: SaludRepository | None = None) -> None:
        self._salud = salud

    def vivo(self) -> EstadoSalud:
        """Liveness: no toca la base de datos."""
        return EstadoSalud(estado=ESTADO_OK)

    def listo(self) -> EstadoSalud:
        """Readiness: la base de datos responde."""
        assert self._salud is not None
        self._salud.ping()
        return EstadoSalud(estado=ESTADO_OK)
