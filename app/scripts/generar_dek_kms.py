"""Genera una DEK con AWS KMS (GenerateDataKey) e imprime SOLO el bloque cifrado.

Uso: python -m app.scripts.generar_dek_kms --kms-key-id <arn o alias>
Guarda el resultado en CIFRADO_DEK_ENVUELTA. La parte en claro nunca se imprime ni se guarda.
"""

import argparse
import sys

from app.core.config import get_settings
from app.crypto.kms_cifrador import KmsCifrador
from app.scripts._comun import preparar_consola


def main() -> int:
    preparar_consola()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kms-key-id", required=True)
    argumentos = parser.parse_args()
    print(KmsCifrador(get_settings()).generar_dek_envuelta(argumentos.kms_key_id))
    return 0


if __name__ == "__main__":
    sys.exit(main())
