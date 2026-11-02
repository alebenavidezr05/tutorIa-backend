import io
import json
from collections.abc import Callable
from typing import Any

import boto3
import httpx
import pytest
from moto import mock_aws
from PIL import Image

from app.almacen.local_almacen import LocalAlmacen
from app.almacen.s3_almacen import S3Almacen
from app.core.config import ConfigProveedor, Settings
from app.correo.base import Correo
from app.correo.ses_correo_client import SesCorreoClient
from app.crypto.kms_cifrador import KmsCifrador
from app.exceptions.base import (
    AlmacenamientoError,
    FuentesNoDisponiblesError,
    ImagenesNoDisponiblesError,
)
from app.fuentes.adaptadores.ckan import CkanFuentesClient
from app.fuentes.adaptadores.medlineplus import MedlinePlusFuentesClient
from app.fuentes.adaptadores.rest_json import OpenAlexFuentesClient
from app.fuentes.registro import construir_fuentes
from app.imagenes.adaptadores.commons import CommonsImagenesClient
from app.imagenes.adaptadores.iiif_museo import IiifMuseoImagenesClient
from app.imagenes.descarga_segura import DescargadorSeguro
from app.imagenes.licencias import licencia_permitida, normalizar_licencia
from app.imagenes.procesador import ProcesadorPillow
from app.imagenes.registro import construir_imagenes
from app.videos.youtube_client import YouTubeClient, duracion_iso_a_segundos


def _http(manejador: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(manejador))


def _json(datos: Any) -> Callable[[httpx.Request], httpx.Response]:
    return lambda _: httpx.Response(200, json=datos)


def _config(adaptador: str, categoria: str, **extra: Any) -> ConfigProveedor:
    return ConfigProveedor(
        id=f"p-{adaptador}",
        categoria=categoria,
        adaptador=adaptador,
        base_url="https://api.example.org/x",
        **extra,
    )


