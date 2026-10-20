from typing import Any, ClassVar


class AppError(Exception):
    status_code: ClassVar[int] = 500
    codigo: ClassVar[str] = "ERROR_INTERNO"
    mensaje_por_defecto: ClassVar[str] = "Ocurrió un error inesperado. Intenta de nuevo más tarde."

    def __init__(self, mensaje: str | None = None, detalles: Any = None) -> None:
        self.mensaje = mensaje or self.mensaje_por_defecto
        self.detalles = detalles
        super().__init__(self.mensaje)


# 400
class FirmaPagoInvalidaError(AppError):
    status_code = 400
    codigo = "FIRMA_INVALIDA"
    mensaje_por_defecto = "La firma de la notificación de pago no es válida."


# 401
class CredencialesInvalidasError(AppError):
    status_code = 401
    codigo = "CREDENCIALES_INVALIDAS"
    mensaje_por_defecto = "El correo o la contraseña no son correctos."


class TokenInvalidoError(AppError):
    status_code = 401
    codigo = "SESION_INVALIDA"
    mensaje_por_defecto = "Tu sesión no es válida o expiró. Inicia sesión de nuevo."


# 403
class CuentaDesactivadaError(AppError):
    status_code = 403
    codigo = "CUENTA_DESACTIVADA"
    mensaje_por_defecto = "Esta cuenta está desactivada."


class AutorizacionPendienteError(AppError):
    status_code = 403
    codigo = "AUTORIZACION_PENDIENTE"
    mensaje_por_defecto = (
        "Tu cuenta necesita la autorización de tu acudiente. Pídele que confirme desde su correo."
    )


class AccesoDenegadoError(AppError):
    status_code = 403
    codigo = "ACCESO_DENEGADO"
    mensaje_por_defecto = "No tienes permiso para realizar esta acción."


class OrigenNoPermitidoError(AppError):
    status_code = 403
    codigo = "ORIGEN_NO_PERMITIDO"
    mensaje_por_defecto = "La solicitud no proviene de un origen permitido."


class LimiteFreemiumError(AppError):
    status_code = 403
    codigo = "LIMITE_PLAN_GRATUITO"
    mensaje_por_defecto = "Alcanzaste el límite diario del plan gratuito. Vuelve mañana."


class FuncionPremiumError(AppError):
    status_code = 403
    codigo = "FUNCION_PREMIUM"
    mensaje_por_defecto = "Esta función está disponible en el plan Premium."


class CompraNoPermitidaError(AppError):
    status_code = 403
    codigo = "COMPRA_NO_PERMITIDA"
    mensaje_por_defecto = "Tu acudiente no autorizó compras en esta cuenta."


class ArchivoNoPermitidoError(AppError):
    status_code = 403
    codigo = "ARCHIVO_NO_PERMITIDO"
    mensaje_por_defecto = "Entregar archivos está disponible solo en el nivel avanzado."


class OperacionNoPermitidaError(AppError):
    status_code = 403
    codigo = "OPERACION_NO_PERMITIDA"
    mensaje_por_defecto = "Esta operación no está permitida."


# 404
class RecursoNoEncontradoError(AppError):
    status_code = 404
    codigo = "RECURSO_NO_ENCONTRADO"
    mensaje_por_defecto = "No encontramos lo que buscas."


class AutorizacionInvalidaError(AppError):
    status_code = 404
    codigo = "AUTORIZACION_INVALIDA"
    mensaje_por_defecto = "El enlace de autorización no es válido o ya venció."


# 409
class CorreoYaRegistradoError(AppError):
    status_code = 409
    codigo = "CORREO_YA_REGISTRADO"
    mensaje_por_defecto = "Ese correo ya tiene una cuenta."


class SesionYaEvaluadaError(AppError):
    status_code = 409
    codigo = "SESION_YA_EVALUADA"
    mensaje_por_defecto = "Este diagnóstico ya fue respondido."


class SesionSinEvaluarError(AppError):
    status_code = 409
    codigo = "SESION_SIN_EVALUAR"
    mensaje_por_defecto = "Primero responde el diagnóstico para generar tu plan."


class ConversacionCerradaError(AppError):
    status_code = 409
    codigo = "CONVERSACION_CERRADA"
    mensaje_por_defecto = "Esta conversación ya fue cerrada. Inicia una nueva."


class PoliticaDesactualizadaError(AppError):
    status_code = 409
    codigo = "POLITICA_DESACTUALIZADA"
    mensaje_por_defecto = "Actualizamos la política de tratamiento de datos. Revísala y acéptala."


# 413
class ArchivoMuyGrandeError(AppError):
    status_code = 413
    codigo = "ARCHIVO_MUY_GRANDE"
    mensaje_por_defecto = "El archivo supera el tamaño máximo permitido."


