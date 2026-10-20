"""Textos de los correos transaccionales. Deben revisarse con el equipo legal antes de producción."""

from app.correo.base import Correo

PROVEEDORES_INFORMADOS = (
    "Anthropic (EE. UU.) para generar las explicaciones; OpenAI (EE. UU.) para moderar contenido "
    "y, como último recurso, generar ilustraciones; Amazon Web Services para alojar el servicio, "
    "los archivos y el correo; y YouTube/Google cuando se reproduce un video."
)


def solicitud_autorizacion(
    destinatario: str, correo_estudiante: str, enlace: str, horas_vigencia: int, enlace_revocar: str
) -> Correo:
    texto = f"""Hola:

Recibimos una solicitud para que {correo_estudiante} use TutorIA, un asistente de estudio con \
inteligencia artificial que enseña sin resolver tareas. Como su representante legal, tu \
autorización es necesaria antes de que pueda usar la aplicación.

Para qué tratamos sus datos: crear la cuenta, personalizar las explicaciones de estudio (solo \
información pedagógica) y guardar el historial de sus sesiones. No pedimos documento, teléfono \
ni dirección, y no usamos sus datos para publicidad.

Quién recibe datos: {PROVEEDORES_INFORMADOS}

Para revisar y confirmar la autorización, abre este enlace (vence en {horas_vigencia} horas):
{enlace}

Puedes revocar la autorización en cualquier momento desde:
{enlace_revocar}

Si no reconoces esta solicitud, ignora este correo: la cuenta seguirá bloqueada."""
    return Correo(destinatario, "Autoriza el uso de TutorIA", texto)


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
