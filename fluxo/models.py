from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Source:
    id: str
    name: str
    institution: str
    url: str
    method: str
    bee_number: int | None = None
    extra: bool = False
    group: str = ""
    tier: int = 15
    lang: str = "en"
    enabled: bool = True
    feeds: list[str] = field(default_factory=list)
    listing_url: str | None = None
    link_pattern: str | None = None
    exclude_pattern: str | None = None
    title_filter: str | None = None
    date_in_url: bool = False
    mode: str | None = None
    frequency: str = ""
    licence: str = ""
    verified: str = ""
    notes: str = ""
    duplicate_of: str | None = None

    @property
    def collectable(self) -> bool:
        return self.enabled and self.method in {"rss", "html", "json"}


@dataclass
class Item:
    source_id: str
    title: str
    url: str
    published: str | None = None        # ISO 8601; None quando a fonte não indica
    collected_at: str = ""
    summary: str = ""
    date_inferred: bool = False         # True quando a data é a da 1.ª deteção
    id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Item":
        known = {k: d[k] for k in cls.__dataclass_fields__ if k in d}
        return cls(**known)


@dataclass
class Draft:
    """Artigo pronto a validar (notícia redigida ou peça de dados)."""
    kind: str                     # "noticia" | "dados"
    title: str
    lead: str
    body: str                     # Markdown
    category: str
    key_points: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    sources: list[dict[str, str]] = field(default_factory=list)   # {name, url, date}
    facts: list[dict[str, str]] = field(default_factory=list)     # {claim, evidence}
    ai: dict[str, Any] = field(default_factory=lambda: {"used": False})
    score: float | None = None
    event_date: str | None = None
    chart: str | None = None      # caminho relativo de um gráfico gerado
    slug: str = ""
