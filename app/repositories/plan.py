import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.actividad import Actividad
from app.models.plan_estudio import PlanEstudio
from app.repositories.base import RepositorioBase


class PlanEstudioRepository(RepositorioBase[PlanEstudio]):
    modelo = PlanEstudio

    def obtener_con_actividades(self, id_plan: uuid.UUID) -> PlanEstudio | None:
        consulta = (
            select(PlanEstudio)
            .options(selectinload(PlanEstudio.actividades), selectinload(PlanEstudio.sesion))
            .where(PlanEstudio.id_plan == id_plan)
        )
        return self._session.scalar(consulta)

    def listar_historial(
        self, id_usuario: uuid.UUID, desplazamiento: int, limite: int
    ) -> list[PlanEstudio]:
        consulta = (
            select(PlanEstudio)
            .options(selectinload(PlanEstudio.sesion))
            .where(PlanEstudio.id_usuario == id_usuario)
            .order_by(PlanEstudio.fecha_generacion.desc())
            .offset(desplazamiento)
            .limit(limite)
        )
        return list(self._session.scalars(consulta))

    def contar_por_usuario(self, id_usuario: uuid.UUID) -> int:
        consulta = select(func.count()).where(PlanEstudio.id_usuario == id_usuario)
        return int(self._session.scalar(consulta) or 0)

    def listar_por_usuario(self, id_usuario: uuid.UUID) -> list[PlanEstudio]:
        consulta = (
            select(PlanEstudio)
            .options(selectinload(PlanEstudio.actividades), selectinload(PlanEstudio.sesion))
            .where(PlanEstudio.id_usuario == id_usuario)
            .order_by(PlanEstudio.fecha_generacion)
        )
        return list(self._session.scalars(consulta))


class ActividadRepository(RepositorioBase[Actividad]):
    modelo = Actividad

    def obtener_con_plan(self, id_actividad: uuid.UUID) -> Actividad | None:
        consulta = (
            select(Actividad)
            .options(selectinload(Actividad.plan))
            .where(Actividad.id_actividad == id_actividad)
        )
        return self._session.scalar(consulta)
