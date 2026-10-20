import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, Dialect, Enum
from sqlalchemy.types import TypeDecorator

LONGITUD_ENUM = 40


def tipo_enum(enum: type[StrEnum]) -> Enum:
    return Enum(enum, native_enum=False, length=LONGITUD_ENUM, validate_strings=True)


class FechaHoraUTC(TypeDecorator[datetime]):
    """Garantiza fechas con zona UTC también en motores que no la conservan (SQLite en pruebas)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def nuevo_uuid() -> uuid.UUID:
    return uuid.uuid4()
