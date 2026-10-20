import uuid

from app.almacen.base import Almacen
from app.core.config import Settings
from app.core.tiempo import hoy_utc
from app.core.unit_of_work import UnitOfWork
from app.exceptions.base import RecursoNoEncontradoError
from app.models.usuario import Usuario
from app.repositories.usuario import UsuarioRepository
from app.schemas.usuario import ActualizarPerfilEntrada, UsuarioPublico
from app.services.presentacion import usuario_publico
from app.services.supresor_datos import SupresorDatos
from app.validators.propiedad import validar_propietario


class PerfilService:
    def __init__(
        self,
        usuarios: UsuarioRepository,
        supresor: SupresorDatos,
        almacen: Almacen,
        settings: Settings,
        uow: UnitOfWork,
    ) -> None:
        self._usuarios = usuarios
        self._supresor = supresor
        self._almacen = almacen
        self._settings = settings
        self._uow = uow

    def obtener(self, uid: uuid.UUID, id_usuario_actual: uuid.UUID) -> UsuarioPublico:
        return self._publico(self._propio(uid, id_usuario_actual))

    def actualizar(
        self, uid: uuid.UUID, id_usuario_actual: uuid.UUID, entrada: ActualizarPerfilEntrada
    ) -> UsuarioPublico:
        usuario = self._propio(uid, id_usuario_actual)
        usuario.nombre = entrada.nombre
        usuario.tipo_nivel = entrada.tipo_nivel
        usuario.nivel_educativo = entrada.nivel_educativo
        self._uow.commit()
        return self._publico(usuario)

    def desactivar(self, uid: uuid.UUID, id_usuario_actual: uuid.UUID) -> None:
        usuario = self._propio(uid, id_usuario_actual)
        usuario.activo = False
        # Invalida todas las sesiones abiertas de la cuenta.
        usuario.version_token += 1
        self._uow.commit()

    def suprimir_datos(self, id_usuario: uuid.UUID) -> None:
        claves = self._supresor.suprimir(self._existente(id_usuario))
        self._uow.commit()
        self._almacen.eliminar_sin_fallar(claves)

    def _propio(self, uid: uuid.UUID, id_usuario_actual: uuid.UUID) -> Usuario:
        validar_propietario(uid, id_usuario_actual)
        return self._existente(uid)

    def _existente(self, id_usuario: uuid.UUID) -> Usuario:
        usuario = self._usuarios.obtener_por_id(id_usuario)
        if usuario is None:
            raise RecursoNoEncontradoError()
        return usuario

    def _publico(self, usuario: Usuario) -> UsuarioPublico:
        return usuario_publico(usuario, hoy_utc(), self._settings.edad_mayoria)
