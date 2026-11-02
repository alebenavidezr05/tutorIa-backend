import logging
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.almacen.base import Almacen
from app.core.config import Settings
from app.exceptions.base import AlmacenamientoError

logger = logging.getLogger(__name__)

CIFRADO_SERVIDOR = "aws:kms"


class S3Almacen(Almacen):
    """Bucket privado; cada objeto se cifra en reposo con SSE-KMS."""

    def __init__(self, settings: Settings, cliente: Any | None = None) -> None:
        self._bucket = settings.s3_bucket
        self._kms_key_id = settings.kms_key_id
        self._s3 = cliente or boto3.client("s3", region_name=settings.s3_region or None)

    def guardar(self, clave: str, contenido: bytes, mime: str) -> None:
        parametros: dict[str, Any] = {
            "Bucket": self._bucket,
            "Key": clave,
            "Body": contenido,
            "ContentType": mime,
            "ServerSideEncryption": CIFRADO_SERVIDOR,
        }
        if self._kms_key_id:
            parametros["SSEKMSKeyId"] = self._kms_key_id
        self._ejecutar("guardar", lambda: self._s3.put_object(**parametros))

    def leer(self, clave: str) -> bytes:
        respuesta = self._ejecutar(
            "leer", lambda: self._s3.get_object(Bucket=self._bucket, Key=clave)
        )
        contenido: bytes = respuesta["Body"].read()
        return contenido

    def eliminar(self, clave: str) -> None:
        self._ejecutar("eliminar", lambda: self._s3.delete_object(Bucket=self._bucket, Key=clave))

    def _ejecutar(self, operacion: str, accion: Any) -> Any:
        try:
            return accion()
        except (BotoCoreError, ClientError) as exc:
            logger.warning("s3_error operacion=%s tipo=%s", operacion, type(exc).__name__)
            raise AlmacenamientoError() from exc
