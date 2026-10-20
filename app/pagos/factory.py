from app.core.config import Settings
from app.pagos.base import PasarelaPagos
from app.pagos.fake_pasarela import FakePasarela


def crear_pasarela(settings: Settings) -> PasarelaPagos:
    # Solo existe la pasarela simulada: el adaptador real se agrega tras verificar su firma.
    return FakePasarela(settings.pasarela_secreto_webhook.get_secret_value())
