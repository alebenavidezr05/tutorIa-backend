import hashlib
import hmac


class IndiceCiego:
    """HMAC-SHA256 de valores ya normalizados: permite buscar por igualdad sin descifrar."""

    def __init__(self, clave: str) -> None:
        self._clave = clave.encode()

    def calcular(self, valor_normalizado: str) -> str:
        return hmac.new(self._clave, valor_normalizado.encode(), hashlib.sha256).hexdigest()


def sha256_hex(valor: str | bytes) -> str:
    datos = valor.encode() if isinstance(valor, str) else valor
    return hashlib.sha256(datos).hexdigest()
