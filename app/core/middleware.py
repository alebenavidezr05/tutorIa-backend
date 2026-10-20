from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.seguridad import METODOS_MUTACION, PREFIJO_WEBHOOK
from app.exceptions.base import OrigenNoPermitidoError
from app.exceptions.handlers import respuesta_error
from app.validators.origen import validar_origen

CABECERAS_SEGURIDAD = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}
HSTS = "max-age=31536000; includeSubDomains"
NO_CACHE = "no-store"
TIPO_JSON = "application/json"


class OrigenMiddleware(BaseHTTPMiddleware):
    """Contra CSRF: toda mutación debe venir de un origen permitido (salvo webhooks firmados)."""

    def __init__(self, app: ASGIApp, origenes_permitidos: list[str]) -> None:
        super().__init__(app)
        self._permitidos = origenes_permitidos

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        es_mutacion = request.method in METODOS_MUTACION
        exento = request.url.path.startswith(PREFIJO_WEBHOOK)
        permitido = validar_origen(
            request.headers.get("origin"), request.headers.get("referer"), self._permitidos
        )
        if es_mutacion and not exento and not permitido:
            error = OrigenNoPermitidoError()
            return respuesta_error(error.status_code, error.codigo, error.mensaje)
        return await call_next(request)


class CabecerasSeguridadMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, es_produccion: bool) -> None:
        super().__init__(app)
        self._es_produccion = es_produccion

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        respuesta = await call_next(request)
        respuesta.headers.update(CABECERAS_SEGURIDAD)
        if respuesta.headers.get("content-type", "").startswith(TIPO_JSON):
            respuesta.headers.setdefault("Cache-Control", NO_CACHE)
        if self._es_produccion:
            respuesta.headers["Strict-Transport-Security"] = HSTS
        return respuesta
