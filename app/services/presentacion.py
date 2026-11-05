"""Conversión de entidades a schemas públicos, compartida por varios services."""

from datetime import date

from app.llm.politica_nivel import politica_de
from app.models.actividad import Actividad
from app.models.archivo_adjunto import ArchivoAdjunto
from app.models.conversacion import Conversacion
from app.models.fuente import Fuente
from app.models.usuario import Usuario
from app.schemas.actividad import ActividadPublica
from app.schemas.archivo import ArchivoPublico
from app.schemas.conversacion import ConversacionPublica
from app.schemas.fuente import FuentePublica
from app.schemas.usuario import UsuarioPublico
from app.validators.edad import es_menor


def usuario_publico(usuario: Usuario, hoy: date, edad_mayoria: int) -> UsuarioPublico:
    return UsuarioPublico(
        id_usuario=usuario.id_usuario,
        nombre=usuario.nombre,
        correo=usuario.correo,
        tipo_nivel=usuario.tipo_nivel,
        nivel_educativo=usuario.nivel_educativo,
        estado_cuenta=usuario.estado_cuenta,
        es_menor=es_menor(usuario.fecha_nacimiento, hoy, edad_mayoria),
        correo_verificado=usuario.correo_verificado,
        fecha_registro=usuario.fecha_registro,
    )


def fuente_publica(fuente: Fuente) -> FuentePublica:
    return FuentePublica.model_validate(fuente)


def archivo_publico(archivo: ArchivoAdjunto) -> ArchivoPublico:
    return ArchivoPublico(
        id_archivo=archivo.id_archivo,
        nombre=archivo.nombre_original,
        mime=archivo.mime,
        tamano_bytes=archivo.tamano_bytes,
    )


def actividad_publica(actividad: Actividad, archivo: ArchivoAdjunto | None) -> ActividadPublica:
    return ActividadPublica(
        id_actividad=actividad.id_actividad,
        numero_orden=actividad.numero_orden,
        enunciado=actividad.enunciado,
        respuesta_usuario=actividad.respuesta_usuario,
        archivo=archivo_publico(archivo) if archivo else None,
        estado=actividad.estado,
        fecha_completado=actividad.fecha_completado,
    )


def conversacion_publica(conversacion: Conversacion) -> ConversacionPublica:
    return ConversacionPublica(
        id_conversacion=conversacion.id_conversacion,
        tema=conversacion.tema,
        estado=conversacion.estado,
        nivel_cognitivo=conversacion.nivel_cognitivo,
        id_plan=conversacion.id_plan,
        acepta_archivos=politica_de(conversacion.nivel_cognitivo).permite_archivos,
        fecha_inicio=conversacion.fecha_inicio,
        fecha_ultimo_mensaje=conversacion.fecha_ultimo_mensaje,
    )
