"""OpenAlex con API key, reintentos, semáforo y caché; cero fuentes; reintento del cuestionario."""

import json
import logging
import threading
import time
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select, update

from app.core.config import ConfigProveedor, Settings
from app.core.tiempo import ahora_utc
from app.core.unit_of_work import FabricaUnitOfWork
from app.exceptions.base import FuentesNoDisponiblesError
from app.fuentes.adaptadores.rest_json import OpenAlexFuentesClient
from app.fuentes.base import FuenteCandidata, FuentesClient
from app.fuentes.registro import avisar_configuracion, construir_fuentes
from app.llm.base import TareaLLM
from app.llm.fake_client import FakeClient, respuesta_texto
from app.models.cache_fuentes import CacheFuentes
from app.models.enums import CategoriaFuente, NivelCognitivo, TipoNivel
from app.repositories.fuente import FuenteRepository
from app.services.fuentes.cache_fuentes import CacheBusquedaFuentes
from app.services.fuentes.fuentes_service import ContextoFuentes, FuentesService
from tests.conftest import contenedor_de, registrar

CLAVE = "clave-openalex-super-secreta-123"
CONFIG_OPENALEX = ConfigProveedor(
    id="openalex",
    categoria="ACADEMICA_ABIERTA",
    adaptador="openalex",
    base_url="https://api.openalex.org/works",
)
OBRA = {
    "results": [
        {
            "id": "https://openalex.org/W1",
            "doi": "https://doi.org/10.1234/abc",
            "title": "La fotosíntesis",
            "type": "article",
            "language": "es",
            "publication_date": "2024-01-01",
            "authorships": [{"author": {"display_name": "Ana Ruiz"}}],
            "primary_location": {
                "landing_page_url": "https://revista.example.org/a",
                "source": {"display_name": "Revista", "is_in_doaj": True},
            },
            "abstract_inverted_index": {"La": [0], "luz": [1]},
        }
    ]
}


class _Servidor:
    """Respuestas programadas en orden; registra cada petición recibida."""

    def __init__(self, *respuestas: httpx.Response) -> None:
        self._respuestas = list(respuestas)
        self.peticiones: list[httpx.Request] = []

    def __call__(self, peticion: httpx.Request) -> httpx.Response:
        self.peticiones.append(peticion)
        return self._respuestas.pop(0) if self._respuestas else httpx.Response(200, json=OBRA)


def _openalex(
    servidor: Callable[[httpx.Request], httpx.Response],
    esperas: list[float] | None = None,
    clave: str | None = CLAVE,
) -> OpenAlexFuentesClient:
    return OpenAlexFuentesClient(
        CONFIG_OPENALEX,
        httpx.Client(transport=httpx.MockTransport(servidor)),
        SecretStr(clave) if clave else None,
        dormir=(esperas if esperas is not None else []).append,
    )


def _limite(reset: str | None) -> httpx.Response:
    return httpx.Response(429, headers={"X-RateLimit-Reset": reset} if reset else {})


# OpenAlex: clave, reintentos, semáforo
def test_clave_va_en_authorization_y_nunca_en_url_ni_logs(caplog: pytest.LogCaptureFixture) -> None:
    servidor = _Servidor(_limite("3600"))
    cliente = _openalex(servidor)
    with caplog.at_level(logging.DEBUG), pytest.raises(FuentesNoDisponiblesError) as error:
        cliente.buscar("fotosíntesis", "es", 3)
    assert cliente.buscar("fotosíntesis", "es", 3)
    for peticion in servidor.peticiones:
        assert peticion.headers["Authorization"] == f"Bearer {CLAVE}"
        assert CLAVE not in str(peticion.url)
        assert "api_key" not in peticion.url.params and "mailto" not in peticion.url.params
    assert CLAVE not in caplog.text and CLAVE not in str(error.value)
    assert "Authorization" not in caplog.text and "Bearer" not in caplog.text


def test_sin_clave_no_envia_authorization() -> None:
    servidor = _Servidor()
    _openalex(servidor, clave=None).buscar("fotosíntesis", "es", 3)
    assert "Authorization" not in servidor.peticiones[0].headers


def test_429_corto_espera_y_reintenta_una_vez() -> None:
    servidor, esperas = _Servidor(_limite("1")), []
    resultado = _openalex(servidor, esperas).buscar("fotosíntesis", "es", 3)
    assert len(resultado) == 1 and esperas == [1.0] and len(servidor.peticiones) == 2


def test_429_largo_no_reintenta_y_propaga_retry_after(caplog: pytest.LogCaptureFixture) -> None:
    servidor, esperas = _Servidor(_limite("3600")), []
    with caplog.at_level(logging.WARNING), pytest.raises(FuentesNoDisponiblesError) as error:
        _openalex(servidor, esperas).buscar("fotosíntesis", "es", 3)
    assert esperas == [] and len(servidor.peticiones) == 1
    assert error.value.cabeceras == {"Retry-After": "3600"}
    assert "fuentes_error proveedor=openalex tipo=HTTPStatusError estado=429 reset=3600.0" in (
        caplog.text
    )


