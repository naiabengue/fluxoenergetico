"""Gerador do site estático (HTML, RSS, sitemap, pesquisa)."""
from __future__ import annotations

import json
import shutil
from collections import OrderedDict
from datetime import date, datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from xml.sax.saxutils import escape

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..config import Config
from ..store import Store

HERE = Path(__file__).parent
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
         "outubro", "novembro", "dezembro"]


def data_extenso(value: Any) -> str:
    try:
        d = date.fromisoformat(str(value)[:10])
    except ValueError:
        return str(value or "")
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def _render_md(text: str) -> str:
    safe = text.replace("<", "&lt;").replace(">", "&gt;")   # nunca HTML vindo de texto gerado
    return markdown.markdown(safe, extensions=["extra", "sane_lists"])


def _write(out: Path, rel: str, content: str) -> None:
    path = out / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def public_base(site: dict[str, Any]) -> str:
    """Endereço público do site, sem barra final."""
    return f"https://{site['domain']}" if site.get("domain") else site["base_url"].rstrip("/")


REDIRECT = """<!doctype html>
<html lang="pt-PT">
<head>
<meta charset="utf-8">
<title>{title}</title>
<meta http-equiv="refresh" content="0; url={target}">
<link rel="canonical" href="{canonical}">
<meta name="robots" content="noindex">
</head>
<body>
<p><a href="{target}">{title}</a></p>
</body>
</html>
"""


def build_with_subdir(cfg: Config, out: Path, subdir: str) -> dict[str, Any]:
    """Gera o site em out/<subdir> e põe na raiz um redirecionamento para lá.

    Serve para um repositório de projeto do GitHub Pages (ex.: /fluxoenergetico) cujo site vive numa
    subpasta (ex.: /fluxoenergetico/news). O base_url tem de terminar nessa subpasta.
    """
    out = Path(out)
    subdir = subdir.strip("/")
    base = public_base(cfg.site)
    prefix = urlsplit(base).path.rstrip("/")
    if not subdir or not prefix.endswith("/" + subdir):
        raise ValueError(f"base_url ({base}) não termina em /{subdir}")
    if out.exists():
        shutil.rmtree(out)
    report = build_site(cfg, out / subdir)
    _write(out, "index.html", REDIRECT.format(title=cfg.site["title"], target=f"{prefix}/", canonical=f"{base}/"))
    shutil.copyfile(out / subdir / "404.html", out / "404.html")
    _write(out, ".nojekyll", "")
    return report


def build_site(cfg: Config, out: Path) -> dict[str, Any]:
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    site = dict(cfg.site)
    base = public_base(site)
    prefix = urlsplit(base).path.rstrip("/")
    cats = cfg.editorial["categories"]
    policy = cfg.editorial["policy"]

    articles = []
    for a in Store(cfg.root).published_articles():
        d = str(a.get("date", ""))
        a["url"] = f"{prefix}/artigos/{d[:4]}/{d[5:7]}/{a['slug']}/"
        a["abs_url"] = base + a["url"][len(prefix):]
        a["category_name"] = cats.get(a.get("category"), {}).get("name", a.get("category", ""))
        a["html"] = _render_md(a.get("body", ""))
        ai = a.get("ai") or {}
        a["ai_note"] = (policy["ai_label_reviewed"] if ai.get("review") == "pr" else policy["ai_label"]) \
            if ai.get("used") else ""
        articles.append(a)

    env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html"]))
    env.filters["data"] = data_extenso
    common = {"site": site, "base": base, "prefix": prefix, "categories": cats,
              "year": datetime.now(timezone.utc).year}

    def page(tpl: str, rel: str, **ctx) -> None:
        _write(out, rel, env.get_template(tpl).render(**common, **ctx))

    per_page = int(site.get("articles_per_page", 20))
    page("index.html", "index.html", articles=articles[:per_page], canonical=base + "/")
    for a in articles:
        d = str(a["date"])
        page("article.html", f"artigos/{d[:4]}/{d[5:7]}/{a['slug']}/index.html", a=a, canonical=a["abs_url"])
    for cid, c in cats.items():
        items = [a for a in articles if a.get("category") == cid]
        page("list.html", f"categoria/{cid}/index.html", title=c["name"], articles=items,
             canonical=f"{base}/categoria/{cid}/", empty="Ainda não há artigos nesta categoria.")
    months: "OrderedDict[str, list]" = OrderedDict()
    for a in articles:
        d = date.fromisoformat(str(a["date"])[:10])
        months.setdefault(f"{MESES[d.month - 1].capitalize()} de {d.year}", []).append(a)
    page("archive.html", "arquivo/index.html", months=months, canonical=f"{base}/arquivo/")
    page("search.html", "pesquisa/index.html", canonical=f"{base}/pesquisa/")
    bee = [s for s in cfg.sources if s.bee_number is not None and s.group != "ferramenta"]
    extra = [s for s in cfg.sources if s.extra]
    page("sources.html", "fontes/index.html", bee=bee, extra=extra, canonical=f"{base}/fontes/")
    page("about.html", "sobre/index.html", policy=policy, canonical=f"{base}/sobre/")
    page("privacy.html", "privacidade/index.html", canonical=f"{base}/privacidade/")
    # Página de aprovação do email de revisão (fora do sitemap e com noindex).
    page("aprovar.html", "aprovar/index.html", policy=policy, canonical=f"{base}/aprovar/")
    page("404.html", "404.html", canonical=base + "/")

    # Pesquisa, RSS, sitemap, robots
    _write(out, "search.json", json.dumps(
        [{"t": a["title"], "u": a["url"], "d": str(a["date"]), "c": a["category_name"], "s": a.get("lead", "")}
         for a in articles], ensure_ascii=False))
    items_xml = []
    for a in articles[:20]:
        dt = datetime.fromisoformat(str(a.get("datetime") or f"{a['date']}T08:00:00+00:00"))
        items_xml.append(
            f"<item><title>{escape(a['title'])}</title><link>{a['abs_url']}</link>"
            f"<guid isPermaLink=\"true\">{a['abs_url']}</guid><pubDate>{format_datetime(dt)}</pubDate>"
            f"<category>{escape(a['category_name'])}</category><description>{escape(a.get('lead', ''))}</description></item>")
    _write(out, "feed.xml",
           '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel>'
           f"<title>{escape(site['title'])}</title><link>{base}/</link><description>{escape(site['description'])}"
           f"</description><language>pt-PT</language>{''.join(items_xml)}</channel></rss>\n")
    urls = [base + "/"] + [a["abs_url"] for a in articles] + \
           [f"{base}/categoria/{c}/" for c in cats] + [f"{base}/{p}/" for p in ("arquivo", "fontes", "sobre")]
    _write(out, "sitemap.xml",
           '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
           + "".join(f"<url><loc>{u}</loc></url>" for u in urls) + "</urlset>\n")
    _write(out, "robots.txt", f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n")
    _write(out, ".nojekyll", "")
    if site.get("domain"):
        _write(out, "CNAME", site["domain"] + "\n")

    shutil.copytree(HERE / "static", out / "static")
    for folder in ("media", "instagram"):
        src = cfg.root / "content" / folder
        if src.exists():
            shutil.copytree(src, out / folder)
    return {"articles": len(articles), "pages": sum(1 for _ in out.rglob("*.html")), "base": base}
