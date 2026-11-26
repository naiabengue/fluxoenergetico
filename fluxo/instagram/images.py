"""Imagens geradas por IA para todos os diapositivos do carrossel (Cloudflare Workers AI, plano gratuito).

Fluxo, diapositivo a diapositivo:
1. a IA de texto (Gemini) lê o artigo e descreve, em inglês, uma cena concreta por diapositivo (capa + pontos);
   sem IA de texto, ou com resposta inválida, usa cenas fixas por categoria e por palavras-chave;
2. o modelo de imagem desenha a cena, sem texto (o texto é escrito depois pelo código, em render.py);
3. a IA de texto vê a imagem e recusa-a se tiver letras, pessoas, bandeiras, logótipos ou mapas;
   recusada → nova tentativa com outra semente; sem verificação disponível → a imagem é aceite;
4. sem imagem válida, o diapositivo fica tipográfico. Nunca bloqueia a publicação.

Quotas do plano gratuito: 10 000 neurons por dia (renovados às 00:00 UTC); acima disso o pedido falha e não é
cobrado. FLUX.1 [schnell]: 4,80 neurons por bloco de 512×512 + 9,60 por passo (1024×1024, 8 passos ≈ 96).
FLUX.2 [klein] 4B: 26,05 neurons por bloco de saída (1024×1024 ≈ 104). Fonte:
developers.cloudflare.com/workers-ai/platform/pricing/ (consultado a 26/11/2026).
"""
from __future__ import annotations

import base64
import re
import zlib
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any, Callable, Mapping

import requests
from PIL import Image

from ..dedup import strip_accents
from ..llm import generate_json
from .cover_image import DEFAULT_SCENE, ENDPOINT, MOTIFS, SCENES, STYLE

MODELS = {
    "flux-1-schnell": {"id": "@cf/black-forest-labs/flux-1-schnell", "form": False},
    "flux-2-klein-4b": {"id": "@cf/black-forest-labs/flux-2-klein-4b", "form": True},
}
DEFAULTS = {"enabled": False, "slides": "all", "model": "flux-1-schnell", "steps": 8, "size": 1024,
            "max_attempts": 2, "max_generations": 14, "check": True}

# Cenas de reserva por categoria (variam de diapositivo para diapositivo).
VARIANTS = {
    "combustiveis-petroleo": ["an oil tanker sailing on a calm sea", "fuel storage tanks at a coastal terminal",
                              "a fuel station on an empty road at dusk", "a refinery skyline with distillation towers",
                              "pipelines running across a dry landscape"],
    "eletricidade-gas": ["high-voltage transmission towers across open fields",
                         "an electrical substation with transformers", "large spherical gas storage tanks",
                         "a gas pipeline crossing a green valley", "a town at dusk with lit windows and power lines"],
    "renovaveis-transicao": ["wind turbines on rolling hills", "rows of solar panels in a field",
                             "a hydroelectric dam in a green valley", "offshore wind turbines at sea",
                             "battery storage containers next to a solar farm"],
    "regulacao-politica": ["an abstract institutional building facade with columns",
                           "a set of balanced scales next to a small wind turbine model",
                           "an empty meeting room with a long table and chairs",
                           "a modern office building with power lines in the background",
                           "a closed padlock resting on an electricity meter"],
    "dados-indicadores": ["an abstract landscape of geometric columns of different heights",
                          "a magnifying glass over abstract geometric shapes",
                          "flowing lines of light over a quiet industrial landscape",
                          "an industrial skyline at dusk under a clear sky",
                          "a compass resting on a table beside a small model of a power plant"],
    "economia-investimento": ["container ships in a harbour with energy infrastructure",
                              "an industrial port with cranes at dusk", "a factory with solar panels on the roof",
                              "a business district skyline next to wind turbines",
                              "a cargo train passing fuel storage tanks"],
}

