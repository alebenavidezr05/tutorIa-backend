from app.core.config import Settings
from app.crypto.base import CifradorAesGcm, decodificar_clave


def crear_cifrador_local(settings: Settings) -> CifradorAesGcm:
    """Solo desarrollo y pruebas: la clave vive en la configuración en vez de en KMS."""
    claves = {
        version: decodificar_clave(clave.get_secret_value())
        for version, clave in settings.cifrado_claves_anteriores.items()
    }
    claves[settings.cifrado_version_actual] = decodificar_clave(
        settings.cifrado_clave_local.get_secret_value()
    )
    return CifradorAesGcm(claves, settings.cifrado_version_actual)
