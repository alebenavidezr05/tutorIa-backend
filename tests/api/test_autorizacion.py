"""Autorización del acudiente iniciada desde el registro del estudiante (§8.3)."""

import re
import uuid
from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.core.config import Settings
from app.core.fabrica import FabricaServicios
from app.core.seguridad import RUTAS_PUBLICAS
from app.core.tiempo import ahora_utc
from app.correo.fake_client import FakeCorreoClient
from app.crypto.indice_ciego import sha256_hex
from app.models.autorizacion_acudiente import AutorizacionAcudiente
from app.models.consentimiento import Consentimiento
from app.models.usuario import Usuario
from tests.conftest import (
    CONTRASENA,
    contenedor_de,
    datos_registro,
    fecha_hace_anios,
    iniciar_conversacion,
    nuevo_cliente,
)

_PATRON_TOKEN = re.compile(r"#token=([A-Za-z0-9_-]+)")
ACUDIENTE = "acudiente@example.com"


def _correo(cliente: TestClient) -> FakeCorreoClient:
    correo = contenedor_de(cliente).correo
    assert isinstance(correo, FakeCorreoClient)
    return correo


def _token_del_ultimo_correo(cliente: TestClient) -> str:
    coincidencia = _PATRON_TOKEN.search(_correo(cliente).enviados[-1].texto)
    assert coincidencia is not None
    return coincidencia.group(1)


def _datos_menor(**cambios: Any) -> dict[str, Any]:
    base = {
        "fecha_nacimiento": fecha_hace_anios(15),
        "tipo_nivel": "COLEGIO",
        "nivel_educativo": "10",
        "entiende_datos_menor": True,
        "correo_acudiente": ACUDIENTE,
    }
    return datos_registro(**{**base, **cambios})


def registrar_menor(cliente: TestClient, **cambios: Any) -> dict[str, Any]:
    respuesta = cliente.post("/api/v1/auth/registro", json=_datos_menor(**cambios))
    assert respuesta.status_code == 201, respuesta.text
    usuario: dict[str, Any] = respuesta.json()
    return usuario


def autorizar_menor(cliente: TestClient) -> tuple[dict[str, Any], str]:
    menor = registrar_menor(cliente)
    token = _token_del_ultimo_correo(cliente)
    respuesta = cliente.post(
        "/api/v1/autorizaciones/confirmar", json={"token": token, "version_politica": "1"}
    )
    assert respuesta.status_code == 200, respuesta.text
    return menor, token


def _confirmar(cliente: TestClient, token: str, version: str = "1") -> Any:
    return cliente.post(
        "/api/v1/autorizaciones/confirmar", json={"token": token, "version_politica": version}
    )


def _retroceder_solicitudes(cliente: TestClient, segundos: int) -> None:
    """Simula el paso del tiempo para la espera mínima entre reenvíos."""
    with contenedor_de(cliente).fabrica_sesiones() as session:
        for fila in session.scalars(select(AutorizacionAcudiente)):
            fila.fecha_solicitud -= timedelta(seconds=segundos)
            if fila.fecha_verificacion is not None:
                fila.fecha_verificacion -= timedelta(seconds=segundos)
        session.commit()


def _pasar_espera(cliente: TestClient, settings: Settings) -> None:
    _retroceder_solicitudes(cliente, settings.autorizacion_reenvio_espera_segundos + 1)


def _codigo(respuesta: Any) -> str:
    codigo: str = respuesta.json()["error"]["codigo"]
    return codigo


# Registro
def test_mayor_de_edad_registra_igual_e_ignora_correo_acudiente(client: TestClient) -> None:
    respuesta = client.post(
        "/api/v1/auth/registro", json=datos_registro(correo_acudiente="no-es-correo")
    )
    assert respuesta.status_code == 201 and respuesta.json()["estado_cuenta"] == "ACTIVA"
    assert _correo(client).enviados == []
    assert client.get("/api/v1/autorizaciones/mia").json()["estado"] == "SIN_SOLICITUD"


