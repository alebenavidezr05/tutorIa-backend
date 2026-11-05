"""Control de acceso deny-by-default (§6.6.9)."""

import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.dependencies import get_usuario_activo_id, get_usuario_actual_id
from app.core.seguridad import RUTAS_PUBLICAS
from app.main import create_app
from tests.conftest import CONTRASENA, ORIGEN, contenedor_de, nuevo_cliente, registrar

_PATRON_PARAMETRO = re.compile(r"\{[^}]+\}")
RUTAS_SOLO_SESION = {
    ("GET", "/api/v1/auth/me"),
    ("POST", "/api/v1/auth/logout"),
    ("POST", "/api/v1/privacidad/aceptar-politica"),
    ("GET", "/api/v1/autorizaciones/mia"),
    ("POST", "/api/v1/auth/verificar-correo/reenviar"),
    ("GET", "/api/v1/auth/verificar-correo/estado"),
    ("POST", "/api/v1/autorizaciones/reenviar"),
}
DEPENDENCIAS_DE_SESION = {get_usuario_actual_id, get_usuario_activo_id}


def _contextos(app: Any) -> list[Any]:
    """FastAPI 0.14x monta los routers incluidos de forma perezosa: se recorren sus contextos."""
    contextos: list[Any] = []
    for ruta in app.routes:
        if hasattr(ruta, "effective_route_contexts"):
            contextos.extend(ruta.effective_route_contexts())
        elif isinstance(ruta, APIRoute):
            contextos.append(ruta)
    return contextos


def _rutas(app: Any) -> list[tuple[str, str, Any]]:
    return [(metodo, c.path, c) for c in _contextos(app) for metodo in c.methods]


def _dependencias(dependant: Any) -> set[Any]:
    encontradas = {dependant.call}
    for sub in dependant.dependencies:
        encontradas |= _dependencias(sub)
    return encontradas


def _con_relleno(path: str) -> str:
    return _PATRON_PARAMETRO.sub(str(uuid.uuid4()), path)


def test_toda_ruta_no_publica_responde_401_sin_cookie(client: TestClient) -> None:
    privadas = [(m, p) for m, p, _ in _rutas(client.app) if (m, p) not in RUTAS_PUBLICAS]
    assert len(privadas) > 30
    for metodo, path in privadas:
        respuesta = client.request(metodo, _con_relleno(path), json={"campo": "x"})
        assert respuesta.status_code == 401, (metodo, path, respuesta.text)
        assert respuesta.json()["error"]["codigo"] == "SESION_INVALIDA"


def test_arbol_de_dependencias_exige_sesion_y_lista_publica_es_exacta(client: TestClient) -> None:
    publicas = set()
    for metodo, path, ruta in _rutas(client.app):
        if (metodo, path) in RUTAS_PUBLICAS:
            publicas.add((metodo, path))
            continue
        assert _dependencias(ruta.dependant) & DEPENDENCIAS_DE_SESION, (metodo, path)
    assert publicas == RUTAS_PUBLICAS
    for metodo, path, ruta in _rutas(client.app):
        if (metodo, path) in RUTAS_PUBLICAS:
            assert not _dependencias(ruta.dependant) & DEPENDENCIAS_DE_SESION, (metodo, path)


def _token(settings: Settings, id_usuario: str, **cambios: Any) -> str:
    ahora = datetime.now(UTC)
    claims = {
        "sub": id_usuario,
        "iat": int(ahora.timestamp()),
        "exp": int((ahora + timedelta(hours=1)).timestamp()),
        "jti": uuid.uuid4().hex,
        "ver": 0,
    }
    claims.update(cambios)
    return jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm="HS256")


@pytest.mark.parametrize(
    "fabricar",
    [
        lambda s, uid: _token(s, uid)[:-4] + "abcd",
        lambda s, uid: _token(
            s, uid, exp=int((datetime.now(UTC) - timedelta(hours=1)).timestamp())
        ),
        lambda s, uid: jwt.encode(
            {"sub": uid, "ver": 0}, "otra-clave-totalmente-distinta-0000000", algorithm="HS256"
        ),
        lambda s, uid: jwt.encode(
            {"sub": uid, "iat": 1, "exp": 9999999999, "jti": "x", "ver": 0},
            key="",
            algorithm="none",
        ),
        lambda s, uid: "no-es-un-jwt",
    ],
)
def test_cookies_invalidas_responden_401(
    client: TestClient, settings: Settings, fabricar: Any
) -> None:
    usuario = registrar(client)
    client.cookies.clear()
    client.cookies.set(settings.cookie_nombre, fabricar(settings, usuario["id_usuario"]))
    respuesta = client.get("/api/v1/auth/me")
    assert respuesta.status_code == 401
    assert respuesta.json()["error"]["codigo"] == "SESION_INVALIDA"


