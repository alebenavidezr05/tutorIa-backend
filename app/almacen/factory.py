from app.almacen.base import Almacen
from app.almacen.local_almacen import LocalAlmacen
from app.almacen.s3_almacen import S3Almacen
from app.core.config import Settings


def crear_almacen(settings: Settings) -> Almacen:
    if settings.almacen_proveedor == "s3":
        return S3Almacen(settings)
    return LocalAlmacen(settings.almacen_ruta_local)
