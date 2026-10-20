import uuid
from collections.abc import Iterable
from typing import Generic, TypeVar

from sqlalchemy.orm import Session

from app.core.database import Base

ModeloT = TypeVar("ModeloT", bound=Base)


class RepositorioBase(Generic[ModeloT]):
    modelo: type[ModeloT]

    def __init__(self, session: Session) -> None:
        self._session = session

    def agregar(self, entidad: ModeloT) -> ModeloT:
        self._session.add(entidad)
        self._session.flush()
        return entidad

    def agregar_varios(self, entidades: Iterable[ModeloT]) -> None:
        self._session.add_all(list(entidades))
        self._session.flush()

    def obtener_por_id(self, id_entidad: uuid.UUID) -> ModeloT | None:
        return self._session.get(self.modelo, id_entidad)

    def eliminar(self, entidad: ModeloT) -> None:
        self._session.delete(entidad)
        self._session.flush()
