import io
import uuid
from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

from app.core.fabrica import FabricaServicios
from app.core.tiempo import ahora_utc
from app.imagenes.fake_client import FakeDescargador, FakeImagenesIAClient, imagen_falsa
from app.llm.fake_client import FakeClient, respuesta_herramienta
from app.llm.herramientas import BUSCAR_VIDEO, RESPONDER
from app.models.consumo_ia import ConsumoIA
from app.models.enums import EstadoTrabajoVisual, EstadoVideo, OperacionIA, ProveedorIA
from app.models.trabajo_visual import TrabajoVisual
from app.models.video_curado import VideoCurado
from app.videos.fake_client import FakeVideosClient
from tests.conftest import (
    contenedor_de,
    crear_diagnostico,
    enviar,
    evaluar,
    iniciar_conversacion,
    registrar,
)


def _llm(cliente: TestClient) -> FakeClient:
    llm = contenedor_de(cliente).llm
    assert isinstance(llm, FakeClient)
    return llm


def _ia(cliente: TestClient) -> FakeImagenesIAClient:
    ia = contenedor_de(cliente).imagenes_ia
    assert isinstance(ia, FakeImagenesIAClient)
    return ia


def _solicitud_visual(**cambios: Any) -> dict[str, Any]:
    datos = {
        "concepto_canonico": f"concepto {uuid.uuid4().hex[:6]}",
        "tipo_preferido": "IMAGEN_REAL",
        "descripcion_visual": "Ilustración del concepto",
        "exige_exactitud": False,
    }
    datos.update(cambios)
    return datos


def _turno_visual(cliente: TestClient, id_conv: str, solicitud: dict[str, Any]) -> dict[str, Any]:
    entrada = {
        "ambito": "ACADEMICO",
        "bloques": [{"tipo": "texto", "contenido": "Observa."}],
        "solicitud_visual": solicitud,
    }
    _llm(cliente).programar(respuesta_herramienta(RESPONDER, entrada))
    turno = enviar(cliente, id_conv, "Muéstrame el concepto")
    assert turno.status_code == 201, turno.text
    visual: dict[str, Any] = cliente.get(
        f"/api/v1/mensajes/{turno.json()['id_mensaje']}/visual"
    ).json()
    return visual


def _preparar(cliente: TestClient) -> str:
    registrar(cliente)
    return str(iniciar_conversacion(cliente)["id_conversacion"])


