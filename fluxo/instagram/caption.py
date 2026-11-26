"""Legenda do Instagram no estilo «misto»: gancho, pontos-chave, apelo, fontes, ligação, hashtags."""
from __future__ import annotations

from typing import Any

LIMIT = 2200


def make_caption(article: dict[str, Any], site_base: str, hashtags: list[str],
                 style: dict[str, Any] | None = None, ai_cover: bool = False, ai_images: int = 0) -> str:
    style = style or {}
    domain = site_base.replace("https://", "").replace("http://", "").rstrip("/")
    emoji = (style.get("hook_emoji") or {}).get(article.get("category"), "")
    # O gancho é o próprio título (nunca reescrito: não se inventam factos), com um emoji opcional.
    head = f"{emoji} {article['title']}".strip() + "\n\n"
    points = "\n".join(f"• {k}" for k in article.get("key_points", [])[:4])
    sources = ", ".join(s["name"] for s in article.get("sources", []))
    cta = style.get("cta_caption", "")
    notes = []
    if (article.get("ai") or {}).get("used"):
        notes.append("Texto com apoio de inteligência artificial, verificado contra a fonte.")
    elif article.get("type") == "dados":
        notes.append("Peça gerada a partir de dados oficiais.")
    if ai_images > 1:
        notes.append("Imagens geradas por IA.")
    elif ai_cover or ai_images == 1:
        notes.append("Imagem de capa gerada por IA." if ai_cover else "Imagem gerada por IA.")
    link = f"{style.get('link_emoji', '')} Artigo completo em {domain} (ligação na bio).".strip()
    tail = [f"{style.get('cta_emoji', '')} {cta}".strip() if cta else "",
            "\n".join(x for x in [f"Fonte: {sources}." if sources else "", *notes] if x),
            link,
            " ".join(hashtags[:8])]
    tail_text = "\n\n".join(t for t in tail if t)
    room = LIMIT - len(head) - len(points) - len(tail_text) - 6
    lead = article.get("lead", "")
    if len(lead) > room:
        lead = lead[: max(0, room - 1)].rsplit(" ", 1)[0] + "…"
    return f"{head}{lead}\n\n{points}\n\n{tail_text}"[:LIMIT]
