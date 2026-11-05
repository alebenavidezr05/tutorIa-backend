import uuid

from fastapi import APIRouter, Depends, Response, status

from app.core.cookies import CookieSesion
from app.core.dependencies import (
    get_auth_service,
    get_contexto,
    get_cookie_sesion,
    get_usuario_actual_id,
    get_verificacion_correo_service,
)
from app.schemas.auth import ContextoSolicitud, LoginEntrada, RegistroEntrada
from app.schemas.autorizacion import MensajeGenerico
from app.schemas.usuario import UsuarioPublico
from app.schemas.verificacion_correo import (
    EstadoVerificacionCorreo,
    VerificacionCorreoResultado,
    VerificarCorreoEntrada,
)
from app.services.auth_service import AuthService
from app.services.verificacion_correo_service import VerificacionCorreoService

publico = APIRouter(prefix="/auth", tags=["auth"])
sesion = APIRouter(prefix="/auth", tags=["auth"])


@publico.post("/registro", response_model=UsuarioPublico, status_code=status.HTTP_201_CREATED)
def registrar(
    entrada: RegistroEntrada,
    response: Response,
    contexto: ContextoSolicitud = Depends(get_contexto),
    servicio: AuthService = Depends(get_auth_service),
    cookie: CookieSesion = Depends(get_cookie_sesion),
) -> UsuarioPublico:
    sesion_autenticada = servicio.registrar(entrada, contexto)
    cookie.emitir(response, sesion_autenticada.token)
    return sesion_autenticada.usuario


@publico.post("/login", response_model=UsuarioPublico)
def iniciar_sesion(
    entrada: LoginEntrada,
    response: Response,
    contexto: ContextoSolicitud = Depends(get_contexto),
    servicio: AuthService = Depends(get_auth_service),
    cookie: CookieSesion = Depends(get_cookie_sesion),
) -> UsuarioPublico:
    sesion_autenticada = servicio.autenticar(entrada, contexto)
    cookie.emitir(response, sesion_autenticada.token)
    return sesion_autenticada.usuario


@sesion.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def cerrar_sesion(response: Response, cookie: CookieSesion = Depends(get_cookie_sesion)) -> None:
    cookie.limpiar(response)


@sesion.get("/me", response_model=UsuarioPublico)
def yo(
    id_usuario: uuid.UUID = Depends(get_usuario_actual_id),
    servicio: AuthService = Depends(get_auth_service),
) -> UsuarioPublico:
    return servicio.obtener_actual(id_usuario)


@publico.post("/verificar-correo", response_model=VerificacionCorreoResultado)
def verificar_correo(
    entrada: VerificarCorreoEntrada,
    servicio: VerificacionCorreoService = Depends(get_verificacion_correo_service),
) -> VerificacionCorreoResultado:
    """No inicia sesión ni crea cookies: el enlace puede abrirse en otro dispositivo."""
    return servicio.verificar(entrada)


@sesion.post(
    "/verificar-correo/reenviar",
    response_model=MensajeGenerico,
    status_code=status.HTTP_202_ACCEPTED,
)
def reenviar_verificacion(
    id_usuario: uuid.UUID = Depends(get_usuario_actual_id),
    servicio: VerificacionCorreoService = Depends(get_verificacion_correo_service),
) -> MensajeGenerico:
    return servicio.reenviar(id_usuario)


@sesion.get("/verificar-correo/estado", response_model=EstadoVerificacionCorreo)
def estado_verificacion(
    id_usuario: uuid.UUID = Depends(get_usuario_actual_id),
    servicio: VerificacionCorreoService = Depends(get_verificacion_correo_service),
) -> EstadoVerificacionCorreo:
    return servicio.estado(id_usuario)
