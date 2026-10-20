from typing import Final, Literal

from fastapi import Response

from app.core.config import Settings

SEGUNDOS_POR_MINUTO = 60
SAME_SITE: Final[Literal["lax"]] = "lax"


class CookieSesion:
    """La sesión viaja solo en una cookie httpOnly: nunca en el cuerpo ni en localStorage."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def emitir(self, response: Response, token: str) -> None:
        response.set_cookie(
            key=self._settings.cookie_nombre,
            value=token,
            max_age=self._settings.jwt_expira_minutos * SEGUNDOS_POR_MINUTO,
            path="/",
            domain=self._settings.cookie_domain,
            secure=self._settings.cookie_secure or self._settings.es_produccion,
            httponly=True,
            samesite=SAME_SITE,
        )

    def limpiar(self, response: Response) -> None:
        response.delete_cookie(
            key=self._settings.cookie_nombre,
            path="/",
            domain=self._settings.cookie_domain,
            secure=self._settings.cookie_secure or self._settings.es_produccion,
            httponly=True,
            samesite=SAME_SITE,
        )