class TestFuentes:
    def test_openalex_reconstruye_resumen_doi_y_autoridad(self) -> None:
        datos = {
            "results": [
                {
                    "title": "Fotosíntesis en plantas",
                    "doi": "https://doi.org/10.1234/abc",
                    "type": "article",
                    "language": "es",
                    "publication_date": "2023-04-01",
                    "authorships": [{"author": {"display_name": f"Autor {i}"}} for i in range(4)],
                    "primary_location": {
                        "landing_page_url": "https://revista.example.org/a",
                        "source": {"display_name": "Revista", "is_in_doaj": True},
                    },
                    "best_oa_location": {"license": "cc-by"},
                    "abstract_inverted_index": {"La": [0], "luz": [1], "importa": [2]},
                },
                {
                    "title": "Preprint",
                    "type": "preprint",
                    "primary_location": {"landing_page_url": "https://x.org/p"},
                    "abstract_inverted_index": {"Hola": [0]},
                },
                {
                    "title": "Sin resumen",
                    "primary_location": {"landing_page_url": "https://x.org/s"},
                },
            ]
        }
        cliente = OpenAlexFuentesClient(
            _config("openalex", "ACADEMICA_ABIERTA"), _http(_json(datos))
        )
        fuentes = cliente.buscar("fotosintesis", "es", 5)
        assert len(fuentes) == 2
        primera, preprint = fuentes
        assert primera.extracto == "La luz importa" and primera.doi == "10.1234/abc"
        assert (
            primera.autoridad == 4
            and primera.revisada_por_pares
            and primera.autor.endswith("et al.")
        )  # type: ignore[union-attr]
        assert preprint.autoridad == 2 and preprint.revisada_por_pares is False

    def test_medlineplus_xml_y_ckan(self) -> None:
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?><nlmSearchResult><list num="2">'
            '<document rank="0" url="https://medlineplus.gov/spanish/diabetes.html">'
            '<content name="title">&lt;span class="qt0"&gt;Diabetes&lt;/span&gt;</content>'
            '<content name="organizationName">Biblioteca Nacional de Medicina</content>'
            '<content name="FullSummary">¿Qué es la &lt;span class="qt0"&gt;diabetes'
            "&lt;/span&gt;?&lt;p&gt;Una enfermedad.</content></document>"
            '<document rank="1" url="http://medlineplus.gov/sin-tls.html">'
            '<content name="title">X</content><content name="snippet">Y</content></document>'
            "</list></nlmSearchResult>"
        )
        peticiones: list[httpx.Request] = []

        def manejador(peticion: httpx.Request) -> httpx.Response:
            peticiones.append(peticion)
            return httpx.Response(200, content=xml.encode())

        fuentes = MedlinePlusFuentesClient(
            _config("medlineplus", "INSTITUCIONAL_OFICIAL"), _http(manejador)
        ).buscar("diabetes", "es", 3)
        assert peticiones[0].url.params["db"] == "healthTopicsSpanish"
        assert len(fuentes) == 1 and fuentes[0].titulo == "Diabetes"
        assert fuentes[0].autoridad == 4 and fuentes[0].licencia == "Dominio público"
        assert "<" not in fuentes[0].extracto and "Una enfermedad" in fuentes[0].extracto
        ckan = {
            "result": {
                "results": [
                    {
                        "title": "Datos",
                        "notes": "Descripción",
                        "name": "datos-1",
                        "organization": {"title": "Ministerio"},
                        "metadata_modified": "2025-01-01T00:00",
                    }
                ]
            }
        }
        institucional = CkanFuentesClient(
            _config(
                "ckan",
                "INSTITUCIONAL_OFICIAL",
                parametros={"url_dataset": "https://datos.example.gov/dataset/"},
            ),
            _http(_json(ckan)),
        ).buscar("x", "es", 3)
        assert institucional[0].autoridad == 4 and institucional[0].url.endswith("datos-1")

    @pytest.mark.parametrize(
        "respuesta",
        [
            httpx.Response(503),
            httpx.Response(200, content=b"<no-cierra>"),
            httpx.Response(200, content=b'<!DOCTYPE x [<!ENTITY a "b">]><x>&a;</x>'),
        ],
    )
    def test_errores_de_red_y_xml_se_traducen(self, respuesta: httpx.Response) -> None:
        cliente = MedlinePlusFuentesClient(
            _config("medlineplus", "INSTITUCIONAL_OFICIAL"), _http(lambda _: respuesta)
        )
        with pytest.raises(FuentesNoDisponiblesError):
            cliente.buscar("x", "es", 3)

    def test_registro_por_configuracion(self, settings: Settings) -> None:
        configs = [
            _config("openalex", "ACADEMICA_ABIERTA"),
            _config("medlineplus", "INSTITUCIONAL_OFICIAL", activo=False),
            _config("medlineplus", "WEB_GENERAL"),
        ]
        clientes = construir_fuentes(settings.model_copy(update={"fuentes_proveedores": configs}))
        assert [c.proveedor for c in clientes] == ["p-openalex"]
        with pytest.raises(ValueError, match="no implementado"):
            construir_fuentes(
                settings.model_copy(
                    update={"fuentes_proveedores": [_config("oai_pmh", "ACADEMICA_ABIERTA")]}
                )
            )

    @pytest.mark.parametrize(
        "proveedor",
        [
            ConfigProveedor(
                id="enciclopedia",
                categoria="REFERENCIA",
                adaptador="ckan",
                base_url="https://es.wikipedia.org/w/api.php",
            ),
            # Inactivo y por la lista de dominios: tampoco se admite.
            ConfigProveedor(
                id="libros",
                categoria="EDUCATIVA_ABIERTA",
                adaptador="ckan",
                activo=False,
                base_url="https://api.example.org/x",
                dominios=["es.wikibooks.org"],
            ),
        ],
    )
    def test_proveedor_de_texto_bloqueado_impide_arrancar(
        self, settings: Settings, proveedor: ConfigProveedor
    ) -> None:
        configurado = settings.model_copy(update={"fuentes_proveedores": [proveedor]})
        with pytest.raises(ValueError, match="dominios bloqueados"):
            construir_fuentes(configurado)

    def test_bloqueo_ampliado_por_configuracion(self, settings: Settings) -> None:
        configurado = settings.model_copy(
            update={
                "fuentes_proveedores": [_config("openalex", "ACADEMICA_ABIERTA")],
                "fuentes_dominios_bloqueados": ["example.org"],
            }
        )
        with pytest.raises(ValueError, match="p-openalex"):
            construir_fuentes(configurado)

    def test_commons_sigue_arrancando_para_imagenes(self, settings: Settings) -> None:
        commons = ConfigProveedor(
            id="wikimedia_commons",
            categoria="REPOSITORIO_COLABORATIVO",
            adaptador="mediawiki_commons",
            base_url="https://commons.wikimedia.org/w/api.php",
            dominios=["upload.wikimedia.org"],
        )
        imagenes = construir_imagenes(
            settings.model_copy(update={"imagenes_proveedores": [commons]})
        )
        assert [i.proveedor for i in imagenes] == ["wikimedia_commons"]
        for cliente in imagenes:
            cliente.cerrar()