def test_version_de_token_desactualizada_invalida_la_sesion(
    client: TestClient, settings: Settings
) -> None:
    usuario = registrar(client)
    token_viejo = client.cookies.get(settings.cookie_nombre)
    assert client.delete(f"/api/v1/perfil/{usuario['id_usuario']}").status_code == 204
    client.cookies.set(settings.cookie_nombre, token_viejo)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_cuenta_pendiente_solo_accede_a_me_y_logout(client: TestClient) -> None:
    from tests.conftest import fecha_hace_anios

    registrar(
        client,
        fecha_nacimiento=fecha_hace_anios(15),
        entiende_datos_menor=True,
        correo_acudiente="acudiente@example.com",
    )
    assert client.get("/api/v1/auth/me").status_code == 200
    respuesta = client.get("/api/v1/suscripcion")
    assert respuesta.status_code == 403
    assert respuesta.json()["error"]["codigo"] == "AUTORIZACION_PENDIENTE"
    assert client.post("/api/v1/diagnostico", json={"tema": "células"}).status_code == 403
    assert client.post("/api/v1/auth/logout").status_code == 204


def test_cuenta_desactivada_no_inicia_sesion(client: TestClient) -> None:
    usuario = registrar(client)
    client.delete(f"/api/v1/perfil/{usuario['id_usuario']}")
    respuesta = client.post(
        "/api/v1/auth/login", json={"correo": usuario["correo"], "contrasena": CONTRASENA}
    )
    assert respuesta.status_code == 403
    assert respuesta.json()["error"]["codigo"] == "CUENTA_DESACTIVADA"


def test_recursos_ajenos_responden_404(client: TestClient, app: Any) -> None:
    from tests.conftest import iniciar_conversacion

    registrar(client)
    conversacion = iniciar_conversacion(client)
    otro = nuevo_cliente(app)
    registrar(otro)
    respuesta = otro.get(f"/api/v1/conversaciones/{conversacion['id_conversacion']}")
    assert respuesta.status_code == 404
    assert (
        otro.delete(f"/api/v1/conversaciones/{conversacion['id_conversacion']}").status_code == 404
    )


def test_uid_ajeno_en_perfil_e_historial_responde_403(client: TestClient, app: Any) -> None:
    primero = registrar(client)
    otro = nuevo_cliente(app)
    registrar(otro)
    assert otro.get(f"/api/v1/perfil/{primero['id_usuario']}").status_code == 403
    assert otro.get(f"/api/v1/historial/{primero['id_usuario']}").status_code == 403


def test_origen_ajeno_en_mutacion_responde_403(client: TestClient) -> None:
    registrar(client)
    respuesta = client.post(
        "/api/v1/conversaciones",
        json={"tema": "átomos"},
        headers={"Origin": "https://malicioso.example"},
    )
    assert respuesta.status_code == 403
    assert respuesta.json()["error"]["codigo"] == "ORIGEN_NO_PERMITIDO"
    sin_origen = TestClient(client.app)
    assert (
        sin_origen.post(
            "/api/v1/auth/login", json={"correo": "a@b.co", "contrasena": "x"}
        ).status_code
        == 403
    )


def test_documentacion_desactivada_en_produccion(settings: Settings) -> None:
    produccion = settings.model_copy(update={"app_env": "production"})
    app = create_app(produccion)
    rutas = {getattr(r, "path", "") for r in app.routes}
    assert "/docs" not in rutas and "/openapi.json" not in rutas


def test_peticion_anonima_con_cuerpo_invalido_recibe_401_y_no_422(client: TestClient) -> None:
    respuesta = client.post("/api/v1/diagnostico", json={"otro": 1})
    assert respuesta.status_code == 401


def test_cabeceras_de_seguridad(client: TestClient) -> None:
    respuesta = client.get("/api/v1/health")
    assert respuesta.headers["X-Content-Type-Options"] == "nosniff"
    assert "Referrer-Policy" in respuesta.headers


def test_ruta_inexistente_formato_uniforme(client: TestClient) -> None:
    respuesta = client.get("/api/v1/no-existe")
    assert respuesta.status_code == 404
    assert respuesta.json()["error"]["codigo"] == "RECURSO_NO_ENCONTRADO"


def test_cookie_httponly_y_samesite(client: TestClient, settings: Settings) -> None:
    from tests.conftest import datos_registro

    respuesta = client.post("/api/v1/auth/registro", json=datos_registro())
    cookie = respuesta.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and settings.cookie_nombre in cookie
    assert "token" not in respuesta.json()


def test_login_limita_intentos(client: TestClient, settings: Settings) -> None:
    usuario = registrar(client)
    for _ in range(settings.rate_limit_login_intentos):
        client.post(
            "/api/v1/auth/login", json={"correo": usuario["correo"], "contrasena": "incorrecta-1"}
        )
    respuesta = client.post(
        "/api/v1/auth/login", json={"correo": usuario["correo"], "contrasena": CONTRASENA}
    )
    assert respuesta.status_code == 429


def test_contenedor_disponible(client: TestClient) -> None:
    assert contenedor_de(client).settings.app_env == "test"
    assert ORIGEN in contenedor_de(client).settings.cors_origins
