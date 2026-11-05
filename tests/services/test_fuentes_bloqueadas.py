"""Regla: ninguna fuente de datos verificables puede ser editable por cualquiera (§1)."""

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import Response
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.cookies import CookieSesion
from app.exceptions.base import TemaSinFuentesError
from app.fuentes.base import FuenteCandidata, FuentesClient
from app.fuentes.bloqueo import es_dominio_bloqueado
from app.models.enums import AmbitoMensaje, CategoriaFuente, NivelCognitivo, TipoNivel
from app.models.fuente import Fuente
from app.schemas.bloques import BloqueTexto, RespuestaTutor
from app.scripts.cargar_fuentes_curadas import validar_curadas
from app.scripts.depurar_fuentes_bloqueadas import diagnosticar
from app.services.fuentes.fuentes_service import ContextoFuentes, FuentesService
from app.services.fuentes.referencias_service import ReferenciasService
from app.validators.fuentes import validar_citas
from app.validators.respuesta_tutor import RespuestaTutorValidator
from tests.conftest import contenedor_de, registrar

RAIZ = Path(__file__).resolve().parents[2]
WIKIPEDIA = "https://es.wikipedia.org/wiki/Fotos%C3%ADntesis"


class TestEsDominioBloqueado:
    @pytest.mark.parametrize(
        "entrada",
        [
            "es.wikipedia.org",
            "es.m.wikipedia.org",
            "WIKIPEDIA.ORG.",
            "commons.wikimedia.org",  # bloqueado como fuente de texto
            "https://usuario@es.wikipedia.org/",
            "https://ｗｉｋｉｐｅｄｉａ.org/x",  # IDN (ancho completo) normalizado
            "https://es.wikipedia.org:443/wiki/Sol",
            "https://www.reddit.com/r/x",
            "",
            "sin host://",
            "https://[::1",
        ],
    )
    def test_bloqueados_e_invalidos(self, entrada: str) -> None:
        assert es_dominio_bloqueado(entrada)

    @pytest.mark.parametrize(
        "entrada",
        [
            "notwikipedia.org",
            "https://wikipedia.org@otro.com/",
            "https://otro.com/?u=wikipedia.org",
            "wikipedia.org.evil.com",  # no es Wikipedia; lo frena la lista de permitidos
            "https://medlineplus.gov/spanish/diabetes.html",
            "https://box.com",  # no coincide con x.com por subcadena
        ],
    )
    def test_no_coinciden_con_la_regla(self, entrada: str) -> None:
        assert not es_dominio_bloqueado(entrada)

    def test_ampliacion_por_configuracion_y_punycode(self) -> None:
        assert es_dominio_bloqueado("https://Foro-Ñandú.co/x", ["foro-ñandú.co"])
        punycode = "foro-ñandú.co".encode("idna").decode("ascii")
        assert punycode.startswith("xn--")
        assert es_dominio_bloqueado(f"https://{punycode}/x", ["foro-ñandú.co"])
        assert es_dominio_bloqueado("https://foro-ñandú.co/x", [punycode])
        assert es_dominio_bloqueado("https://sub.ejemplo.org", ["EJEMPLO.ORG."])


def _candidata(url: str, autoridad: int, categoria: CategoriaFuente) -> FuenteCandidata:
    return FuenteCandidata(
        titulo=f"Fuente {uuid.uuid4().hex[:6]}",
        autor="Autor",
        sitio="Sitio",
        url=url,
        extracto="Texto sobre fotosíntesis",
        categoria=categoria,
        autoridad=autoridad,
        proveedor="p",
        idioma="es",
    )


class _Proveedor(FuentesClient):
    def __init__(self, categoria: CategoriaFuente, candidatas: list[FuenteCandidata]) -> None:
        super().__init__(f"p-{categoria.value.lower()}", categoria, None)
        self._candidatas = candidatas
        self.vacio = False

    def buscar(self, consulta: str, idioma: str, limite: int) -> list[FuenteCandidata]:
        return [] if self.vacio else self._candidatas


