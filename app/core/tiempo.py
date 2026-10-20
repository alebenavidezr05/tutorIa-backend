from datetime import UTC, date, datetime


def ahora_utc() -> datetime:
    return datetime.now(UTC)


def hoy_utc() -> date:
    return ahora_utc().date()


def inicio_de_mes_utc() -> datetime:
    return ahora_utc().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
