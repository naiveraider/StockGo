from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote_plus

import feedparser
import httpx
from dateutil import parser as dtparser
from sqlmodel import Session, select

from app.models.news import NewsItem
from app.services.sentiment_service import score_sentiment


def google_news_rss_url(query: str) -> str:
    # US English, US region
    return f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"


def _parse_published(entry) -> Optional[datetime]:
    for key in ("published", "updated"):
        val = getattr(entry, key, None)
        if not val:
            continue
        try:
            dt = dtparser.parse(val)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue
    return None


def fetch_google_news_entries(query: str, *, timeout_s: float = 10.0) -> list[dict]:
    url = google_news_rss_url(query)
    with httpx.Client(timeout=timeout_s, headers={"User-Agent": "StockGo/0.1"}) as client:
        resp = client.get(url)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)

    out: list[dict] = []
    for e in getattr(feed, "entries", []) or []:
        title = (getattr(e, "title", "") or "").strip()
        link = (getattr(e, "link", "") or "").strip()
        if not title or not link:
            continue
        published_at = _parse_published(e)
        out.append(
            {
                "title": title,
                "url": link,
                "published_at": published_at,
            }
        )
    return out


def get_last_news_published_at(session: Session, *, instrument_id: int) -> Optional[datetime]:
    item = session.exec(
        select(NewsItem)
        .where(NewsItem.instrument_id == instrument_id, NewsItem.published_at.is_not(None))
        .order_by(NewsItem.published_at.desc())
        .limit(1)
    ).first()
    if not item or not item.published_at:
        return None
    dt = item.published_at
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def upsert_news_items(
    session: Session,
    *,
    instrument_id: int,
    entries: list[dict],
    start: datetime,
    end: datetime,
) -> int:
    if not entries:
        return 0

    entry_urls = [e["url"] for e in entries if e.get("url")]
    existing_urls = set()
    if entry_urls:
        existing_urls = set(session.exec(select(NewsItem.url).where(NewsItem.url.in_(entry_urls))).all())
    to_add: list[NewsItem] = []

    for e in entries:
        url = e["url"]
        if url in existing_urls:
            continue
        published_at: Optional[datetime] = e.get("published_at")
        if published_at and (published_at < start or published_at > end):
            continue

        title = e["title"]
        source = None
        # Common pattern: "Headline - Source"
        if " - " in title:
            maybe_head, maybe_src = title.rsplit(" - ", 1)
            if len(maybe_src) <= 40:
                title = maybe_head.strip()
                source = maybe_src.strip()

        label, score, model = score_sentiment(title)
        to_add.append(
            NewsItem(
                instrument_id=instrument_id,
                published_at=published_at,
                source=source,
                title=title[:512],
                summary=None,
                # Column is VARCHAR(512); enforce hard limit when inserting.
                url=url[:512],
                lang="en",
                sentiment_label=label,
                sentiment_score=score,
                sentiment_model=model,
            )
        )

    if not to_add:
        return 0
    session.add_all(to_add)
    session.commit()
    return len(to_add)

