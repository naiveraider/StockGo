from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session

from app.models.pick_cache import PickCache
from app.schemas.universe import LongTermIdeasResponse, ShortTermIdeasResponse
from app.services.long_term_ideas_service import generate_long_term_ideas
from app.services.short_term_ideas_service import generate_short_term_ideas


@dataclass(frozen=True)
class PickCacheDefinition:
    key: str
    title: str
    response_model: type[ShortTermIdeasResponse | LongTermIdeasResponse]


PICK_CACHE_DEFINITIONS: dict[str, PickCacheDefinition] = {
    "short_term_pick": PickCacheDefinition(
        key="short_term_pick",
        title="Short-term pick",
        response_model=ShortTermIdeasResponse,
    ),
    "long_term_pick": PickCacheDefinition(
        key="long_term_pick",
        title="Long-term pick",
        response_model=LongTermIdeasResponse,
    ),
}

SHORT_TERM_PICK_CONFIG = {"idea_count": 3, "candidate_pool_size": 12, "min_confidence": 0.65}
LONG_TERM_PICK_CONFIG = {"idea_count": 3, "candidate_pool_size": 15}


def list_pick_cache_keys() -> list[str]:
    return list(PICK_CACHE_DEFINITIONS.keys())


def get_pick_cache_definition(key: str) -> PickCacheDefinition:
    try:
        return PICK_CACHE_DEFINITIONS[key]
    except KeyError as exc:
        raise ValueError(f"Unsupported pick cache key: {key}") from exc


def _empty_payload() -> dict[str, Any]:
    return {"ideas": []}


def ensure_default_pick_caches(engine) -> None:
    with Session(engine) as session:
        changed = False
        for key in list_pick_cache_keys():
            existing = session.get(PickCache, key)
            if existing is None:
                session.add(
                    PickCache(
                        key=key,
                        generated_at=datetime.now(timezone.utc),
                        source_model=None,
                        fallback_used=True,
                        candidates_considered=0,
                        ideas=_empty_payload(),
                    )
                )
                changed = True
        if changed:
            session.commit()


def refresh_pick_cache(session: Session, key: str) -> PickCache:
    definition = get_pick_cache_definition(key)
    if key == "short_term_pick":
        result, model_used, fallback_used = generate_short_term_ideas(session, **SHORT_TERM_PICK_CONFIG)
    elif key == "long_term_pick":
        result, model_used, fallback_used = generate_long_term_ideas(session, **LONG_TERM_PICK_CONFIG)
    else:
        raise ValueError(f"Unsupported pick cache key: {key}")

    cache = session.get(PickCache, key)
    if cache is None:
        cache = PickCache(key=key)
    cache.generated_at = result.get("generated_at") or datetime.now(timezone.utc)
    cache.source_model = model_used
    cache.fallback_used = bool(fallback_used)
    cache.candidates_considered = int(result.get("candidates_considered") or 0)
    cache.ideas = {"ideas": result.get("ideas") or []}
    session.add(cache)
    session.commit()
    session.refresh(cache)
    return cache


def read_pick_cache(session: Session, key: str) -> ShortTermIdeasResponse | LongTermIdeasResponse:
    definition = get_pick_cache_definition(key)
    cache = session.get(PickCache, key)
    if cache is None:
        return definition.response_model(
            generated_at=datetime.now(timezone.utc),
            source_model=None,
            fallback_used=True,
            candidates_considered=0,
            ideas=[],
        )

    return definition.response_model(
        generated_at=cache.generated_at,
        source_model=cache.source_model,
        fallback_used=cache.fallback_used,
        candidates_considered=cache.candidates_considered,
        ideas=(cache.ideas or {}).get("ideas") or [],
    )