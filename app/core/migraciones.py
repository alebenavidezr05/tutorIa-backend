"""Migraciones de esquema que `create_all` no cubre (añadir columnas a tablas existentes).

Se aplican solas al arrancar, dentro del mismo candado que `create_all`, y son idempotentes:
cada paso revisa el esquema real antes de actuar."""

from sqlalchemy import Connection, Engine, inspect, text


def aplicar_migraciones(engine: Engine) -> None:
    with engine.begin() as conexion:
        _verificacion_correo(conexion)


def _verificacion_correo(conexion: Connection) -> None:
    """Añade la verificación del correo. Las cuentas que ya existían quedan verificadas (hoy solo
    hay cuentas de prueba y no se deja a nadie bloqueado); las nuevas nacen sin verificar porque
    el ORM siempre escribe el valor explícito."""
    columnas = {c["name"] for c in inspect(conexion).get_columns("usuario")}
    postgres = conexion.dialect.name == "postgresql"
    if "correo_verificado" not in columnas:
        conexion.execute(
            text("ALTER TABLE usuario ADD COLUMN correo_verificado BOOLEAN NOT NULL DEFAULT TRUE")
        )
        if postgres:
            conexion.execute(
                text("ALTER TABLE usuario ALTER COLUMN correo_verificado SET DEFAULT FALSE")
            )
    if "fecha_verificacion_correo" not in columnas:
        tipo = "TIMESTAMP WITH TIME ZONE" if postgres else "DATETIME"
        conexion.execute(text(f"ALTER TABLE usuario ADD COLUMN fecha_verificacion_correo {tipo}"))