class TestImagenes:
    def test_commons_extrae_atribucion(self) -> None:
        datos = {
            "query": {
                "pages": [
                    {
                        "index": 1,
                        "title": "File:Celula.svg",
                        "imageinfo": [
                            {
                                "thumburl": "https://upload.wikimedia.org/thumb/c.svg.png",
                                "thumbwidth": 800,
                                "thumbheight": 600,
                                "mime": "image/svg+xml",
                                "descriptionurl": "https://commons.wikimedia.org/wiki/File:Celula.svg",
                                "extmetadata": {
                                    "Artist": {"value": "<a href='x'>Ana</a>"},
                                    "LicenseShortName": {"value": "CC BY-SA 4.0"},
                                    "LicenseUrl": {
                                        "value": "https://creativecommons.org/licenses/by-sa/4.0"
                                    },
                                    "ImageDescription": {"value": "Una <b>célula</b>"},
                                },
                            }
                        ],
                    }
                ]
            }
        }
        imagen = CommonsImagenesClient(
            _config(
                "mediawiki_commons", "REPOSITORIO_COLABORATIVO", dominios=["upload.wikimedia.org"]
            ),
            _http(_json(datos)),
        ).buscar("célula", 3)[0]
        assert (
            imagen.autor == "Ana"
            and imagen.descripcion == "Una célula"
            and imagen.titulo == "Celula.svg"
        )
        assert imagen.url_archivo.endswith(".png") and imagen.ancho == 800

    def test_museo_solo_dominio_publico(self) -> None:
        datos = {
            "config": {
                "iiif_url": "https://www.artic.edu/iiif/2",
                "website_url": "https://www.artic.edu",
            },
            "data": [
                {
                    "id": 1,
                    "title": "Volcán",
                    "artist_display": "Pintor\nFrancia",
                    "is_public_domain": True,
                    "image_id": "abc",
                    "thumbnail": {"width": 1000, "height": 500},
                },
                {"id": 2, "title": "Moderna", "is_public_domain": False, "image_id": "def"},
            ],
        }
        imagenes = IiifMuseoImagenesClient(
            _config("iiif_museo", "PATRIMONIO_ABIERTO"), _http(_json(datos))
        ).buscar("volcán", 5)
        assert (
            len(imagenes) == 1
            and imagenes[0].autor == "Pintor"
            and "abc/full/843," in imagenes[0].url_archivo
        )

    @pytest.mark.parametrize(
        ("licencia", "permitida"),
        [
            ("CC BY-NC 4.0", False),
            ("CC BY-ND 2.0", False),
            ("GFDL", False),
            ("Public domain", True),
            ("CC0", True),
            ("CC BY 3.0", True),
        ],
    )
    def test_licencias(self, licencia: str, permitida: bool) -> None:
        assert (
            licencia_permitida(normalizar_licencia(licencia), ["PD", "CC0", "CC-BY", "CC-BY-SA"])
            is permitida
        )


def _jpeg_con_exif(ancho: int = 900) -> bytes:
    imagen = Image.new("RGB", (ancho, 500), (200, 10, 10))
    exif = imagen.getexif()
    exif[0x010F] = "Camara privada"
    salida = io.BytesIO()
    imagen.save(salida, "JPEG", exif=exif)
    return salida.getvalue()


def _descargador(
    settings: Settings,
    manejador: Callable[[httpx.Request], httpx.Response],
    ip: str = "93.184.216.34",
) -> DescargadorSeguro:
    cliente = httpx.Client(transport=httpx.MockTransport(manejador), follow_redirects=False)
    return DescargadorSeguro(settings, ProcesadorPillow(), cliente=cliente, resolver=lambda _: [ip])