class TestVisual:
    def test_prefiere_imagen_real_con_atribucion(self, client: TestClient) -> None:
        visual = _turno_visual(client, _preparar(client), _solicitud_visual())
        assert (
            visual["estado"] == "LISTO"
            and visual["tipo"] == "REAL"
            and not visual["generado_por_ia"]
        )
        assert visual["imagen"]["url"].startswith("/api/v1/recursos/")
        assert visual["imagen"]["licencia"].startswith("CC BY-SA")

    def test_sin_imagen_real_usa_diagrama_y_luego_ia(self, client: TestClient) -> None:
        id_conv = _preparar(client)
        for proveedor in contenedor_de(client).imagenes:
            proveedor.vacio = True  # type: ignore[attr-defined]
        diagrama = {
            "tipo_diagrama": "flujo",
            "titulo": "Ciclo",
            "nodos": [{"id": "a", "texto": "A"}, {"id": "b", "texto": "B"}],
            "aristas": [{"desde": "a", "hasta": "b"}],
        }
        con_diagrama = _turno_visual(client, id_conv, _solicitud_visual(diagrama=diagrama))
        assert con_diagrama["tipo"] == "DIAGRAMA" and con_diagrama["diagrama"]["titulo"] == "Ciclo"
        ilustracion = _turno_visual(client, id_conv, _solicitud_visual())
        assert (
            ilustracion["tipo"] == "IA"
            and ilustracion["generado_por_ia"]
            and ilustracion["aviso_ia"]
        )
        prompt, safety = _ia(client).llamadas[-1]
        assert "Muéstrame" not in prompt and "Sin texto" in prompt and len(safety) == 64
        with contenedor_de(client).fabrica_sesiones() as session:
            consumo = session.scalars(
                select(ConsumoIA).where(ConsumoIA.operacion == OperacionIA.IMAGEN)
            ).one()
        assert consumo.proveedor == ProveedorIA.OPENAI

    def test_exige_exactitud_nunca_genera_ia(self, client: TestClient) -> None:
        id_conv = _preparar(client)
        visual = _turno_visual(client, id_conv, _solicitud_visual(exige_exactitud=True))
        assert visual["estado"] == "FALLIDO" and not _ia(client).llamadas

    def test_presupuesto_agotado_falla_sin_afectar_el_texto(
        self, client: TestClient, settings: Any
    ) -> None:
        id_conv = _preparar(client)
        for proveedor in contenedor_de(client).imagenes:
            proveedor.vacio = True  # type: ignore[attr-defined]
        with contenedor_de(client).fabrica_sesiones() as session:
            FabricaServicios(contenedor_de(client), session).consumo.registrar(
                None,
                ProveedorIA.OPENAI,
                "fake-image",
                OperacionIA.IMAGEN,
                __import__("app.services.consumo_service", fromlist=["UsoTokens"]).UsoTokens(),
                imagenes=500,
            )
        visual = _turno_visual(client, id_conv, _solicitud_visual())
        assert visual["estado"] == "FALLIDO" and not _ia(client).llamadas
        with contenedor_de(client).fabrica_sesiones() as session:
            trabajo = session.scalars(select(TrabajoVisual)).one()
        assert trabajo.codigo_error == "LIMITE_USO"

    def test_reutiliza_cache_y_descarga_falla(self, client: TestClient) -> None:
        id_conv = _preparar(client)
        solicitud = _solicitud_visual()
        _turno_visual(client, id_conv, solicitud)
        descargador = contenedor_de(client).descargador
        assert isinstance(descargador, FakeDescargador)
        descargas = len(descargador.urls)
        assert _turno_visual(client, id_conv, solicitud)["tipo"] == "REAL"
        assert len(descargador.urls) == descargas
        descargador.falla = True
        contenedor_de(client).settings.imagenes_ia_activa = False
        assert _turno_visual(client, id_conv, _solicitud_visual())["estado"] == "FALLIDO"

    def test_huerfanos_y_vencidos(self, client: TestClient, settings: Any) -> None:
        id_conv = _preparar(client)
        turno = enviar(client, id_conv, "Muéstrame una imagen")
        with contenedor_de(client).fabrica_sesiones() as session:
            trabajo = session.scalars(select(TrabajoVisual)).one()
            trabajo.estado = EstadoTrabajoVisual.PROCESANDO
            trabajo.fecha_creacion = ahora_utc() - timedelta(
                seconds=settings.trabajo_visual_timeout_segundos + 5
            )
            session.commit()
            recuperados = FabricaServicios(
                contenedor_de(client), session
            ).trabajo_visual.recuperar_huerfanos()
        assert recuperados == 1
        assert (
            client.get(f"/api/v1/mensajes/{turno.json()['id_mensaje']}/visual").json()["estado"]
            == "FALLIDO"
        )

    def test_imagen_ajena_404(self, client: TestClient, app: Any) -> None:
        from tests.conftest import nuevo_cliente

        visual = _turno_visual(client, _preparar(client), _solicitud_visual())
        otro = nuevo_cliente(app)
        registrar(otro)
        assert otro.get(visual["imagen"]["url"]).status_code == 404
        respuesta = client.get(visual["imagen"]["url"])
        assert respuesta.headers["cache-control"] == "private, no-store"


