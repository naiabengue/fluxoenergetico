"""Pontuação editorial (0–100) com condições de bloqueio que nenhuma pontuação compensa."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .dedup import strip_accents
from .models import Item, Source
from .store import parse_iso

EU_SOURCES = ("eurostat", "ecb", "eib", "gie")


@dataclass
class Score:
    total: float
    parts: dict[str, float]
    category: str | None
    blocked: list[str] = field(default_factory=list)
    decision: str = "rejeitar"     # candidato | rever | rejeitar


def _norm(text: str) -> str:
    return " " + strip_accents(text.lower()) + " "


def _hits(text: str, keywords: list[str]) -> int:
    return sum(1 for k in keywords if strip_accents(k.lower()) in text)


def excluded(text: str, keywords: list[str]) -> bool:
    """Palavra ou expressão inteira (sem acentos, minúsculas): «ENSE» não apanha «licensed»."""
    norm = strip_accents(text.lower())
    return any(re.search(rf"\b{re.escape(strip_accents(k.lower()))}\b", norm) for k in keywords)


def categorise(text: str, editorial: dict[str, Any]) -> tuple[str | None, int]:
    best, best_hits = None, 0
    for cid, cat in editorial["categories"].items():
        h = _hits(text, cat["keywords"])
        if h > best_hits:
            best, best_hits = cid, h
    return best, best_hits


def score(item: Item, source: Source, editorial: dict[str, Any], now: datetime) -> Score:
    sc = editorial["scoring"]
    w = sc["weights"]
    text = _norm(f"{item.title} {item.summary}")
    blocked: list[str] = []
    if not item.url:
        blocked.append("sem URL da fonte")
    if len(item.title.strip()) < sc.get("min_title_chars", 20):
        blocked.append("título insuficiente")
    if not source.enabled or source.method in {"tool", "manual"}:
        blocked.append("fonte não elegível")
    if excluded(f"{item.title} {item.summary}", editorial.get("excluded_keywords", [])):
        blocked.append("tema excluído")

    category, hits = categorise(text, editorial)
    energia = w["energia"] if hits >= 2 else (w["energia"] * 2 / 3 if hits == 1 else 0)

    credibilidade = min(source.tier, w["credibilidade"])

    ts = parse_iso(item.published) or parse_iso(item.collected_at)
    age_h = (now - ts).total_seconds() / 3600 if ts else 10**6
    novidade = 0
    for max_h, pts in sc["freshness_hours"]:
        if age_h <= max_h:
            novidade = pts
            break

    geo_cfg = editorial["geo"]
    if source.lang == "pt" or _hits(text, geo_cfg["pt_keywords"]):
        geografia = w["geografia"]
    elif source.id.startswith(EU_SOURCES) or _hits(text, geo_cfg["eu_keywords"]):
        geografia = round(w["geografia"] * 2 / 3)
    else:
        geografia = 0

    verificabilidade = w["verificabilidade"] if not item.date_inferred else w["verificabilidade"] / 2

    parts = {"energia": energia, "credibilidade": credibilidade, "novidade": novidade,
             "geografia": geografia, "verificabilidade": verificabilidade}
    total = sum(parts.values())
    if category and category not in editorial.get("core_categories", []):
        total -= editorial.get("non_core_penalty", 0)
    if hits == 0:
        blocked.append("sem relação com energia")

    th = sc["thresholds"]
    if blocked or total < th["review"]:
        decision = "rejeitar"
    elif total >= th["publish"]:
        decision = "candidato"
    else:
        decision = "rever"
    return Score(total=round(total, 1), parts=parts, category=category, blocked=blocked, decision=decision)
