from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any


def pick_for_week(articles: list[dict[str, Any]], now: datetime, n: int = 2, days: int = 7,
                  already_posted: set[str] | None = None) -> list[dict[str, Any]]:
    """Os n artigos mais bem pontuados dos últimos `days` dias que ainda não foram ao Instagram."""
    posted = already_posted or set()
    since = now.date() - timedelta(days=days)
    pool = []
    for a in articles:
        try:
            d = date.fromisoformat(str(a.get("date", ""))[:10])
        except ValueError:
            continue
        if d >= since and a.get("slug") not in posted:
            pool.append(a)
    pool.sort(key=lambda a: (a.get("score") if a.get("score") is not None else 80, str(a.get("date"))), reverse=True)
    return pool[:n]