def _video(cliente: TestClient, **cambios: Any) -> VideoCurado:
    datos: dict[str, Any] = {
        "youtube_id": uuid.uuid4().hex[:11],
        "tema_clave": "revolucion francesa",
        "titulo": "La Revolución Francesa",
        "canal": "Historia Abierta",
        "id_canal": "UCabc",
        "duracion_segundos": 600,
        "idioma": "es",
        "es_para_ninos": False,
        "estado": EstadoVideo.APROBADO,
        "puntos_clave": ["Comenzó en 1789", "Abolió la monarquía absoluta"],
        "fecha_revision": ahora_utc(),
        "fecha_metadatos": ahora_utc(),
        "fecha_creacion": ahora_utc(),
    }
    datos.update(cambios)
    with contenedor_de(cliente).fabrica_sesiones() as session:
        video = VideoCurado(**datos)
        session.add(video)
        session.commit()
        return video


class TestVideos:
    def test_video_aprobado_y_pregunta_resumen(self, client: TestClient) -> None:
        id_conv = _preparar(client)
        video = _video(client)
        _video(client, duracion_segundos=5000)
        _video(client, es_para_ninos=True)
        _video(client, fecha_metadatos=ahora_utc() - timedelta(days=40))
        _llm(client).programar(respuesta_herramienta(BUSCAR_VIDEO, {"tema": "Revolución Francesa"}))
        cuerpo = enviar(client, id_conv, "Quiero un video de la revolucion francesa").json()
        videos = [b for b in cuerpo["bloques"] if b["tipo"] == "video"]
        assert (
            len(videos) == 1
            and videos[0]["youtube_id"] == video.youtube_id
            and videos[0]["verificado"]
        )
        assert any(b["tipo"] == "pregunta_resumen" for b in cuerpo["bloques"])
        enviar(client, id_conv, "Mi resumen: empezó en 1789")
        dinamico = _llm(client).solicitudes[-1].system[1].texto
        assert "<video_activo>" in dinamico and "Comenzó en 1789" in dinamico

    def test_video_retirado_no_se_muestra(self, client: TestClient) -> None:
        id_conv = _preparar(client)
        video = _video(client)
        _llm(client).programar(respuesta_herramienta(BUSCAR_VIDEO, {"tema": "revolucion francesa"}))
        enviar(client, id_conv, "video de la revolucion francesa")
        with contenedor_de(client).fabrica_sesiones() as session:
            fila = session.get(VideoCurado, video.id_video)
            assert fila is not None
            fila.estado = EstadoVideo.RETIRADO
            session.commit()
        detalle = client.get(f"/api/v1/conversaciones/{id_conv}").json()
        assert all(b["tipo"] != "video" for m in detalle["mensajes"] for b in (m["bloques"] or []))

    def test_busqueda_dinamica_filtra_canales(self, client: TestClient) -> None:
        from app.services.videos.video_service import VideoService
        from app.videos.base import MetadatosVideo

        registrar(client)
        contenedor = contenedor_de(client)
        interno = contenedor.videos.interno  # type: ignore[attr-defined]
        assert isinstance(interno, FakeVideosClient)
        confiable = MetadatosVideo(
            "aaaaaaaaaaa", "Clase", "Canal confiable", "UCok", 700, "es", True, False
        )
        dudoso = MetadatosVideo("bbbbbbbbbbb", "Clase", "Otro", "UCno", 700, "es", True, False)
        interno.buscar = lambda tema, limite: [confiable, dudoso]  # type: ignore[method-assign]
        settings = contenedor.settings.model_copy(
            update={"videos_busqueda_dinamica": True, "videos_canales_confiables": ["UCok"]}
        )
        with contenedor.fabrica_sesiones() as session:
            fabrica = FabricaServicios(contenedor, session)
            servicio = VideoService(fabrica.videos_repo, contenedor.videos, fabrica.uso, settings)
            usuario = fabrica.usuarios_repo.obtener_por_correo_hash(
                contenedor.indice.calcular(contenedor_de(client).settings.cookie_nombre)
            )
            texto, videos = servicio.buscar_para_herramienta(
                "tema", usuario.id_usuario if usuario else uuid.uuid4()
            )
        assert [v.youtube_id for v in videos] == ["aaaaaaaaaaa"] and '"verificado": false' in texto


