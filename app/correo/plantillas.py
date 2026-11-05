"""Textos de los correos transaccionales. Deben revisarse con el equipo legal antes de producción."""

from app.correo.base import Correo


def solicitud_autorizacion(
    destinatario: str,
    nombre_estudiante: str,
    correo_estudiante: str,
    enlace: str,
    horas_vigencia: int,
) -> Correo:
    """Correo al acudiente: solo primer nombre y correo enmascarado del estudiante."""
    texto = f"""Hola:

{nombre_estudiante} ({correo_estudiante}) se registró en TutorIA y necesita tu autorización para usarla. TutorIA es un asistente de estudio con inteligencia artificial que explica los temas sin resolver las tareas.

Revisar y autorizar: {enlace}

El enlace vence en {horas_vigencia} horas.

Si no esperabas este mensaje, puedes ignorarlo."""
    asunto = f"{nombre_estudiante} necesita tu autorización para usar TutorIA"
    return Correo(destinatario, asunto, texto)


def verificacion_correo(destinatario: str, enlace: str, horas_vigencia: int) -> Correo:
    texto = f"""Hola:

TutorIA es una aplicación de estudio; confirma que este correo es tuyo para empezar.

Confirmar mi correo: {enlace}

El enlace vence en {horas_vigencia} horas.

Si no fuiste tú, puedes ignorar este mensaje."""
    return Correo(destinatario, "Confirma tu correo en TutorIA", texto)


def autorizacion_confirmada(
    destinatario: str, correo_estudiante: str, enlace_revocar: str
) -> Correo:
    texto = f"""Hola:

Confirmaste que {correo_estudiante} puede usar TutorIA. Gracias.

Si cambias de opinión, puedes revocar la autorización y pedir que borremos sus datos desde:
{enlace_revocar}"""
    return Correo(destinatario, "Autorización de TutorIA confirmada", texto)


def solicitud_titular_recibida(destinatario: str, tipo: str, fecha_limite: str) -> Correo:
    texto = f"""Hola:

Recibimos tu solicitud de tipo {tipo} sobre tus datos personales. Te responderemos a más tardar \
el {fecha_limite}.

Este es un mensaje automático de TutorIA."""
    return Correo(destinatario, "Recibimos tu solicitud sobre tus datos", texto)