def _fuente(
    url: str, autoridad: int = 4, categoria: CategoriaFuente = CategoriaFuente.CURADA
) -> Fuente:
    ahora = datetime.now(UTC)
    return Fuente(
        id_fuente=uuid.uuid4(),
        titulo="Fotosíntesis",
        autor=None,
        sitio="Sitio",
        url=url,
        url_hash=uuid.uuid4().hex,
        fecha_publicacion=None,
        fecha_consulta=ahora,
        licencia=None,
        extracto="Texto",
        categoria=categoria,
        autoridad=autoridad,
        proveedor="p",
        doi=None,
        revisada_por_pares=None,
        idioma="es",
        fecha_expiracion=ahora + timedelta(days=30),
    )


class _RepoFuentes:
    def __init__(self, curadas: list[Fuente] | None = None) -> None:
        self.curadas = curadas or []

    def listar_por_url_hashes(self, _: Any) -> list[Fuente]:
        return []

    def buscar_curadas(self, *_: Any) -> list[Fuente]:
        return self.curadas


AVANZADO = ContextoFuentes(NivelCognitivo.AVANZADO, TipoNivel.UNIVERSIDAD_TECNICA)
WIKI = _candidata(WIKIPEDIA, 3, CategoriaFuente.REFERENCIA)
AUTORIDAD_UNO = _candidata(
    "https://repositorio.example.org/a", 1, CategoriaFuente.ACADEMICA_ABIERTA
)
VALIDA = _candidata("https://revista.example.org/b", 4, CategoriaFuente.ACADEMICA_ABIERTA)


def _servicio(
    settings: Settings, proveedores: list[FuentesClient], repo: _RepoFuentes | None = None
) -> FuentesService:
    return FuentesService(proveedores, repo or _RepoFuentes(), settings)  # type: ignore[arg-type]


class TestFuentesService:
    def test_solo_llega_la_valida(self, settings: Settings, caplog: Any) -> None:
        proveedores: list[FuentesClient] = [
            _Proveedor(CategoriaFuente.REFERENCIA, [WIKI]),
            _Proveedor(CategoriaFuente.ACADEMICA_ABIERTA, [AUTORIDAD_UNO, VALIDA]),
        ]
        fuentes = _servicio(settings, proveedores).recopilar("fotosintesis", AVANZADO)
        assert [f.url for f in fuentes] == [VALIDA.url]
        avisos = [r.getMessage() for r in caplog.records]
        assert any("fuente_bloqueada_descartada proveedor=p" in a for a in avisos)
        assert not any("wikipedia" in a for a in avisos)

    def test_sin_validas_no_hay_fuentes_suficientes(self, settings: Settings) -> None:
        proveedores: list[FuentesClient] = [
            _Proveedor(CategoriaFuente.REFERENCIA, [WIKI]),
            _Proveedor(CategoriaFuente.ACADEMICA_ABIERTA, [AUTORIDAD_UNO]),
        ]
        with pytest.raises(TemaSinFuentesError):
            _servicio(settings, proveedores).recopilar_suficientes("fotosintesis", AVANZADO)

    def test_fila_antigua_bloqueada_no_se_entrega(self, settings: Settings) -> None:
        antigua, buena = _fuente(WIKIPEDIA), _fuente("https://medlineplus.gov/spanish/a.html")
        servicio = _servicio(settings, [], _RepoFuentes(curadas=[antigua, buena]))
        assert servicio.recopilar("fotosintesis", AVANZADO) == [buena]
        assert [c.id_fuente for c in servicio.a_contexto([antigua, buena])] == [buena.id_fuente]
        assert servicio.permitidas([antigua, _fuente("https://x.org/b", autoridad=1)]) == []

    @pytest.mark.parametrize(("respalda_sola", "suficiente"), [(False, False), (True, True)])
    def test_prensa_y_autoridad_minima(
        self, settings: Settings, respalda_sola: bool, suficiente: bool
    ) -> None:
        configurado = settings.model_copy(
            update={"prensa_respalda_sola": respalda_sola, "autoridad_minima_avanzado": 2}
        )
        prensa = _candidata("https://diario.example.co/nota", 2, CategoriaFuente.PRENSA_CONFIABLE)
        servicio = _servicio(configurado, [_Proveedor(CategoriaFuente.PRENSA_CONFIABLE, [prensa])])
        if suficiente:
            assert servicio.recopilar_suficientes("elecciones", AVANZADO)
        else:
            with pytest.raises(TemaSinFuentesError):
                servicio.recopilar_suficientes("elecciones", AVANZADO)


