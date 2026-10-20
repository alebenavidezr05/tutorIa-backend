from typing import Any

import jwt

from app.exceptions.base import TokenInvalidoError

# El algoritmo lo fija el servidor: se rechaza `alg=none` y cualquier otro algoritmo.
ALGORITMO_JWT = "HS256"
CLAIMS_OBLIGATORIOS = ["sub", "exp", "iat", "jti", "ver"]


class FirmadorJwt:
    """Frontera con PyJWT: cualquier token ausente, vencido, alterado o mal firmado es inválido."""

    def __init__(self, secreto: str) -> None:
        self._secreto = secreto

    def firmar(self, claims: dict[str, Any]) -> str:
        return jwt.encode(claims, self._secreto, algorithm=ALGORITMO_JWT)

    def verificar(self, token: str) -> dict[str, Any]:
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                self._secreto,
                algorithms=[ALGORITMO_JWT],
                options={"require": CLAIMS_OBLIGATORIOS},
            )
        except jwt.PyJWTError as exc:
            raise TokenInvalidoError() from exc
        return claims
