"""Execução diária: recolher → peças de dados → selecionar → redigir → validar → publicar ou enviar para revisão."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping

import requests

from . import llm
from .charts import line_chart
from .collect.runner import collect_all
from .config import Config
from .datasets.agsi import fetch_agsi
from .datasets.ecb import fetch_usd
from .datasets.eia import fetch_brent
from .dedup import cluster
from .extract import extract_text
from .publish import decide, slugify, write_article
from .scoring import score
from .calendar_pt import is_business_day, lisbon_date
from .store import Store
from .validate import validate
from .write.data_pieces import brent_fx_piece, gas_storage_piece
from .write.news import Refused, draft_news

MIN_SOURCE_CHARS = 600


def _due_pieces(cfg: Config, now: datetime) -> list[str]:
    return [name for name, p in cfg.editorial.get("data_pieces", {}).items() if p.get("weekday") == now.weekday()]


def _http_errors(fetcher, host: str) -> str:
    errs = sorted({e for u, e in getattr(fetcher, "errors", {}).items() if host in u})
    return (": " + "; ".join(errs)) if errs else ""


def _build_piece(name: str, cfg: Config, fetcher, env: Mapping[str, str], now: datetime):
    if name == "brent_fx":
        if not env.get("EIA_API_KEY"):
            return None, "falta EIA_API_KEY"
        brent, fx = fetch_brent(fetcher, env["EIA_API_KEY"]), fetch_usd(fetcher)
        if len(brent) < 3 or len(fx) < 3:
            return None, "dados insuficientes (EIA/BCE)" + _http_errors(fetcher, "api.eia.gov") + _http_errors(fetcher, "ecb.europa.eu")
        draft, evidence = brent_fx_piece(brent, fx)
        series = {"Brent (USD/barril)": [(o.date, o.value) for o in brent]}
        return (draft, evidence, series, "USD por barril", 2, "EIA"), None
    if name == "gas_storage":
        if not env.get("AGSI_API_KEY"):
            return None, "falta AGSI_API_KEY"
        key = env["AGSI_API_KEY"]
        eu, pt = fetch_agsi(fetcher, key, "eu", today=now.date()), fetch_agsi(fetcher, key, "PT", today=now.date())
        if len(eu) < 2 or len(pt) < 2:
            return None, "dados insuficientes (AGSI)" + _http_errors(fetcher, "agsi.gie.eu")
        es = fetch_agsi(fetcher, key, "ES", today=now.date()) if "ES" in cfg.editorial["data_pieces"]["gas_storage"].get("countries", []) else []
        draft, evidence = gas_storage_piece(eu, pt, es or None)
        series = {"UE": [(s.date, s.full) for s in eu], "Portugal": [(s.date, s.full) for s in pt]}
        return (draft, evidence, series, "% da capacidade", 1, "GIE AGSI+"), None
    return None, f"peça desconhecida: {name}"


def _news_today(store: Store, today: str) -> int:
    return sum(1 for v in store.processed().values()
               if v.get("date") == today and v.get("decision") in ("publicar", "rever"))


def run_daily(cfg: Config, fetcher, now: datetime, env: Mapping[str, str], drafts_dir: Path,
              post: Callable = requests.post, data_pieces: list[str] | str = "auto",
              catch_up: bool = False) -> dict[str, Any]:
    """catch_up=True: tentativa extra num dia útil; só procura notícia se ainda não houver nenhuma hoje."""
    ed = cfg.editorial
    store = Store(cfg.root)
    llm.reset_usage()
    summary: dict[str, Any] = {"started": now.isoformat(), "published": [], "review": [], "rejected": [],
                               "data_pieces": {}, "news": {}, "errors": []}

    # 1. Recolha
    summary["collect"] = collect_all(cfg, store, fetcher, now)
    published = store.published_articles()

    # 2. Peças de dados (sem IA)
    for name in (_due_pieces(cfg, now) if data_pieces == "auto" else data_pieces):
        built, reason = _build_piece(name, cfg, fetcher, env, now)
        if not built:
            summary["data_pieces"][name] = reason
            continue
        draft, evidence, series, ylabel, dec, src = built
        draft.slug = slugify(draft.title)
        rel = f"media/{now:%Y%m%d}-{name}.png"
        line_chart(series, cfg.root / "content" / rel, ylabel, dec, src)
        draft.chart = rel
        v = validate(draft, evidence, ed, published, today=now.date())
        decision = decide(draft, v, "candidato", ed)
        summary["data_pieces"][name] = decision
        if decision == "publicar":
            write_article(draft, cfg.root, now)
            summary["published"].append({"kind": "dados", "title": draft.title})
        elif decision == "rever":
            write_article(draft, drafts_dir, now)
            summary["review"].append({"kind": "dados", "title": draft.title})
        else:
            summary["rejected"].append({"kind": "dados", "title": draft.title, "errors": v.errors})
            store.log_rejected({"date": now.isoformat(), "kind": "dados", "title": draft.title, "errors": v.errors})

    # 3. Notícias (IA opcional). Nos dias úteis de Lisboa tem de haver uma: se nenhum item chega ao limiar
    #    normal, aceita-se até policy.business_day_min_score, sempre com revisão humana (nunca publicação direta).
    today = lisbon_date(now)
    business = is_business_day(today)
    fallback_min = ed["policy"].get("business_day_min_score")
    processed = store.processed()
    scored = []
    for it in store.recent_items(days=3, now=now):
        if it.id in processed:
            continue
        try:
            src = cfg.source(it.source_id)
        except KeyError:
            continue
        sc = score(it, src, ed, now)
        if sc.decision == "rejeitar" and business and fallback_min is not None and not sc.blocked \
                and sc.total >= fallback_min:
            sc.decision = "rever"
        if sc.decision != "rejeitar":
            scored.append((sc, it, src))
    scored.sort(key=lambda t: t[0].total, reverse=True)
    groups = cluster(scored, ed["scoring"]["cluster_similarity"], key=lambda t: t[1].title)
    candidates = [g[0] for g in groups]   # o mais pontuado de cada acontecimento
    summary["news"] = {"candidates": len(candidates), "attempted": 0, "skipped": None, "business_day": business}
    already = _news_today(store, now.date().isoformat())
    has_llm = any(env.get(p.get("key_env", "")) for p in ed["llm"]["providers"])
    remaining = max(0, ed["policy"]["max_news_per_day"] - already)
    if not remaining:                 # tentativa extra ou agendamento atrasado: o limite do dia já foi cumprido
        summary["news"]["skipped"] = "já há notícia hoje"
        candidates = []
    elif not has_llm:
        summary["news"]["skipped"] = "sem IA configurada"
        candidates = []

    max_calls = ed["llm"].get("business_day_max_calls", ed["llm"]["max_calls_per_run"]) if business \
        else ed["llm"]["max_calls_per_run"]
    produced = 0
    for sc, it, src in candidates:
        if produced >= remaining or llm.USAGE["calls"] >= max_calls:
            break
        summary["news"]["attempted"] += 1
        resp = fetcher.get(it.url)
        text = extract_text(resp) if resp else ""
        if len(text) < MIN_SOURCE_CHARS:
            store.mark_processed(it.id, "rejeitado: fonte inacessível ou curta", now.isoformat())
            summary["rejected"].append({"kind": "noticia", "title": it.title, "errors": ["texto da fonte indisponível"]})
            continue
        try:
            draft = draft_news(it.to_dict(), src, text, ed, env=env, post=post)
        except Refused as why:
            store.mark_processed(it.id, f"rejeitado: {why}", now.isoformat())
            summary["rejected"].append({"kind": "noticia", "title": it.title, "errors": [str(why)]})
            store.log_rejected({"date": now.isoformat(), "kind": "noticia", "title": it.title,
                                "source": it.url, "errors": [str(why)]})
            continue
        if draft is None:
            reasons = "; ".join(dict.fromkeys(llm.USAGE["errors"])) or "sem detalhe"
            summary["errors"].append(f"IA sem resposta utilizável para: {it.title} ({reasons})")
            break   # quota ou falha do fornecedor: o item fica por tratar e tenta-se no dia seguinte
        draft.score = sc.total
        draft.slug = slugify(draft.title)
        v = validate(draft, text, ed, published, today=now.date())
        decision = decide(draft, v, sc.decision, ed)
        store.mark_processed(it.id, decision, now.isoformat())
        if decision == "publicar":
            draft.ai["review"] = "auto"
            write_article(draft, cfg.root, now)
            summary["published"].append({"kind": "noticia", "title": draft.title})
            produced += 1
        elif decision == "rever":
            draft.ai["review"] = "pr"
            write_article(draft, drafts_dir, now)
            summary["review"].append({"kind": "noticia", "title": draft.title, "source": it.url, "score": sc.total})
            produced += 1
        else:
            summary["rejected"].append({"kind": "noticia", "title": draft.title, "errors": v.errors})
            store.log_rejected({"date": now.isoformat(), "kind": "noticia", "title": draft.title,
                                "source": it.url, "errors": v.errors})

    if business and not produced and not already:
        summary["errors"].append(
            f"Dia útil sem notícia ({summary['news']['candidates']} candidatos, {summary['news']['attempted']} tentados"
            + (f", {summary['news']['skipped']}" if summary["news"]["skipped"] else "") + ")")
    summary["llm"] = dict(llm.USAGE)
    store.log_run({k: summary[k] for k in ("started", "published", "review", "rejected", "data_pieces", "news",
                                           "llm", "errors")} |
                  {"collect": {k: summary["collect"][k] for k in ("new", "dup", "ok", "failed")},
                   "failed_sources": [s for s, r in summary["collect"]["sources"].items() if r["status"] == "erro"],
                   "http_requests": getattr(fetcher, "requests", None)})
    return summary
