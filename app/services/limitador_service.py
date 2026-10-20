from datetime import timedelta

from app.core.tiempo import ahora_utc
from app.crypto.indice_ciego import IndiceCiego
from app.exceptions.base import SolicitudesExcesivasError
from app.models.limite_frecuencia import LimiteFrecuencia
from app.repositories.uso import LimiteFrecuenciaRepository


class LimitadorFrecuencia:
    """Frena la fuerza bruta contando intentos por clave (IP o correo) en ventanas fijas.
    Las claves se guardan como HMAC: la base nunca contiene la IP ni el correo en claro."""

    def __init__(
        self,
        repositorio: LimiteFrecuenciaRepository,
        indice: IndiceCiego,
        max_intentos: int,
        ventana_minutos: int,
    ) -> None:
        self._repositorio = repositorio
        self._indice = indice
        self._max_intentos = max_intentos
        self._ventana = timedelta(minutes=ventana_minutos)

    def asegurar_permitido(self, *claves: str) -> None:
        if any(self._intentos_vigentes(c) >= self._max_intentos for c in claves if c):
            raise SolicitudesExcesivasError()

    def registrar_fallo(self, *claves: str) -> None:
        for clave in (c for c in claves if c):
            self._incrementar(self._indice.calcular(clave))

    def _intentos_vigentes(self, clave: str) -> int:
        registro = self._repositorio.obtener(self._indice.calcular(clave))
        if registro is None or registro.ventana_inicio + self._ventana < ahora_utc():
            return 0
        return registro.intentos

    def _incrementar(self, clave_hash: str) -> None:
        registro = self._repositorio.obtener(clave_hash)
        ahora = ahora_utc()
        if registro is None:
            self._repositorio.agregar(
                LimiteFrecuencia(clave_hash=clave_hash, ventana_inicio=ahora, intentos=1)
            )
            return
        if registro.ventana_inicio + self._ventana < ahora:
            registro.ventana_inicio, registro.intentos = ahora, 0
        registro.intentos += 1