DOMINIOS = ["upload.wikimedia.org"]
URL = "https://upload.wikimedia.org/a.jpg"


class TestDescargaSegura:
    def test_descarga_recodifica_y_quita_exif(self, settings: Settings) -> None:
        imagen = _descargador(
            settings, lambda _: httpx.Response(200, content=_jpeg_con_exif())
        ).descargar(URL, DOMINIOS)
        assert imagen.mime == "image/webp" and imagen.ancho <= settings.imagenes_lado_maximo
        assert not Image.open(io.BytesIO(imagen.contenido)).getexif()

    @pytest.mark.parametrize(
        ("url", "ip"),
        [
            ("http://upload.wikimedia.org/a.jpg", "93.184.216.34"),
            ("https://malicioso.example/a.jpg", "93.184.216.34"),
            ("https://localhost/a.jpg", "127.0.0.1"),
            ("https://169.254.169.254/latest/meta-data/", "169.254.169.254"),
            (URL, "169.254.169.254"),  # metadatos de la instancia EC2
            (URL, "169.254.10.10"),  # 169.254.0.0/16
            (URL, "127.0.0.1"),
            (URL, "127.8.9.10"),  # 127.0.0.0/8
            (URL, "10.0.0.5"),  # 10.0.0.0/8
            (URL, "172.16.0.1"),  # 172.16.0.0/12
            (URL, "172.31.255.254"),
            (URL, "192.168.1.10"),  # 192.168.0.0/16
            (URL, "::1"),
            (URL, "fd12:3456::1"),  # fc00::/7
            (URL, "fe80::1"),  # fe80::/10
            (URL, "::ffff:169.254.169.254"),  # IPv4 mapeada en IPv6
        ],
    )
    def test_rechaza_destinos_peligrosos(self, settings: Settings, url: str, ip: str) -> None:
        with pytest.raises(ImagenesNoDisponiblesError):
            _descargador(
                settings, lambda _: httpx.Response(200, content=_jpeg_con_exif()), ip
            ).descargar(url, DOMINIOS)

    @pytest.mark.parametrize(
        "ip_privada", ["169.254.169.254", "127.0.0.1", "10.1.1.1", "192.168.0.1", "::1"]
    )
    def test_redireccion_que_resuelve_a_ip_privada(
        self, settings: Settings, ip_privada: str
    ) -> None:
        """La resolución se repite en cada salto: un dominio permitido que apunta a una IP
        interna tras una redirección también se rechaza."""
        dominios = ["upload.wikimedia.org", "interno.wikimedia.org"]
        ips = {"upload.wikimedia.org": "93.184.216.34", "interno.wikimedia.org": ip_privada}
        cliente = httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    302, headers={"location": "https://interno.wikimedia.org/a.jpg"}
                )
            ),
            follow_redirects=False,
        )
        descargador = DescargadorSeguro(
            settings, ProcesadorPillow(), cliente=cliente, resolver=lambda h: [ips[h]]
        )
        with pytest.raises(ImagenesNoDisponiblesError, match="no pública"):
            descargador.descargar(URL, dominios)

    def test_rechaza_redireccion_fuera_de_dominio_tamano_y_tipo(self, settings: Settings) -> None:
        redireccion = _descargador(
            settings,
            lambda _: httpx.Response(302, headers={"location": "https://169.254.169.254/latest"}),
        )
        with pytest.raises(ImagenesNoDisponiblesError):
            redireccion.descargar(URL, DOMINIOS)
        grande = settings.model_copy(update={"imagenes_max_bytes": 100})
        with pytest.raises(ImagenesNoDisponiblesError):
            _descargador(grande, lambda _: httpx.Response(200, content=_jpeg_con_exif())).descargar(
                URL, DOMINIOS
            )
        with pytest.raises(ImagenesNoDisponiblesError):
            _descargador(
                settings, lambda _: httpx.Response(200, content=b"<svg></svg>" * 10)
            ).descargar(URL, DOMINIOS)
        with pytest.raises(ImagenesNoDisponiblesError):
            _descargador(
                settings, lambda _: httpx.Response(200, content=_jpeg_con_exif(ancho=100))
            ).descargar(URL, DOMINIOS)

    def test_redireccion_valida_y_tolerancia(self, settings: Settings) -> None:
        def manejador(peticion: httpx.Request) -> httpx.Response:
            if peticion.url.path == "/a.jpg":
                return httpx.Response(301, headers={"location": "/b.jpg"})
            return httpx.Response(200, content=_jpeg_con_exif())

        descargador = _descargador(settings, manejador)
        assert descargador.descargar(URL, DOMINIOS).mime == "image/webp"
        assert descargador.intentar_descargar("https://otro.example/x.jpg", DOMINIOS) is None


