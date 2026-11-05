from datetime import datetime

from sqlalchemy import select

from app.models.cache_fuentes import CacheFuentes
from app.repositories.base import RepositorioBase


class CacheFuentesRepository(RepositorioBase[CacheFuentes]):
    modelo = CacheFuentes

    def listar_vigentes(self, claves: list[str], ahora: datetime) -> list[CacheFuentes]:
        consulta = select(CacheFuentes).where(
            CacheFuentes.clave_hash.in_(claves), CacheFuentes.fecha_expiracion > ahora
        )
        return list(self._session.scalars(consulta))

    def guardar(self, entrada: CacheFuentes) -> None:
        """Inserta o reemplaza (una entrada vencida se sobrescribe)."""
        self._session.merge(entrada)
        self._session.flush()
