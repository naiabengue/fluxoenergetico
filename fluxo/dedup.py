"""Normalização de URLs e deteção de acontecimentos repetidos."""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING = re.compile(r"^(utm_|_ga|gclid|fbclid|mc_|ref$)")

STOPWORDS = set("""
a o as os um uma uns umas de do da dos das em no na nos nas por para com sem sobre entre e ou que se ao aos à às
pelo pela pelos pelas é são foi ser mais menos até já não sua seu suas seus como the of and in on for to by with
from at an is are be as its this that new 2024 2025 2026 2027
""".split())


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not TRACKING.match(k)]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower() or "https", parts.netloc.lower(), path, urlencode(query), ""))


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def title_tokens(title: str) -> frozenset[str]:
    norm = strip_accents(title.lower())
    words = re.findall(r"[a-z0-9]+", norm)
    return frozenset(w for w in words if w not in STOPWORDS and len(w) > 2)


def similarity(a: str, b: str) -> float:
    ta, tb = title_tokens(a), title_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def cluster(items: list, threshold: float = 0.5, key=lambda it: it.title) -> list[list]:
    """Agrupa itens cujo título é semelhante (mesmo acontecimento). Mantém a ordem de entrada."""
    groups: list[list] = []
    for it in items:
        for g in groups:
            if any(similarity(key(it), key(other)) >= threshold for other in g):
                g.append(it)
                break
        else:
            groups.append([it])
    return groups
