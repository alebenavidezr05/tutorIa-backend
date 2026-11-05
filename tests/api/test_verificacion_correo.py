"""Verificación del correo de quien se registra."""

import logging
import re
import uuid
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text, update

from app.core.config import Settings
from app.core.fabrica import FabricaServicios
from app.core.migraciones import aplicar_migraciones
from app.core.tiempo import ahora_utc
from app.correo.fake_client import FakeCorreoClient
from app.crypto.indice_ciego import sha256_hex
from app.models.usuario import Usuario
from app.models.verificacion_correo import VerificacionCorreo
from tests.conftest import (
    contenedor_de,
    datos_registro,
    fecha_hace_anios,
    nuevo_cliente,
    registrar,
    token_verificacion,
)

VERIFICAR = "/api/v1/auth/verificar-correo"
REENVIAR = "/api/v1/auth/verificar-correo/reenviar"
ESTADO = "/api/v1/auth/verificar-correo/estado"


def _correo(cliente: TestClient) -> FakeCorreoClient:
    correo = contenedor_de(cliente).correo
    assert isinstance(correo, FakeCorreoClient)
    return correo


def _sin_verificar(cliente: TestClient, **cambios: Any) -> dict[str, Any]:
    return registrar(cliente, verificar=False, **cambios)


def _codigo(respuesta: Any) -> str:
    codigo: str = respuesta.json()["error"]["codigo"]
    return codigo


def _retroceder_envios(cliente: TestClient, segundos: int) -> None:
    with contenedor_de(cliente).fabrica_sesiones() as session:
        for fila in session.scalars(select(VerificacionCorreo)):
            fila.fecha_creacion -= timedelta(seconds=segundos)
        session.commit()


def _pasar_espera(cliente: TestClient, settings: Settings) -> None:
    _retroceder_envios(cliente, settings.verificacion_reenvio_espera_segundos + 1)


# Registro
def test_registro_crea_cuenta_sin_verificar_y_envia_enlace(client: TestClient) -> None:
    usuario = _sin_verificar(client)
    assert usuario["correo_verificado"] is False
    enviado = _correo(client).enviados[-1]
    token = token_verificacion(client, usuario["correo"])
    assert enviado.destinatario == usuario["correo"]
    assert enviado.asunto == "Confirma tu correo en TutorIA"
    assert "Confirmar mi correo: http://localhost:4200/verificar-correo#token=" in enviado.texto
    assert "Si no fuiste tú, puedes ignorar este mensaje." in enviado.texto
    assert re.search(r"\btutor\b", enviado.texto, re.IGNORECASE) is None
    with contenedor_de(client).fabrica_sesiones() as session:
        fila = session.scalars(select(VerificacionCorreo)).one()
    assert fila.token_hash == sha256_hex(token) and fila.usado is False
    assert token not in {fila.token_hash, fila.correo_hash}
    estado = client.get(ESTADO).json()
    assert (
        estado["correo_verificado"] is False and estado["correo_enmascarado"] == "a***@example.com"
    )
    assert estado["puede_reenviar_en_segundos"] > 0


