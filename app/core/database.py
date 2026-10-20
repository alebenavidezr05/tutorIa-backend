from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, MetaData, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import Settings

CONVENCION_NOMBRES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
# Identificador arbitrario y estable del candado consultivo que serializa create_all entre réplicas.
CLAVE_CANDADO_CREAR_TABLAS = 7_316_202_401


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENCION_NOMBRES)


def crear_engine(settings: Settings) -> Engine:
    if settings.es_postgres:
        return create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            connect_args={"sslmode": settings.db_sslmode},
        )
    engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
    event.listen(engine, "connect", _activar_claves_foraneas_sqlite)
    return engine


def _activar_claves_foraneas_sqlite(conexion_dbapi: Any, _: Any) -> None:
    # SQLite ignora ON DELETE CASCADE salvo que se active por conexión.
    cursor = conexion_dbapi.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def crear_fabrica_sesiones(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def _candado_creacion(engine: Engine) -> Iterator[None]:
    if engine.dialect.name != "postgresql":
        yield
        return
    with engine.connect() as conexion:
        conexion.execute(
            text("SELECT pg_advisory_lock(:clave)"), {"clave": CLAVE_CANDADO_CREAR_TABLAS}
        )
        yield
        conexion.execute(
            text("SELECT pg_advisory_unlock(:clave)"), {"clave": CLAVE_CANDADO_CREAR_TABLAS}
        )


def crear_tablas(engine: Engine) -> None:
    import app.models  # noqa: F401  (registra todas las entidades en Base.metadata)

    with _candado_creacion(engine):
        Base.metadata.create_all(engine)


def eliminar_tablas(engine: Engine) -> None:
    import app.models  # noqa: F401

    Base.metadata.drop_all(engine)
