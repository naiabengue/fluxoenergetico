"""Monitorização de páginas HTML sem feed: links que cumprem um padrão, ou alteração da página."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..models import Item, Source

MONTHS = {
    "jan": 1, "janeiro": 1, "january": 1, "fev": 2, "feb": 2, "fevereiro": 2, "february": 2,
    "mar": 3, "março": 3, "marco": 3, "march": 3, "abr": 4, "apr": 4, "abril": 4, "april": 4,
    "mai": 5, "may": 5, "maio": 5, "jun": 6, "junho": 6, "june": 6, "jul": 7, "julho": 7, "july": 7,
    "ago": 8, "aug": 8, "agosto": 8, "august": 8, "set": 9, "sep": 9, "sept": 9, "setembro": 9,
    "september": 9, "out": 10, "oct": 10, "outubro": 10, "october": 10, "nov": 11, "novembro": 11,
    "november": 11, "dez": 12, "dec": 12, "dezembro": 12, "december": 12,
}
RE_NUMERIC = re.compile(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](20\d\d)\b")
RE_ISO = re.compile(r"\b(20\d\d)-(\d{2})-(\d{2})\b")
RE_TEXT = re.compile(r"\b(\d{1,2})(?:\.º)?\s+(?:de\s+)?([A-Za-zçÇ]{3,9})\.?\s+(?:de\s+)?(20\d\d)\b", re.I)
RE_URL_DATE = re.compile(r"/(20\d\d)/(\d{2})/(\d{2})/")
MAX_ITEMS = 40


def _safe_date(y: int, m: int, d: int) -> datetime | None:
    try:
        return datetime(y, m, d, 12, tzinfo=timezone.utc)
    except ValueError:
        return None


def find_date(text: str) -> datetime | None:
    m = RE_ISO.search(text)
    if m:
        return _safe_date(int(m[1]), int(m[2]), int(m[3]))
    m = RE_NUMERIC.search(text)
    if m:
        return _safe_date(int(m[3]), int(m[2]), int(m[1]))
    for m in RE_TEXT.finditer(text):
        month = MONTHS.get(m[2].lower())
        if month:
            return _safe_date(int(m[3]), month, int(m[1]))
    return None


def _context_text(anchor) -> str:
    """Texto à volta do link (até dois níveis acima), onde costuma estar a data."""
    node, parts = anchor, []
    for _ in range(2):
        node = node.parent
        if node is None or node.name in ("body", "html", "[document]"):
            break
        parts.append(node.get_text(" ", strip=True))
    return " ".join(parts)[:400]


def parse_listing(html: str, source: Source, page_url: str, now: datetime) -> list[Item]:
    soup = BeautifulSoup(html, "html.parser")
    pattern = re.compile(source.link_pattern) if source.link_pattern else None
    exclude = re.compile(source.exclude_pattern) if source.exclude_pattern else None
    seen: set[str] = set()
    items: list[Item] = []
    for a in soup.find_all("a", href=True):
        url = urljoin(page_url, a["href"].strip()).split("#")[0]
        if url in seen or (pattern and not pattern.search(url)) or (exclude and exclude.search(url)):
            continue
        title = re.sub(r"\s+", " ", a.get_text(" ", strip=True) or a.get("title", "")).strip()
        if len(title) < 15:
            continue
        seen.add(url)
        if source.date_in_url and (m := RE_URL_DATE.search(url)):
            date = _safe_date(int(m[1]), int(m[2]), int(m[3]))
        else:
            date = find_date(_context_text(a).replace(title, " "))
        items.append(Item(source_id=source.id, title=title, url=url,
                          published=date.isoformat() if date else None,
                          collected_at=now.isoformat(), date_inferred=date is None))
        if len(items) >= MAX_ITEMS:
            break
    return items


def parse_pagehash(html: str, source: Source, page_url: str, now: datetime) -> list[Item]:
    """Para páginas sem links individuais: um item por cada versão diferente da listagem."""
    soup = BeautifulSoup(html, "html.parser")
    root = soup.find("main") or soup.body or soup
    text = re.sub(r"\s+", " ", root.get_text(" ", strip=True))
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    date = find_date(text)
    return [Item(source_id=source.id, title=f"{source.name}: página de notícias atualizada",
                 url=f"{page_url}#v-{digest}", published=date.isoformat() if date else None,
                 collected_at=now.isoformat(), summary=text[:500], date_inferred=date is None)]
