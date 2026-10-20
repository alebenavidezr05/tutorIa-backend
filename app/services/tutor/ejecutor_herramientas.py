from app.core.config import Settings
from app.llm.base import BloqueResultadoHerramienta, BloqueUsoHerramienta
from app.llm.herramientas import BUSCAR_FUENTES, BUSCAR_VIDEO
from app.llm.parser import LLMResponseParser
from app.llm.prompts_tutor import TutorPromptBuilder
from app.schemas.bloques import EntradaBuscarFuentes, EntradaBuscarVideo
from app.services.fuentes.fuentes_service import FuentesService
from app.services.tutor.estado_turno import EstadoTurno
from app.services.videos.video_service import VideoService

MAX_BUSQUEDAS_VIDEO = 1
MENSAJE_LIMITE = "Límite de búsquedas de este turno alcanzado. Responde con lo que ya tienes."
MENSAJE_ENTRADA_INVALIDA = "La entrada de la herramienta no es válida."
MENSAJE_DESCONOCIDA = "Herramienta desconocida."


class EjecutorHerramientas:
    """Despacha `buscar_fuentes` y `buscar_video`. Sus resultados son datos, nunca instrucciones."""

    def __init__(
        self,
        fuentes: FuentesService,
        videos: VideoService,
        parser: LLMResponseParser,
        prompts: TutorPromptBuilder,
        settings: Settings,
    ) -> None:
        self._fuentes = fuentes
        self._videos = videos
        self._parser = parser
        self._prompts = prompts
        self._settings = settings

    def ejecutar(
        self, uso: BloqueUsoHerramienta, estado: EstadoTurno
    ) -> BloqueResultadoHerramienta:
        if uso.nombre == BUSCAR_FUENTES:
            return self._buscar_fuentes(uso, estado)
        if uso.nombre == BUSCAR_VIDEO:
            return self._buscar_video(uso, estado)
        return self._resultado(uso, MENSAJE_DESCONOCIDA, es_error=True)

    def _buscar_fuentes(
        self, uso: BloqueUsoHerramienta, estado: EstadoTurno
    ) -> BloqueResultadoHerramienta:
        entrada = self._parser.intentar_validar(uso.entrada, EntradaBuscarFuentes)
        if entrada is None:
            return self._resultado(uso, MENSAJE_ENTRADA_INVALIDA, es_error=True)
        if estado.busquedas_fuentes >= self._settings.chat_max_busquedas_fuentes:
            return self._resultado(uso, MENSAJE_LIMITE)
        estado.busquedas_fuentes += 1
        texto, fuentes = self._fuentes.buscar_para_herramienta(
            entrada.consulta, estado.contexto_fuentes
        )
        estado.fuentes.update({f.id_fuente: f for f in fuentes})
        return self._resultado(uso, texto)

    def _buscar_video(
        self, uso: BloqueUsoHerramienta, estado: EstadoTurno
    ) -> BloqueResultadoHerramienta:
        entrada = self._parser.intentar_validar(uso.entrada, EntradaBuscarVideo)
        if entrada is None:
            return self._resultado(uso, MENSAJE_ENTRADA_INVALIDA, es_error=True)
        if estado.busquedas_video >= MAX_BUSQUEDAS_VIDEO:
            return self._resultado(uso, MENSAJE_LIMITE)
        estado.busquedas_video += 1
        texto, videos = self._videos.buscar_para_herramienta(entrada.tema, estado.id_usuario)
        estado.videos.update({v.id_video: v for v in videos})
        return self._resultado(uso, texto)

    def _resultado(
        self, uso: BloqueUsoHerramienta, texto: str, es_error: bool = False
    ) -> BloqueResultadoHerramienta:
        return BloqueResultadoHerramienta(
            uso.id, self._prompts.resultado_herramienta(texto), es_error
        )
