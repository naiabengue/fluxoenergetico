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


def format_summary(summary: dict) -> list[str]:
    """Linhas legíveis para o registo do GitHub Actions: o quê, e porquê quando algo ficou de fora."""
    c = summary["collect"]
    llm_info = summary.get("llm", {})
    lines = [f"Recolha: {c['new']} novos, {c['dup']} repetidos, {c['ok']} fontes ok, {c['failed']} com erro",
             f"Publicados: {len(summary['published'])} | Para revisão: {len(summary['review'])} | "
             f"Rejeitados: {len(summary['rejected'])} | IA: {llm_info.get('calls', 0)} pedidos"]
    for name, outcome in summary.get("data_pieces", {}).items():
        lines.append(f"Peça de dados {name}: {outcome}")
    for p in summary["published"]:
        lines.append(f"Publicado ({p['kind']}): {p['title']}")
    for r in summary["review"]:
        lines.append(f"Para revisão ({r['kind']}): {r['title']}")
    for r in summary["rejected"]:
        lines.append(f"Rejeitado ({r['kind']}): {r['title']} — {'; '.join(r.get('errors', [])) or 'sem motivo'}")
    for e in dict.fromkeys(llm_info.get("errors", [])):
        lines.append(f"IA: {e}")
    for e in summary["errors"]:
        lines.append(f"Aviso: {e}")
    return lines


def cmd_daily(args) -> int:
    from .http import Fetcher
    from .pipeline import run_daily

    cfg = load_config(args.root)
    pieces = args.data.split(",") if args.data else "auto"
    if args.catch_up:
        pieces = []          # tentativa extra: só notícias; as peças de dados já correram de manhã
    summary = run_daily(cfg, Fetcher(), _now(), os.environ, Path(args.drafts), data_pieces=pieces,
                        catch_up=args.catch_up)
    if args.summary:
        Path(args.summary).parent.mkdir(parents=True, exist_ok=True)
        Path(args.summary).write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(format_summary(summary)))
    return 0


def cmd_build(args) -> int:
    from .site.build import build_site, build_with_subdir

    cfg = load_config(args.root)
    if args.subdir:
        report = build_with_subdir(cfg, Path(args.out), args.subdir)
        where = f"{args.out}/{args.subdir.strip('/')} (com redirecionamento na raiz)"
    else:
        report = build_site(cfg, Path(args.out))
        where = args.out
    print(f"Site gerado em {where}: {report['articles']} artigos, {report['pages']} páginas ({report['base']})")
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
    from .instagram.cover_image import cover_enabled, generate_cover
    from .instagram.render import render_carousel
    from .instagram.select import pick_for_week
    from .site.build import public_base
    from .store import Store

    cfg = load_config(args.root)
    store = Store(cfg.root)
    state = store.instagram_state()
    ig = cfg.editorial["instagram"]
    base = public_base(cfg.site)
    label = base.replace("https://", "")
    picks = pick_for_week(store.published_articles(), _now(), n=1, already_posted=set(state))
    if not picks:
        print("Nenhum artigo novo para o Instagram.")
        return 0
    a = _article_for_ig(cfg, picks[0])
    folder = f"instagram/{_now():%Y-%m-%d}/{a['slug']}"
    cover = generate_cover(a, os.environ) if cover_enabled(cfg.editorial, os.environ) else None
    paths = render_carousel(a, cfg.root / "content" / folder, ig.get("max_slides", 7), label,
                            cover_image=cover, style=ig)
    caption = make_caption(a, base, ig["hashtags"], style=ig, ai_cover=cover is not None)
    (cfg.root / "content" / folder / "legenda.txt").write_text(caption, encoding="utf-8")
    state[a["slug"]] = {"prepared": _now().isoformat(), "folder": folder, "slides": len(paths), "media_id": None,
                        "ai_cover": cover is not None}
    store.save_instagram_state(state)
    capa = "capa com imagem IA" if cover is not None else "capa tipográfica"
    print(f"Carrossel preparado: content/{folder} ({len(paths)} imagens, {capa})")
    return 0


