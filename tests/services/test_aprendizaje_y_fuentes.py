import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.config import Settings, TarifaModelo
from app.core.unit_of_work import FabricaUnitOfWork
from app.exceptions.base import FuentesNoDisponiblesError, TemaSinFuentesError
from app.fuentes.base import FuenteCandidata, FuentesClient
from app.fuentes.fake_client import FakeFuentesClient
from app.llm.base import LLMRespuesta
from app.models.enums import (
    CategoriaFuente,
    FormatoExplicacion,
    GrupoEdad,
    IntencionMensaje,
    NivelCognitivo,
    TipoEvento,
    TipoNivel,
)
from app.schemas.perfil_aprendizaje import PreferenciasAprendizaje, TemaPerfil
from app.services.aprendizaje.actualizador_preferencias import ActualizadorPreferencias
from app.services.aprendizaje.perfil_aprendizaje_service import etiqueta_formato
from app.services.aprendizaje.senales_extractor import SenalesExtractor
from app.services.consumo_service import ConsumoService, UsoTokens, _costo_tokens
from app.services.estudiante import PerfilEstudiante
from app.services.fuentes import formato_apa
from app.services.fuentes.fuentes_service import ContextoFuentes, FuentesService
from app.services.tutor.contexto_estudiante_builder import ContextoEstudianteBuilder, DatosContexto
from app.validators.perfil import fusionar_tema

extractor = SenalesExtractor()


class TestSenales:
    @pytest.mark.parametrize(
        ("frase", "evento"),
        [
            ("¿Me das un ejemplo?", TipoEvento.PIDE_EJEMPLO),
            ("me das un ejemplo", TipoEvento.PIDE_EJEMPLO),
            ("Muéstrame una imagen", TipoEvento.PIDE_VISUAL),
            ("muestrame un diagrama", TipoEvento.PIDE_VISUAL),
            ("Explícalo paso a paso", TipoEvento.PIDE_PASO_A_PASO),
            ("Hazlo más fácil por favor", TipoEvento.PIDE_SIMPLIFICAR),
            ("mas facil", TipoEvento.PIDE_SIMPLIFICAR),
            ("¿Puedes profundizar más?", TipoEvento.PIDE_MAS_DETALLE),
            ("Resúmelo en pocas palabras", TipoEvento.PIDE_RESUMEN),
            ("No entendí nada", TipoEvento.NO_ENTENDIO),
            ("no entendi", TipoEvento.NO_ENTENDIO),
            ("Sigo sin entender", TipoEvento.NO_ENTENDIO),
            ("¿cuál es la respuesta del punto 2?", TipoEvento.PIDE_RESPUESTA_DIRECTA),
        ],
    )
    def test_frases_reales_con_y_sin_tildes(self, frase: str, evento: TipoEvento) -> None:
        assert evento in extractor.extraer(frase, None).eventos

    def test_repregunta_y_estilo(self) -> None:
        senales = extractor.extraer(
            "¿Qué es una derivada en cálculo?", "que es una derivada en calculo"
        )
        assert TipoEvento.REPREGUNTA in senales.eventos and senales.usa_vocabulario_tecnico
        assert senales.longitud_palabras == 6 and senales.intencion == IntencionMensaje.CONSULTA
        assert extractor.extraer("hola", "adiós").repite_pregunta is False


class TestActualizador:
    actualizador = ActualizadorPreferencias(alpha=0.2, observaciones_confianza=10)

    def test_converge_y_confianza_con_tope(self) -> None:
        preferencias = PreferenciasAprendizaje()
        pide = extractor.extraer("dame un ejemplo", None)
        for _ in range(30):
            preferencias = self.actualizador.aplicar_senales(preferencias, pide, [])
        ejemplo = preferencias.formatos.de(FormatoExplicacion.EJEMPLO)
        assert ejemplo.puntaje > 0.99 and ejemplo.confianza == 1.0 and ejemplo.observaciones == 30
        assert preferencias.formatos.de(FormatoExplicacion.VISUAL).puntaje == 0.5

    def test_no_entendi_penaliza_formatos_previos_y_detalle(self) -> None:
        preferencias = self.actualizador.aplicar_senales(
            PreferenciasAprendizaje(),
            extractor.extraer("no entendí, más fácil", None),
            [FormatoExplicacion.FORMAL],
        )
        assert preferencias.formatos.de(FormatoExplicacion.FORMAL).puntaje == pytest.approx(0.4)
        assert preferencias.detalle.value == "BREVE"

    def test_feedback(self) -> None:
        preferencias = self.actualizador.aplicar_feedback(
            PreferenciasAprendizaje(), False, [FormatoExplicacion.ANALOGIA]
        )
        assert preferencias.formatos.de(FormatoExplicacion.ANALOGIA).puntaje == pytest.approx(0.4)

    def test_topes_del_perfil(self) -> None:
        ahora = datetime.now(UTC)
        preferencias = PreferenciasAprendizaje()
        for i in range(35):
            preferencias = fusionar_tema(
                preferencias, f"tema {i}", ["d" * 200], [], ahora.replace(microsecond=i)
            )
        assert len(preferencias.temas) == 30
        assert all(len(t.dificultades[0]) <= 120 for t in preferencias.temas.values())
        with pytest.raises(ValueError):
            PreferenciasAprendizaje.model_validate({"salud": "x"})

    def test_etiquetas_legibles(self) -> None:
        assert (
            etiqueta_formato(FormatoExplicacion.EJEMPLO, 0.8, 0.9)
            == "Suele entender mejor con ejemplos"
        )
        assert "suficiente evidencia" in etiqueta_formato(FormatoExplicacion.VISUAL, 0.9, 0.1)
        assert "servido menos" in etiqueta_formato(FormatoExplicacion.FORMAL, 0.2, 0.9)


