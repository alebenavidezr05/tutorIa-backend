import hashlib
import hmac
import json
from collections.abc import Mapping

from app.exceptions.base import FirmaPagoInvalidaError
from app.pagos.base import EventoPasarela, PasarelaPagos

CABECERA_FIRMA = "x-firma"
URL_CHECKOUT_FALSA = "https://pagos.example.org/checkout?referencia={referencia}"
CAMPOS_EVENTO = ("id_evento", "tipo", "referencia")


def firmar(cuerpo: bytes, secreto: str) -> str:
    return hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()


class FakePasarela(PasarelaPagos):
    """Solo desarrollo y pruebas: firma HMAC-SHA256 del cuerpo con el secreto del webhook."""

    nombre = "fake"

    def __init__(self, secreto: str) -> None:
        self._secreto = secreto

    def crear_checkout(self, referencia: str, monto_cop: int, descripcion: str) -> str:
        return URL_CHECKOUT_FALSA.format(referencia=referencia)

    def verificar_webhook(self, cuerpo: bytes, cabeceras: Mapping[str, str]) -> EventoPasarela:
        firma = {k.lower(): v for k, v in cabeceras.items()}.get(CABECERA_FIRMA, "")
        if not hmac.compare_digest(firma, firmar(cuerpo, self._secreto)):
            raise FirmaPagoInvalidaError()
        datos = json.loads(cuerpo)
        if not isinstance(datos, dict) or any(
            not isinstance(datos.get(c), str) for c in CAMPOS_EVENTO
        ):
            raise FirmaPagoInvalidaError("El evento de pago no tiene el formato esperado.")
        return EventoPasarela(datos["id_evento"], datos["tipo"], datos["referencia"])
