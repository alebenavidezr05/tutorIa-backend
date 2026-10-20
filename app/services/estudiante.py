"""Datos derivados del estudiante que varios casos de uso necesitan para adaptar el contenido."""

from dataclasses import dataclass

from app.core.config import Settings
from app.core.tiempo import hoy_utc
from app.models.enums import GrupoEdad, TipoNivel
from app.models.usuario import Usuario
from app.validators.edad import es_menor, grupo_edad


@dataclass(frozen=True)
class PerfilEstudiante:
    tipo_nivel: TipoNivel
    nivel_educativo: str
    grupo_edad: GrupoEdad
    es_menor: bool


def perfil_estudiante(usuario: Usuario, settings: Settings) -> PerfilEstudiante:
    hoy = hoy_utc()
    return PerfilEstudiante(
        tipo_nivel=usuario.tipo_nivel,
        nivel_educativo=usuario.nivel_educativo,
        grupo_edad=grupo_edad(usuario.fecha_nacimiento, hoy, settings.edad_mayoria),
        es_menor=es_menor(usuario.fecha_nacimiento, hoy, settings.edad_mayoria),
    )
