"""Imagens todos os dias: carrossel em todos os dias de instagram.weekdays e imagem de topo em cada notícia."""
import base64
from datetime import date, datetime, timezone
from io import BytesIO

from PIL import Image

from fluxo.cli import instagram_due
from fluxo.config import load_config
from fluxo.instagram.images import (XMP_AI_PURE, article_images_enabled, make_article_image, make_images,
                                    save_article_image)
from fluxo.models import Draft
from fluxo.pipeline import _article_image
from fluxo.publish import write_article
from fluxo.site.build import build_site

ENV = {"CF_ACCOUNT_ID": "acc123", "CF_API_TOKEN": "tok"}       # sem chave de IA: cenas de reserva, sem verificação
WHEN = datetime(2026, 11, 27, 7, 0, tzinfo=timezone.utc)
ART = {"title": "Energia eólica lidera produção renovável em Portugal durante o mês de outubro",
       "slug": "eolica-outubro", "category": "renovaveis-transicao", "category_name": "Renováveis e transição",
       "lead": "A produção renovável atingiu 65,0% em outubro.",
       "key_points": ["A eólica foi a principal fonte renovável.", "Taxa de incorporação de 73,4%.",
                      "Benefícios de 2,17 mil milhões de euros."]}


class R:
    def __init__(self, status, data):
        self.status_code, self._d = status, data

    def json(self):
        return self._d


def ok_post(calls):
    def post(url, headers=None, json=None, files=None, timeout=None):
        calls.append(url)
        buf = BytesIO()
        Image.new("RGB", (1024, 1024), (30, 90, 150)).save(buf, "JPEG")
        return R(200, {"success": True, "result": {"image": base64.b64encode(buf.getvalue()).decode()}})
    return post


def _draft():
    return Draft(kind="noticia", title=ART["title"], lead=ART["lead"], body="## O que aconteceu\n\nTexto.",
                 category="renovaveis-transicao", key_points=ART["key_points"],
                 sources=[{"name": "APREN", "url": "https://www.apren.pt/x", "date": "2026-11-10"}],
                 ai={"used": True, "review": "auto"}, slug="energia-eolica-lidera-producao-renovavel")


def test_instagram_every_day_by_default(project):
    ed = load_config(project).editorial
    assert ed["instagram"]["weekdays"] == [0, 1, 2, 3, 4, 5, 6]
    assert instagram_due(ed, date(2026, 11, 28)) == (True, "")     # sábado
    assert instagram_due(ed, date(2026, 12, 8)) == (True, "")      # feriado: todos os dias inclui feriados


def test_business_days_setting_skips_weekends_and_holidays(project):
    ed = load_config(project).editorial
    ed["instagram"]["weekdays"] = [0, 1, 2, 3, 4]
    assert instagram_due(ed, date(2026, 11, 27))[0] is True        # sexta
    assert instagram_due(ed, date(2026, 11, 28))[0] is False       # sábado
    assert instagram_due(ed, date(2026, 12, 8)) == (False, "feriado em Lisboa")


def test_article_image_needs_flag_and_credentials(project):
    ed = load_config(project).editorial
    assert article_images_enabled(ed, ENV) is True
    assert article_images_enabled(ed, {"CF_ACCOUNT_ID": "acc123"}) is False
    ed["article_images"]["enabled"] = False
    assert article_images_enabled(ed, ENV) is False


def test_make_article_image_is_capped(project):
    ed = load_config(project).editorial
    calls = []

    def llm(system, prompt, cfg, env, image_jpeg=None):   # cena da IA, depois recusa todas as imagens
        if image_jpeg:
            return {"ok": False, "problems": ["four blades"]}
        return {"cover": "tall wind turbines on green coastal hills above the ocean at golden hour", "points": []}
    im, log = make_article_image(ART, ed, ENV, post=ok_post(calls), llm=llm)   # 2 com a cena da IA + 1 de reserva
    assert im is None and len(calls) == int(ed["instagram"]["ai_images"]["max_attempts"]) + 1
    assert all("recusada" in line for line in log)


def test_daily_pipeline_saves_article_image_with_ai_metadata(project):
    cfg = load_config(project)
    draft, summary, calls = _draft(), {}, []
    _article_image(draft, cfg, ENV, WHEN, project, summary, ok_post(calls))
    assert draft.image == "media/20261127-energia-eolica-lidera-producao-renovavel.jpg" and len(calls) == 1
    with Image.open(project / "content" / draft.image) as im:
        assert im.info.get("xmp") == XMP_AI_PURE
    assert summary["image_log"] == ["imagem do artigo: ok (sem verificação)"]


def test_daily_pipeline_without_credentials_keeps_news_without_image(project):
    cfg = load_config(project)
    draft, summary = _draft(), {}
    _article_image(draft, cfg, {}, WHEN, project, summary, ok_post([]))
    assert draft.image is None and "image_log" not in summary


def test_image_failure_never_blocks_the_news(project):
    cfg = load_config(project)
    draft, summary = _draft(), {}

    def boom(*a, **k):
        raise RuntimeError("rede")
    _article_image(draft, cfg, ENV, WHEN, project, summary, boom)
    assert draft.image is None and any("falhou" in line for line in summary["image_log"])


def test_site_shows_image_with_ai_caption_and_og_image(project):
    draft = _draft()
    draft.image = "media/20261127-eolica.jpg"
    save_article_image(Image.new("RGB", (1024, 1024)), project / "content" / draft.image)
    write_article(draft, project, WHEN)
    cfg = load_config(project)
    build_site(cfg, project / "_site")
    html = next((project / "_site").rglob("energia-eolica-lidera-producao-renovavel*/index.html")).read_text()
    assert 'class="hero"' in html and "Imagem gerada por inteligência artificial" in html
    assert '<meta property="og:image"' in html and "media/20261127-eolica.jpg" in html


def test_carousel_reuses_site_image_as_cover(project):
    ed = load_config(project).editorial
    calls = []
    hero = Image.new("RGB", (1024, 1024), (200, 0, 0))
    out = make_images(ART, 3, ed, ENV, post=ok_post(calls), llm=lambda *a, **k: None, cover=hero)
    assert out.cover is hero and len(calls) == 3 and out.count == 4
    assert out.log[0] == "capa: usa a imagem do artigo no site"
