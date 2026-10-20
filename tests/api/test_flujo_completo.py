"""Criterio de aceptación: con adaptadores falsos, el flujo completo funciona sin red ni llaves."""

from fastapi.testclient import TestClient

from tests.conftest import crear_diagnostico, enviar, evaluar, iniciar_conversacion, registrar


def test_flujo_completo_sin_red(client: TestClient) -> None:
    usuario = registrar(client)
    assert client.get("/api/v1/auth/me").json()["id_usuario"] == usuario["id_usuario"]

    cuestionario = crear_diagnostico(client)
    assert 3 <= len(cuestionario["preguntas"]) <= 5
    resultado = evaluar(client, cuestionario, aciertos=len(cuestionario["preguntas"]))
    assert resultado["nivel_estimado"] == "AVANZADO"

    plan = client.post("/api/v1/plan-aprendizaje", json={"id_sesion": cuestionario["id_sesion"]})
    assert plan.status_code == 201, plan.text
    plan_json = plan.json()
    assert plan_json["validado"] is True
    assert plan_json["fuentes"]
    actividad = plan_json["actividades"][0]
    respuesta_actividad = client.patch(
        f"/api/v1/actividades/{actividad['id_actividad']}",
        json={"estado": "COMPLETADA", "respuesta_usuario": "Mi explicación"},
    )
    assert respuesta_actividad.status_code == 200, respuesta_actividad.text

    historial = client.get(f"/api/v1/historial/{usuario['id_usuario']}")
    assert historial.status_code == 200 and historial.json()["total"] == 1

    conversacion = iniciar_conversacion(client, id_plan=plan_json["id_plan"])
    turno = enviar(client, conversacion["id_conversacion"], "Explícame con un ejemplo y una imagen")
    assert turno.status_code == 201, turno.text
    cuerpo = turno.json()
    assert cuerpo["ambito"] == "ACADEMICO"
    assert cuerpo["fuentes"], cuerpo
    assert cuerpo["visual"]["estado"] == "PENDIENTE"

    visual = client.get(f"/api/v1/mensajes/{cuerpo['id_mensaje']}/visual")
    assert visual.status_code == 200
    assert visual.json()["estado"] == "LISTO", visual.json()
    imagen = visual.json()["imagen"]
    assert imagen["autor"] and imagen["licencia"] and imagen["url_origen"]
    assert client.get(imagen["url"]).status_code == 200

    diagrama = enviar(client, conversacion["id_conversacion"], "Hazme un diagrama del proceso")
    assert diagrama.status_code == 201, diagrama.text
    visual_diagrama = client.get(f"/api/v1/mensajes/{diagrama.json()['id_mensaje']}/visual").json()
    assert visual_diagrama["tipo"] == "DIAGRAMA"

    feedback = client.post(f"/api/v1/mensajes/{cuerpo['id_mensaje']}/feedback", json={"util": True})
    assert feedback.status_code == 204

    cierre = client.post(f"/api/v1/conversaciones/{conversacion['id_conversacion']}/cerrar")
    assert cierre.status_code == 200, cierre.text
    assert cierre.json()["referencias"]

    perfil = client.get("/api/v1/perfil-aprendizaje")
    assert perfil.status_code == 200
    assert perfil.json()["total_interacciones"] == 2