# 422
class DatoInvalidoError(AppError):
    status_code = 422
    codigo = "DATO_INVALIDO"
    mensaje_por_defecto = "Uno de los datos enviados no es válido."


class ConsentimientoRequeridoError(AppError):
    status_code = 422
    codigo = "CONSENTIMIENTO_REQUERIDO"
    mensaje_por_defecto = "Debes aceptar las autorizaciones obligatorias para continuar."


class EdadNoPermitidaError(AppError):
    status_code = 422
    codigo = "EDAD_NO_PERMITIDA"
    mensaje_por_defecto = "TutorIA está disponible a partir de los 13 años."


class TemaNoPermitidoError(AppError):
    status_code = 422
    codigo = "TEMA_NO_PERMITIDO"
    mensaje_por_defecto = (
        "Escribe un tema académico que quieras aprender, no una tarea por resolver."
    )


class TemaSinFuentesError(AppError):
    status_code = 422
    codigo = "TEMA_SIN_FUENTES"
    mensaje_por_defecto = (
        "No encontramos fuentes verificables sobre ese tema. Prueba con otras palabras."
    )


class MensajeNoPermitidoError(AppError):
    status_code = 422
    codigo = "MENSAJE_NO_PERMITIDO"
    mensaje_por_defecto = "No podemos procesar ese mensaje. Reformúlalo como una duda de estudio."


class ArchivoInvalidoError(AppError):
    status_code = 422
    codigo = "ARCHIVO_INVALIDO"
    mensaje_por_defecto = "El archivo no es válido. Usa texto, PDF, PNG, JPEG o WebP."


class ContenidoNoPermitidoError(AppError):
    status_code = 422
    codigo = "CONTENIDO_NO_PERMITIDO"
    mensaje_por_defecto = "El archivo contiene material que no está permitido."


class RespuestasIncompletasError(AppError):
    status_code = 422
    codigo = "RESPUESTAS_INCOMPLETAS"
    mensaje_por_defecto = "Responde todas las preguntas del diagnóstico."


# 429
class SolicitudesExcesivasError(AppError):
    status_code = 429
    codigo = "DEMASIADAS_SOLICITUDES"
    mensaje_por_defecto = "Hiciste demasiadas solicitudes. Espera un momento e intenta de nuevo."


class LimiteUsoError(AppError):
    status_code = 429
    codigo = "LIMITE_USO"
    mensaje_por_defecto = "Se alcanzó el límite de uso disponible por hoy."


# 500 / 502
class CifradoError(AppError):
    status_code = 500
    codigo = "ERROR_INTERNO"


class LLMError(AppError):
    """Base de los fallos del modelo de lenguaje; permite capturarlos juntos (§13.3)."""

    status_code = 502
    codigo = "LLM_NO_DISPONIBLE"
    mensaje_por_defecto = "El tutor no está disponible en este momento. Intenta de nuevo."


class LLMNoConfiguradoError(LLMError):
    status_code = 500
    codigo = "LLM_NO_CONFIGURADO"
    mensaje_por_defecto = "El servicio de IA no está configurado correctamente."


class LLMNoDisponibleError(LLMError):
    status_code = 502
    codigo = "LLM_NO_DISPONIBLE"


class LLMRespuestaInvalidaError(LLMError):
    status_code = 502
    codigo = "LLM_RESPUESTA_INVALIDA"
    mensaje_por_defecto = "El tutor generó una respuesta inválida. Intenta de nuevo."


class AlmacenamientoError(AppError):
    status_code = 502
    codigo = "ALMACENAMIENTO_NO_DISPONIBLE"
    mensaje_por_defecto = "No pudimos guardar o leer el archivo. Intenta de nuevo."


class CorreoNoEnviadoError(AppError):
    status_code = 502
    codigo = "CORREO_NO_ENVIADO"
    mensaje_por_defecto = "No pudimos enviar el correo. Intenta de nuevo más tarde."


class PasarelaPagosError(AppError):
    status_code = 502
    codigo = "PASARELA_NO_DISPONIBLE"
    mensaje_por_defecto = "La pasarela de pagos no está disponible. Intenta más tarde."


class ProveedorNoDisponibleError(AppError):
    """Base de fallos internos de proveedores que el sistema degrada sin mostrar al estudiante."""

    status_code = 502
    codigo = "PROVEEDOR_NO_DISPONIBLE"
    mensaje_por_defecto = "Un servicio externo no está disponible."


class ImagenesNoDisponiblesError(ProveedorNoDisponibleError):
    pass


class GeneracionImagenError(ProveedorNoDisponibleError):
    pass


class FuentesNoDisponiblesError(ProveedorNoDisponibleError):
    pass


class VideosNoDisponiblesError(ProveedorNoDisponibleError):
    pass


class ModeracionNoDisponibleError(ProveedorNoDisponibleError):
    pass
