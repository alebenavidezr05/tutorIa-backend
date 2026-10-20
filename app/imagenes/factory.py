from app.core.config import Settings
from app.imagenes.base import DescargadorImagenes, ImagenesIAClient, ProcesadorImagenes
from app.imagenes.descarga_segura import DescargadorSeguro
from app.imagenes.fake_client import FakeDescargador, FakeImagenesIAClient
from app.imagenes.openai_imagenes_client import OpenAIImagenesClient

PROVEEDOR_FALSO = "fake"


def crear_imagenes_ia_client(settings: Settings) -> ImagenesIAClient:
    if settings.imagenes_ia_proveedor == "openai":
        return OpenAIImagenesClient(settings)
    return FakeImagenesIAClient()


def crear_descargador(settings: Settings, procesador: ProcesadorImagenes) -> DescargadorImagenes:
    # Con proveedores falsos no hay red: el descargador simulado devuelve una imagen local.
    if all(p.adaptador == PROVEEDOR_FALSO for p in settings.imagenes_proveedores if p.activo):
        return FakeDescargador()
    return DescargadorSeguro(settings, procesador)
