from app.exceptions.base import ModeracionNoDisponibleError
from app.moderacion.base import ModeradorClient, ResultadoModeracion

PUNTAJE_MARCADO = 0.99
# Disparadores deterministas para desarrollo y pruebas, sin red.
DISPARADORES = {
    "quiero hacerme daño": "self-harm",
    "contenido sexual": "sexual",
    "quiero golpear a alguien": "violence",
}


class FakeModeradorClient(ModeradorClient):
    def __init__(self) -> None:
        self.imagen_marcada = False
        self.no_disponible = False

    def moderar_texto(self, texto: str) -> ResultadoModeracion:
        self._verificar_disponible()
        minusculas = texto.lower()
        categorias = {
            cat: PUNTAJE_MARCADO for frase, cat in DISPARADORES.items() if frase in minusculas
        }
        return ResultadoModeracion(marcado=bool(categorias), categorias=categorias)

    def moderar_imagen(self, contenido: bytes, mime: str) -> ResultadoModeracion:
        self._verificar_disponible()
        if self.imagen_marcada:
            return ResultadoModeracion(marcado=True, categorias={"sexual": PUNTAJE_MARCADO})
        return ResultadoModeracion(marcado=False)

    def _verificar_disponible(self) -> None:
        if self.no_disponible:
            raise ModeracionNoDisponibleError()
