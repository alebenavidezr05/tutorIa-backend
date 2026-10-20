import json
from datetime import date
from typing import Any

from sqlalchemy import Dialect, Text
from sqlalchemy.types import TypeDecorator

from app.crypto.registro import registro_cifrador


class TextoCifrado(TypeDecorator[str]):
    """Texto cifrado con AES-GCM; el AAD `tabla.columna` impide mover un valor a otra columna."""

    impl = Text
    cache_ok = True

    def __init__(self, aad: str) -> None:
        super().__init__()
        self.aad = aad

    def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return registro_cifrador.obtener().cifrar(value, self.aad)

    def process_result_value(self, value: str | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return registro_cifrador.obtener().descifrar(value, self.aad)


class JsonCifrado(TypeDecorator[Any]):
    impl = Text
    cache_ok = True

    def __init__(self, aad: str) -> None:
        super().__init__()
        self.aad = aad

    def process_bind_param(self, value: Any, dialect: Dialect) -> str | None:
        if value is None:
            return None
        serializado = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        return registro_cifrador.obtener().cifrar(serializado, self.aad)

    def process_result_value(self, value: str | None, dialect: Dialect) -> Any:
        if value is None:
            return None
        return json.loads(registro_cifrador.obtener().descifrar(value, self.aad))


class FechaCifrada(TypeDecorator[date]):
    impl = Text
    cache_ok = True

    def __init__(self, aad: str) -> None:
        super().__init__()
        self.aad = aad

    def process_bind_param(self, value: date | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return registro_cifrador.obtener().cifrar(value.isoformat(), self.aad)

    def process_result_value(self, value: str | None, dialect: Dialect) -> date | None:
        if value is None:
            return None
        return date.fromisoformat(registro_cifrador.obtener().descifrar(value, self.aad))
