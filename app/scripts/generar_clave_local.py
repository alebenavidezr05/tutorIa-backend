"""Genera claves aleatorias para un `.env` de DESARROLLO. En producción se usan KMS y Secrets Manager."""

import base64
import os
import secrets
import sys

from app.core.config import get_settings
from app.scripts._comun import preparar_consola

BYTES_CLAVE_AES = 32
BYTES_SECRETO = 48


def main() -> int:
    preparar_consola()
    if get_settings().es_produccion:
        print("Este script es solo para desarrollo.")
        return 1
    print(f"CIFRADO_CLAVE_LOCAL={base64.b64encode(os.urandom(BYTES_CLAVE_AES)).decode()}")
    print(f"INDICE_CIEGO_CLAVE={secrets.token_urlsafe(BYTES_SECRETO)}")
    print(f"JWT_SECRET={secrets.token_urlsafe(BYTES_SECRETO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
