from app.core.config import Settings
from app.crypto.base import Cifrador
from app.crypto.kms_cifrador import KmsCifrador
from app.crypto.local_cifrador import crear_cifrador_local
from app.crypto.registro import registro_cifrador


def crear_cifrador(settings: Settings) -> Cifrador:
    if settings.cifrado_proveedor == "kms":
        return KmsCifrador(settings).construir()
    return crear_cifrador_local(settings)


def registrar_cifrador(settings: Settings) -> Cifrador:
    cifrador = crear_cifrador(settings)
    registro_cifrador.registrar(cifrador)
    return cifrador
