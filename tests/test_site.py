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
    assert 'rel="canonical" href="https://fluxoenergetico.github.io/artigos/2026/11/tarifas-' in page


def test_cname_written_when_domain_set(project):
    cfg = load_config(project)
    cfg.site["domain"] = "fluxoenergetico.pt"
    build_site(cfg, project / "_site")
    assert (project / "_site" / "CNAME").read_text().strip() == "fluxoenergetico.pt"