def test_menor_sin_correo_acudiente_es_rechazado(client: TestClient) -> None:
    for valor in (None, "  "):
        respuesta = client.post("/api/v1/auth/registro", json=_datos_menor(correo_acudiente=valor))
        assert respuesta.status_code == 422 and _codigo(respuesta) == "CORREO_ACUDIENTE_REQUERIDO"
    assert _correo(client).enviados == []


def test_menor_con_correo_acudiente_invalido_o_propio(client: TestClient) -> None:
    datos = _datos_menor()
    propio = _datos_menor(correo=datos["correo"], correo_acudiente=f" {datos['correo'].upper()} ")
    for cuerpo in (propio, _datos_menor(correo_acudiente="no-es-correo")):
        respuesta = client.post("/api/v1/auth/registro", json=cuerpo)
        assert respuesta.status_code == 422 and _codigo(respuesta) == "CORREO_ACUDIENTE_INVALIDO"


def test_menor_de_13_es_rechazado(client: TestClient) -> None:
    respuesta = client.post(
        "/api/v1/auth/registro", json=_datos_menor(fecha_nacimiento=fecha_hace_anios(12))
    )
    assert respuesta.status_code == 422 and _codigo(respuesta) == "EDAD_NO_PERMITIDA"


def test_registro_de_menor_crea_solicitud_y_envia_correo(client: TestClient) -> None:
    menor = registrar_menor(client, correo_acudiente="  Acudiente@Example.com ")
    assert menor["estado_cuenta"] == "PENDIENTE_AUTORIZACION" and menor["es_menor"] is True
    enviado = _correo(client).enviados[-1]
    token = _token_del_ultimo_correo(client)
    assert enviado.destinatario == ACUDIENTE
    assert enviado.asunto == "Ana necesita tu autorización para usar TutorIA"
    assert (
        "Revisar y autorizar" in enviado.texto and "/autorizacion/confirmar#token=" in enviado.texto
    )
    assert menor["correo"] not in enviado.texto and "a***@example.com" in enviado.texto
    with contenedor_de(client).fabrica_sesiones() as session:
        fila = session.scalars(select(AutorizacionAcudiente)).one()
        assert (
            fila.token_hash == sha256_hex(token) and fila.estado.value == "PENDIENTE_VERIFICACION"
        )
    mia = client.get("/api/v1/autorizaciones/mia").json()
    assert (
        mia["estado"] == "PENDIENTE" and mia["correo_acudiente_enmascarado"] == "a***@example.com"
    )
    assert mia["puede_reenviar_en_segundos"] > 0


def test_registro_termina_bien_aunque_falle_el_correo(client: TestClient) -> None:
    _correo(client).falla = True
    menor = registrar_menor(client)
    assert menor["estado_cuenta"] == "PENDIENTE_AUTORIZACION"
    assert client.get("/api/v1/autorizaciones/mia").json()["estado"] == "PENDIENTE"


def test_tope_por_acudiente_no_envia_mas_correos_ni_lo_revela(
    client: TestClient, settings: Settings
) -> None:
    for _ in range(settings.autorizacion_max_solicitudes_por_hora):
        registrar_menor(nuevo_cliente(client.app))
    enviados = len(_correo(client).enviados)
    respuesta = nuevo_cliente(client.app).post("/api/v1/auth/registro", json=_datos_menor())
    assert respuesta.status_code == 201
    assert len(_correo(client).enviados) == enviados


# Pantalla del adulto
def test_consultar_muestra_resumen_sin_datos_completos(client: TestClient) -> None:
    menor = registrar_menor(client)
    token = _token_del_ultimo_correo(client)
    respuesta = client.post("/api/v1/autorizaciones/consultar", json={"token": token})
    datos = respuesta.json()
    assert respuesta.status_code == 200 and datos["estado"] == "PENDIENTE_VERIFICACION"
    assert datos["nombre_estudiante"] == "Ana"
    assert datos["correo_estudiante_enmascarado"].startswith("a***@")
    assert "representante legal" in datos["texto_consentimiento"]
    assert datos["version_politica"] == "1" and datos["permite_compras"] is False
    assert menor["correo"] not in respuesta.text and token not in respuesta.text
    assert "Pérez" not in respuesta.text


