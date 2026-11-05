import re
import uuid
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.config import Settings
from app.core.contenedor import Contenedor
from app.core.database import eliminar_tablas
from app.main import create_app

ORIGEN = "http://localhost:4200"
CONTRASENA = "clave-segura-123"


class ConfigPruebas(BaseSettings):
    """Permite correr la suite contra PostgreSQL real en CI (marcador `db`)."""

    model_config = SettingsConfigDict(env_prefix="TEST_", extra="ignore")
    database_url: str = ""


def _url_base_datos(tmp_path: Path) -> str:
    return ConfigPruebas().database_url or f"sqlite:///{tmp_path / 'pruebas.db'}"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if ConfigPruebas().database_url.startswith("postgresql"):
        return
    omitir = pytest.mark.skip(reason="requiere TEST_DATABASE_URL de PostgreSQL")
    for item in items:
        if "db" in item.keywords:
            item.add_marker(omitir)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        database_url=_url_base_datos(tmp_path),
        bcrypt_rounds=4,
        almacen_ruta_local=str(tmp_path / "almacen"),
        responsable_correo_datos="datos@tutoria.example",
        imagenes_ia_activa=True,
    )


@pytest.fixture
def app(settings: Settings) -> Iterator[Any]:
    aplicacion = create_app(settings)
    yield aplicacion


@pytest.fixture
def client(app: Any) -> Iterator[TestClient]:
    with TestClient(app, headers={"Origin": ORIGEN}) as cliente:
        yield cliente
        eliminar_tablas(contenedor_de(cliente).engine)


def contenedor_de(cliente: TestClient) -> Contenedor:
    contenedor: Contenedor = cliente.app.state.contenedor  # type: ignore[attr-defined]
    return contenedor


def datos_registro(**cambios: Any) -> dict[str, Any]:
    datos: dict[str, Any] = {
        "nombre": "Ana Pérez",
        "correo": f"ana-{uuid.uuid4().hex[:8]}@example.com",
        "contrasena": CONTRASENA,
        "fecha_nacimiento": "2000-05-10",
        "tipo_nivel": "UNIVERSIDAD_TECNICA",
        "nivel_educativo": "Pregrado",
        "version_politica": "1",
        "acepta_tratamiento": True,
        "acepta_transferencia_internacional": True,
        "acepta_personalizacion": True,
    }
    datos.update(cambios)
    return datos


_PATRON_VERIFICACION = re.compile(r"/verificar-correo#token=([A-Za-z0-9_-]+)")


def token_verificacion(cliente: TestClient, correo: str) -> str:
    """Token del último correo de verificación enviado a `correo` (cliente de correo falso)."""
    enviados = contenedor_de(cliente).correo.enviados  # type: ignore[attr-defined]
    for enviado in reversed(enviados):
        coincidencia = _PATRON_VERIFICACION.search(enviado.texto)
        if enviado.destinatario == correo and coincidencia:
            return coincidencia.group(1)
    raise AssertionError("no se envió el correo de verificación")


def verificar_correo(cliente: TestClient, correo: str) -> None:
    token = token_verificacion(cliente, correo)
    respuesta = cliente.post("/api/v1/auth/verificar-correo", json={"token": token})
    assert respuesta.status_code == 200, respuesta.text


def registrar(cliente: TestClient, verificar: bool = True, **cambios: Any) -> dict[str, Any]:
    """Registra y, por defecto, confirma el correo (la mayoría de pruebas usan la app activa)."""
    respuesta = cliente.post("/api/v1/auth/registro", json=datos_registro(**cambios))
    assert respuesta.status_code == 201, respuesta.text
    usuario: dict[str, Any] = respuesta.json()
    if verificar:
        verificar_correo(cliente, usuario["correo"])
    return usuario


def fecha_hace_anios(anios: int) -> str:
    hoy = date.today()
    return hoy.replace(year=hoy.year - anios).isoformat()


@pytest.fixture
def usuario(client: TestClient) -> dict[str, Any]:
    return registrar(client)


def nuevo_cliente(app: Any) -> TestClient:
    """Segundo navegador sobre la misma app (otra cookie), sin repetir el lifespan."""
    return TestClient(app, headers={"Origin": ORIGEN})


def crear_diagnostico(cliente: TestClient, tema: str = "fotosíntesis") -> dict[str, Any]:
    respuesta = cliente.post("/api/v1/diagnostico", json={"tema": tema})
    assert respuesta.status_code == 201, respuesta.text
    datos: dict[str, Any] = respuesta.json()
    return datos


def evaluar(cliente: TestClient, cuestionario: dict[str, Any], aciertos: int) -> dict[str, Any]:
    respuestas = [
        {"id_pregunta": p["id_pregunta"], "respuesta": "a" if i < aciertos else "b"}
        for i, p in enumerate(cuestionario["preguntas"])
    ]
    respuesta = cliente.post(
        f"/api/v1/diagnostico/{cuestionario['id_sesion']}/respuestas",
        json={"respuestas": respuestas},
    )
    assert respuesta.status_code == 200, respuesta.text
    datos: dict[str, Any] = respuesta.json()
    return datos


def iniciar_conversacion(
    cliente: TestClient, tema: str = "fotosíntesis", **extra: Any
) -> dict[str, Any]:
    respuesta = cliente.post("/api/v1/conversaciones", json={"tema": tema, **extra})
    assert respuesta.status_code == 201, respuesta.text
    datos: dict[str, Any] = respuesta.json()
    return datos


def enviar(cliente: TestClient, id_conversacion: str, contenido: str, **extra: Any) -> Any:
    return cliente.post(
        f"/api/v1/conversaciones/{id_conversacion}/mensajes", json={"contenido": contenido, **extra}
    )