def cmd_instagram_publish(args) -> int:
    from .instagram.publish import graph_host, publish_carousel, publish_enabled, slide_urls
    from .site.build import public_base
    from .store import Store

    cfg = load_config(args.root)
    if not publish_enabled(cfg.editorial, os.environ):
        print("Publicação automática desligada ou sem credenciais: publicar manualmente (ver docs/MANUAL.md).")
        return 0
    store = Store(cfg.root)
    state = store.instagram_state()
    base = public_base(cfg.site)
    for slug, info in state.items():
        if info.get("media_id"):
            continue
        urls = slide_urls(base, info["folder"], info["slides"])
        for _ in range(20):   # espera que o GitHub Pages sirva as imagens
            if requests.head(urls[0], timeout=20).status_code == 200:
                break
            time.sleep(30)
        caption = (cfg.root / "content" / info["folder"] / "legenda.txt").read_text(encoding="utf-8")
        info["media_id"] = publish_carousel(urls, caption, os.environ["IG_USER_ID"], os.environ["IG_ACCESS_TOKEN"],
                                            cfg.editorial["instagram"].get("api_version", ""),
                                            host=graph_host(cfg.editorial))
        info["published"] = _now().isoformat()
        print(f"Publicado no Instagram: {slug} ({info['media_id']})")
    store.save_instagram_state(state)
    return 0


def cmd_instagram_check(args) -> int:
    from .instagram.publish import check_account, graph_host

    cfg = load_config(args.root)
    user = check_account(os.environ["IG_USER_ID"], os.environ["IG_ACCESS_TOKEN"],
                         cfg.editorial["instagram"].get("api_version", ""), graph_host(cfg.editorial))
    print(f"Token válido para a conta @{user}.")
    return 0


def cmd_refresh_token(args) -> int:
    from .instagram.publish import refresh_token

    cfg = load_config(args.root)
    if cfg.editorial["instagram"].get("login", "unified") == "unified":
        print("Login unificado: o token de utilizador de sistema não expira; nada a renovar.")
        return 0
    token, expires = refresh_token(os.environ["IG_ACCESS_TOKEN"])
    print(f"::add-mask::{token}")
    Path(args.out).write_text(token, encoding="utf-8")
    print(f"Token renovado; válido por {expires // 86400} dias.")
    return 0