BRIEF_SYSTEM = (
    "You are the art director of a Portuguese energy news account on Instagram. For each slide you write one short "
    "scene description in English for an image model. Rules: describe only concrete physical things (energy "
    "infrastructure, landscapes, industrial or everyday objects) that match that slide's topic; use a calm visual "
    "metaphor when the topic is abstract; 12 to 40 words per scene; no people, faces or hands; no text, letters, "
    "numbers, signs, screens, documents, charts or maps; no logos, brands, flags or real named places, buildings or "
    "companies; nothing violent or alarming; do not mention style, colours or what to avoid (that is added later). "
    "Make every scene different. Answer only with JSON: "
    '{"cover": "<scene>", "points": ["<scene>", ...]} with exactly one scene per point, in the same order.'
)
CHECK_SYSTEM = (
    "You review images before they are published by a news account. Answer only with JSON: "
    '{"ok": true or false, "problems": ["..."]}. Set ok to false if the image shows any of these: readable text '
    "or text-like scribbles, letters, numbers or symbols; people, faces, hands or human silhouettes; flags, logos or "
    "brand marks; maps; explosions, disasters or injuries; badly distorted objects that look like generation errors; "
    "or if it clearly does not show the requested scene. Otherwise set ok to true."
)
BANNED = re.compile(r"\b(text|letters?|words?|numbers?|digits?|signs?|signage|logos?|brands?|flags?|maps?|charts?|"
                    r"graphs?|screens?|documents?|newspapers?|persons?|people|man|men|woman|women|faces?|hands?|"
                    r"workers?|crowds?|engineers?|technicians?|operators?|employees?|staff|humans?|figures?|silhouettes?|"
                    r"child|children|boys?|girls?|portugal|portuguese|lisbon|porto|europe|european|ense|adene|police)\b")
PT_WORDS = re.compile(r"\b(de|da|do|das|dos|em|com|uma|um|ao|aos|para|pelo|pela|nas|nos|junto|que|e)\b")


@dataclass
class SlideImages:
    cover: Image.Image | None = None
    points: list[Image.Image | None] = field(default_factory=list)
    model: str = ""
    scenes: list[str] = field(default_factory=list)
    brief: str = "palavras-chave"     # «ia» quando as cenas vieram da IA de texto
    log: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return int(self.cover is not None) + sum(1 for p in self.points if p is not None)


def settings(editorial: dict[str, Any]) -> dict[str, Any]:
    ig = editorial["instagram"]
    cfg = {**DEFAULTS, **(ig.get("ai_images") or {})}
    if "ai_images" not in ig and ig.get("ai_cover"):      # configuração antiga: só a capa
        cfg.update(enabled=True, slides="cover")
    return cfg


def images_enabled(editorial: dict[str, Any], env: Mapping[str, str]) -> bool:
    return bool(settings(editorial)["enabled"] and env.get("CF_ACCOUNT_ID") and env.get("CF_API_TOKEN"))


def _clean_scene(text: Any) -> str | None:
    """Cena aceitável para o modelo de imagem, ou None (português, algarismos, pessoas, texto, nomes reais)."""
    if not isinstance(text, str):
        return None
    s = " ".join(text.split()).strip().rstrip(".")
    probe = re.sub(r"\b(no|without)\s+[a-z ,]+", " ", s.lower())   # «no people» não conta como pessoas
    portuguese = len(PT_WORDS.findall(s.lower())) >= 2
    if (not s.isascii() or portuguese or re.search(r"\d", s) or not 6 <= len(s.split()) <= 60
            or BANNED.search(probe)):
        return None
    return s[:300]


def fallback_scenes(article: dict[str, Any], n_points: int) -> list[str]:
    """Capa + uma cena por ponto, sem IA: motivos do texto e variantes da categoria (sem repetir)."""
    cat = article.get("category")
    pool = list(VARIANTS.get(cat, [DEFAULT_SCENE]))
    cover = SCENES.get(cat, DEFAULT_SCENE)
    scenes, used = [cover], {cover}
    for point in article.get("key_points", [])[:n_points]:
        txt = " " + re.sub(r"[^a-z0-9]+", " ", strip_accents(point.lower())) + " "
        motif = next((m for keys, m in MOTIFS if any(k in txt for k in keys)), None)
        choice = motif if motif and motif not in used else next((v for v in pool if v not in used), pool[0])
        used.add(choice)
        scenes.append(choice)
    return scenes


def visual_brief(article: dict[str, Any], n_points: int, llm_cfg: dict[str, Any], env: Mapping[str, str],
                 llm: Callable = generate_json) -> tuple[list[str], str]:
    """Cenas [capa, ponto 1, …] e a origem («ia» ou «palavras-chave»). Cada cena inválida usa a de reserva."""
    fallback = fallback_scenes(article, n_points)
    points = article.get("key_points", [])[:n_points]
    prompt = (f"Category: {article.get('category_name') or article.get('category', '')}\n"
              f"Title: {article.get('title', '')}\nLead: {article.get('lead', '')}\nPoints:\n"
              + "\n".join(f"{i}. {p}" for i, p in enumerate(points, 1)))
    data = llm(BRIEF_SYSTEM, prompt, llm_cfg, env) if llm_cfg else None
    if not data:
        return fallback, "palavras-chave"
    got = [data.get("cover")] + list(data.get("points") or [])[: len(points)]
    got += [None] * (len(fallback) - len(got))
    scenes = [_clean_scene(g) or f for g, f in zip(got, fallback)]
    return scenes, "ia" if any(_clean_scene(g) for g in got) else "palavras-chave"


