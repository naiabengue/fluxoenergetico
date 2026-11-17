from __future__ import annotations

import re
from calendar import timegm
from datetime import datetime, timezone

import feedparser
from bs4 import BeautifulSoup

from ..models import Item, Source

MAX_ITEMS_PER_FEED = 30


def _clean(html: str, limit: int = 500) -> str:
    text = BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text)[:limit]


def parse_feed(text: str, source: Source, now: datetime) -> list[Item]:
    feed = feedparser.parse(text)
    items: list[Item] = []
    flt = re.compile(source.title_filter) if source.title_filter else None
    for e in feed.entries[:MAX_ITEMS_PER_FEED]:
        title = re.sub(r"\s+", " ", e.get("title", "")).strip()
        link = e.get("link", "").split("#")[0]
        if not title or not link or (flt and not flt.search(title)):
            continue
        parsed = e.get("published_parsed") or e.get("updated_parsed")
        published = (datetime.fromtimestamp(timegm(parsed), tz=timezone.utc).isoformat()
                     if parsed else None)
        items.append(Item(source_id=source.id, title=title, url=link, published=published,
                          collected_at=now.isoformat(), summary=_clean(e.get("summary", "")),
                          date_inferred=published is None))
    return items