def test_api_solo_fuentes_bloqueadas_no_llama_al_llm(client: TestClient) -> None:
    registrar(client)
    contenedor = contenedor_de(client)
    contenedor.fuentes[:] = [
        _Proveedor(CategoriaFuente.REFERENCIA, [WIKI]),
        _Proveedor(CategoriaFuente.ACADEMICA_ABIERTA, [AUTORIDAD_UNO]),
    ]
    llm = contenedor.llm
    llamadas = len(llm.solicitudes)  # type: ignore[attr-defined]
    respuesta = client.post("/api/v1/diagnostico", json={"tema": "fotosintesis"})
    assert respuesta.status_code == 404
    assert respuesta.json()["error"]["codigo"] == "TEMA_SIN_FUENTES"
    assert len(llm.solicitudes) == llamadas  # type: ignore[attr-defined]


class TestFuentesCuradas:
    def _fila(self, url: str) -> dict[str, Any]:
        return {"titulo": "T", "sitio": "S", "url": url, "extracto": "E", "autoridad": 3}

    def test_rechaza_dominio_bloqueado_listando_filas(self) -> None:
        datos = [
            self._fila("https://medlineplus.gov/spanish/a.html"),
            self._fila("https://es.wikipedia.org/wiki/A"),
            self._fila("https://foro.example.org/b"),
        ]
        with pytest.raises(ValueError, match=r"filas: 2 \(es\.wikipedia\.org\), 3"):
            validar_curadas(datos, ["foro.example.org"])

    def test_rechaza_autoridad_uno(self) -> None:
        with pytest.raises(ValueError):
            validar_curadas([{**self._fila("https://x.org/a"), "autoridad": 1}])

    def test_el_ejemplo_del_repositorio_es_valido(self) -> None:
        ruta = RAIZ / "data" / "fuentes_curadas.ejemplo.json"
        curadas = validar_curadas(json.loads(ruta.read_text(encoding="utf-8")))
        assert 3 <= len(curadas) <= 5


class TestCitasYReferencias:
    def test_id_bloqueado_invalida_la_respuesta(self, settings: Settings) -> None:
        bloqueada, buena = _fuente(WIKIPEDIA), _fuente("https://medlineplus.gov/spanish/a.html")
        autoridades = _servicio(settings, []).autoridades([bloqueada, buena])
        bloque = BloqueTexto(
            tipo="texto", contenido="Dato", afirma_hechos=True, fuentes=[bloqueada.id_fuente]
        )
        assert validar_citas([bloque], autoridades)
        bueno = bloque.model_copy(update={"fuentes": [buena.id_fuente]})
        assert validar_citas([bueno], autoridades) == []

    def test_fuente_bloqueada_no_aparece_en_las_referencias(self) -> None:
        usuario, conversacion = uuid.uuid4(), uuid.uuid4()
        bloqueada, buena = _fuente(WIKIPEDIA), _fuente("https://medlineplus.gov/spanish/a.html")
        vacio = SimpleNamespace(
            listar_por_conversacion=lambda _: [],
            listar_por_mensajes=lambda _: [],
            listar_por_ids=lambda _: [],
            obtener_por_ids=lambda _: [],
        )
        servicio = ReferenciasService(
            SimpleNamespace(  # type: ignore[arg-type]
                obtener_por_id=lambda _: SimpleNamespace(
                    id_usuario=usuario, id_conversacion=conversacion, id_plan=None
                )
            ),
            vacio,  # type: ignore[arg-type]
            SimpleNamespace(listar_por_conversacion=lambda _: [bloqueada, buena]),  # type: ignore[arg-type]
            vacio,  # type: ignore[arg-type]
            vacio,  # type: ignore[arg-type]
            vacio,  # type: ignore[arg-type]
        )
        referencias = servicio.de_conversacion(usuario, conversacion)
        assert [r.id_fuente for r in referencias] == [buena.id_fuente]
        assert not any("wikipedia" in (r.url or "") for r in referencias)


