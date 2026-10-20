from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session, sessionmaker


class UnitOfWork:
    """Único lugar que confirma transacciones; los repositorios solo agregan y consultan."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()


class FabricaUnitOfWork:
    """Abre transacciones propias y cortas (consumo de IA, trabajos en segundo plano)."""

    def __init__(self, fabrica_sesiones: sessionmaker[Session]) -> None:
        self._fabrica_sesiones = fabrica_sesiones

    @contextmanager
    def abrir(self) -> Iterator[UnitOfWork]:
        with self._fabrica_sesiones() as session:
            yield UnitOfWork(session)
