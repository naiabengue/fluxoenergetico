"""Linha de comandos: python -m fluxo <comando>."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from .config import load_config


def _now() -> datetime:
    return datetime.now(timezone.utc)


def cmd_daily(args) -> int:
    from .http import Fetcher
    from .pipeline import run_daily

    cfg = load_config(args.root)
    pieces = args.data.split(",") if args.data else "auto"
    summary = run_daily(cfg, Fetcher(), _now(), os.environ, Path(args.drafts), data_pieces=pieces)
    if args.summary:
        Path(args.summary).parent.mkdir(parents=True, exist_ok=True)
        Path(args.summary).write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    c = summary["collect"]
    print(f"Recolha: {c['new']} novos, {c['dup']} repetidos, {c['ok']} fontes ok, {c['failed']} com erro")
    print(f"Publicados: {len(summary['published'])} | Para revisão: {len(summary['review'])} | "
          f"Rejeitados: {len(summary['rejected'])} | IA: {summary['llm']['calls']} pedidos")
    for e in summary["errors"]:
        print(f"Aviso: {e}")
    return 0


def cmd_build(args) -> int:
    from .site.build import build_site

    cfg = load_config(args.root)
    report = build_site(cfg, Path(args.out))
    print(f"Site gerado em {args.out}: {report['articles']} artigos, {report['pages']} páginas ({report['base']})")
    return 0


def cmd_audit(args) -> int:
    from .audit import run_audit
    from .http import Fetcher

    report = run_audit(load_config(args.root), Fetcher(), _now())
    bad = [k for k, r in report.items() if r["enabled"] and r["status"] != "ok"]
    print(f"{len(report)} fontes testadas; com problemas (ativas): {', '.join(bad) or 'nenhuma'}")
    return 0


def _article_for_ig(cfg, a):
    a = dict(a)
    a["category_name"] = cfg.editorial["categories"].get(a.get("category"), {}).get("name", "")
    return a


def cmd_instagram(args) -> int:
    from .instagram.caption import make_caption
    from .instagram.render import render_carousel
    from .instagram.select import pick_for_week
    from .store import Store

    cfg = load_config(args.root)
    store = Store(cfg.root)
    state = store.instagram_state()
    ig = cfg.editorial["instagram"]
    base = f"https://{cfg.site['domain']}" if cfg.site.get("domain") else cfg.site["base_url"].rstrip("/")
    label = base.replace("https://", "")
    picks = pick_for_week(store.published_articles(), _now(), n=1, already_posted=set(state))
    if not picks:
        print("Nenhum artigo novo para o Instagram.")
        return 0
    a = _article_for_ig(cfg, picks[0])
    folder = f"instagram/{_now():%Y-%m-%d}/{a['slug']}"
    paths = render_carousel(a, cfg.root / "content" / folder, ig.get("max_slides", 7), label)
    caption = make_caption(a, base, ig["hashtags"])
    (cfg.root / "content" / folder / "legenda.txt").write_text(caption, encoding="utf-8")
    state[a["slug"]] = {"prepared": _now().isoformat(), "folder": folder, "slides": len(paths), "media_id": None}
    store.save_instagram_state(state)
    print(f"Carrossel preparado: content/{folder} ({len(paths)} imagens)")
    return 0


def cmd_instagram_publish(args) -> int:
    from .instagram.publish import publish_carousel, publish_enabled
    from .store import Store

    cfg = load_config(args.root)
    if not publish_enabled(cfg.editorial, os.environ):
        print("Publicação automática desligada ou sem credenciais: publicar manualmente (ver docs/MANUAL.md).")
        return 0
    store = Store(cfg.root)
    state = store.instagram_state()
    base = f"https://{cfg.site['domain']}" if cfg.site.get("domain") else cfg.site["base_url"].rstrip("/")
    for slug, info in state.items():
        if info.get("media_id"):
            continue
        urls = [f"{base}/{info['folder']}/slide-{i}.jpg" for i in range(1, info["slides"] + 1)]
        for _ in range(20):   # espera que o GitHub Pages sirva as imagens
            if requests.head(urls[0], timeout=20).status_code == 200:
                break
            time.sleep(30)
        caption = (cfg.root / "content" / info["folder"] / "legenda.txt").read_text(encoding="utf-8")
        info["media_id"] = publish_carousel(urls, caption, os.environ["IG_USER_ID"], os.environ["IG_ACCESS_TOKEN"],
                                            cfg.editorial["instagram"].get("api_version", ""))
        info["published"] = _now().isoformat()
        print(f"Publicado no Instagram: {slug} ({info['media_id']})")
    store.save_instagram_state(state)
    return 0


def cmd_refresh_token(args) -> int:
    from .instagram.publish import refresh_token

    token, expires = refresh_token(os.environ["IG_ACCESS_TOKEN"])
    print(f"::add-mask::{token}")
    Path(args.out).write_text(token, encoding="utf-8")
    print(f"Token renovado; válido por {expires // 86400} dias.")
    return 0


def cmd_status(args) -> int:
    from .store import Store

    runs = Store(args.root).runs(limit=14)
    lines = ["# Estado das execuções (últimas 14)", "",
             "| Início (UTC) | Novos | Fontes com erro | Publicados | Revisão | Rejeitados | Pedidos IA |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in reversed(runs):
        lines.append(f"| {r['started'][:16]} | {r['collect']['new']} | {', '.join(r.get('failed_sources', [])) or '—'} "
                     f"| {len(r['published'])} | {len(r['review'])} | {len(r['rejected'])} | {r['llm']['calls']} |")
    out = Path(args.root) / "docs" / "ESTADO.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="fluxo", description="Fluxo Energético — pipeline editorial")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_):
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("--root", default=".")
        sp.set_defaults(fn=fn)
        return sp

    d = add("daily", cmd_daily, "recolha + peças de dados + notícias")
    d.add_argument("--drafts", default="drafts")
    d.add_argument("--summary", default="out/summary.json")
    d.add_argument("--data", default="", help="forçar peças: brent_fx,gas_storage")
    b = add("build", cmd_build, "gerar o site estático")
    b.add_argument("--out", default="_site")
    add("audit", cmd_audit, "testar todas as fontes")
    add("instagram", cmd_instagram, "preparar o carrossel da semana")
    add("instagram-publish", cmd_instagram_publish, "publicar carrosséis preparados (se ativo)")
    r = add("refresh-ig-token", cmd_refresh_token, "renovar o token do Instagram")
    r.add_argument("--out", default="out/ig_token")
    add("status", cmd_status, "resumo das últimas execuções")
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