def _png_con_exif() -> bytes:
    imagen = Image.new("RGB", (600, 400), (10, 20, 30))
    exif = imagen.getexif()
    exif[0x010E] = "descripcion privada"
    salida = io.BytesIO()
    imagen.save(salida, "JPEG", exif=exif)
    return salida.getvalue()


def _conversacion_avanzada(cliente: TestClient) -> str:
    registrar(cliente)
    evaluar(cliente, crear_diagnostico(cliente), 5)
    return str(iniciar_conversacion(cliente, tema="ensayo")["id_conversacion"])


class TestArchivos:
    def test_solo_nivel_avanzado(self, client: TestClient) -> None:
        id_conv = _preparar(client)
        respuesta = client.post(
            "/api/v1/archivos",
            data={"contexto": "CONVERSACION", "id_contexto": id_conv},
            files={"archivo": ("a.txt", b"hola", "text/plain")},
        )
        assert (
            respuesta.status_code == 403
            and respuesta.json()["error"]["codigo"] == "ARCHIVO_NO_PERMITIDO"
        )

    def test_imagen_sin_exif_adjunta_y_descarga(self, client: TestClient) -> None:
        id_conv = _conversacion_avanzada(client)
        subida = client.post(
            "/api/v1/archivos",
            data={"contexto": "CONVERSACION", "id_contexto": id_conv},
            files={"archivo": ("foto.jpg", _png_con_exif(), "image/jpeg")},
        )
        assert subida.status_code == 201, subida.text
        archivo = subida.json()
        contenido = client.get(f"/api/v1/archivos/{archivo['id_archivo']}/contenido").content
        assert not Image.open(io.BytesIO(contenido)).getexif()
        turno = enviar(client, id_conv, "Revisa mi esquema", id_archivo=archivo["id_archivo"])
        assert turno.status_code == 201
        assert _llm(client).solicitudes[-1].nivel_modelo.value == "COMPLEJO"
        assert (
            enviar(client, id_conv, "otra vez", id_archivo=archivo["id_archivo"]).status_code == 422
        )
        detalle = client.get(f"/api/v1/conversaciones/{id_conv}").json()
        assert any(m["archivo"] for m in detalle["mensajes"])

    def test_archivo_moderado_rechazado_y_borrado(self, client: TestClient) -> None:
        id_conv = _conversacion_avanzada(client)
        contenedor_de(client).moderador.interno.imagen_marcada = True  # type: ignore[attr-defined]
        rechazado = client.post(
            "/api/v1/archivos",
            data={"contexto": "CONVERSACION", "id_contexto": id_conv},
            files={"archivo": ("x.png", imagen_falsa(formato="PNG"), "image/png")},
        )
        assert (
            rechazado.status_code == 422
            and rechazado.json()["error"]["codigo"] == "CONTENIDO_NO_PERMITIDO"
        )
        contenedor_de(client).moderador.interno.imagen_marcada = False  # type: ignore[attr-defined]
        texto = client.post(
            "/api/v1/archivos",
            data={"contexto": "CONVERSACION", "id_contexto": id_conv},
            files={"archivo": ("resumen.txt", b"Mi resumen", "text/plain")},
        ).json()
        assert client.delete(f"/api/v1/archivos/{texto['id_archivo']}").status_code == 204
        assert client.get(f"/api/v1/archivos/{texto['id_archivo']}/contenido").status_code == 404

    def test_archivo_falso_y_grande(self, client: TestClient, settings: Any) -> None:
        id_conv = _conversacion_avanzada(client)
        falso = client.post(
            "/api/v1/archivos",
            data={"contexto": "CONVERSACION", "id_contexto": id_conv},
            files={"archivo": ("x.png", b"MZ\x90\x00" + b"\x00" * 50, "image/png")},
        )
        assert falso.status_code == 422
        grande = client.post(
            "/api/v1/archivos",
            data={"contexto": "CONVERSACION", "id_contexto": id_conv},
            files={"archivo": ("x.txt", b"a" * (settings.archivo_max_bytes + 10), "text/plain")},
        )
        assert grande.status_code == 413
