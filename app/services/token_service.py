import re
import uuid
from dataclasses import dataclass
from datetime import timedelta

from app.core.tiempo import ahora_utc
from app.crypto.jwt_firmador import FirmadorJwt
from app.exceptions.base import TokenInvalidoError

_PATRON_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


@dataclass(frozen=True)
class ClaimsSesion:
    id_usuario: uuid.UUID
    version_token: int


class TokenService:
    def __init__(self, firmador: FirmadorJwt, expira_minutos: int) -> None:
        self._firmador = firmador
        self._expira = timedelta(minutes=expira_minutos)

    def emitir(self, id_usuario: uuid.UUID, version_token: int) -> str:
        ahora = ahora_utc()
        return self._firmador.firmar(
            {
                "sub": str(id_usuario),
                "iat": int(ahora.timestamp()),
                "exp": int((ahora + self._expira).timestamp()),
                "jti": uuid.uuid4().hex,
                "ver": version_token,
            }
        )

    def leer(self, token: str | None) -> ClaimsSesion:
        if not token:
            raise TokenInvalidoError()
        claims = self._firmador.verificar(token)
        version = claims.get("ver")
        if not isinstance(version, int):
            raise TokenInvalidoError()
        return ClaimsSesion(id_usuario=self._id_desde(claims.get("sub")), version_token=version)

    def leer_id_usuario(self, token: str | None) -> uuid.UUID:
        return self.leer(token).id_usuario

    @staticmethod
    def _id_desde(sub: object) -> uuid.UUID:
        # Se valida el formato antes de construir el UUID para no depender de capturar ValueError.
        if not isinstance(sub, str) or not _PATRON_UUID.fullmatch(sub):
            raise TokenInvalidoError()
        return uuid.UUID(sub)
