import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.pregunta_diagnostico import PreguntaDiagnostico
from app.models.sesion_diagnostico import SesionDiagnostico
from app.repositories.base import RepositorioBase


class SesionDiagnosticoRepository(RepositorioBase[SesionDiagnostico]):
    modelo = SesionDiagnostico

    def obtener_con_preguntas(self, id_sesion: uuid.UUID) -> SesionDiagnostico | None:
        consulta = (
            select(SesionDiagnostico)
            .options(selectinload(SesionDiagnostico.preguntas))
            .where(SesionDiagnostico.id_sesion == id_sesion)
        )
        return self._session.scalar(consulta)

    def obtener_ultima_evaluada_por_usuario(
        self, id_usuario: uuid.UUID
    ) -> SesionDiagnostico | None:
        consulta = (
            select(SesionDiagnostico)
            .options(selectinload(SesionDiagnostico.preguntas))
            .where(
                SesionDiagnostico.id_usuario == id_usuario,
                SesionDiagnostico.nivel_estimado.is_not(None),
            )
            .order_by(SesionDiagnostico.fecha_creacion.desc())
            .limit(1)
        )
        return self._session.scalar(consulta)

    def listar_por_usuario(self, id_usuario: uuid.UUID) -> list[SesionDiagnostico]:
        consulta = select(SesionDiagnostico).where(SesionDiagnostico.id_usuario == id_usuario)
        return list(self._session.scalars(consulta))


class PreguntaDiagnosticoRepository(RepositorioBase[PreguntaDiagnostico]):
    modelo = PreguntaDiagnostico

    def listar_por_sesion(self, id_sesion: uuid.UUID) -> list[PreguntaDiagnostico]:
        consulta = (
            select(PreguntaDiagnostico)
            .where(PreguntaDiagnostico.id_sesion == id_sesion)
            .order_by(PreguntaDiagnostico.orden)
        )
        return list(self._session.scalars(consulta))
