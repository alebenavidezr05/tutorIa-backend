import uuid
from collections.abc import Collection

from sqlalchemy import select

from app.models.enums import CategoriaFuente
from app.models.fuente import Fuente, MensajeFuente, PlanFuente
from app.models.mensaje import Mensaje
from app.repositories.base import RepositorioBase


class FuenteRepository(RepositorioBase[Fuente]):
    modelo = Fuente

    def obtener_por_url_hash(self, url_hash: str) -> Fuente | None:
        return self._session.scalar(select(Fuente).where(Fuente.url_hash == url_hash))

    def listar_por_url_hashes(self, url_hashes: Collection[str]) -> list[Fuente]:
        return list(self._session.scalars(select(Fuente).where(Fuente.url_hash.in_(url_hashes))))

    def buscar_curadas(self, termino: str, limite: int) -> list[Fuente]:
        consulta = (
            select(Fuente)
            .where(Fuente.categoria == CategoriaFuente.CURADA, Fuente.titulo.ilike(f"%{termino}%"))
            .order_by(Fuente.autoridad.desc())
            .limit(limite)
        )
        return list(self._session.scalars(consulta))

    def listar_por_ids(self, ids: Collection[uuid.UUID]) -> list[Fuente]:
        return list(self._session.scalars(select(Fuente).where(Fuente.id_fuente.in_(ids))))

    def listar_por_conversacion(self, id_conversacion: uuid.UUID) -> list[Fuente]:
        consulta = (
            select(Fuente)
            .join(MensajeFuente, MensajeFuente.id_fuente == Fuente.id_fuente)
            .join(Mensaje, Mensaje.id_mensaje == MensajeFuente.id_mensaje)
            .where(Mensaje.id_conversacion == id_conversacion)
            .distinct()
        )
        return list(self._session.scalars(consulta))

    def listar_por_mensaje(self, id_mensaje: uuid.UUID) -> list[Fuente]:
        consulta = (
            select(Fuente)
            .join(MensajeFuente, MensajeFuente.id_fuente == Fuente.id_fuente)
            .where(MensajeFuente.id_mensaje == id_mensaje)
        )
        return list(self._session.scalars(consulta))

    def listar_por_plan(self, id_plan: uuid.UUID) -> list[Fuente]:
        consulta = (
            select(Fuente)
            .join(PlanFuente, PlanFuente.id_fuente == Fuente.id_fuente)
            .where(PlanFuente.id_plan == id_plan)
        )
        return list(self._session.scalars(consulta))

    def vincular_mensaje(self, id_mensaje: uuid.UUID, ids_fuentes: Collection[uuid.UUID]) -> None:
        self._session.add_all(
            MensajeFuente(id_mensaje=id_mensaje, id_fuente=f) for f in ids_fuentes
        )
        self._session.flush()

    def vincular_plan(self, id_plan: uuid.UUID, ids_fuentes: Collection[uuid.UUID]) -> None:
        self._session.add_all(PlanFuente(id_plan=id_plan, id_fuente=f) for f in ids_fuentes)
        self._session.flush()
