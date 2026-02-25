from __future__ import annotations

from sqlmodel import SQLModel

from app.db.engine import get_engine
from app.db.migrate import ensure_instruments_is_etf_column


def init_db() -> None:
    # Ensure models are imported so metadata is populated
    import app.models  # noqa: F401

    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    ensure_instruments_is_etf_column(engine)

