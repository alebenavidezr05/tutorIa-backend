import base64
import os

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import text

from app.core.config import Settings
from app.crypto.base import CifradorAesGcm
from app.crypto.indice_ciego import IndiceCiego
from app.exceptions.base import CifradoError
from tests.conftest import contenedor_de, enviar, iniciar_conversacion, registrar


def _cifrador(version: str = "v1") -> CifradorAesGcm:
    return CifradorAesGcm({version: os.urandom(32)}, version)


def test_ida_y_vuelta_y_nonce_aleatorio() -> None:
    cifrador = _cifrador()
    uno, dos = cifrador.cifrar("hola", "t.c"), cifrador.cifrar("hola", "t.c")
    assert uno != dos and uno.startswith("v1.")
    assert cifrador.descifrar(uno, "t.c") == "hola"


def test_aad_distinto_falla() -> None:
    cifrador = _cifrador()
    with pytest.raises(CifradoError):
        cifrador.descifrar(cifrador.cifrar("hola", "usuario.nombre"), "usuario.correo")


def test_rotacion_por_version() -> None:
    vieja, nueva = os.urandom(32), os.urandom(32)
    anterior = CifradorAesGcm({"v1": vieja}, "v1")
    valor = anterior.cifrar("dato", "t.c")
    rotado = CifradorAesGcm({"v1": vieja, "v2": nueva}, "v2")
    assert rotado.descifrar(valor, "t.c") == "dato"
    assert not rotado.es_version_actual(valor)
    assert rotado.es_version_actual(rotado.cifrar("dato", "t.c"))


def test_clave_de_tamano_invalido() -> None:
    with pytest.raises(CifradoError):
        CifradorAesGcm({"v1": b"corta"}, "v1")


def test_indice_ciego_determinista() -> None:
    indice = IndiceCiego("clave")
    assert indice.calcular("a@b.co") == indice.calcular("a@b.co")
    assert indice.calcular("a@b.co") != IndiceCiego("otra").calcular("a@b.co")


def test_la_base_no_contiene_datos_legibles(client: TestClient) -> None:
    usuario = registrar(client, nombre="Valentina Secreta")
    conversacion = iniciar_conversacion(client, tema="volcanes activos")
    assert (
        enviar(
            client, conversacion["id_conversacion"], "Mensaje confidencial sobre volcanes"
        ).status_code
        == 201
    )
    with contenedor_de(client).engine.connect() as conexion:
        filas = conexion.execute(text("SELECT nombre, correo FROM usuario")).all()
        mensajes = conexion.execute(text("SELECT contenido FROM mensaje")).all()
        temas = conexion.execute(text("SELECT tema FROM conversacion")).all()
    volcado = repr(filas) + repr(mensajes) + repr(temas)
    assert "Valentina" not in volcado and usuario["correo"] not in volcado
    assert "confidencial" not in volcado and "volcanes" not in volcado


def test_produccion_rechaza_cifrado_local_y_secretos_cortos(settings: Settings) -> None:
    with pytest.raises(ValidationError):
        Settings(**{**settings.model_dump(), "app_env": "production"})


def _datos_produccion(settings: Settings, pasarela: str) -> dict[str, object]:
    return {
        **settings.model_dump(),
        "app_env": "production",
        "jwt_secret": "x" * 40,
        "indice_ciego_clave": "y" * 40,
        "llm_provider": "anthropic",
        "llm_api_key": "sk-ant-prueba",
        "llm_model_sencillo": "modelo-a",
        "llm_model_complejo": "modelo-b",
        "moderacion_proveedor": "openai",
        "correo_proveedor": "ses",
        "cifrado_proveedor": "kms",
        "almacen_proveedor": "s3",
        "videos_proveedor": "youtube",
        "fuentes_proveedores": [],
        "imagenes_proveedores": [],
        "responsable_razon_social": "TutorIA S.A.S.",
        "responsable_nit": "900000000",
        "responsable_domicilio": "Bogotá",
        "pasarela_proveedor": pasarela,
        "pasarela_secreto_webhook": "",
    }


def test_produccion_carga_con_pasarela_ninguna(settings: Settings) -> None:
    cargada = Settings(**_datos_produccion(settings, "ninguna"))
    assert cargada.es_produccion and cargada.pasarela_proveedor == "ninguna"


def test_produccion_rechaza_pasarela_fake(settings: Settings) -> None:
    with pytest.raises(
        ValidationError,
        match="PASARELA_PROVEEDOR=fake no se permite en producción; usa 'ninguna' o un adaptador real",
    ):
        Settings(**_datos_produccion(settings, "fake"))


def test_llave_local_es_base64_de_32_bytes(settings: Settings) -> None:
    assert len(base64.b64decode(settings.cifrado_clave_local.get_secret_value())) == 32
