"""Imagem de capa gerada por IA (Cloudflare Workers AI, modelo FLUX.1 [schnell]), opcional e gratuita.

Plano gratuito: 10 000 «neurons» por dia; o FLUX.1 [schnell] custa 4,80 por bloco de 512×512 e 9,60 por passo,
ou seja, cerca de 58 por imagem de 1024×1024 com 4 passos. Acima da quota, no plano gratuito, o pedido falha
(não é cobrado) e o carrossel usa a capa tipográfica. Fontes: developers.cloudflare.com/workers-ai/platform/pricing/
e developers.cloudflare.com/workers-ai/models/flux-1-schnell/.
"""
from __future__ import annotations

import base64
import re
from io import BytesIO
from typing import Any, Callable, Mapping

import requests
from PIL import Image

from ..dedup import strip_accents

MODEL = "@cf/black-forest-labs/flux-1-schnell"
ENDPOINT = "https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}"
STEPS = 4

# Cena base por categoria (inglês: o modelo segue melhor instruções em inglês).
SCENES = {
    "combustiveis-petroleo": "an oil refinery and fuel storage tanks by the sea at dusk",
    "eletricidade-gas": "high-voltage transmission towers and gas pipelines across a landscape",
    "renovaveis-transicao": "wind turbines and solar panels on rolling hills",
    "regulacao-politica": "an abstract institutional building facade with energy infrastructure in the background",
    "dados-indicadores": "an abstract landscape of rising and falling geometric bars evoking energy data",
    "economia-investimento": "an abstract harbour with container ships and energy infrastructure",
}
DEFAULT_SCENE = "energy infrastructure in a wide landscape"

# Motivos detetados no título (sem traduzir o título: nenhum texto português chega ao modelo).
MOTIFS = [
    (("gas natural", "gas ", "gnl", "lng"), "natural gas storage tanks and pipelines"),
    (("petroleo", "brent", "crude", "barril"), "an oil tanker at sea"),
    (("combustive", "gasolina", "gasoleo", "diesel"), "a fuel station at dusk"),
    (("eletric", "rede eletrica", "tarifa"), "high-voltage power lines"),
    (("solar", "fotovolta"), "rows of solar panels"),
    (("eolic", "vento", "offshore"), "wind turbines"),
    (("hidrogenio", "hydrogen"), "a hydrogen electrolyser facility"),
    (("barragem", "hidric", "hidroel"), "a hydroelectric dam"),
    (("bateria", "armazenamento"), "storage tanks and battery containers"),
]
STYLE = ("editorial illustration, flat geometric shapes, muted navy blue and amber palette, soft light, "
         "wide composition with empty space at the top. No text, no letters, no numbers, no logos, no flags, "
         "no watermark, no people.")


def cover_enabled(editorial: dict[str, Any], env: Mapping[str, str]) -> bool:
    return bool(editorial["instagram"].get("ai_cover") and env.get("CF_ACCOUNT_ID") and env.get("CF_API_TOKEN"))


def build_prompt(article: dict[str, Any]) -> str:
    title = " " + re.sub(r"[^a-z0-9]+", " ", strip_accents(article.get("title", "").lower())) + " "
    motifs = [m for keys, m in MOTIFS if any(k in title for k in keys)][:2]
    scene = SCENES.get(article.get("category"), DEFAULT_SCENE)
    detail = f", featuring {' and '.join(motifs)}" if motifs else ""
    return f"{scene}{detail}. {STYLE}"


def generate_cover(article: dict[str, Any], env: Mapping[str, str], post: Callable = requests.post,
                   timeout: int = 90) -> Image.Image | None:
    """Devolve a imagem gerada, ou None em qualquer falha (sem credenciais, quota, rede, resposta inválida)."""
    account, token = env.get("CF_ACCOUNT_ID"), env.get("CF_API_TOKEN")
    if not account or not token:
        return None
    try:
        resp = post(ENDPOINT.format(account=account, model=MODEL),
                    headers={"Authorization": f"Bearer {token}"},
                    json={"prompt": build_prompt(article), "steps": STEPS}, timeout=timeout)
        data = resp.json()
        if resp.status_code != 200 or not data.get("success"):
            return None
        raw = base64.b64decode(data["result"]["image"], validate=True)
        im = Image.open(BytesIO(raw))
        im.load()
        return im.convert("RGB")
    except Exception:
        return None
