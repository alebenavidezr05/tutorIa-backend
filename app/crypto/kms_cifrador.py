import base64
import logging
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import Settings
from app.crypto.base import CifradorAesGcm
from app.exceptions.base import CifradoError

logger = logging.getLogger(__name__)


class KmsCifrador:
    """Cifrado de sobre: KMS solo desenvuelve las DEK al arrancar; el cifrado es local (AES-GCM)."""

    def __init__(self, settings: Settings, cliente_kms: Any | None = None) -> None:
        self._settings = settings
        self._kms = cliente_kms or boto3.client("kms", region_name=settings.kms_region)

    def construir(self) -> CifradorAesGcm:
        if self._settings.cifrado_dek_envuelta is None:
            raise CifradoError("Falta CIFRADO_DEK_ENVUELTA para el cifrado con KMS.")
        envueltas = {
            version: dek.get_secret_value()
            for version, dek in self._settings.cifrado_claves_anteriores.items()
        }
        envueltas[self._settings.cifrado_version_actual] = (
            self._settings.cifrado_dek_envuelta.get_secret_value()
        )
        claves = {version: self._desenvolver(dek) for version, dek in envueltas.items()}
        return CifradorAesGcm(claves, self._settings.cifrado_version_actual)

    def generar_dek_envuelta(self, kms_key_id: str) -> str:
        try:
            respuesta = self._kms.generate_data_key(KeyId=kms_key_id, KeySpec="AES_256")
        except (BotoCoreError, ClientError) as exc:
            logger.error("kms_generar_dek_fallo tipo=%s", type(exc).__name__)
            raise CifradoError("KMS no pudo generar la clave de datos.") from exc
        return base64.b64encode(respuesta["CiphertextBlob"]).decode()

    def _desenvolver(self, dek_envuelta: str) -> bytes:
        try:
            respuesta = self._kms.decrypt(CiphertextBlob=base64.b64decode(dek_envuelta))
        except (BotoCoreError, ClientError) as exc:
            logger.error("kms_descifrar_dek_fallo tipo=%s", type(exc).__name__)
            raise CifradoError("KMS no pudo descifrar la clave de datos.") from exc
        return bytes(respuesta["Plaintext"])
