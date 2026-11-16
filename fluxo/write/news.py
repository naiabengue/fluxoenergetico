"""Redação de notícias com IA, ancorada no texto da fonte."""
from __future__ import annotations

from typing import Any, Callable, Mapping

import requests

from ..llm import generate_json
from ..models import Draft, Source

SYSTEM = """És o editor do Fluxo Energético, publicação digital sobre energia em Portugal e na União Europeia.
Escreves em português europeu (norma de Portugal, Acordo Ortográfico de 1990), com rigor técnico e linguagem clara.
Regras obrigatórias:
1. Usa APENAS factos que estejam no TEXTO DA FONTE. Não acrescentes números, datas, nomes ou citações que não estejam lá.
2. Escreve com palavras tuas. Nunca copies mais de 8 palavras seguidas da fonte.
3. Cada número que escreveres tem de aparecer na fonte com o mesmo valor (podes arredondar a 1 casa decimal).
4. Distingue factos de interpretação: a secção "Porque importa" pode interpretar, mas sem previsões nem certezas.
5. Não uses adjetivos sensacionalistas.
Responde só com JSON válido."""

PROMPT = """FONTE: {institution} — {source_name}
URL: {url}
DATA DA FONTE: {published}
TÍTULO ORIGINAL: {title}

TEXTO DA FONTE:
\"\"\"
{text}
\"\"\"

Produz um JSON com estas chaves:
- "title": título informativo em português, 40 a 100 caracteres;
- "lead": uma frase de 20 a 45 palavras com o essencial;
- "body_markdown": 180 a 450 palavras em Markdown com exatamente estas secções: "## O que aconteceu", "## Contexto", "## Porque importa para Portugal e a UE";
- "key_points": lista de 3 a 5 frases curtas;
- "category": uma de {categories};
- "tags": até 5 etiquetas em minúsculas;
- "facts": 2 a 5 objetos {{"claim": "afirmação do teu texto", "evidence": "excerto LITERAL da fonte, com 6 a 30 palavras, que a prova"}};
- "event_date": data do acontecimento (AAAA-MM-DD) se a fonte a indicar, senão null;
- "suitable": false se a fonte não tiver informação suficiente para um artigo rigoroso, senão true."""


def draft_news(item: dict[str, Any], source: Source, source_text: str, editorial: dict[str, Any],
               env: Mapping[str, str] | None = None, post: Callable = requests.post) -> Draft | None:
    prompt = PROMPT.format(institution=source.institution, source_name=source.name, url=item["url"],
                           published=item.get("published") or "não indicada", title=item["title"],
                           text=source_text[:12000], categories=", ".join(editorial["categories"]))
    data = generate_json(SYSTEM, prompt, editorial["llm"], env=env, post=post)
    if not data or not data.get("suitable", True):
        return None
    required = ("title", "lead", "body_markdown", "key_points", "category", "facts")
    if any(k not in data for k in required):
        return None
    return Draft(kind="noticia", title=str(data["title"]).strip(), lead=str(data["lead"]).strip(),
                 body=str(data["body_markdown"]).strip(), category=str(data["category"]).strip(),
                 key_points=[str(k).strip() for k in data["key_points"]][:5],
                 tags=[str(t).strip().lower() for t in data.get("tags", [])][:5],
                 sources=[{"name": f"{source.institution} — {source.name}", "url": item["url"],
                           "date": (item.get("published") or "")[:10]}],
                 facts=[{"claim": str(f.get("claim", "")), "evidence": str(f.get("evidence", ""))}
                        for f in data["facts"] if isinstance(f, dict)],
                 ai={"used": True, "provider": data["_provider"], "model": data["_model"], "reviewed": False},
                 event_date=data.get("event_date") or None)
