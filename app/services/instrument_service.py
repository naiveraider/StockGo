from __future__ import annotations

from sqlmodel import Session, select

from app.models.instrument import Instrument


def get_or_create_instrument(session: Session, ticker: str) -> Instrument:
    norm = ticker.strip().upper()
    inst = session.exec(select(Instrument).where(Instrument.ticker == norm)).first()
    if inst:
        return inst
    inst = Instrument(ticker=norm, exchange="US")
    session.add(inst)
    session.commit()
    session.refresh(inst)
    return inst