def build_prompt(scene: str) -> str:
    return f"{scene}. {STYLE}"


def generate_image(prompt: str, env: Mapping[str, str], model: str = "flux-1-schnell", seed: int = 1,
                   steps: int = 8, size: int = 1024, post: Callable = requests.post,
                   timeout: int = 120) -> tuple[Image.Image | None, str]:
    """(imagem, motivo). Nunca lança exceção; o motivo nunca inclui o token."""
    spec = MODELS.get(model)
    account, token = env.get("CF_ACCOUNT_ID"), env.get("CF_API_TOKEN")
    if not spec or not account or not token:
        return None, "sem modelo ou sem credenciais"
    url = ENDPOINT.format(account=account, model=spec["id"])
    headers = {"Authorization": f"Bearer {token}"}
    try:
        if spec["form"]:   # FLUX.2: o pedido é multipart, mesmo só com texto
            fields = {"prompt": prompt, "width": str(size), "height": str(size), "seed": str(seed)}
            resp = post(url, headers=headers, files={k: (None, v) for k, v in fields.items()}, timeout=timeout)
        else:
            resp = post(url, headers=headers, json={"prompt": prompt, "steps": max(1, min(int(steps), 8)),
                                                    "seed": seed}, timeout=timeout)
        data = resp.json()
        if resp.status_code != 200 or data.get("success") is False:
            errs = data.get("errors") or []
            code = errs[0].get("code") if errs and isinstance(errs[0], dict) else ""
            return None, f"HTTP {resp.status_code} {code}".strip()
        raw = (data.get("result") or {}).get("image") or data.get("image")
        im = Image.open(BytesIO(base64.b64decode(raw, validate=True)))
        im.load()
        return im.convert("RGB"), "ok"
    except Exception as e:   # rede, JSON, base64 ou imagem inválida
        return None, e.__class__.__name__


def check_image(im: Image.Image, scene: str, llm_cfg: dict[str, Any], env: Mapping[str, str],
                llm: Callable = generate_json) -> tuple[bool | None, str]:
    """True = aprovada, False = recusada, None = verificação indisponível (a imagem é aceite)."""
    small = im.copy()
    small.thumbnail((512, 512))
    buf = BytesIO()
    small.save(buf, "JPEG", quality=85)
    data = llm(CHECK_SYSTEM, f"Requested scene: {scene}", llm_cfg, env, image_jpeg=buf.getvalue())
    if not data or not isinstance(data.get("ok"), bool):
        return None, "verificação indisponível"
    problems = "; ".join(str(p) for p in (data.get("problems") or []))[:200]
    return data["ok"], problems


def _seed(slug: str, slot: int, attempt: int) -> int:
    return (zlib.crc32(slug.encode()) + slot * 1009 + attempt * 7919) % 2_147_483_647


def make_images(article: dict[str, Any], n_points: int, editorial: dict[str, Any], env: Mapping[str, str],
                model: str | None = None, post: Callable = requests.post, llm: Callable = generate_json) -> SlideImages:
    cfg = settings(editorial)
    model = model or cfg["model"]
    llm_cfg = editorial.get("llm") or {}
    out = SlideImages(model=model, points=[None] * n_points)
    if cfg["slides"] == "cover":
        n_points = 0
    out.scenes, out.brief = visual_brief(article, n_points, llm_cfg, env, llm=llm)
    budget = int(cfg["max_generations"])
    for slot, scene in enumerate(out.scenes):
        name = "capa" if slot == 0 else f"ponto {slot}"
        for attempt in range(int(cfg["max_attempts"])):
            if budget <= 0:
                out.log.append(f"{name}: limite de {cfg['max_generations']} imagens por carrossel atingido")
                break
            budget -= 1
            im, why = generate_image(build_prompt(scene), env, model, _seed(article.get("slug", ""), slot, attempt),
                                     cfg["steps"], int(cfg["size"]), post=post)
            if im is None:
                out.log.append(f"{name}: falhou ({why})")
                if why.startswith("HTTP 4"):   # quota esgotada ou credenciais: não vale a pena insistir
                    budget = 0
                break
            verdict, problems = check_image(im, scene, llm_cfg, env, llm=llm) if cfg["check"] else (None, "")
            if verdict is False:
                out.log.append(f"{name}: recusada na verificação ({problems})")
                continue
            out.log.append(f"{name}: ok" + (" (sem verificação)" if verdict is None else ""))
            if slot == 0:
                out.cover = im
            else:
                out.points[slot - 1] = im
            break
    return out
