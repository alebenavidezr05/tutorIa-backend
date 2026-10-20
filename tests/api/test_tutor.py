"""Turno del tutor: moderación, ámbito, citas, reintentos, respaldo y transaccionalidad (§8.2)."""

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.exceptions.base import LLMNoDisponibleError
from app.llm.base import LLMSolicitud
from app.llm.fake_client import FakeClient, respuesta_herramienta
from app.llm.herramientas import BUSCAR_FUENTES, RESPONDER
from app.models.alerta_seguridad import AlertaSeguridad
from app.models.evento_aprendizaje import EventoAprendizaje
from app.models.mensaje import Mensaje
from app.services.seguridad.textos import MENSAJE_NO_ACADEMICO, MENSAJE_RECHAZO, RESPALDO_TEXTO
from tests.conftest import contenedor_de, enviar, iniciar_conversacion, registrar


def _llm(cliente: TestClient) -> FakeClient:
    llm = contenedor_de(cliente).llm
    assert isinstance(llm, FakeClient)
    return llm


def _contar(cliente: TestClient, modelo: Any) -> int:
    with contenedor_de(cliente).fabrica_sesiones() as session:
        return int(session.scalar(select(func.count()).select_from(modelo)) or 0)


def _preparar(cliente: TestClient, **registro: Any) -> str:
    registrar(cliente, **registro)
    return str(iniciar_conversacion(cliente)["id_conversacion"])


def _texto_bloques(cuerpo: dict[str, Any]) -> str:
    return " ".join(b.get("contenido", "") for b in cuerpo["bloques"])


def test_turno_academico_con_fuentes_y_modelo(client: TestClient) -> None:
    id_conv = _preparar(client)
    respuesta = enviar(client, id_conv, "¿Qué es la fotosíntesis?")
    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["validado"] and cuerpo["fuentes"] and cuerpo["visual"] is None
    assert "TEORIA" in cuerpo["formatos_usados"]
    solicitud = _llm(client).solicitudes[-1]
    assert solicitud.herramienta_forzada == "*"
    assert solicitud.system[0].cacheable and not solicitud.system[1].cacheable
    assert "<mensaje_estudiante>" in solicitud.mensajes[0].contenido[-1].texto  # type: ignore[union-attr]


def test_no_academico_y_riesgo_usan_textos_fijos(client: TestClient) -> None:
    id_conv = _preparar(client)
    no_academico = enviar(client, id_conv, "¿Quién ganó el partido de futbol ayer?").json()
    assert (
        no_academico["ambito"] == "NO_ACADEMICO"
        and _texto_bloques(no_academico) == MENSAJE_NO_ACADEMICO
    )
    riesgo = enviar(client, id_conv, "a veces pienso en hacerme daño").json()
    assert riesgo["ambito"] == "RIESGO" and "141" in _texto_bloques(riesgo)
    assert _contar(client, AlertaSeguridad) == 1


def test_moderacion_responde_sin_llamar_al_llm(client: TestClient) -> None:
    id_conv = _preparar(client)
    antes = len(_llm(client).solicitudes)
    apoyo = enviar(client, id_conv, "quiero hacerme daño").json()
    rechazo = enviar(client, id_conv, "quiero golpear a alguien").json()
    assert len(_llm(client).solicitudes) == antes
    assert "123" in _texto_bloques(apoyo) and _texto_bloques(rechazo) == MENSAJE_RECHAZO
    with contenedor_de(client).fabrica_sesiones() as session:
        categorias = {a.categoria.value for a in session.scalars(select(AlertaSeguridad))}
    assert categorias == {"AUTOLESION", "VIOLENCIA"}


def test_moderador_caido_continua_con_segunda_capa(client: TestClient) -> None:
    id_conv = _preparar(client)
    contenedor_de(client).moderador.interno.no_disponible = True  # type: ignore[attr-defined]
    assert enviar(client, id_conv, "¿Qué es un átomo?").status_code == 201


def _responder(bloques: list[dict[str, Any]], ambito: str = "ACADEMICO") -> Any:
    return respuesta_herramienta(RESPONDER, {"ambito": ambito, "bloques": bloques})


