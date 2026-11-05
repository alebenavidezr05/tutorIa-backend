import math
from datetime import UTC, date, datetime


def ahora_utc() -> datetime:
    return datetime.now(UTC)


def hoy_utc() -> date:
    return ahora_utc().date()


def inicio_de_mes_utc() -> datetime:
    return ahora_utc().replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def segundos_hasta(momento: datetime) -> int:
    """Segundos enteros (hacia arriba) que faltan para `momento`; 0 si ya pasó."""
    return max(0, math.ceil((momento - ahora_utc()).total_seconds()))
