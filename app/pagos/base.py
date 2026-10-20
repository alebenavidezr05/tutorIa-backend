from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class EventoPasarela:
    id_evento: str
    tipo: str
    referencia: str


TIPO_PAGO_APROBADO = "pago.aprobado"
TIPO_SUSCRIPCION_CANCELADA = "suscripcion.cancelada"


class PasarelaPagos(ABC):
    nombre: str

    @abstractmethod
    def crear_checkout(self, referencia: str, monto_cop: int, descripcion: str) -> str:
        """Devuelve la URL de pago de la pasarela. Nunca se reciben datos de tarjeta."""

    @abstractmethod
    def verificar_webhook(self, cuerpo: bytes, cabeceras: Mapping[str, str]) -> EventoPasarela:
        """Valida la firma y devuelve el evento; firma inválida → FirmaPagoInvalidaError."""
