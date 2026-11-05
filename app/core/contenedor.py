"""Clientes únicos de proceso, creados en el lifespan y reutilizados por todas las peticiones."""

from dataclasses import dataclass

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.almacen.base import Almacen
from app.almacen.factory import crear_almacen
from app.core.config import Settings
from app.core.database import crear_engine, crear_fabrica_sesiones
from app.correo.base import CorreoClient
from app.correo.factory import crear_correo_client
from app.crypto.indice_ciego import IndiceCiego
from app.crypto.jwt_firmador import FirmadorJwt
from app.fuentes.base import FuentesClient
from app.fuentes.registro import construir_fuentes
from app.imagenes.base import (
    DescargadorImagenes,
    ImagenesClient,
    ImagenesIAClient,
    ProcesadorImagenes,
)
from app.imagenes.factory import crear_descargador, crear_imagenes_ia_client
from app.imagenes.procesador import ProcesadorPillow
from app.imagenes.registro import construir_imagenes
from app.legal import TextosLegales, cargar_textos_legales
from app.llm.base import LLMClient
from app.llm.factory import crear_llm_client
from app.moderacion.base import ModeradorClient
from app.moderacion.factory import crear_moderador
from app.pagos.base import PasarelaPagos
from app.pagos.factory import crear_pasarela
from app.services.password_service import PasswordService
from app.videos.base import VideosClient
from app.videos.factory import crear_videos_client


@dataclass
class Contenedor:
    settings: Settings
    engine: Engine
    fabrica_sesiones: sessionmaker[Session]
    llm: LLMClient
    moderador: ModeradorClient
    fuentes: list[FuentesClient]
    imagenes: list[ImagenesClient]
    imagenes_ia: ImagenesIAClient
    descargador: DescargadorImagenes
    procesador: ProcesadorImagenes
    videos: VideosClient
    almacen: Almacen
    correo: CorreoClient
    pasarela: PasarelaPagos | None
    indice: IndiceCiego
    firmador: FirmadorJwt
    passwords: PasswordService
    textos_legales: TextosLegales

    def cerrar(self) -> None:
        self.llm.cerrar()
        self.moderador.cerrar()
        self.imagenes_ia.cerrar()
        self.descargador.cerrar()
        self.videos.cerrar()
        self.correo.cerrar()
        self.almacen.cerrar()
        for fuente in self.fuentes:
            fuente.cerrar()
        for coleccion in self.imagenes:
            coleccion.cerrar()
        self.engine.dispose()


def crear_contenedor(settings: Settings) -> Contenedor:
    engine = crear_engine(settings)
    procesador = ProcesadorPillow()
    return Contenedor(
        settings=settings,
        engine=engine,
        fabrica_sesiones=crear_fabrica_sesiones(engine),
        llm=crear_llm_client(settings),
        moderador=crear_moderador(settings),
        fuentes=construir_fuentes(settings),
        imagenes=construir_imagenes(settings),
        imagenes_ia=crear_imagenes_ia_client(settings),
        descargador=crear_descargador(settings, procesador),
        procesador=procesador,
        videos=crear_videos_client(settings),
        almacen=crear_almacen(settings),
        correo=crear_correo_client(settings),
        pasarela=crear_pasarela(settings),
        indice=IndiceCiego(settings.indice_ciego_clave.get_secret_value()),
        firmador=FirmadorJwt(settings.jwt_secret.get_secret_value()),
        passwords=PasswordService(settings.bcrypt_rounds),
        textos_legales=cargar_textos_legales(settings.politica_version),
    )
