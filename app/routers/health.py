from fastapi import APIRouter, Depends

from app.core.dependencies import get_salud_service, get_salud_sin_db
from app.services.salud_service import EstadoSalud, SaludService

publico = APIRouter(prefix="/health", tags=["health"])


@publico.get("", response_model=EstadoSalud)
def vivo(servicio: SaludService = Depends(get_salud_sin_db)) -> EstadoSalud:
    return servicio.vivo()


@publico.get("/ready", response_model=EstadoSalud)
def listo(servicio: SaludService = Depends(get_salud_service)) -> EstadoSalud:
    return servicio.listo()
