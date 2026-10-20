from collections.abc import Collection
from datetime import date, timedelta

SABADO = 5


def _es_habil(dia: date, festivos: Collection[date]) -> bool:
    return dia.weekday() < SABADO and dia not in festivos


def sumar_dias_habiles(fecha: date, dias: int, festivos: Collection[date]) -> date:
    actual = fecha
    restantes = dias
    while restantes > 0:
        actual += timedelta(days=1)
        if _es_habil(actual, festivos):
            restantes -= 1
    return actual