def _respuesta(texto: str) -> RespuestaTutor:
    return RespuestaTutor(
        ambito=AmbitoMensaje.ACADEMICO, bloques=[BloqueTexto(tipo="texto", contenido=texto)]
    )


class TestValidadorDeSalida:
    @pytest.mark.parametrize(
        "texto",
        [
            "Según Wikipedia, la fotosíntesis ocurre en los cloroplastos.",
            "De acuerdo con la Wikipedia en español, eso es así.",
            "Wikipedia dice que el Sol es una estrella.",
            "Puedes leerlo en es.wikipedia.org/wiki/Sol",
            "Lo explican en reddit.com",
        ],
    )
    def test_rechaza_atribucion_y_url_bloqueada(self, texto: str) -> None:
        motivos = RespuestaTutorValidator().validar(_respuesta(texto), {}, set()).motivos
        assert any("Wikipedia" in m or "cualquiera puede editar" in m for m in motivos)

    @pytest.mark.parametrize(
        "texto",
        [
            "No uso Wikipedia porque cualquiera puede editarla.",
            "Lo que viste en Wikipedia puede tener errores; revisemos con las fuentes disponibles.",
        ],
    )
    def test_acepta_mencion_neutra(self, texto: str) -> None:
        assert RespuestaTutorValidator().validar(_respuesta(texto), {}, set()).valido

    def test_bloqueo_ampliado_en_el_validador(self) -> None:
        validador = RespuestaTutorValidator(["foro.example.org"])
        assert not validador.validar(_respuesta("Míralo en foro.example.org"), {}, set()).valido


class TestDepuracion:
    def test_diagnostico_separa_referenciadas(self) -> None:
        bloqueada_usada, bloqueada_libre, buena = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        repo = SimpleNamespace(
            listar_id_y_url=lambda: [
                (bloqueada_usada, WIKIPEDIA),
                (bloqueada_libre, "https://brainly.lat/tarea/1"),
                (buena, "https://medlineplus.gov/spanish/a.html"),
            ],
            ids_en_mensajes=lambda ids: {bloqueada_usada} & set(ids),
            ids_en_planes=lambda ids: set(),
            ids_en_diagnosticos=lambda ids: {bloqueada_usada} & set(ids),
        )
        diagnostico = diagnosticar(repo, [])  # type: ignore[arg-type]
        assert set(diagnostico.bloqueadas) == {bloqueada_usada, bloqueada_libre}
        assert diagnostico.no_referenciadas == [bloqueada_libre]
        assert sorted(diagnostico.referencias[bloqueada_usada]) == ["diagnósticos", "mensajes"]


class TestCookieSinDominio:
    def _cabeceras(self, settings: Settings) -> tuple[str, str]:
        cookie = CookieSesion(settings)
        emitida, borrada = Response(), Response()
        cookie.emitir(emitida, "token")
        cookie.limpiar(borrada)
        return emitida.headers["set-cookie"], borrada.headers["set-cookie"]

    def test_vacio_no_envia_domain(self, settings: Settings) -> None:
        for cabecera in self._cabeceras(settings.model_copy(update={"cookie_domain": ""})):
            assert "domain=" not in cabecera.lower()
            assert "httponly" in cabecera.lower() and "samesite=lax" in cabecera.lower()

    def test_con_valor_envia_domain_y_secure_en_produccion(self, settings: Settings) -> None:
        configurado = settings.model_copy(
            update={"cookie_domain": ".tutoria.co", "app_env": "production"}
        )
        for cabecera in self._cabeceras(configurado):
            assert "domain=.tutoria.co" in cabecera.lower() and "secure" in cabecera.lower()

    @pytest.mark.parametrize("valor", ["", None])
    def test_configuracion_vacia_es_valida(self, valor: str | None) -> None:
        assert Settings(cookie_domain=valor).cookie_domain == ""

    @pytest.mark.parametrize("valor", ["no es dominio", "https://tutoria.co", "localhost"])
    def test_configuracion_invalida(self, valor: str) -> None:
        with pytest.raises(ValueError, match="COOKIE_DOMAIN"):
            Settings(cookie_domain=valor)
