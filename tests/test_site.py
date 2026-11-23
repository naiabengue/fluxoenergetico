import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import yaml

from fluxo.config import load_config
from fluxo.models import Draft
from fluxo.publish import decide, slugify, write_article
from fluxo.site.build import build_site
from fluxo.validate import Validation

WHEN = datetime(2026, 11, 16, 7, 0, tzinfo=timezone.utc)


def _news(title="Tarifas reguladas de gás natural sobem 6,4% desde outubro", review="auto"):
    return Draft(kind="noticia", title=title, lead="A subida aplica-se ao mercado regulado.",
                 body="## O que aconteceu\n\nTexto <script>alert(1)</script> da notícia.", category="eletricidade-gas",
                 key_points=["Um", "Dois", "Três"], tags=["gás natural"],
                 sources=[{"name": "ERSE", "url": "https://www.erse.pt/x", "date": "2026-09-30"}],
                 ai={"used": True, "provider": "gemini", "model": "gemini-2.5-flash-lite", "review": review})


def _data():
    return Draft(kind="dados", title="Armazenamento de gás: UE a 87,1% e Portugal a 94,5% da capacidade",
                 lead="Dados da GIE.", body="## Nível das reservas\n\nTexto.", category="eletricidade-gas",
                 key_points=["a", "b", "c"], sources=[{"name": "GIE", "url": "https://agsi.gie.eu/", "date": "2026-11-14"}],
                 ai={"used": False})


def test_slugify_portuguese():
    assert slugify("Tarifas de gás sobem 6,4% — ERSE") == "tarifas-de-gas-sobem-6-4-erse"


def test_write_article_front_matter(project):
    path = write_article(_news(), project, WHEN)
    assert path.relative_to(project).as_posix().startswith("content/articles/2026/11/tarifas-reguladas")
    meta = yaml.safe_load(path.read_text(encoding="utf-8").split("---")[1])
    assert meta["date"] == "2026-11-16" and meta["type"] == "noticia" and meta["ai"]["used"] is True


def test_decide_policy(project):
    ed = load_config(project).editorial
    ok, bad = Validation(ok=True), Validation(ok=False, errors=["x"])
    assert decide(_data(), ok, "rejeitar", ed) == "publicar"
    assert decide(_news(), ok, "candidato", ed) == "rever"          # fase 1: notícias com IA vão a revisão
    assert decide(_news(), bad, "candidato", ed) == "rejeitado"
    ed["policy"]["auto_publish_news"] = True
    assert decide(_news(), ok, "candidato", ed) == "publicar"
    assert decide(_news(), ok, "rever", ed) == "rever"


def _build(project):
    write_article(_news(), project, WHEN)
    write_article(_data(), project, WHEN)
    cfg = load_config(project)
    return build_site(cfg, project / "_site"), project / "_site"


def test_build_creates_index_article_category_feed_sitemap(project):
    report, out = _build(project)
    assert report["articles"] == 2
    index = (out / "index.html").read_text()
    assert "Tarifas reguladas de gás natural" in index and "Armazenamento de gás" in index
    assert (out / "categoria" / "eletricidade-gas" / "index.html").exists()
    items = ET.parse(out / "feed.xml").getroot().findall("./channel/item")
    assert len(items) == 2
    sitemap = (out / "sitemap.xml").read_text()
    assert "/artigos/2026/11/" in sitemap
    search = json.loads((out / "search.json").read_text())
    assert len(search) == 2
    for page in ("sobre", "fontes", "privacidade", "arquivo", "pesquisa"):
        assert (out / page / "index.html").exists()
    assert (out / "robots.txt").exists() and (out / ".nojekyll").exists()


def test_ai_label_and_escaping(project):
    _, out = _build(project)
    ed = load_config(project).editorial
    news = next(out.glob("artigos/2026/11/tarifas-*/index.html")).read_text()
    data = next(out.glob("artigos/2026/11/armazenamento-*/index.html")).read_text()
    assert ed["policy"]["ai_label"] in news
    assert ed["policy"]["ai_label"] not in data and "dados oficiais" in data
    assert "<script>alert(1)</script>" not in news


def test_reviewed_label_for_pr_articles(project):
    write_article(_news(title="Outra notícia revista pela redação sobre gás natural", review="pr"), project, WHEN)
    cfg = load_config(project)
    build_site(cfg, project / "_site")
    page = next((project / "_site").glob("artigos/2026/11/outra-*/index.html")).read_text()
    assert cfg.editorial["policy"]["ai_label_reviewed"] in page