def test_token_inexistente_y_vencido_mismo_error(client: TestClient) -> None:
    registrar_menor(client)
    token = _token_del_ultimo_correo(client)
    with contenedor_de(client).fabrica_sesiones() as session:
        autorizacion = session.scalars(select(AutorizacionAcudiente)).one()
        autorizacion.fecha_expiracion_token = ahora_utc() - timedelta(hours=1)
        session.commit()
    for ruta in ("consultar", "rechazar"):
        vencido = client.post(f"/api/v1/autorizaciones/{ruta}", json={"token": token})
        inexistente = client.post(f"/api/v1/autorizaciones/{ruta}", json={"token": "x" * 43})
        assert vencido.status_code == inexistente.status_code == 404
        assert vencido.json() == inexistente.json()
    assert _confirmar(client, token).json() == _confirmar(client, "x" * 43).json()
    assert client.get("/api/v1/autorizaciones/mia").json()["estado"] == "EXPIRADA"


def test_confirmar_activa_y_registra_consentimiento_con_huella(client: TestClient) -> None:
    registrar_menor(client)
    token = _token_del_ultimo_correo(client)
    assert client.get("/api/v1/perfil-aprendizaje").status_code == 403
    texto = client.post("/api/v1/autorizaciones/consultar", json={"token": token}).json()[
        "texto_consentimiento"
    ]
    assert _confirmar(client, token).json()["estado"] == "AUTORIZADA"
    assert _confirmar(client, token).status_code == 200
    assert client.get("/api/v1/perfil-aprendizaje").status_code == 200
    assert "/autorizacion/revocar#token=" in _correo(client).enviados[-1].texto
    with contenedor_de(client).fabrica_sesiones() as session:
        filas = session.scalars(
            select(Consentimiento).where(Consentimiento.id_autorizacion.is_not(None))
        ).all()
    assert sorted(f.finalidad.value for f in filas) == [
        "TRANSFERENCIA_INTERNACIONAL",
        "TRATAMIENTO",
    ]
    assert all(
        f.otorgado
        and f.otorgado_por.value == "REPRESENTANTE_LEGAL"
        and f.version_politica == "1"
        and f.texto_sha256 == sha256_hex(texto)
        and f.ip_hash
        for f in filas
    )
    assert client.get("/api/v1/autorizaciones/mia").json()["estado"] == "AUTORIZADA"


def test_confirmar_con_version_desactualizada(client: TestClient) -> None:
    registrar_menor(client)
    respuesta = _confirmar(client, _token_del_ultimo_correo(client), version="0")
    assert respuesta.status_code == 409 and _codigo(respuesta) == "POLITICA_DESACTUALIZADA"
    assert client.get("/api/v1/auth/me").json()["estado_cuenta"] == "PENDIENTE_AUTORIZACION"


def test_rechazar_deja_pendiente_y_bloquea_el_mismo_correo(
    client: TestClient, settings: Settings
) -> None:
    registrar_menor(client)
    token = _token_del_ultimo_correo(client)
    enviados = len(_correo(client).enviados)
    for _ in range(2):
        respuesta = client.post("/api/v1/autorizaciones/rechazar", json={"token": token})
        assert respuesta.status_code == 200 and respuesta.json()["estado"] == "RECHAZADA"
    assert len(_correo(client).enviados) == enviados
    assert _confirmar(client, token).status_code == 404
    assert client.get("/api/v1/auth/me").json()["estado_cuenta"] == "PENDIENTE_AUTORIZACION"
    assert client.get("/api/v1/autorizaciones/mia").json()["estado"] == "RECHAZADA"
    _pasar_espera(client, settings)
    for cuerpo in ({}, {"correo_acudiente": ACUDIENTE}):
        bloqueado = client.post("/api/v1/autorizaciones/reenviar", json=cuerpo)
        assert bloqueado.status_code == 429 and _codigo(bloqueado) == "DEMASIADAS_SOLICITUDES"
        bloqueo = settings.autorizacion_bloqueo_rechazo_dias * 86400
        assert bloqueo - 300 < int(bloqueado.headers["Retry-After"]) <= bloqueo
    otro = client.post("/api/v1/autorizaciones/reenviar", json={"correo_acudiente": "otro@ex.com"})
    assert otro.status_code == 202 and _correo(client).enviados[-1].destinatario == "otro@ex.com"