def cmd_notify_review(args) -> int:
    from . import notify
    from .notify import email_due, review_digest, seconds_until

    cfg = load_config(args.root)
    today = _now().date()
    if not args.test and not email_due(cfg.editorial, today):
        print("Fora do período de revisão por email: nada a enviar.")
        return 0
    need = ["GITHUB_REPOSITORY", "GITHUB_TOKEN", "SMTP_USER", "SMTP_PASSWORD", "REVIEW_EMAIL_TO"]
    if missing := [k for k in need if not os.environ.get(k)]:
        print("Sem configuração de email (" + ", ".join(missing) + "): nada a enviar.")
        return 0
    repo = os.environ["GITHUB_REPOSITORY"]
    headers = {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "Accept": "application/vnd.github+json"}
    r = requests.get(f"https://api.github.com/repos/{repo}/pulls",
                     params={"state": "open", "per_page": 50}, timeout=30, headers=headers)
    r.raise_for_status()
    digest = review_digest(r.json(), today)
    if digest is None and not args.test:
        digest = _no_news_digest(args.root, repo, headers)
    if digest is None and args.test:
        until = cfg.editorial["policy"].get("review_email_until", "—")
        digest = (f"Fluxo Energético: teste do aviso de revisão ({today:%d/%m/%Y})",
                  "Teste: o aviso diário está configurado.\n\nTodos os dias às 8h30 (Lisboa), até "
                  f"{until}, recebes aqui a ligação para cada notícia à espera de revisão. "
                  "Se um dia útil ficar sem notícia, recebes um aviso com o motivo; ao fim de semana, "
                  "sem notícias por rever, não há email.\n\n— Fluxo Energético (mensagem automática)")
    if digest is None:
        print("Nenhuma notícia à espera de revisão: sem email hoje.")
        return 0
    if args.wait:
        time.sleep(seconds_until(_now(), args.at))
    notify.send_email(*digest, os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"], os.environ["REVIEW_EMAIL_TO"])
    print(f"Email enviado: {digest[0]}")
    return 0


def _no_news_digest(root: str, repo: str, headers: dict[str, str]) -> tuple[str, str] | None:
    """Num dia útil sem notícia publicada nem enviada para revisão, um aviso com o motivo; senão None."""
    from .calendar_pt import is_business_day, lisbon_date
    from .notify import no_news_alert
    from .pipeline import news_today
    from .store import Store

    now = _now()
    today = lisbon_date(now)
    store = Store(root)
    if not is_business_day(today) or news_today(store.processed(), now.date().isoformat()):
        return None
    runs_today = [r for r in store.runs(limit=10) if lisbon_date(datetime.fromisoformat(r["started"])) == today]
    failed: list[dict] = []
    try:
        r = requests.get(f"https://api.github.com/repos/{repo}/actions/workflows/diario.yml/runs",
                         params={"created": f">={today.isoformat()}", "per_page": 20}, timeout=30, headers=headers)
        r.raise_for_status()
        failed = sorted((w for w in r.json().get("workflow_runs", []) if w.get("conclusion") == "failure"),
                        key=lambda w: w["created_at"])
    except requests.RequestException as e:      # o aviso segue na mesma, só sem as ligações
        print(f"Não foi possível ler as execuções do diário: {e}")
    return no_news_alert(today, runs_today[-1] if runs_today else None, failed, repo)


def cmd_release_review(args) -> int:
    """O pedido de revisão não abriu: liberta as notícias do dia para a tentativa seguinte as voltar a redigir."""
    from .store import Store

    path = Path(args.summary)
    if not path.exists():
        print("Sem resumo da execução: nada a libertar.")
        return 0
    summary = json.loads(path.read_text(encoding="utf-8"))
    ids = [r["id"] for r in summary.get("review", []) if r.get("id")]
    freed = Store(args.root).release_review(ids)
    titles = {r.get("id"): r["title"] for r in summary.get("review", [])}
    for i in freed:
        print(f"Libertada para a tentativa seguinte: {titles.get(i, i)}")
    if not freed:
        print("Nada a libertar.")
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
    d.add_argument("--catch-up", action="store_true",
                   help="tentativa extra num dia útil: só procura notícia se ainda não houver nenhuma hoje")
    b = add("build", cmd_build, "gerar o site estático")
    b.add_argument("--out", default="_site")
    b.add_argument("--subdir", default="", help="gerar em <out>/<subdir> com redirecionamento na raiz (ex.: news)")
    add("audit", cmd_audit, "testar todas as fontes")
    add("instagram", cmd_instagram, "preparar o carrossel da semana")
    add("instagram-publish", cmd_instagram_publish, "publicar carrosséis preparados (se ativo)")
    add("instagram-check", cmd_instagram_check, "confirmar que o token dá acesso à conta (não publica)")
    r = add("refresh-ig-token", cmd_refresh_token, "renovar o token do Instagram")
    r.add_argument("--out", default="out/ig_token")
    n = add("notify-review", cmd_notify_review, "email com as notícias à espera de revisão")
    n.add_argument("--wait", action="store_true", help="esperar pela hora local indicada em --at")
    n.add_argument("--at", default="08:30")
    n.add_argument("--test", action="store_true", help="enviar um email de teste mesmo sem notícias por rever")
    rr = add("release-review", cmd_release_review,
             "o pedido de revisão não abriu: libertar a notícia do dia para a tentativa seguinte")
    rr.add_argument("--summary", default="out/summary.json")
    add("status", cmd_status, "resumo das últimas execuções")
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
