"""Deny-by-default (§6.6): todo módulo se monta en `router_privado`, que exige sesión activa.
Hacer pública una ruta exige tocar `router_publico` y `RUTAS_PUBLICAS` (core/seguridad.py)."""

from fastapi import APIRouter, Depends

from app.core.dependencies import get_usuario_activo_id, get_usuario_actual_id
from app.routers import (
    actividades,
    archivos,
    auth,
    autorizaciones,
    conversaciones,
    diagnostico,
    health,
    historial,
    mensajes,
    pagos,
    perfil,
    perfil_aprendizaje,
    plan,
    privacidad,
    recursos,
    reportes,
    suscripcion,
)

router_publico = APIRouter()
router_publico.include_router(auth.publico)
router_publico.include_router(health.publico)
router_publico.include_router(privacidad.publico)
router_publico.include_router(autorizaciones.publico)
router_publico.include_router(pagos.publico)

# Sesión válida aunque la cuenta esté pendiente de autorización o deba aceptar la política.
router_sesion = APIRouter(dependencies=[Depends(get_usuario_actual_id)])
router_sesion.include_router(auth.sesion)
router_sesion.include_router(privacidad.sesion)

router_privado = APIRouter(dependencies=[Depends(get_usuario_activo_id)])
router_privado.include_router(diagnostico.router)
router_privado.include_router(plan.router)
router_privado.include_router(actividades.router)
router_privado.include_router(archivos.router)
router_privado.include_router(historial.router)
router_privado.include_router(perfil.router)
router_privado.include_router(suscripcion.router)
router_privado.include_router(reportes.router)
router_privado.include_router(conversaciones.router)
router_privado.include_router(mensajes.router)
router_privado.include_router(recursos.router)
router_privado.include_router(perfil_aprendizaje.router)
router_privado.include_router(privacidad.router)