def _datos(preferencias: PreferenciasAprendizaje | None, turno: int) -> DatosContexto:
    conversacion = SimpleNamespace(
        tema="Fotosíntesis de plantas", nivel_cognitivo=NivelCognitivo.INTERMEDIO, resumen=None
    )
    estudiante = PerfilEstudiante(TipoNivel.COLEGIO, "9", GrupoEdad.ADOLESCENTE_TEMPRANO, True)
    return DatosContexto(conversacion, estudiante, preferencias, None, None, None, turno, False)  # type: ignore[arg-type]


class TestContexto:
    builder = ContextoEstudianteBuilder(exploracion_cada=4)

    def test_sin_perfil_si_desactivado(self) -> None:
        contexto = self.builder.construir(_datos(None, 1))
        assert contexto.perfil_estudiante is None and "INTERMEDIO" in contexto.politica_nivel
        assert "13 a 14" in contexto.grupo_edad

    def test_preferidos_temas_y_exploracion(self) -> None:
        preferencias = PreferenciasAprendizaje()
        preferencias.formatos.ejemplo.puntaje, preferencias.formatos.ejemplo.confianza = 0.8, 0.7
        preferencias.temas["fotosintesis de plantas"] = TemaPerfil(
            dificultades=["clorofila"], ultima_vez=datetime.now(UTC)
        )
        preferencias.temas["historia"] = TemaPerfil(
            fortalezas=["fechas"], ultima_vez=datetime.now(UTC)
        )
        normal = self.builder.construir(_datos(preferencias, 3)).perfil_estudiante or ""
        explora = self.builder.construir(_datos(preferencias, 4)).perfil_estudiante or ""
        assert "ejemplo" in normal and "clorofila" in normal and "historia" not in normal
        assert (
            "Prueba un formato distinto" in explora and "Prueba un formato distinto" not in normal
        )


class _Proveedor(FuentesClient):
    def __init__(
        self,
        categoria: CategoriaFuente,
        candidatas: list[FuenteCandidata] | None = None,
        falla: bool = False,
    ) -> None:
        super().__init__(f"p-{uuid.uuid4().hex[:4]}", categoria, None)
        self._candidatas = candidatas or []
        self._falla = falla

    def buscar(self, consulta: str, idioma: str, limite: int) -> list[FuenteCandidata]:
        if self._falla:
            raise FuentesNoDisponiblesError()
        return self._candidatas


def _candidata(
    titulo: str, autoridad: int, categoria: CategoriaFuente, **extra: Any
) -> FuenteCandidata:
    datos: dict[str, Any] = {
        "titulo": titulo,
        "autor": "Autor",
        "sitio": "Sitio",
        "url": f"https://x.org/{uuid.uuid4().hex}",
        "extracto": f"Texto sobre {titulo}",
        "categoria": categoria,
        "autoridad": autoridad,
        "proveedor": "p",
        "idioma": "es",
    }
    datos.update(extra)
    return FuenteCandidata(**datos)


class _RepoFuentes:
    def listar_por_url_hashes(self, _: Any) -> list[Any]:
        return []

    def buscar_curadas(self, *_: Any) -> list[Any]:
        return []


