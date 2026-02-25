from __future__ import annotations

from datetime import date, datetime, time, timezone


def as_utc_dt(d: date | datetime, *, end_of_day: bool = False) -> datetime:
    if isinstance(d, datetime):
        if d.tzinfo is None:
            return d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)

    t = time(23, 59, 59) if end_of_day else time(0, 0, 0)
    return datetime.combine(d, t, tzinfo=timezone.utc)

