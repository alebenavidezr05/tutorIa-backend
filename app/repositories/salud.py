from sqlalchemy import text
from sqlalchemy.orm import Session


class SaludRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def ping(self) -> int:
        return int(self._session.execute(text("SELECT 1")).scalar_one())