@pytest.mark.parametrize("reset", [None, "no-numero"])
def test_429_sin_reset_valido_no_reintenta(reset: str | None) -> None:
    servidor = _Servidor(_limite(reset))
    with pytest.raises(FuentesNoDisponiblesError):
        _openalex(servidor).buscar("fotosíntesis", "es", 3)
    assert len(servidor.peticiones) == 1


def test_5xx_reintenta_una_vez_con_espera_corta() -> None:
    servidor, esperas = _Servidor(httpx.Response(503)), []
    assert _openalex(servidor, esperas).buscar("fotosíntesis", "es", 3)
    assert esperas == [1.0]
    persistente = _Servidor(httpx.Response(500), httpx.Response(502))
    with pytest.raises(FuentesNoDisponiblesError):
        _openalex(persistente).buscar("fotosíntesis", "es", 3)
    assert len(persistente.peticiones) == 2


def test_maximo_una_peticion_simultanea_por_proceso() -> None:
    estado = {"actuales": 0, "maximo": 0}
    candado = threading.Lock()

    def lento(_: httpx.Request) -> httpx.Response:
        with candado:
            estado["actuales"] += 1
            estado["maximo"] = max(estado["maximo"], estado["actuales"])
        time.sleep(0.05)
        with candado:
            estado["actuales"] -= 1
        return httpx.Response(200, json=OBRA)

    clientes = [_openalex(lento) for _ in range(4)]
    hilos = [threading.Thread(target=c.buscar, args=("tema", "es", 3)) for c in clientes]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()
    assert estado["maximo"] == 1


