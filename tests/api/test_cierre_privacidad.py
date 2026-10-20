import json
from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.tiempo import ahora_utc
from app.exceptions.base import LLMNoDisponibleError
from app.llm.fake_client import FakeClient, actualizacion_falsa, respuesta_herramienta
from app.llm.herramientas import ACTUALIZAR_PERFIL
from app.models.consentimiento import Consentimiento
from app.models.conversacion import Conversacion
from app.models.usuario import Usuario
from tests.conftest import contenedor_de, enviar, iniciar_conversacion, nuevo_cliente, registrar


def _llm(cliente: TestClient) -> FakeClient:
    llm = contenedor_de(cliente).llm
    assert isinstance(llm, FakeClient)
    return llm


def _conversacion(cliente: TestClient) -> str:
    registrar(cliente)
    id_conv = str(iniciar_conversacion(cliente)["id_conversacion"])
    enviar(cliente, id_conv, "Explícame con un ejemplo y una imagen")
    return id_conv


class TestConsolidacion:
    def test_fusiona_perfil_y_entrega_referencias(self, client: TestClient) -> None:
        id_conv = _conversacion(client)
        resumen = client.post(f"/api/v1/conversaciones/{id_conv}/cerrar").json()
        assert resumen["resumen"] == actualizacion_falsa()["resumen_conversacion"]
        assert "IA" in resumen["aviso"]
        tipos = {r["tipo"] for r in resumen["referencias"]}
        assert "REAL" in tipos and tipos - {"REAL"}
        textos = [r["texto_apa"] for r in resumen["referencias"]]
        assert textos == sorted(textos, key=str.casefold) and len(textos) == len(set(textos))
        perfil = client.get("/api/v1/perfil-aprendizaje").json()
        assert perfil["resumen"] == actualizacion_falsa()["resumen_perfil"]
        assert perfil["temas"][0]["dificultades"] == actualizacion_falsa()["dificultades"]
        assert (
            client.get(f"/api/v1/conversaciones/{id_conv}/referencias").json()
            == resumen["referencias"]
        )

    def test_idempotente(self, client: TestClient) -> None:
        id_conv = _conversacion(client)
        client.post(f"/api/v1/conversaciones/{id_conv}/cerrar")
        llamadas = len(_llm(client).solicitudes)
        assert client.post(f"/api/v1/conversaciones/{id_conv}/cerrar").status_code == 200
        assert len(_llm(client).solicitudes) == llamadas

    def test_llm_caido_cierra_sin_consolidar_y_reintenta(self, client: TestClient) -> None:
        id_conv = _conversacion(client)
        _llm(client).programar(LLMNoDisponibleError())
        assert client.post(f"/api/v1/conversaciones/{id_conv}/cerrar").status_code == 200
        with contenedor_de(client).fabrica_sesiones() as session:
            conversacion = session.scalars(select(Conversacion)).one()
            assert conversacion.estado.value == "CERRADA" and conversacion.consolidada is False
        client.post(f"/api/v1/conversaciones/{id_conv}/cerrar")
        with contenedor_de(client).fabrica_sesiones() as session:
            assert session.scalars(select(Conversacion)).one().consolidada is True

    def test_topes_fifo_de_dificultades(self, client: TestClient) -> None:
        registrar(client)
        for i in range(3):
            id_conv = iniciar_conversacion(client)["id_conversacion"]
            enviar(client, id_conv, "Hola")
            datos = {
                **actualizacion_falsa(),
                "dificultades": [f"dificultad {i}-{j}" for j in range(3)],
            }
            _llm(client).programar(respuesta_herramienta(ACTUALIZAR_PERFIL, datos))
            client.post(f"/api/v1/conversaciones/{id_conv}/cerrar")
        dificultades = client.get("/api/v1/perfil-aprendizaje").json()["temas"][0]["dificultades"]
        assert len(dificultades) == 5 and dificultades[-1] == "dificultad 2-2"

    def test_inactiva_se_consolida_al_iniciar_otra(self, client: TestClient, settings: Any) -> None:
        id_conv = _conversacion(client)
        with contenedor_de(client).fabrica_sesiones() as session:
            conversacion = session.scalars(select(Conversacion)).one()
            conversacion.fecha_ultimo_mensaje = ahora_utc() - timedelta(
                minutes=settings.chat_inactividad_minutos + 1
            )
            session.commit()
        assert client.post("/api/v1/conversaciones", json={"tema": "planetas"}).status_code == 201
        with contenedor_de(client).fabrica_sesiones() as session:
            anterior = session.get(Conversacion, __import__("uuid").UUID(id_conv))
            assert (
                anterior is not None and anterior.estado.value == "CERRADA" and anterior.consolidada
            )


