from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


class DatabaseManager:
    def __init__(self, database_url: str) -> None:
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self._engine: Engine = create_engine(database_url, future=True, connect_args=connect_args)
        self._session_factory: sessionmaker = sessionmaker(
            bind=self._engine,
            autoflush=False,
            autocommit=False,
            future=True,
        )

    @property
    def engine(self) -> Engine:
        return self._engine

    def create_session(self) -> Session:
        return self._session_factory()

    def dispose(self) -> None:
        self._engine.dispose()
