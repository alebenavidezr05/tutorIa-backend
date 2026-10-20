from fastapi import APIRouter, Depends, status

from app.core.dependencies import get_cabeceras, get_cuerpo_crudo, get_pago_service
from app.services.pago_service import PagoService

publico = APIRouter(prefix="/pagos", tags=["pagos"])


@publico.post("/webhook/{proveedor}", status_code=status.HTTP_204_NO_CONTENT)
def webhook(
    proveedor: str,
    cuerpo: bytes = Depends(get_cuerpo_crudo),
    cabeceras: dict[str, str] = Depends(get_cabeceras),
    servicio: PagoService = Depends(get_pago_service),
) -> None:
    servicio.procesar_webhook(proveedor, cuerpo, cabeceras)
