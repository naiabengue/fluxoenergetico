"""Escrita de artigos em Markdown e regra de decisão (publicar / rever / rejeitar)."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .dedup import strip_accents
from .models import Draft


def slugify(text: str, max_len: int = 80) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", strip_accents(text.lower())).strip("-")
    return s[:max_len].rstrip("-")


def front_matter(draft: Draft, when: datetime) -> dict[str, Any]:
    return {
        "title": draft.title,
        "slug": draft.slug or slugify(draft.title),
        "date": when.date().isoformat(),
        "datetime": when.isoformat(timespec="minutes"),
        "type": draft.kind,
        "category": draft.category,
        "tags": draft.tags,
        "lead": draft.lead,
        "key_points": draft.key_points,
        "sources": draft.sources,
        "event_date": draft.event_date,
        "ai": draft.ai,
        "score": draft.score,
        "chart": draft.chart,
        "image": draft.image,
    }


def write_article(draft: Draft, root: Path, when: datetime, folder: str = "content/articles") -> Path:
    meta = front_matter(draft, when)
    path = Path(root) / folder / f"{when:%Y}" / f"{when:%m}" / f"{meta['slug']}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False)
    path.write_text(f"---\n{fm}---\n\n{draft.body.strip()}\n", encoding="utf-8")
    return path


def decide(draft: Draft, validation, score_decision: str, editorial: dict[str, Any]) -> str:
    """publicar | rever | rejeitado. A validação falhada bloqueia sempre."""
    if not validation.ok:
        return "rejeitado"
    policy = editorial["policy"]
    if draft.kind == "dados":
        return "publicar" if policy.get("auto_publish_data", True) else "rever"
    if score_decision == "rejeitar":
        return "rejeitado"
    if policy.get("auto_publish_news") and score_decision == "candidato":
        return "publicar"
    return "rever"