def test_rechazo_vencido_permite_volver_a_pedir_al_mismo(
    client: TestClient, settings: Settings
) -> None:
    registrar_menor(client)
    client.post("/api/v1/autorizaciones/rechazar", json={"token": _token_del_ultimo_correo(client)})
    _retroceder_solicitudes(client, settings.autorizacion_bloqueo_rechazo_dias * 86400 + 1)
    assert client.post("/api/v1/autorizaciones/reenviar", json={}).status_code == 202


# Reenvío
def test_reenviar_respeta_espera_e_invalida_el_token_anterior(
    client: TestClient, settings: Settings
) -> None:
    registrar_menor(client)
    viejo = _token_del_ultimo_correo(client)
    pronto = client.post("/api/v1/autorizaciones/reenviar", json={})
    assert pronto.status_code == 429 and _codigo(pronto) == "DEMASIADAS_SOLICITUDES"
    assert 0 < int(pronto.headers["Retry-After"]) <= settings.autorizacion_reenvio_espera_segundos
    _pasar_espera(client, settings)
    respuesta = client.post("/api/v1/autorizaciones/reenviar", json={})
    assert respuesta.status_code == 202 and respuesta.json()["mensaje"]
    nuevo = _token_del_ultimo_correo(client)
    assert nuevo != viejo and _correo(client).enviados[-1].destinatario == ACUDIENTE
    assert client.post("/api/v1/autorizaciones/consultar", json={"token": viejo}).status_code == 404
    assert _confirmar(client, nuevo).status_code == 200


def test_reenviar_tope_por_hora(client: TestClient, settings: Settings) -> None:
    registrar_menor(client)
    for _ in range(settings.autorizacion_max_solicitudes_por_hora - 1):
        _pasar_espera(client, settings)
        assert client.post("/api/v1/autorizaciones/reenviar", json={}).status_code == 202
    _pasar_espera(client, settings)
    respuesta = client.post(
        "/api/v1/autorizaciones/reenviar", json={"correo_acudiente": "b@ex.com"}
    )
    assert respuesta.status_code == 429 and int(respuesta.headers["Retry-After"]) > 0
    assert client.get("/api/v1/autorizaciones/mia").json()["puede_reenviar_en_segundos"] > 0


def test_reenviar_valida_correo_y_cuenta(client: TestClient, settings: Settings) -> None:
    menor = registrar_menor(client)
    _pasar_espera(client, settings)
    for correo in (menor["correo"], "no-es-correo"):
        respuesta = client.post(
            "/api/v1/autorizaciones/reenviar", json={"correo_acudiente": correo}
        )
        assert respuesta.status_code == 422 and _codigo(respuesta) == "CORREO_ACUDIENTE_INVALIDO"
    _confirmar(client, _token_del_ultimo_correo(client))
    activa = client.post("/api/v1/autorizaciones/reenviar", json={})
    assert activa.status_code == 403 and _codigo(activa) == "OPERACION_NO_PERMITIDA"


def test_reenviar_y_mia_exigen_sesion(client: TestClient) -> None:
    assert client.get("/api/v1/autorizaciones/mia").status_code == 401
    assert client.post("/api/v1/autorizaciones/reenviar", json={}).status_code == 401


