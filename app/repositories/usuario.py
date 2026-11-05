from sqlalchemy import exists, select

from app.models.enums import EstadoCuenta
from app.models.usuario import Usuario
from app.repositories.base import RepositorioBase


class UsuarioRepository(RepositorioBase[Usuario]):
    modelo = Usuario

    def obtener_por_correo_hash(self, correo_hash: str) -> Usuario | None:
        return self._session.scalar(select(Usuario).where(Usuario.correo_hash == correo_hash))

    def existe_correo_hash(self, correo_hash: str) -> bool:
        return bool(
            self._session.scalar(select(exists().where(Usuario.correo_hash == correo_hash)))
        )

    def listar_pendientes_autorizacion(self) -> list[Usuario]:
        consulta = select(Usuario).where(
            Usuario.estado_cuenta == EstadoCuenta.PENDIENTE_AUTORIZACION,
            Usuario.activo.is_(True),
        )
        return list(self._session.scalars(consulta))