def test_registro_termina_bien_aunque_falle_el_correo(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    _correo(client).falla = True
    with caplog.at_level(logging.WARNING):
        usuario = _sin_verificar(client)
    assert usuario["correo_verificado"] is False
    assert "verificacion_correo_no_enviado" in caplog.text
    assert usuario["correo"] not in caplog.text and "Ana" not in caplog.text


# Verificación
def test_verificar_activa_la_cuenta_es_idempotente_y_no_crea_sesion(client: TestClient) -> None:
    usuario = _sin_verificar(client)
    token = token_verificacion(client, usuario["correo"])
    otro_dispositivo = nuevo_cliente(client.app)
    for _ in range(2):
        respuesta = otro_dispositivo.post(VERIFICAR, json={"token": token})
        assert respuesta.status_code == 200 and respuesta.json() == {"estado": "VERIFICADO"}
        assert "set-cookie" not in respuesta.headers
    me = client.get("/api/v1/auth/me").json()
    assert me["correo_verificado"] is True
    assert client.get(ESTADO).json()["puede_reenviar_en_segundos"] == 0
    assert client.get("/api/v1/suscripcion").status_code == 200


def test_token_invalido_o_vencido_mismo_error(client: TestClient) -> None:
    usuario = _sin_verificar(client)
    token = token_verificacion(client, usuario["correo"])
    with contenedor_de(client).fabrica_sesiones() as session:
        session.execute(update(VerificacionCorreo).values(fecha_expiracion=ahora_utc()))
        session.commit()
    vencido = client.post(VERIFICAR, json={"token": token})
    inexistente = client.post(VERIFICAR, json={"token": "x" * 43})
    assert vencido.status_code == inexistente.status_code == 404
    assert vencido.json() == inexistente.json()
    assert _codigo(vencido) == "VERIFICACION_INVALIDA"
    assert token not in vencido.text


def test_token_usado_no_sirve_para_otra_cuenta(client: TestClient) -> None:
    primera = _sin_verificar(client)
    token = token_verificacion(client, primera["correo"])
    assert client.post(VERIFICAR, json={"token": token}).status_code == 200
    segunda_cliente = nuevo_cliente(client.app)
    _sin_verificar(segunda_cliente)
    assert segunda_cliente.post(VERIFICAR, json={"token": token}).status_code == 200
    assert segunda_cliente.get("/api/v1/auth/me").json()["correo_verificado"] is False


# Qué bloquea
def test_sin_verificar_bloquea_rutas_activas_y_permite_las_de_espera(client: TestClient) -> None:
    _sin_verificar(client)
    bloqueadas = [
        client.post("/api/v1/diagnostico", json={"tema": "células"}),
        client.post("/api/v1/plan-aprendizaje", json={"id_sesion": str(uuid.uuid4())}),
        client.post("/api/v1/archivos", files={"archivo": ("a.txt", b"hola", "text/plain")}),
        client.post("/api/v1/conversaciones", json={"tema": "volcanes"}),
        client.get("/api/v1/suscripcion"),
    ]
    for respuesta in bloqueadas:
        assert respuesta.status_code == 403 and _codigo(respuesta) == "CORREO_NO_VERIFICADO"
    for ruta in (ESTADO, "/api/v1/auth/me", "/api/v1/politica-tratamiento"):
        assert client.get(ruta).status_code == 200, ruta
    assert client.get("/api/v1/autorizaciones/mia").status_code == 200
    assert client.post("/api/v1/auth/logout").status_code == 204


def test_menor_necesita_ambas_condiciones(client: TestClient) -> None:
    datos = datos_registro(
        fecha_nacimiento=fecha_hace_anios(15),
        tipo_nivel="COLEGIO",
        nivel_educativo="10",
        entiende_datos_menor=True,
        correo_acudiente="acudiente@example.com",
    )
    menor = client.post("/api/v1/auth/registro", json=datos).json()
    token_acudiente = re.search(
        r"confirmar#token=([A-Za-z0-9_-]+)", _correo(client).enviados[-1].texto
    )
    assert token_acudiente is not None
    client.post(
        "/api/v1/autorizaciones/confirmar",
        json={"token": token_acudiente.group(1), "version_politica": "1"},
    )
    autorizado = client.get("/api/v1/suscripcion")
    assert autorizado.status_code == 403 and _codigo(autorizado) == "CORREO_NO_VERIFICADO"
    client.post(VERIFICAR, json={"token": token_verificacion(client, menor["correo"])})
    assert client.get("/api/v1/suscripcion").status_code == 200

    otro = nuevo_cliente(client.app)
    verificado = registrar(otro, **{**datos, "correo": f"b-{uuid.uuid4().hex[:6]}@example.com"})
    assert verificado["estado_cuenta"] == "PENDIENTE_AUTORIZACION"
    pendiente = otro.get("/api/v1/suscripcion")
    assert pendiente.status_code == 403 and _codigo(pendiente) == "AUTORIZACION_PENDIENTE"


# Reenvío
def test_reenviar_respeta_espera_e_invalida_el_token_anterior(
    client: TestClient, settings: Settings
) -> None:
    usuario = _sin_verificar(client)
    viejo = token_verificacion(client, usuario["correo"])
    pronto = client.post(REENVIAR)
    assert pronto.status_code == 429 and _codigo(pronto) == "DEMASIADAS_SOLICITUDES"
    assert 0 < int(pronto.headers["Retry-After"]) <= settings.verificacion_reenvio_espera_segundos
    _pasar_espera(client, settings)
    respuesta = client.post(REENVIAR)
    assert respuesta.status_code == 202 and respuesta.json()["mensaje"]
    nuevo = token_verificacion(client, usuario["correo"])
    assert nuevo != viejo
    assert client.post(VERIFICAR, json={"token": viejo}).status_code == 404
    assert client.post(VERIFICAR, json={"token": nuevo}).status_code == 200
    ya = client.post(REENVIAR)
    assert ya.status_code == 409 and _codigo(ya) == "CORREO_YA_VERIFICADO"


def test_reenviar_tope_por_hora(client: TestClient, settings: Settings) -> None:
    _sin_verificar(client)
    for _ in range(settings.verificacion_max_envios_por_hora - 1):
        _pasar_espera(client, settings)
        assert client.post(REENVIAR).status_code == 202
    _pasar_espera(client, settings)
    respuesta = client.post(REENVIAR)
    assert respuesta.status_code == 429 and int(respuesta.headers["Retry-After"]) > 0
    assert client.get(ESTADO).json()["puede_reenviar_en_segundos"] > 0


def test_reenviar_exige_sesion(client: TestClient) -> None:
    assert client.post(REENVIAR).status_code == 401
    assert client.get(ESTADO).status_code == 401


# Migración y limpieza
def test_migracion_deja_verificadas_las_cuentas_existentes(client: TestClient) -> None:
    existente = _sin_verificar(client)
    engine = contenedor_de(client).engine
    with engine.begin() as conexion:
        conexion.execute(text("ALTER TABLE usuario DROP COLUMN correo_verificado"))
        conexion.execute(text("ALTER TABLE usuario DROP COLUMN fecha_verificacion_correo"))
    aplicar_migraciones(engine)
    aplicar_migraciones(engine)
    assert client.get("/api/v1/auth/me").json()["correo_verificado"] is True
    nueva = _sin_verificar(nuevo_cliente(client.app))
    with contenedor_de(client).fabrica_sesiones() as session:
        assert session.get(Usuario, uuid.UUID(existente["id_usuario"])).correo_verificado  # type: ignore[union-attr]
        assert not session.get(Usuario, uuid.UUID(nueva["id_usuario"])).correo_verificado  # type: ignore[union-attr]


def test_limpieza_elimina_cuenta_sin_verificar_vencida_con_sus_tokens(
    client: TestClient, settings: Settings
) -> None:
    vieja = _sin_verificar(client)
    verificada = registrar(nuevo_cliente(client.app))
    reciente = _sin_verificar(nuevo_cliente(client.app))
    hace = ahora_utc() - timedelta(days=settings.retencion_no_verificada_dias + 1)
    ids = {
        k: uuid.UUID(u["id_usuario"])
        for k, u in (("v", vieja), ("ok", verificada), ("r", reciente))
    }
    contenedor = contenedor_de(client)
    with contenedor.fabrica_sesiones() as session:
        session.execute(
            update(Usuario)
            .where(Usuario.id_usuario.in_([ids["v"], ids["ok"]]))
            .values(fecha_registro=hace)
        )
        session.commit()
        resumen = FabricaServicios(contenedor, session).retencion.limpiar()
    assert resumen.cuentas_no_verificadas_eliminadas == 1
    with contenedor.fabrica_sesiones() as session:
        eliminada = session.get(Usuario, ids["v"])
        tokens = session.scalars(select(VerificacionCorreo.id_usuario)).all()
        assert eliminada is not None and not eliminada.activo
        assert eliminada.correo != vieja["correo"]
        assert ids["v"] not in tokens and ids["r"] in tokens
        assert session.get(Usuario, ids["ok"]).activo  # type: ignore[union-attr]
        assert session.get(Usuario, ids["r"]).activo  # type: ignore[union-attr]
    # El correo queda libre para registrarse de nuevo.
    assert (
        nuevo_cliente(client.app)
        .post("/api/v1/auth/registro", json=datos_registro(correo=vieja["correo"]))
        .status_code
        == 201
    )
