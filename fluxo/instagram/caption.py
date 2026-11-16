from __future__ import annotations

from typing import Any

LIMIT = 2200


def make_caption(article: dict[str, Any], site_base: str, hashtags: list[str]) -> str:
    domain = site_base.replace("https://", "").replace("http://", "").rstrip("/")
    points = "\n".join(f"• {k}" for k in article.get("key_points", [])[:4])
    sources = ", ".join(s["name"] for s in article.get("sources", []))
    tail = [f"Fonte: {sources}." if sources else "",
            "Texto com apoio de inteligência artificial, verificado contra a fonte." if (article.get("ai") or {}).get("used") else "",
            f"Artigo completo em {domain} (ligação na bio).",
            " ".join(hashtags[:8])]
    tail_text = "\n\n".join(t for t in tail if t)
    head = f"{article['title']}\n\n"
    room = LIMIT - len(head) - len(points) - len(tail_text) - 6
    lead = article.get("lead", "")
    if len(lead) > room:
        lead = lead[: max(0, room - 1)].rsplit(" ", 1)[0] + "…"
    return f"{head}{lead}\n\n{points}\n\n{tail_text}"[:LIMIT]
