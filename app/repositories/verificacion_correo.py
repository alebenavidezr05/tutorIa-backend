import uuid
from datetime import datetime

from sqlalchemy import or_, select

from app.models.verificacion_correo import VerificacionCorreo
from app.repositories.base import RepositorioBase


class VerificacionCorreoRepository(RepositorioBase[VerificacionCorreo]):
    modelo = VerificacionCorreo

    def obtener_por_token_hash(self, token_hash: str) -> VerificacionCorreo | None:
        consulta = select(VerificacionCorreo).where(VerificacionCorreo.token_hash == token_hash)
        return self._session.scalar(consulta)

    def obtener_ultima_por_usuario(self, id_usuario: uuid.UUID) -> VerificacionCorreo | None:
        consulta = (
            select(VerificacionCorreo)
            .where(VerificacionCorreo.id_usuario == id_usuario)
            .order_by(VerificacionCorreo.fecha_creacion.desc())
            .limit(1)
        )
        return self._session.scalar(consulta)

    def listar_por_usuario(self, id_usuario: uuid.UUID) -> list[VerificacionCorreo]:
        consulta = select(VerificacionCorreo).where(VerificacionCorreo.id_usuario == id_usuario)
        return list(self._session.scalars(consulta))

    def fechas_envio_desde(
        self, id_usuario: uuid.UUID, correo_hash: str, desde: datetime
    ) -> list[datetime]:
        """Envíos recientes al usuario o a la dirección (aunque sea de otra cuenta)."""
        consulta = select(VerificacionCorreo.fecha_creacion).where(
            or_(
                VerificacionCorreo.id_usuario == id_usuario,
                VerificacionCorreo.correo_hash == correo_hash,
            ),
            VerificacionCorreo.fecha_creacion >= desde,
        )
        return list(self._session.scalars(consulta))
