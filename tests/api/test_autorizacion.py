"""Autorización del acudiente por correo verificado (§8.3)."""

import re
from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.tiempo import ahora_utc
from app.correo.fake_client import FakeCorreoClient
from app.models.autorizacion_acudiente import AutorizacionAcudiente
from app.models.consentimiento import Consentimiento
from tests.conftest import contenedor_de, datos_registro, fecha_hace_anios, iniciar_conversacion

_PATRON_TOKEN = re.compile(r"#token=([A-Za-z0-9_-]+)")


def _correo(cliente: TestClient) -> FakeCorreoClient:
    correo = contenedor_de(cliente).correo
    assert isinstance(correo, FakeCorreoClient)
    return correo


def solicitar(cliente: TestClient, correo_estudiante: str, permite_compras: bool = False) -> str:
    respuesta = cliente.post(
        "/api/v1/autorizaciones",
        json={
            "correo_acudiente": "acudiente@example.com",
            "correo_estudiante": correo_estudiante,
            "declara_representante_legal": True,
            "version_politica": "1",
            "acepta_tratamiento": True,
            "acepta_transferencia_internacional": True,
            "permite_compras": permite_compras,
        },
    )
    assert respuesta.status_code == 202, respuesta.text
    coincidencia = _PATRON_TOKEN.search(_correo(cliente).enviados[-1].texto)
    assert coincidencia is not None
    return coincidencia.group(1)


def registrar_menor(cliente: TestClient) -> dict[str, Any]:
    datos = datos_registro(
        fecha_nacimiento=fecha_hace_anios(15),
        tipo_nivel="COLEGIO",
        nivel_educativo="10",
        entiende_datos_menor=True,
    )
    respuesta = cliente.post("/api/v1/auth/registro", json=datos)
    assert respuesta.status_code == 201
    usuario: dict[str, Any] = respuesta.json()
    return usuario


def autorizar_menor(
    cliente: TestClient, permite_compras: bool = False
) -> tuple[dict[str, Any], str]:
    menor = registrar_menor(cliente)
    token = solicitar(cliente, menor["correo"], permite_compras)
    assert (
        cliente.post("/api/v1/autorizaciones/confirmar", json={"token": token}).status_code == 200
    )
    return menor, token


def test_menor_queda_pendiente_hasta_autorizar(client: TestClient) -> None:
    menor = registrar_menor(client)
    assert menor["estado_cuenta"] == "PENDIENTE_AUTORIZACION" and menor["es_menor"] is True
    assert client.get("/api/v1/perfil-aprendizaje").status_code == 403
    token = solicitar(client, menor["correo"])
    assert _correo(client).enviados[-1].destinatario == "acudiente@example.com"
    consulta = client.post("/api/v1/autorizaciones/consultar", json={"token": token}).json()
    assert (
        consulta["estado"] == "PENDIENTE_VERIFICACION"
        and "***" in consulta["correo_estudiante_enmascarado"]
    )
    assert (
        client.post("/api/v1/autorizaciones/confirmar", json={"token": token}).json()["estado"]
        == "AUTORIZADA"
    )
    assert client.post("/api/v1/autorizaciones/confirmar", json={"token": token}).status_code == 200
    assert client.get("/api/v1/perfil-aprendizaje").status_code == 200


def test_autorizacion_previa_activa_el_registro(client: TestClient) -> None:
    datos = datos_registro(fecha_nacimiento=fecha_hace_anios(14), entiende_datos_menor=True)
    token = solicitar(client, datos["correo"])
    client.post("/api/v1/autorizaciones/confirmar", json={"token": token})
    respuesta = client.post("/api/v1/auth/registro", json=datos)
    assert respuesta.json()["estado_cuenta"] == "ACTIVA"


def test_token_inexistente_y_vencido_mismo_error(client: TestClient) -> None:
    menor = registrar_menor(client)
    token = solicitar(client, menor["correo"])
    with contenedor_de(client).fabrica_sesiones() as session:
        autorizacion = session.scalars(select(AutorizacionAcudiente)).one()
        autorizacion.fecha_expiracion_token = ahora_utc() - timedelta(hours=1)
        session.commit()
    vencido = client.post("/api/v1/autorizaciones/confirmar", json={"token": token})
    inexistente = client.post("/api/v1/autorizaciones/confirmar", json={"token": "x" * 43})
    assert vencido.status_code == inexistente.status_code == 404
    assert vencido.json() == inexistente.json()


def test_nueva_solicitud_vence_la_anterior(client: TestClient) -> None:
    menor = registrar_menor(client)
    primero = solicitar(client, menor["correo"])
    solicitar(client, menor["correo"])
    assert (
        client.post("/api/v1/autorizaciones/confirmar", json={"token": primero}).status_code == 404
    )


def test_limite_de_solicitudes_por_hora(client: TestClient, settings: Any) -> None:
    menor = registrar_menor(client)
    for _ in range(settings.autorizacion_max_solicitudes_por_hora):
        solicitar(client, menor["correo"])
    respuesta = client.post(
        "/api/v1/autorizaciones",
        json={
            "correo_acudiente": "otro@example.com",
            "correo_estudiante": menor["correo"],
            "declara_representante_legal": True,
            "version_politica": "1",
            "acepta_tratamiento": True,
            "acepta_transferencia_internacional": True,
        },
    )
    assert respuesta.status_code == 429


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


def test_revocar_sin_borrado_deja_cuenta_pendiente(client: TestClient) -> None:
    menor, token = autorizar_menor(client)
    client.post("/api/v1/autorizaciones/revocar", json={"token": token, "eliminar_datos": False})
    from tests.conftest import CONTRASENA

    client.cookies.clear()
    client.post("/api/v1/auth/login", json={"correo": menor["correo"], "contrasena": CONTRASENA})
    respuesta = client.get("/api/v1/suscripcion")
    assert (
        respuesta.status_code == 403
        and respuesta.json()["error"]["codigo"] == "AUTORIZACION_PENDIENTE"
    )


def test_solicitud_exige_declaracion_y_correos_distintos(client: TestClient) -> None:
    base = {
        "correo_acudiente": "a@example.com",
        "correo_estudiante": "b@example.com",
        "version_politica": "1",
        "acepta_tratamiento": True,
        "acepta_transferencia_internacional": True,
    }
    assert client.post("/api/v1/autorizaciones", json=base).status_code == 422
    iguales = {**base, "declara_representante_legal": True, "correo_estudiante": "a@example.com"}
    assert client.post("/api/v1/autorizaciones", json=iguales).status_code == 422