def test_article_has_jsonld_and_canonical(project):
    _, out = _build(project)
    page = next(out.glob("artigos/2026/11/tarifas-*/index.html")).read_text()
    assert '"@type": "NewsArticle"' in page
    assert 'rel="canonical" href="https://naiabengue.com/fluxoenergetico/news/artigos/2026/11/tarifas-' in page


def test_cname_written_when_domain_set(project):
    cfg = load_config(project)
    cfg.site["domain"] = "fluxoenergetico.pt"
    build_site(cfg, project / "_site")
    assert (project / "_site" / "CNAME").read_text().strip() == "fluxoenergetico.pt"


def test_public_sources_page_hides_internal_tools(project):
    _, out = _build(project)
    page = (out / "fontes" / "index.html").read_text()
    assert "ERSE" in page and "ME-QR" not in page and "Issuu" not in page


def _internal_links(html):
    import re
    return re.findall(r'(?:href|src)="(/[^"]*)"', html)


def test_all_internal_links_use_news_prefix_and_no_cname(project):
    _, out = _build(project)
    assert not (out / "CNAME").exists()
    pages = list(out.rglob("*.html"))
    assert pages
    for page in pages:
        for link in _internal_links(page.read_text()):
            assert link.startswith("/fluxoenergetico/news/"), (page, link)
    search = json.loads((out / "search.json").read_text())
    assert all(s["u"].startswith("/fluxoenergetico/news/artigos/") for s in search)
    assert "https://naiabengue.com/fluxoenergetico/news/sobre/" in (out / "sitemap.xml").read_text()


def test_build_with_subdir_writes_root_redirect(project):
    from fluxo.site.build import build_with_subdir

    write_article(_news(), project, WHEN)
    cfg = load_config(project)
    report = build_with_subdir(cfg, project / "_site", "news")
    root = project / "_site"
    assert report["articles"] == 1
    assert (root / "news" / "index.html").exists()
    redirect = (root / "index.html").read_text()
    assert 'http-equiv="refresh" content="0; url=/fluxoenergetico/news/"' in redirect
    assert 'rel="canonical" href="https://naiabengue.com/fluxoenergetico/news/"' in redirect
    assert 'href="/fluxoenergetico/news/"' in redirect
    assert (root / "404.html").read_text() == (root / "news" / "404.html").read_text()
    assert (root / ".nojekyll").exists() and not (root / "CNAME").exists()


def test_build_with_subdir_rejects_mismatched_base_url(project):
    import pytest
    from fluxo.site.build import build_with_subdir

    with pytest.raises(ValueError):
        build_with_subdir(load_config(project), project / "_site", "noticias")


def test_owner_and_personal_site_disclaimer(project):
    _, out = _build(project)
    about = (out / "sobre" / "index.html").read_text()
    index = (out / "index.html").read_text()
    assert "Pedro Camilo Ramos" in about and "Lisboa" in about and "pedrocamiloramos@gmail.com" in about
    for page in (about, index):
        assert "não representam a entidade empregadora" in page
    for page in out.rglob("*.html"):
        text = page.read_text()
        assert "ENSE" not in text and "Entidade Nacional para o Setor" not in text


def test_cli_build_subdir(project):
    from fluxo.cli import main

    write_article(_news(), project, WHEN)
    assert main(["build", "--root", str(project), "--out", str(project / "_site"), "--subdir", "news"]) == 0
    assert (project / "_site" / "news" / "sobre" / "index.html").exists()
    assert "url=/fluxoenergetico/news/" in (project / "_site" / "index.html").read_text()


def test_approval_page_is_built_hidden_from_search_and_configured(project, tmp_path):
    cfg = load_config(project)
    cfg.editorial["policy"]["approve_api"] = "https://script.google.com/macros/s/X/exec"
    out = tmp_path / "site"
    build_site(cfg, out)
    html = (out / "aprovar" / "index.html").read_text(encoding="utf-8")
    assert 'content="noindex, nofollow"' in html
    assert 'data-api="https://script.google.com/macros/s/X/exec"' in html
    assert 'data-repo="naiabengue/fluxoenergetico"' in html and "static/aprovar.js" in html
    assert (out / "static" / "aprovar.js").exists() and (out / "static" / "frontmatter.js").exists()
    assert html.index("frontmatter.js") < html.index("aprovar.js")
    assert "/aprovar/" not in (out / "sitemap.xml").read_text(encoding="utf-8")
