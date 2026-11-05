from app.core.config import Settings
from app.pagos.base import PasarelaPagos
from app.pagos.fake_pasarela import FakePasarela


def crear_pasarela(settings: Settings) -> PasarelaPagos | None:
    # "ninguna": pagos desactivados, sin adaptador. El adaptador real se agrega tras verificar su firma.
    if settings.pasarela_proveedor == "ninguna":
        return None
    return FakePasarela(settings.pasarela_secreto_webhook.get_secret_value())
