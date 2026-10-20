from collections.abc import Iterable, Mapping

from app.exceptions.base import ConsentimientoRequeridoError, PoliticaDesactualizadaError
from app.models.enums import FinalidadConsentimiento

FINALIDADES_OBLIGATORIAS = (
    FinalidadConsentimiento.TRATAMIENTO,
    FinalidadConsentimiento.TRANSFERENCIA_INTERNACIONAL,
)
FINALIDADES_OPCIONALES = (
    FinalidadConsentimiento.PERSONALIZACION,
    FinalidadConsentimiento.COMUNICACIONES,
)


def _faltantes(
    otorgadas: Mapping[FinalidadConsentimiento, bool], requeridas: Iterable[FinalidadConsentimiento]
) -> list[str]:
    return [f.value for f in requeridas if not otorgadas.get(f, False)]


def validar_consentimientos_requeridos(
    otorgadas: Mapping[FinalidadConsentimiento, bool],
    requeridas: Iterable[FinalidadConsentimiento] = FINALIDADES_OBLIGATORIAS,
) -> None:
    faltantes = _faltantes(otorgadas, requeridas)
    if faltantes:
        raise ConsentimientoRequeridoError(detalles={"finalidades": faltantes})


def _partes_version(version: str) -> tuple[int, ...]:
    return tuple(int(p) for p in version.split(".") if p.isdigit())


def comparar_versiones(a: str, b: str) -> int:
    pa, pb = _partes_version(a), _partes_version(b)
    return (pa > pb) - (pa < pb)


def validar_version_politica(version: str, vigente: str) -> None:
    """Quien acepta debe estar viendo exactamente la versión vigente de la política."""
    if comparar_versiones(version, vigente) != 0:
        raise PoliticaDesactualizadaError()


def validar_version_aceptada(version_aceptada: str, minima: str) -> None:
    if comparar_versiones(version_aceptada, minima) < 0:
        raise PoliticaDesactualizadaError()
