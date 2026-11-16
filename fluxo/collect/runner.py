from __future__ import annotations

from datetime import datetime
from typing import Any

from ..config import Config
from ..store import Store
from .html import parse_listing, parse_pagehash
from .rss import parse_feed


def targets(source) -> list[str]:
    if source.method == "rss":
        return list(source.feeds)
    return [source.listing_url or source.url]


def collect_source(source, fetcher, now: datetime) -> tuple[list, list[str]]:
    items, errors = [], []
    for url in targets(source):
        resp = fetcher.get(url)
        if resp is None:
            errors.append(f"{url}: {fetcher.errors.get(url, 'falha')}")
            continue
        if source.method == "rss":
            items += parse_feed(resp.text, source, now)
        elif source.mode == "pagehash":
            items += parse_pagehash(resp.text, source, url, now)
        else:
            items += parse_listing(resp.text, source, resp.url or url, now)
    return items, errors


def collect_all(cfg: Config, store: Store, fetcher, now: datetime) -> dict[str, Any]:
    """Recolhe todas as fontes ativas. Uma fonte em falha nunca interrompe as outras."""
    stats: dict[str, Any] = {"sources": {}, "new": 0, "dup": 0, "ok": 0, "failed": 0}
    for source in cfg.sources:
        if not source.collectable:
            continue
        try:
            items, errors = collect_source(source, fetcher, now)
        except Exception as exc:  # erro inesperado de parsing
            items, errors = [], [f"{type(exc).__name__}: {exc}"[:200]]
        new, dup = store.add_items(items)
        status = "erro" if errors and not items else ("parcial" if errors else "ok")
        stats["sources"][source.id] = {"status": status, "found": len(items), "new": new,
                                       "dup": dup, "errors": errors}
        stats["new"] += new
        stats["dup"] += dup
        stats["failed" if status == "erro" else "ok"] += 1
    return stats