class TestYouTube:
    def test_duracion(self) -> None:
        assert (
            duracion_iso_a_segundos("PT1H2M3S") == 3723 and duracion_iso_a_segundos("PT15M") == 900
        )
        assert duracion_iso_a_segundos("raro") == 0

    def test_busqueda_confirma_metadatos(self, settings: Settings) -> None:
        def manejador(peticion: httpx.Request) -> httpx.Response:
            if peticion.url.path.endswith("/search"):
                assert (
                    peticion.url.params["safeSearch"] == "strict"
                    and peticion.url.params["videoDuration"] == "medium"
                )
                return httpx.Response(200, json={"items": [{"id": {"videoId": "abcdefghijk"}}]})
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "abcdefghijk",
                            "snippet": {
                                "title": "T",
                                "channelTitle": "C",
                                "channelId": "UC1",
                                "defaultAudioLanguage": "es",
                            },
                            "contentDetails": {"duration": "PT10M"},
                            "status": {"embeddable": True, "madeForKids": False},
                        }
                    ]
                },
            )

        videos = YouTubeClient(settings, cliente=_http(manejador)).buscar("historia", 3)
        assert (
            videos[0].duracion_segundos == 600
            and videos[0].embeddable
            and not videos[0].es_para_ninos
        )


@mock_aws
class TestAws:
    def test_kms_envuelve_y_desenvuelve_la_dek(self, settings: Settings) -> None:
        kms = boto3.client("kms", region_name="us-east-1")
        llave = kms.create_key()["KeyMetadata"]["KeyId"]
        envuelta = KmsCifrador(settings, cliente_kms=kms).generar_dek_envuelta(llave)
        configurado = settings.model_copy(
            update={
                "cifrado_proveedor": "kms",
                "cifrado_dek_envuelta": __import__("pydantic").SecretStr(envuelta),
            }
        )
        cifrador = KmsCifrador(configurado, cliente_kms=kms).construir()
        assert cifrador.descifrar(cifrador.cifrar("dato", "t.c"), "t.c") == "dato"

    def test_s3_privado_con_sse_kms(self, settings: Settings) -> None:
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="tutoria-pruebas")
        almacen = S3Almacen(
            settings.model_copy(update={"s3_bucket": "tutoria-pruebas"}), cliente=s3
        )
        almacen.guardar("archivos/u/1", b"contenido", "text/plain")
        assert almacen.leer("archivos/u/1") == b"contenido"
        assert (
            s3.head_object(Bucket="tutoria-pruebas", Key="archivos/u/1")["ServerSideEncryption"]
            == "aws:kms"
        )
        almacen.eliminar("archivos/u/1")
        with pytest.raises(AlmacenamientoError):
            almacen.leer("archivos/u/1")

    def test_ses_envia(self, settings: Settings) -> None:
        ses = boto3.client("sesv2", region_name="us-east-1")
        boto3.client("ses", region_name="us-east-1").verify_email_identity(
            EmailAddress=settings.correo_remitente
        )
        SesCorreoClient(settings, cliente=ses).enviar(Correo("a@example.com", "Asunto", "Texto"))


def test_almacen_local_no_escapa_del_directorio(tmp_path: Any) -> None:
    almacen = LocalAlmacen(str(tmp_path))
    almacen.guardar("archivos/x", b"1", "text/plain")
    assert almacen.leer("archivos/x") == b"1"
    with pytest.raises(AlmacenamientoError):
        almacen.guardar("../fuera", b"1", "text/plain")
    assert almacen.eliminar_sin_fallar(["archivos/x", "../fuera"]) == {"../fuera"}


def test_json_de_ejemplo_serializable() -> None:
    assert json.loads(json.dumps({"ok": True}))["ok"]