class TestFuentesService:
    contexto = ContextoFuentes(NivelCognitivo.AVANZADO, TipoNivel.UNIVERSIDAD_TECNICA)

    def _servicio(self, settings: Settings, proveedores: list[FuentesClient]) -> FuentesService:
        return FuentesService(proveedores, _RepoFuentes(), settings)  # type: ignore[arg-type]

    def test_proveedor_caido_no_rompe_y_ordena_por_autoridad(self, settings: Settings) -> None:
        proveedores: list[FuentesClient] = [
            _Proveedor(
                CategoriaFuente.REFERENCIA,
                [_candidata("enciclopedia", 1, CategoriaFuente.REFERENCIA)],
            ),
            _Proveedor(
                CategoriaFuente.ACADEMICA_ABIERTA,
                [_candidata("articulo", 4, CategoriaFuente.ACADEMICA_ABIERTA)],
            ),
            _Proveedor(CategoriaFuente.INSTITUCIONAL_OFICIAL, falla=True),
        ]
        fuentes = self._servicio(settings, proveedores).recopilar("articulo", self.contexto)
        assert [f.autoridad for f in fuentes] == [4, 1]

    def test_deduplica_por_doi_url_y_titulo(self, settings: Settings) -> None:
        url = "https://x.org/mismo"
        candidatas = [
            _candidata("A", 4, CategoriaFuente.ACADEMICA_ABIERTA, doi="10.1/X"),
            _candidata("B", 3, CategoriaFuente.ACADEMICA_ABIERTA, doi="10.1/x"),
            _candidata("C", 3, CategoriaFuente.ACADEMICA_ABIERTA, url=url),
            _candidata("D", 3, CategoriaFuente.ACADEMICA_ABIERTA, url=url),
            _candidata("A", 2, CategoriaFuente.ACADEMICA_ABIERTA),
            _candidata("E", 3, CategoriaFuente.ACADEMICA_ABIERTA, url="http://inseguro.org/x"),
            _candidata("F", 3, CategoriaFuente.ACADEMICA_ABIERTA, idioma="ru"),
        ]
        fuentes = self._servicio(
            settings, [_Proveedor(CategoriaFuente.ACADEMICA_ABIERTA, candidatas)]
        ).recopilar("x", self.contexto)
        assert sorted(f.titulo for f in fuentes) == ["A", "C"]

    def test_autoridad_minima_por_nivel(self, settings: Settings) -> None:
        solo_colaborativa = [
            _Proveedor(
                CategoriaFuente.REFERENCIA, [_candidata("wiki", 1, CategoriaFuente.REFERENCIA)]
            )
        ]
        with pytest.raises(TemaSinFuentesError):
            self._servicio(settings, solo_colaborativa).recopilar_suficientes("wiki", self.contexto)

    def test_categorias_escolares(self, settings: Settings) -> None:
        academica = FakeFuentesClient("a", CategoriaFuente.ACADEMICA_ABIERTA)
        educativa = FakeFuentesClient("e", CategoriaFuente.EDUCATIVA_ABIERTA)
        fuentes = self._servicio(settings, [academica, educativa]).recopilar(
            "plantas", ContextoFuentes(NivelCognitivo.BASICO, TipoNivel.COLEGIO)
        )
        assert {f.categoria for f in fuentes} == {CategoriaFuente.EDUCATIVA_ABIERTA}

    def test_respaldo_academico_si_lo_escolar_no_alcanza(self, settings: Settings) -> None:
        academica = FakeFuentesClient("a", CategoriaFuente.ACADEMICA_ABIERTA)
        colaborativa = FakeFuentesClient("w", CategoriaFuente.REFERENCIA)
        fuentes = self._servicio(settings, [academica, colaborativa]).recopilar_suficientes(
            "plantas", ContextoFuentes(NivelCognitivo.BASICO, TipoNivel.COLEGIO)
        )
        assert {f.categoria for f in fuentes} == {
            CategoriaFuente.ACADEMICA_ABIERTA,
            CategoriaFuente.REFERENCIA,
        }


class TestApaYCostos:
    def test_referencias_apa(self) -> None:
        consulta = datetime(2026, 10, 18, tzinfo=UTC)
        con_autor = formato_apa.referencia_texto(
            "Título",
            "Pérez, A.",
            date(2020, 1, 1),
            "Revista",
            "https://x.org",
            "10.1/abc",
            consulta,
        )
        assert con_autor == "Pérez, A. (2020). Título. Revista. https://doi.org/10.1/abc"
        sin_autor = formato_apa.referencia_texto(
            "Fotosíntesis", None, None, "Wikipedia", "https://w.org/f", None, consulta
        )
        assert (
            sin_autor.startswith("Fotosíntesis. (s. f.).")
            and "Recuperado el 18 de octubre de 2026" in sin_autor
        )
        assert "[Imagen]" in formato_apa.referencia_imagen(
            "Célula", "Ana", "Commons", "https://c.org", "CC BY 4.0"
        )
        assert "[Video]. YouTube." in formato_apa.referencia_video("Clase", "Canal", "https://y.t")
        assert "generada por IA con modelo" in formato_apa.referencia_ilustracion_ia(
            "modelo", consulta
        )

    def test_costo_por_tarifa_y_estimacion(self, settings: Settings) -> None:
        tarifa = TarifaModelo(entrada=2.0, salida=10.0, cache_lectura=0.2, cache_escritura=2.5)
        assert _costo_tokens(UsoTokens(1_000_000, 100_000, 0, 0), tarifa) == Decimal("3.000000")
        configurado = settings.model_copy(update={"tarifas_ia": {"m": tarifa}})
        servicio = ConsumoService(FabricaUnitOfWork(None), configurado)  # type: ignore[arg-type]
        assert servicio._costo("m", UsoTokens(1000, 0), 0) == (Decimal("0.002000"), False)
        assert servicio._costo("otro", UsoTokens(), 1)[1] is True
        respuesta = LLMRespuesta((), "end_turn", "m", 1, 1)
        assert respuesta.texto() == ""
