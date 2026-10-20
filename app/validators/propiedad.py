import uuid

from app.exceptions.base import AccesoDenegadoError, RecursoNoEncontradoError


def validar_propietario(id_propietario: uuid.UUID, id_usuario_actual: uuid.UUID) -> None:
    if id_propietario != id_usuario_actual:
        raise AccesoDenegadoError()


def validar_recurso_propio(id_propietario: uuid.UUID, id_usuario_actual: uuid.UUID) -> None:
    """Para recursos por id: un recurso ajeno responde 404 para no revelar que existe (§6.6)."""
    if id_propietario != id_usuario_actual:
        raise RecursoNoEncontradoError()