def test_aviso_de_arranque_sin_clave_en_produccion(
    settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    produccion = settings.model_copy(update={"app_env": "production"})
    with caplog.at_level(logging.WARNING):
        avisar_configuracion(produccion, [CONFIG_OPENALEX])
    assert "OpenAlex sin API key: presupuesto diario muy limitado" in caplog.text
    caplog.clear()
    con_clave = produccion.model_copy(update={"openalex_api_key": SecretStr(CLAVE)})
    with caplog.at_level(logging.WARNING):
        avisar_configuracion(con_clave, [CONFIG_OPENALEX])
    assert caplog.text == ""


def test_registro_inyecta_la_clave_de_la_configuracion(settings: Settings) -> None:
    con_clave = settings.model_copy(
        update={"openalex_api_key": SecretStr(CLAVE), "fuentes_proveedores": [CONFIG_OPENALEX]}
    )
    (cliente,) = construir_fuentes(con_clave)
    assert isinstance(cliente, OpenAlexFuentesClient)
    assert cliente._cabeceras() == {"Authorization": f"Bearer {CLAVE}"}
    cliente.cerrar()


# Caché por tema normalizado y proveedor
class _Contador(FuentesClient):
    def __init__(self) -> None:
        super().__init__("academico", CategoriaFuente.ACADEMICA_ABIERTA, None)
        self.llamadas = 0
        self.falla = False
        self.vacio = False

    def buscar(self, consulta: str, idioma: str, limite: int) -> list[FuenteCandidata]:
        self.llamadas += 1
        if self.falla:
            raise FuentesNoDisponiblesError(cabeceras={"Retry-After": "3600"})
        if self.vacio:
            return []
        return [
            FuenteCandidata(
                titulo="Fotosíntesis",
                autor="Ana Ruiz",
                sitio="Revista",
                url="https://revista.example.org/fotosintesis",
                extracto="La fotosíntesis convierte luz en energía química.",
                categoria=self.categoria,
                autoridad=4,
                proveedor=self.proveedor,
                idioma="es",
            )
        ]


CONTEXTO = ContextoFuentes(NivelCognitivo.AVANZADO, TipoNivel.UNIVERSIDAD_TECNICA)


def _servicio(client: TestClient, settings: Settings, proveedor: _Contador) -> FuentesService:
    contenedor = contenedor_de(client)
    session = contenedor.fabrica_sesiones()
    cache = CacheBusquedaFuentes(FabricaUnitOfWork(contenedor.fabrica_sesiones), 72)
    return FuentesService([proveedor], FuenteRepository(session), settings, cache)


def test_cache_acierta_por_tema_normalizado_y_no_llama_al_proveedor(
    client: TestClient, settings: Settings
) -> None:
    proveedor = _Contador()
    primera = _servicio(client, settings, proveedor).recopilar("Fotosíntesis", CONTEXTO)
    segunda = _servicio(client, settings, proveedor).recopilar("  fotosintesis  ", CONTEXTO)
    assert proveedor.llamadas == 1
    assert [f.url for f in primera] == [f.url for f in segunda]
    with contenedor_de(client).fabrica_sesiones() as session:
        fila = session.scalars(select(CacheFuentes)).one()
    assert "fotos" not in fila.clave_hash and fila.proveedor == "academico"


def test_cache_falla_con_otro_tema_o_vencida(client: TestClient, settings: Settings) -> None:
    proveedor = _Contador()
    _servicio(client, settings, proveedor).recopilar("fotosíntesis", CONTEXTO)
    _servicio(client, settings, proveedor).recopilar("respiración celular", CONTEXTO)
    assert proveedor.llamadas == 2
    with contenedor_de(client).fabrica_sesiones() as session:
        session.execute(update(CacheFuentes).values(fecha_expiracion=ahora_utc() - timedelta(1)))
        session.commit()
    _servicio(client, settings, proveedor).recopilar("fotosíntesis", CONTEXTO)
    assert proveedor.llamadas == 3


def test_cache_no_guarda_errores_ni_vacios(client: TestClient, settings: Settings) -> None:
    proveedor = _Contador()
    proveedor.falla = True
    _servicio(client, settings, proveedor).recopilar("fotosíntesis", CONTEXTO)
    proveedor.falla, proveedor.vacio = False, True
    _servicio(client, settings, proveedor).recopilar("fotosíntesis", CONTEXTO)
    with contenedor_de(client).fabrica_sesiones() as session:
        assert session.scalars(select(CacheFuentes)).all() == []
    proveedor.vacio = False
    assert _servicio(client, settings, proveedor).recopilar("fotosíntesis", CONTEXTO)
    assert proveedor.llamadas == 3


# Cero fuentes en el diagnóstico
def _llm(client: TestClient) -> FakeClient:
    llm = contenedor_de(client).llm
    assert isinstance(llm, FakeClient)
    return llm


def test_cero_fuentes_por_fallo_del_proveedor_es_503_sin_llamar_al_llm(
    client: TestClient,
) -> None:
    registrar(client)
    proveedor = _Contador()
    proveedor.falla = True
    contenedor_de(client).fuentes[:] = [proveedor]
    llamadas = len(_llm(client).solicitudes)
    respuesta = client.post("/api/v1/diagnostico", json={"tema": "fotosíntesis"})
    assert respuesta.status_code == 503
    assert respuesta.json()["error"]["codigo"] == "FUENTES_NO_DISPONIBLES"
    assert respuesta.headers["Retry-After"] == "3600"
    assert len(_llm(client).solicitudes) == llamadas


def test_cero_fuentes_sin_fallos_es_404_tema_sin_fuentes(client: TestClient) -> None:
    registrar(client)
    proveedor = _Contador()
    proveedor.vacio = True
    contenedor_de(client).fuentes[:] = [proveedor]
    respuesta = client.post("/api/v1/diagnostico", json={"tema": "fotosíntesis"})
    assert respuesta.status_code == 404
    assert respuesta.json()["error"]["codigo"] == "TEMA_SIN_FUENTES"


# Cuestionario inválido: un reintento pidiendo corregir el formato
INVALIDO = json.dumps(
    {
        "tema_academico": True,
        "materia": "Ciencias",
        "preguntas": [
            {
                "enunciado": "TEXTO-GENERADO-PRIVADO ¿qué es?",
                "opciones": {"a": "x", "b": "y", "c": "z"},
                "respuesta_correcta": "a",
            }
        ],
    }
)


def _cuestionarios(client: TestClient) -> list[Any]:
    return [s for s in _llm(client).solicitudes if s.tarea == TareaLLM.CUESTIONARIO]


def test_cuestionario_invalido_registra_campos_y_reintenta_una_vez(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    registrar(client)
    _llm(client).programar(respuesta_texto(INVALIDO))
    with caplog.at_level(logging.WARNING):
        respuesta = client.post("/api/v1/diagnostico", json={"tema": "fotosíntesis"})
    assert respuesta.status_code == 201, respuesta.text
    solicitudes = _cuestionarios(client)
    assert len(solicitudes) == 2
    correccion = solicitudes[1].texto_usuario()
    assert "CORRECCIÓN DE FORMATO" in correccion and "preguntas.0.opciones.d:missing" in correccion
    assert "TEXTO-GENERADO-PRIVADO" not in correccion
    assert "llm_respuesta_invalida operacion=CUESTIONARIO intento=1" in caplog.text
    assert "preguntas.0.opciones.d:missing" in caplog.text
    assert "TEXTO-GENERADO-PRIVADO" not in caplog.text


def test_cuestionario_invalido_dos_veces_es_502(client: TestClient) -> None:
    registrar(client)
    _llm(client).programar(respuesta_texto(INVALIDO), respuesta_texto("no es json"))
    respuesta = client.post("/api/v1/diagnostico", json={"tema": "fotosíntesis"})
    assert respuesta.status_code == 502
    assert respuesta.json()["error"]["codigo"] == "LLM_RESPUESTA_INVALIDA"
    assert len(_cuestionarios(client)) == 2


def test_prompt_de_cuestionario_explica_el_esquema_exacto(client: TestClient) -> None:
    registrar(client)
    client.post("/api/v1/diagnostico", json={"tema": "fotosíntesis"})
    prompt = _cuestionarios(client)[-1].texto_usuario()
    for regla in ("sin claves adicionales", "a, b, c y d", "una sola letra minúscula"):
        assert regla in prompt
