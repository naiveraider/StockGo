from __future__ import annotations

from collections.abc import Generator

from sqlmodel import Session

from app.db.engine import get_engine


def get_session() -> Generator[Session, None, None]:
    engine = get_engine()
    with Session(engine) as session:
        yield session