def test_cita_inventada_reintenta_y_usa_respaldo(client: TestClient) -> None:
    id_conv = _preparar(client)
    inventada = [
        {
            "tipo": "texto",
            "contenido": "Dato",
            "afirma_hechos": True,
            "fuentes": [str(uuid.uuid4())],
        }
    ]
    _llm(client).programar(_responder(inventada), _responder(inventada))
    cuerpo = enviar(client, id_conv, "Dime un dato").json()
    assert cuerpo["validado"] is False and RESPALDO_TEXTO in _texto_bloques(cuerpo)
    errores = [
        b
        for m in _llm(client).solicitudes[-1].mensajes
        for b in m.contenido
        if getattr(b, "es_error", False)
    ]
    assert errores and "no se recuperaron" in errores[0].contenido


def test_reintento_corrige_la_respuesta(client: TestClient) -> None:
    id_conv = _preparar(client)
    invalida = [{"tipo": "texto", "contenido": "La respuesta es 7"}]
    valida = [{"tipo": "texto", "contenido": "Piensa qué pasa al despejar x."}]
    _llm(client).programar(_responder(invalida), _responder(valida))
    cuerpo = enviar(client, id_conv, "Resuélveme la ecuación").json()
    assert cuerpo["validado"] is True
    assert "modo_guia" in _llm(client).solicitudes[-1].system[1].texto


def test_iteraciones_excedidas_y_llm_caido_no_guardan_nada(
    client: TestClient, settings: Any
) -> None:
    id_conv = _preparar(client)
    buscar = respuesta_herramienta(BUSCAR_FUENTES, {"consulta": "tema largo"})
    _llm(client).programar(*[buscar] * settings.chat_max_iteraciones_herramientas)
    excedido = enviar(client, id_conv, "Explícame algo")
    assert (
        excedido.status_code == 502
        and excedido.json()["error"]["codigo"] == "LLM_RESPUESTA_INVALIDA"
    )
    _llm(client).programar(LLMNoDisponibleError())
    caido = enviar(client, id_conv, "Explícame algo")
    assert caido.status_code == 502
    assert _contar(client, Mensaje) == 0
    assert (
        client.get("/api/v1/suscripcion").json()["limites"]["mensajes_restantes_hoy"]
        == settings.limite_mensajes_gratis
    )


def test_texto_libre_recibe_recordatorio_y_entrada_invalida_falla(client: TestClient) -> None:
    from app.llm.fake_client import respuesta_texto

    id_conv = _preparar(client)
    _llm(client).programar(
        respuesta_texto("Hola, te explico..."),
        _responder([{"tipo": "texto", "contenido": "Listo"}]),
    )
    assert enviar(client, id_conv, "Hola").json()["validado"] is True
    _llm(client).programar(
        respuesta_herramienta(RESPONDER, {"ambito": "ACADEMICO", "bloques": [{"tipo": "html"}]})
    )
    assert enviar(client, id_conv, "Hola").status_code == 502


def test_video_desconocido_se_descarta(client: TestClient) -> None:
    id_conv = _preparar(client)
    bloques = [
        {"tipo": "texto", "contenido": "Mira este recurso."},
        {"tipo": "video", "id_video": str(uuid.uuid4())},
    ]
    _llm(client).programar(_responder(bloques))
    cuerpo = enviar(client, id_conv, "Muéstrame algo").json()
    assert cuerpo["validado"] and all(b["tipo"] != "video" for b in cuerpo["bloques"])


def test_rechazo_del_modelo_usa_respaldo(client: TestClient) -> None:
    from app.llm.base import BloqueTextoLLM, LLMRespuesta

    id_conv = _preparar(client)
    _llm(client).programar(LLMRespuesta((BloqueTextoLLM(""),), "refusal", "fake", 1, 1))
    assert enviar(client, id_conv, "Hola").json()["validado"] is False


