import uuid

from fastapi import APIRouter, Depends

from app.core.dependencies import get_pago_service, get_suscripcion_service, get_usuario_activo_id
from app.schemas.suscripcion import CheckoutPublico, SuscripcionPublica
from app.services.pago_service import PagoService
from app.services.suscripcion_service import SuscripcionService

router = APIRouter(prefix="/suscripcion", tags=["suscripcion"])


@router.get("", response_model=SuscripcionPublica)
def obtener(
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: SuscripcionService = Depends(get_suscripcion_service),
) -> SuscripcionPublica:
    return servicio.obtener_actual(id_usuario)


@router.post("/checkout", response_model=CheckoutPublico)
def checkout(
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: PagoService = Depends(get_pago_service),
) -> CheckoutPublico:
    return servicio.iniciar_checkout(id_usuario)
