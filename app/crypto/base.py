import base64
import os
from abc import ABC, abstractmethod
from collections.abc import Mapping

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.exceptions.base import CifradoError

LONGITUD_NONCE = 12
LONGITUD_CLAVE = 32
SEPARADOR_VERSION = "."


class Cifrador(ABC):
    @abstractmethod
    def cifrar(self, texto: str, aad: str) -> str: ...

    @abstractmethod
    def descifrar(self, valor: str, aad: str) -> str: ...

    @abstractmethod
    def es_version_actual(self, valor: str) -> bool: ...


class CifradorAesGcm(Cifrador):
    """AES-256-GCM con nonce aleatorio por valor; el prefijo de versión permite rotar claves."""

    def __init__(self, claves: Mapping[str, bytes], version_actual: str) -> None:
        if version_actual not in claves:
            raise CifradoError("No existe la clave de la versión actual de cifrado.")
        if any(len(clave) != LONGITUD_CLAVE for clave in claves.values()):
            raise CifradoError("Las claves de cifrado deben tener 32 bytes.")
        self._claves = {version: AESGCM(clave) for version, clave in claves.items()}
        self._version_actual = version_actual

    def cifrar(self, texto: str, aad: str) -> str:
        nonce = os.urandom(LONGITUD_NONCE)
        cuerpo = self._claves[self._version_actual].encrypt(nonce, texto.encode(), aad.encode())
        codificado = base64.urlsafe_b64encode(nonce + cuerpo).decode()
        return f"{self._version_actual}{SEPARADOR_VERSION}{codificado}"

    def descifrar(self, valor: str, aad: str) -> str:
        version, _, codificado = valor.partition(SEPARADOR_VERSION)
        aes = self._claves.get(version)
        if aes is None:
            raise CifradoError("Versión de clave de cifrado desconocida.")
        datos = base64.urlsafe_b64decode(codificado.encode())
        try:
            texto = aes.decrypt(datos[:LONGITUD_NONCE], datos[LONGITUD_NONCE:], aad.encode())
        except InvalidTag as exc:
            raise CifradoError("No fue posible descifrar un valor.") from exc
        return texto.decode()

    def es_version_actual(self, valor: str) -> bool:
        return valor.startswith(f"{self._version_actual}{SEPARADOR_VERSION}")


def decodificar_clave(clave_base64: str) -> bytes:
    return base64.b64decode(clave_base64.encode())