def test_conversacion_cerrada_y_limite_de_mensajes(client: TestClient, settings: Any) -> None:
    id_conv = _preparar(client)
    client.post(f"/api/v1/conversaciones/{id_conv}/cerrar")
    cerrada = enviar(client, id_conv, "Hola")
    assert (
        cerrada.status_code == 409 and cerrada.json()["error"]["codigo"] == "CONVERSACION_CERRADA"
    )
    otra = iniciar_conversacion(client, tema="planetas")["id_conversacion"]
    for _ in range(settings.limite_mensajes_gratis):
        assert enviar(client, otra, "Hola").status_code == 201
    agotado = enviar(client, otra, "Hola")
    assert (
        agotado.status_code == 403 and agotado.json()["error"]["codigo"] == "LIMITE_PLAN_GRATUITO"
    )


def test_datos_personales_redactados_antes_del_llm(client: TestClient) -> None:
    id_conv = _preparar(client)
    enviar(client, id_conv, "Mi correo es ana@x.co y mi celular 3001234567, ¿qué es un ion?")
    enviado = str(_llm(client).solicitudes[0].mensajes)
    assert "ana@x.co" not in enviado and "3001234567" not in enviado
    detalle = client.get(f"/api/v1/conversaciones/{id_conv}").json()
    assert "ana@x.co" not in detalle["mensajes"][0]["contenido"]


def test_personalizacion_desactivada_no_crea_eventos(client: TestClient) -> None:
    id_conv = _preparar(client, acepta_personalizacion=False)
    enviar(client, id_conv, "Dame un ejemplo paso a paso")
    assert _contar(client, EventoAprendizaje) == 0
    assert client.get("/api/v1/perfil-aprendizaje").json()["total_interacciones"] == 0
    assert "<perfil_estudiante>" not in _llm(client).solicitudes[-1].system[1].texto


def test_ejemplo_y_feedback_suben_puntaje_y_reiniciar_vuelve_a_neutro(client: TestClient) -> None:
    id_conv = _preparar(client)
    for _ in range(3):
        cuerpo = enviar(client, id_conv, "Explícame con un ejemplo").json()
        client.post(f"/api/v1/mensajes/{cuerpo['id_mensaje']}/feedback", json={"util": True})
    perfil = client.get("/api/v1/perfil-aprendizaje").json()
    ejemplo = next(f for f in perfil["formatos"] if f["formato"] == "EJEMPLO")
    assert ejemplo["puntaje"] > 0.5 and ejemplo["confianza"] > 0
    assert "<perfil_estudiante>" in _llm(client).solicitudes[-1].system[1].texto
    assert client.delete("/api/v1/perfil-aprendizaje").status_code == 204
    reiniciado = client.get("/api/v1/perfil-aprendizaje").json()
    assert all(f["puntaje"] == 0.5 and f["confianza"] == 0 for f in reiniciado["formatos"])
    assert reiniciado["personalizacion_activa"] is True


def test_borrar_conversacion_elimina_mensajes_y_eventos(client: TestClient) -> None:
    id_conv = _preparar(client)
    enviar(client, id_conv, "Dame un ejemplo")
    assert _contar(client, EventoAprendizaje) > 0
    assert client.delete(f"/api/v1/conversaciones/{id_conv}").status_code == 204
    assert _contar(client, Mensaje) == 0 and _contar(client, EventoAprendizaje) == 0


def test_reportar_mensaje_crea_alerta(client: TestClient) -> None:
    id_conv = _preparar(client)
    cuerpo = enviar(client, id_conv, "¿Qué es un ion?").json()
    respuesta = client.post(
        f"/api/v1/mensajes/{cuerpo['id_mensaje']}/reportar",
        json={"categoria": "CONTENIDO_INCORRECTO", "comentario": "Está mal"},
    )
    assert respuesta.status_code == 204 and _contar(client, AlertaSeguridad) == 1


def test_selector_usa_modelo_complejo_en_preguntas_analiticas(client: TestClient) -> None:
    registrar(client)
    id_conv = iniciar_conversacion(client, tema="economía")["id_conversacion"]
    enviar(
        client, id_conv, "Compara y justifica las dos teorías, demuestra cuál es mejor paso a paso"
    )
    solicitud: LLMSolicitud = _llm(client).solicitudes[-1]
    assert solicitud.nivel_modelo.value == "COMPLEJO"