class TestPrivacidad:
    def test_politica_y_cumplimiento_publicos(self, client: TestClient) -> None:
        politica = client.get("/api/v1/politica-tratamiento").json()
        assert politica["version"] == "1" and len(politica["finalidades"]) == 6
        assert "PLANTILLA" in politica["texto"]
        cumplimiento = client.get("/api/v1/cumplimiento").json()
        assert cumplimiento["edad_minima"] == 13 and cumplimiento["proveedores"]

    def test_consentimientos_con_prueba_y_revocatoria_inserta_fila(
        self, client: TestClient
    ) -> None:
        registrar(client, acepta_comunicaciones=False)
        estado = {
            c["finalidad"]: c["otorgado"]
            for c in client.get("/api/v1/privacidad/consentimientos").json()
        }
        assert estado["TRATAMIENTO"] and not estado["COMUNICACIONES"]
        cambio = client.post(
            "/api/v1/privacidad/consentimientos",
            json={"finalidad": "PERSONALIZACION", "otorgado": False, "version_politica": "1"},
        )
        assert cambio.status_code == 200
        assert client.get("/api/v1/perfil-aprendizaje").json()["personalizacion_activa"] is False
        with contenedor_de(client).fabrica_sesiones() as session:
            filas = session.scalars(select(Consentimiento)).all()
        personalizacion = [f for f in filas if f.finalidad.value == "PERSONALIZACION"]
        assert [f.otorgado for f in personalizacion] == [True, False]
        assert all(
            len(f.texto_sha256) == 64 and f.version_politica == "1" and f.ip_hash for f in filas
        )

    def test_revocar_tratamiento_crea_solicitud_de_supresion(self, client: TestClient) -> None:
        registrar(client)
        client.post(
            "/api/v1/privacidad/consentimientos",
            json={"finalidad": "TRATAMIENTO", "otorgado": False, "version_politica": "1"},
        )
        solicitudes = client.get("/api/v1/privacidad/solicitudes").json()
        assert solicitudes[0]["tipo"] == "SUPRESION"
        no_modificable = client.post(
            "/api/v1/privacidad/consentimientos",
            json={"finalidad": "COMPRAS_MENOR", "otorgado": True, "version_politica": "1"},
        )
        assert no_modificable.status_code == 422

    def test_mis_datos_y_exportar_sin_hashes(self, client: TestClient, app: Any) -> None:
        usuario = registrar(client)
        otro = nuevo_cliente(app)
        registrar(otro, nombre="Persona Ajena")
        datos = client.get("/api/v1/privacidad/mis-datos").json()
        texto = json.dumps(datos)
        assert datos["usuario"]["correo"] == usuario["correo"]
        assert "Persona Ajena" not in texto and "hash" not in texto and "ip_" not in texto
        exportado = client.get("/api/v1/privacidad/mis-datos/exportar")
        assert exportado.headers["content-disposition"].startswith("attachment")
        assert json.loads(exportado.content)["usuario"]["correo"] == usuario["correo"]

    def test_solicitud_con_plazo_en_dias_habiles(self, client: TestClient) -> None:
        registrar(client)
        consulta = client.post(
            "/api/v1/privacidad/solicitudes",
            json={"tipo": "CONSULTA", "detalle": "Quiero saber mis datos"},
        ).json()
        reclamo = client.post(
            "/api/v1/privacidad/solicitudes",
            json={"tipo": "RECLAMO", "detalle": "Hay un error en mis datos"},
        ).json()
        assert consulta["fecha_limite"] < reclamo["fecha_limite"]
        assert consulta["estado"] == "RECIBIDA"

    def test_politica_desactualizada_bloquea_hasta_aceptar(self, client: TestClient) -> None:
        registrar(client)
        contenedor_de(client).settings.politica_version = "2"
        contenedor_de(client).settings.politica_version_minima_aceptada = "2"
        bloqueado = client.get("/api/v1/suscripcion")
        assert (
            bloqueado.status_code == 409
            and bloqueado.json()["error"]["codigo"] == "POLITICA_DESACTUALIZADA"
        )
        aceptar = client.post(
            "/api/v1/privacidad/aceptar-politica",
            json={
                "version_politica": "2",
                "acepta_tratamiento": True,
                "acepta_transferencia_internacional": True,
            },
        )
        assert aceptar.status_code == 200
        assert client.get("/api/v1/suscripcion").status_code == 200

    def test_suprimir_anonimiza_y_conserva_prueba(self, client: TestClient) -> None:
        import uuid

        from app.core.fabrica import FabricaServicios

        usuario = registrar(client, nombre="Nombre Borrable")
        iniciar_conversacion(client)
        with contenedor_de(client).fabrica_sesiones() as session:
            FabricaServicios(contenedor_de(client), session).privacidad.suprimir(
                uuid.UUID(usuario["id_usuario"])
            )
        with contenedor_de(client).fabrica_sesiones() as session:
            fila = session.get(Usuario, uuid.UUID(usuario["id_usuario"]))
            assert fila is not None and fila.nombre != "Nombre Borrable" and not fila.activo
            assert session.scalars(select(Conversacion)).all() == []
            assert session.scalars(select(Consentimiento)).all()