def test_solicitud_publica_retirada(client: TestClient) -> None:
    assert ("POST", "/api/v1/autorizaciones") not in RUTAS_PUBLICAS
    respuesta = client.post(
        "/api/v1/autorizaciones",
        json={"correo_acudiente": ACUDIENTE, "correo_estudiante": "b@example.com"},
    )
    assert respuesta.status_code in (404, 405)
    assert _correo(client).enviados == []


# Bloqueo y revocación
def test_menor_pendiente_bloqueado_en_rutas_activas(client: TestClient) -> None:
    registrar_menor(client)
    respuesta = client.get("/api/v1/suscripcion")
    assert respuesta.status_code == 403 and _codigo(respuesta) == "AUTORIZACION_PENDIENTE"
    assert client.post("/api/v1/diagnostico", json={"tema": "células"}).status_code == 403


def test_revocar_con_borrado_bloquea_y_suprime(client: TestClient) -> None:
    _menor, token = autorizar_menor(client)
    iniciar_conversacion(client, tema="volcanes")
    respuesta = client.post(
        "/api/v1/autorizaciones/revocar", json={"token": token, "eliminar_datos": True}
    )
    assert respuesta.status_code == 200 and respuesta.json()["estado"] == "REVOCADA"
    assert client.get("/api/v1/auth/me").status_code == 401
    with contenedor_de(client).fabrica_sesiones() as session:
        filas = session.scalars(select(Consentimiento)).all()
    assert any(not f.otorgado and f.otorgado_por.value == "REPRESENTANTE_LEGAL" for f in filas)
    assert (
        client.post(
            "/api/v1/autorizaciones/revocar", json={"token": token, "eliminar_datos": False}
        ).status_code
        == 404
    )


def test_revocar_sin_borrado_vuelve_a_bloquear(client: TestClient) -> None:
    menor, token = autorizar_menor(client)
    client.post("/api/v1/autorizaciones/revocar", json={"token": token, "eliminar_datos": False})
    client.cookies.clear()
    client.post("/api/v1/auth/login", json={"correo": menor["correo"], "contrasena": CONTRASENA})
    respuesta = client.get("/api/v1/suscripcion")
    assert respuesta.status_code == 403 and _codigo(respuesta) == "AUTORIZACION_PENDIENTE"
    assert client.get("/api/v1/autorizaciones/mia").json()["estado"] == "REVOCADA"


# Limpieza
def test_limpieza_elimina_cuenta_pendiente_vencida_con_su_solicitud(
    client: TestClient, settings: Settings
) -> None:
    vieja = registrar_menor(client)
    reciente = registrar_menor(nuevo_cliente(client.app), correo_acudiente="otro@example.com")
    hace = ahora_utc() - timedelta(days=settings.retencion_pendiente_dias + 1)
    id_vieja, id_reciente = uuid.UUID(vieja["id_usuario"]), uuid.UUID(reciente["id_usuario"])
    contenedor = contenedor_de(client)
    with contenedor.fabrica_sesiones() as session:
        session.execute(
            update(Usuario).where(Usuario.id_usuario == id_vieja).values(fecha_registro=hace)
        )
        for fila in session.scalars(select(AutorizacionAcudiente)):
            if fila.correo_acudiente == ACUDIENTE:
                fila.fecha_solicitud = hace
        session.commit()
        resumen = FabricaServicios(contenedor, session).retencion.limpiar()
    assert resumen.cuentas_pendientes_eliminadas == 1
    with contenedor.fabrica_sesiones() as session:
        solicitudes = session.scalars(select(AutorizacionAcudiente)).all()
        eliminado = session.get(Usuario, id_vieja)
        conservado = session.get(Usuario, id_reciente)
    assert [s.correo_acudiente for s in solicitudes] == ["otro@example.com"]
    assert eliminado is not None and not eliminado.activo and eliminado.correo != vieja["correo"]
    assert conservado is not None and conservado.activo
