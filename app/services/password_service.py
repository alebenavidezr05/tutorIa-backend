import bcrypt

from app.validators.usuario import MAX_BYTES_BCRYPT

CONTRASENA_SENUELO = "contrasena-senuelo-0"


class PasswordService:
    def __init__(self, rondas: int) -> None:
        self._rondas = rondas
        # Hash de referencia para verificar aunque el correo no exista: tiempo de respuesta similar.
        self._hash_senuelo = self.hashear(CONTRASENA_SENUELO)

    def hashear(self, contrasena: str) -> str:
        return bcrypt.hashpw(contrasena.encode(), bcrypt.gensalt(rounds=self._rondas)).decode()

    def verificar(self, contrasena: str, hash_guardado: str | None) -> bool:
        objetivo = (hash_guardado or self._hash_senuelo).encode()
        # bcrypt 5 rechaza más de 72 bytes; al registrar ya se impide, aquí solo se acota.
        coincide = bcrypt.checkpw(contrasena.encode()[:MAX_BYTES_BCRYPT], objetivo)
        return coincide and hash_guardado is not None
