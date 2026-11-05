import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.exceptions.base import AppError

logger = logging.getLogger(__name__)

MENSAJE_VALIDACION = "Revisa los datos enviados."
MENSAJE_CONFLICTO = "La operación entró en conflicto con datos existentes. Intenta de nuevo."
MENSAJE_INTERNO = "Ocurrió un error inesperado. Intenta de nuevo más tarde."
MENSAJE_NO_ENCONTRADO = "No encontramos lo que buscas."
MENSAJES_HTTP = {404: MENSAJE_NO_ENCONTRADO, 405: "Método no permitido."}
CODIGOS_HTTP = {404: "RECURSO_NO_ENCONTRADO", 405: "METODO_NO_PERMITIDO"}


def respuesta_error(
    status_code: int,
    codigo: str,
    mensaje: str,
    detalles: Any = None,
    cabeceras: dict[str, str] | None = None,
) -> JSONResponse:
    contenido = {"error": {"codigo": codigo, "mensaje": mensaje, "detalles": detalles}}
    return JSONResponse(status_code=status_code, content=contenido, headers=cabeceras)


def _campo(loc: tuple[Any, ...]) -> str:
    partes = [str(p) for p in loc if p not in ("body", "query", "path", "header", "cookie")]
    return ".".join(partes) or "solicitud"


async def _manejar_app_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    if exc.status_code >= 500:
        logger.error("error_app codigo=%s tipo=%s", exc.codigo, type(exc).__name__)
    return respuesta_error(exc.status_code, exc.codigo, exc.mensaje, exc.detalles, exc.cabeceras)


async def _manejar_validacion(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    detalles = [{"campo": _campo(tuple(e["loc"])), "mensaje": e["msg"]} for e in exc.errors()]
    return respuesta_error(422, "VALIDACION_FALLIDA", MENSAJE_VALIDACION, detalles)


async def _manejar_integridad(_: Request, exc: Exception) -> JSONResponse:
    logger.warning("conflicto_integridad tipo=%s", type(exc).__name__)
    return respuesta_error(409, "CONFLICTO_DE_DATOS", MENSAJE_CONFLICTO)


async def _manejar_http(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    codigo = CODIGOS_HTTP.get(exc.status_code, "ERROR_HTTP")
    mensaje = MENSAJES_HTTP.get(exc.status_code, MENSAJE_INTERNO)
    return respuesta_error(exc.status_code, codigo, mensaje)


async def _manejar_inesperado(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("error_inesperado tipo=%s", type(exc).__name__)
    return respuesta_error(500, "ERROR_INTERNO", MENSAJE_INTERNO)


def registrar_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _manejar_app_error)
    app.add_exception_handler(RequestValidationError, _manejar_validacion)
    app.add_exception_handler(IntegrityError, _manejar_integridad)
    app.add_exception_handler(StarletteHTTPException, _manejar_http)
    app.add_exception_handler(Exception, _manejar_inesperado)
