from datetime import datetime, timezone

from PIL import Image

from fluxo.config import load_config
from fluxo.instagram.caption import make_caption
from fluxo.instagram.publish import publish_carousel, publish_enabled
from fluxo.instagram.render import render_carousel
from fluxo.instagram.select import pick_for_week

NOW = datetime(2026, 11, 17, 9, tzinfo=timezone.utc)
ART = {"title": "Armazenamento de gás: UE a 87,1% e Portugal a 94,5% da capacidade", "slug": "armazenamento-gas",
       "date": "2026-11-16", "category": "eletricidade-gas", "category_name": "Eletricidade e gás",
       "lead": "No dia de gás 14 de novembro de 2026, as reservas da UE desceram 0,87 pontos percentuais.",
       "key_points": ["UE: 87,1% da capacidade (985,2 TWh)", "Portugal: 94,5% da capacidade",
                      "Variação semanal na UE: −0,87 pontos percentuais", "Quarto ponto", "Quinto ponto"],
       "sources": [{"name": "Gas Infrastructure Europe — AGSI+", "url": "https://agsi.gie.eu/"}],
       "ai": {"used": False}, "type": "dados", "url": "/artigos/2026/11/armazenamento-gas/"}


def test_render_jpeg_1080x1350_max_slides(tmp_path):
    paths = render_carousel(ART, tmp_path, max_slides=7, site_label="fluxoenergetico.pt")
    assert 3 <= len(paths) <= 7
    for p in paths:
        with Image.open(p) as im:
            assert im.format == "JPEG" and im.size == (1080, 1350)


def test_caption_under_2200_chars(project):
    cfg = load_config(project)
    cap = make_caption(dict(ART, lead="x" * 3000), "https://fluxoenergetico.pt", cfg.editorial["instagram"]["hashtags"])
    assert len(cap) <= 2200
    assert "fluxoenergetico.pt" in cap and "Fonte: Gas Infrastructure Europe" in cap
    assert sum(1 for w in cap.split() if w.startswith("#")) <= 8


def test_caption_marks_ai_text(project):
    cfg = load_config(project)
    cap = make_caption(dict(ART, ai={"used": True}), "https://x.pt", cfg.editorial["instagram"]["hashtags"])
    assert "inteligência artificial" in cap


def test_pick_for_week_excludes_already_posted_and_old():
    arts = [dict(ART, slug="a", date="2026-11-16", score=90), dict(ART, slug="b", date="2026-11-15", score=85),
            dict(ART, slug="c", date="2026-11-01", score=99), dict(ART, slug="d", date="2026-11-14", score=70)]
    picked = pick_for_week(arts, NOW, n=2, already_posted={"a"})
    assert [a["slug"] for a in picked] == ["b", "d"]


def test_publish_skipped_without_token(project):
    ed = load_config(project).editorial
    ed["instagram"]["auto_publish"] = True
    assert publish_enabled(ed, env={}) is False
    assert publish_enabled(ed, env={"IG_ACCESS_TOKEN": "t", "IG_USER_ID": "1"}) is True


def test_publish_carousel_calls_api_in_order():
    calls = []

    class R:
        def __init__(self, data):
            self.status_code, self._d = 200, data

        def json(self):
            return self._d

    def post(url, data=None, timeout=None):
        calls.append(("POST", url.split("/")[-1], dict(data)))
        if url.endswith("media_publish"):
            return R({"id": "final"})
        return R({"id": f"c{len(calls)}"})

    def get(url, params=None, timeout=None):
        calls.append(("GET", url.split("/")[-1], dict(params)))
        return R({"status_code": "FINISHED"})

    media_id = publish_carousel(["https://x.pt/1.jpg", "https://x.pt/2.jpg"], "legenda", "17841", "TOKEN", "v24.0",
                                post=post, get=get, sleep=lambda s: None)
    assert media_id == "final"
    assert [c[2].get("is_carousel_item") for c in calls[:2]] == ["true", "true"]
    assert calls[2][2]["media_type"] == "CAROUSEL" and calls[2][2]["children"] == "c1,c2"
    assert calls[-1][1] == "media_publish"


def test_slide_urls_follow_public_base(project):
    from fluxo.instagram.publish import slide_urls
    from fluxo.site.build import public_base

    base = public_base(load_config(project).site)
    assert base == "https://naiabengue.com/fluxoenergetico/news"
    urls = slide_urls(base, "instagram/2026-11-17/armazenamento-gas", 3)
    assert urls == [f"https://naiabengue.com/fluxoenergetico/news/instagram/2026-11-17/armazenamento-gas/slide-{i}.jpg"
                    for i in (1, 2, 3)]
