import base64
from io import BytesIO

from PIL import Image

from fluxo.config import load_config
from fluxo.instagram.cover_image import build_prompt, cover_enabled, generate_cover
from fluxo.instagram.render import AI_IMAGE_LABEL, render_carousel

ART = {"title": "Armazenamento de gás: UE a 87,1% e Portugal a 94,5% da capacidade", "slug": "armazenamento-gas",
       "category": "eletricidade-gas", "category_name": "Eletricidade e gás", "lead": "Reservas acima de 87%.",
       "key_points": ["Um ponto", "Dois pontos", "Três pontos"], "sources": [{"name": "GIE", "url": "https://agsi.gie.eu/"}],
       "ai": {"used": False}, "type": "dados"}
ENV = {"CF_ACCOUNT_ID": "acc123", "CF_API_TOKEN": "tok"}


def _jpeg_b64(color=(200, 30, 30), size=(1024, 1024)):
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, "JPEG")
    return base64.b64encode(buf.getvalue()).decode()


class R:
    def __init__(self, status, data):
        self.status_code, self._d = status, data

    def json(self):
        return self._d


def test_cover_enabled_needs_flag_and_credentials(project):
    ed = load_config(project).editorial
    ed["instagram"]["ai_cover"] = True
    assert cover_enabled(ed, ENV) is True
    assert cover_enabled(ed, {"CF_ACCOUNT_ID": "acc123"}) is False
    ed["instagram"]["ai_cover"] = False
    assert cover_enabled(ed, ENV) is False


def test_prompt_is_english_without_text_people_or_title_words():
    prompt = build_prompt(ART)
    low = prompt.lower()
    assert "gas" in low and "no text" in low and "no people" in low and "no logos" in low
    for word in ("armazenamento", "capacidade", "portugal", "87,1"):
        assert word not in low


def test_generate_cover_calls_workers_ai_rest():
    calls = []

    def post(url, headers=None, json=None, timeout=None):
        calls.append((url, headers, json))
        return R(200, {"success": True, "errors": [], "messages": [], "result": {"image": _jpeg_b64()}})

    im = generate_cover(ART, ENV, post=post)
    assert im is not None and im.size == (1024, 1024) and im.mode == "RGB"
    url, headers, body = calls[0]
    assert url == "https://api.cloudflare.com/client/v4/accounts/acc123/ai/run/@cf/black-forest-labs/flux-1-schnell"
    assert headers["Authorization"] == "Bearer tok"
    assert body["prompt"] == build_prompt(ART) and 1 <= body["steps"] <= 8


def test_generate_cover_falls_back_to_none_on_any_failure():
    def boom(*a, **k):
        raise TimeoutError("sem rede")

    assert generate_cover(ART, ENV, post=boom) is None
    assert generate_cover(ART, ENV, post=lambda *a, **k: R(429, {"success": False, "errors": [{"code": 3036}]})) is None
    assert generate_cover(ART, ENV, post=lambda *a, **k: R(200, {"success": True, "result": {"image": "não é base64"}})) is None
    assert generate_cover(ART, {}, post=boom) is None


def test_cover_slide_uses_image_with_dark_overlay(tmp_path):
    cover = Image.new("RGB", (1024, 1024), (220, 30, 30))
    with_img = render_carousel(ART, tmp_path / "a", 7, "naiabengue.com/fluxoenergetico/news", cover_image=cover)
    plain = render_carousel(ART, tmp_path / "b", 7, "naiabengue.com/fluxoenergetico/news")
    with Image.open(with_img[0]) as a, Image.open(plain[0]) as b:
        assert a.size == (1080, 1350)
        r, g, bl = a.getpixel((1000, 200))
        assert r > g + 20 and r < 200            # imagem vermelha escurecida pelo véu
        assert b.getpixel((1000, 200)) == (255, 255, 255) or sum(b.getpixel((1000, 200))) > 740
    assert AI_IMAGE_LABEL == "Imagem gerada por IA"


def test_prompt_picks_motifs_from_title():
    prompt = build_prompt(ART)
    assert "natural gas storage tanks" in prompt
    assert "wind turbines" in build_prompt(dict(ART, title="Eólica offshore: novo leilão em 2027",
                                                category="renovaveis-transicao"))
