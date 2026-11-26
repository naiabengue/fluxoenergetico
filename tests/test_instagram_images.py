import base64
from io import BytesIO

from PIL import Image

from fluxo.config import load_config
from fluxo.instagram.caption import make_caption
from fluxo.instagram.images import (BANNED, BRIEF_SYSTEM, CHECK_SYSTEM, _clean_scene, fallback_scenes, generate_image,
                                    images_enabled, make_images, settings, visual_brief)
from fluxo.instagram.render import AI_IMAGE_LABEL, XMP_AI, carousel_points, render_carousel
from fluxo.llm import generate_json

ENV = {"CF_ACCOUNT_ID": "acc123", "CF_API_TOKEN": "tok", "GEMINI_API_KEY": "g"}
ART = {"title": "Energia eólica lidera produção renovável em Portugal durante o mês de outubro",
       "slug": "eolica-outubro", "category": "renovaveis-transicao", "category_name": "Renováveis e transição",
       "lead": "A produção renovável atingiu 65,0% em outubro.",
       "key_points": ["A energia eólica foi a principal fonte renovável em outubro, com 36,8% da geração limpa.",
                      "Portugal atingiu uma taxa de incorporação renovável de 73,4% entre janeiro e outubro.",
                      "Os benefícios económicos diretos superam os 2,17 mil milhões de euros este ano.",
                      "O país é o quarto mercado europeu com maior penetração de energias renováveis."],
       "sources": [{"name": "APREN", "url": "https://www.apren.pt/"}], "ai": {"used": True}, "type": "noticia"}
GOOD = {"cover": "tall wind turbines on green coastal hills above the ocean at golden hour",
        "points": ["a low angle view of one giant wind turbine against an evening sky",
                   "a valley with wind turbines on the ridge, solar panels on the slope and a dam below",
                   "high-voltage power lines carrying energy from distant wind turbines to a small town",
                   "an abstract continent at night with glowing wind farms linked by thin luminous lines"]}


def _jpeg_b64(color=(40, 90, 160), size=(1024, 1024)):
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, "JPEG")
    return base64.b64encode(buf.getvalue()).decode()


class R:
    def __init__(self, status, data):
        self.status_code, self._d = status, data

    def json(self):
        return self._d


def ok_post(calls):
    def post(url, headers=None, json=None, files=None, timeout=None):
        calls.append({"url": url, "json": json, "files": files})
        return R(200, {"success": True, "result": {"image": _jpeg_b64()}})
    return post


def fake_llm(brief=GOOD, verdicts=None):
    """Simula a IA de texto: devolve as cenas e, para cada imagem, o veredicto seguinte da lista."""
    verdicts = list(verdicts or [])
    seen = {"brief": 0, "check": 0, "images": []}

    def llm(system, prompt, cfg, env, image_jpeg=None):
        if system == BRIEF_SYSTEM:
            seen["brief"] += 1
            return brief
        assert system == CHECK_SYSTEM and image_jpeg
        seen["check"] += 1
        seen["images"].append(image_jpeg)
        return verdicts.pop(0) if verdicts else {"ok": True, "problems": []}
    return llm, seen


def editorial(project, **over):
    ed = load_config(project).editorial
    ed["instagram"]["ai_images"] = {**ed["instagram"]["ai_images"], **over}
    return ed


def test_enabled_needs_flag_and_cloudflare_credentials(project):
    ed = editorial(project, enabled=True)
    assert images_enabled(ed, ENV) is True
    assert images_enabled(ed, {"CF_ACCOUNT_ID": "acc123"}) is False
    assert images_enabled(editorial(project, enabled=False), ENV) is False


def test_old_ai_cover_setting_still_means_cover_only(project):
    ed = load_config(project).editorial
    ed["instagram"].pop("ai_images")
    ed["instagram"]["ai_cover"] = True
    assert settings(ed)["enabled"] is True and settings(ed)["slides"] == "cover"


def test_scene_filter_rejects_portuguese_digits_people_text_and_real_names():
    assert _clean_scene("tall wind turbines on green coastal hills above the ocean at dusk")
    assert _clean_scene("tall wind turbines with no people and no text on green hills")   # negativos não contam
    for bad in ["aerogeradores em colinas verdes junto ao mar ao fim da tarde",       # português (acentos ou não)
                "wind turbines producing 36 percent of the clean power in the country",
                "an engineer in a helmet inspecting a wind turbine on a hill",
                "a sign with the word energy next to a wind turbine on a hill",
                "wind turbines on the hills of Portugal at sunset in autumn",
                "too short", None, 42]:
        assert _clean_scene(bad) is None, bad


def test_fallback_scenes_follow_topic_and_do_not_repeat():
    scenes = fallback_scenes(ART, 4)
    assert len(scenes) == 5 and len(set(scenes)) == 5
    assert "wind turbines" in scenes[1]          # «eólica» no primeiro ponto
    assert all(s.isascii() and not BANNED.search(s) for s in scenes)


def test_visual_brief_uses_llm_and_replaces_only_invalid_scenes():
    llm, seen = fake_llm(dict(GOOD, points=GOOD["points"][:2] + ["pessoas a olhar para um gráfico", None]))
    scenes, origin = visual_brief(ART, 4, {"providers": []}, ENV, llm=llm)
    assert origin == "ia" and seen["brief"] == 1
    assert scenes[:3] == [GOOD["cover"], *GOOD["points"][:2]]
    assert scenes[3:] == fallback_scenes(ART, 4)[3:]


def test_visual_brief_without_llm_uses_fallback():
    scenes, origin = visual_brief(ART, 4, {"providers": []}, ENV, llm=lambda *a, **k: None)
    assert origin == "palavras-chave" and scenes == fallback_scenes(ART, 4)


def test_schnell_uses_json_body_and_klein_uses_multipart():
    calls = []
    im, why = generate_image("wind turbines. STYLE", ENV, "flux-1-schnell", seed=5, steps=12, post=ok_post(calls))
    assert im is not None and why == "ok"
    assert calls[0]["url"].endswith("/accounts/acc123/ai/run/@cf/black-forest-labs/flux-1-schnell")
    assert calls[0]["json"] == {"prompt": "wind turbines. STYLE", "steps": 8, "seed": 5}   # máximo 8 passos
    im, _ = generate_image("wind turbines. STYLE", ENV, "flux-2-klein-4b", seed=5, size=1024, post=ok_post(calls))
    assert im is not None and calls[1]["url"].endswith("@cf/black-forest-labs/flux-2-klein-4b")
    assert calls[1]["files"]["prompt"] == (None, "wind turbines. STYLE")
    assert calls[1]["files"]["width"] == (None, "1024") and calls[1]["json"] is None


def test_generate_image_never_raises_and_never_leaks_token():
    def boom(*a, **k):
        raise TimeoutError("tok")
    assert generate_image("x", ENV, post=boom) == (None, "TimeoutError")
    im, why = generate_image("x", ENV, post=lambda *a, **k: R(429, {"success": False, "errors": [{"code": 3036}]}))
    assert im is None and why == "HTTP 429 3036" and "tok" not in why
    assert generate_image("x", ENV, post=lambda *a, **k: R(200, {"result": {"image": "???"}}))[0] is None
    assert generate_image("x", {}, post=boom)[0] is None
    assert generate_image("x", ENV, model="desconhecido", post=boom)[0] is None


def test_make_images_fills_cover_and_every_point(project):
    calls = []
    llm, seen = fake_llm()
    out = make_images(ART, 4, editorial(project), ENV, post=ok_post(calls), llm=llm)
    assert out.cover is not None and all(out.points) and out.count == 5
    assert len(calls) == 5 and seen["check"] == 5 and out.brief == "ia"
    assert len({c["json"]["seed"] for c in calls}) == 5
    assert all("No text" in c["json"]["prompt"] for c in calls)


def test_rejected_image_is_retried_then_left_typographic(project):
    calls = []
    no = {"ok": False, "problems": ["letters on the tower"]}
    llm, _ = fake_llm(verdicts=[{"ok": True}, no, {"ok": True}, no, no])   # ponto 1 à 2.ª, ponto 2 falha 2×
    out = make_images(ART, 4, editorial(project, max_attempts=2), ENV, post=ok_post(calls), llm=llm)
    assert out.cover is not None and out.points[0] is not None and out.points[1] is None
    assert any("recusada" in line for line in out.log)


def test_check_unavailable_accepts_image(project):
    calls = []

    def llm(system, prompt, cfg, env, image_jpeg=None):
        return GOOD if system == BRIEF_SYSTEM else None
    out = make_images(ART, 4, editorial(project), ENV, post=ok_post(calls), llm=llm)
    assert out.count == 5 and all("sem verificação" in line for line in out.log)


def test_quota_error_stops_further_requests(project):
    calls = []

    def post(url, **k):
        calls.append(url)
        return R(429, {"success": False, "errors": [{"code": 3036}]})
    llm, _ = fake_llm()
    out = make_images(ART, 4, editorial(project), ENV, post=post, llm=llm)
    assert out.count == 0 and len(calls) == 1


def test_cover_only_mode_generates_one_image(project):
    calls = []
    llm, _ = fake_llm()
    out = make_images(ART, 4, editorial(project, slides="cover"), ENV, post=ok_post(calls), llm=llm)
    assert out.cover is not None and out.points == [None] * 4 and len(calls) == 1


def test_llm_sends_image_only_to_gemini():
    sent = []

    def post(url, headers=None, json=None, timeout=None):
        sent.append((url, json))
        return R(200, {"candidates": [{"content": {"parts": [{"text": '{"ok": true, "problems": []}'}]}}]})
    cfg = {"providers": [{"kind": "openai_compatible", "key_env": "LLM_API_KEY"},
                         {"kind": "gemini", "models": ["gemini-x"], "key_env": "GEMINI_API_KEY"}]}
    data = generate_json("s", "p", cfg, {"LLM_API_KEY": "m", "GEMINI_API_KEY": "g"}, post=post, image_jpeg=b"\xff\xd8")
    assert data["ok"] is True and len(sent) == 1 and "gemini-x" in sent[0][0]
    parts = sent[0][1]["contents"][0]["parts"]
    assert parts[0]["inlineData"] == {"mimeType": "image/jpeg", "data": base64.b64encode(b"\xff\xd8").decode()}


def test_render_point_slides_with_images_label_and_metadata(tmp_path):
    pics = [Image.new("RGB", (1024, 1024), (200, 40, 40))] * 4
    paths = render_carousel(ART, tmp_path, 7, "naiabengue.com/fluxoenergetico/news",
                            cover_image=Image.new("RGB", (1024, 1024), (40, 40, 200)), point_images=pics)
    assert len(paths) == 6
    for p in paths:
        with Image.open(p) as im:
            assert im.size == (1080, 1350)
            has_ai = p.name != "slide-6.jpg"
            assert (im.info.get("xmp") == XMP_AI) is has_ai
    with Image.open(paths[1]) as im:
        r, g, b = im.getpixel((540, 400))
        assert r > 150 and g < 90                       # imagem do ponto na faixa de cima
    assert AI_IMAGE_LABEL == "Imagem gerada por IA"


def test_long_point_still_fits_text_area(tmp_path):
    long = dict(ART, key_points=["Os benefícios económicos diretos das energias renováveis superam os 2,17 mil "
                                 "milhões de euros este ano, segundo a associação, que destaca ainda a redução "
                                 "das importações de gás natural e o efeito nos preços do mercado grossista."])
    paths = render_carousel(long, tmp_path, 7, "x", point_images=[Image.new("RGB", (1024, 1024))])
    with Image.open(paths[1]) as im:
        footer_band = im.crop((0, 1225, 1080, 1250))
        assert footer_band.getextrema()[0][0] > 200     # nenhuma linha de texto invade o rodapé


def test_data_piece_gets_real_chart_slide(tmp_path):
    chart = tmp_path / "grafico.png"
    Image.new("RGB", (1200, 675), (10, 120, 90)).save(chart)
    data = dict(ART, type="dados", key_points=["a", "b", "c", "d", "e"])
    assert len(carousel_points(data, 7, chart=True)) == 4
    paths = render_carousel(data, tmp_path / "out", 7, "x", chart_path=chart)
    assert len(paths) == 7
    with Image.open(paths[1]) as im:
        assert im.getpixel((540, 500))[1] > 100 and "xmp" not in im.info   # gráfico real, sem rótulo IA


def test_caption_notes_ai_images():
    tags = ["#energia"]
    assert "Imagens geradas por IA." in make_caption(ART, "https://x.pt", tags, ai_images=5)
    assert "Imagem de capa gerada por IA." in make_caption(ART, "https://x.pt", tags, ai_cover=True, ai_images=1)
    assert "gerada por IA" not in make_caption(ART, "https://x.pt", tags)


def test_cli_carousel_uses_generated_images_and_caption_note(project, monkeypatch, tmp_path):
    import fluxo.instagram.images as images
    from fluxo.cli import _build_carousel

    monkeypatch.setenv("CF_ACCOUNT_ID", "acc123")
    monkeypatch.setenv("CF_API_TOKEN", "tok")
    monkeypatch.setattr(images, "visual_brief", lambda a, n, *x, **k: ([GOOD["cover"], *GOOD["points"][:n]], "ia"))
    monkeypatch.setattr(images, "generate_image", lambda *a, **k: (Image.new("RGB", (1024, 1024), (9, 9, 9)), "ok"))
    monkeypatch.setattr(images, "check_image", lambda *a, **k: (True, ""))
    cfg = load_config(project)
    paths, caption, info = _build_carousel(cfg, ART, tmp_path / "c")
    assert len(paths) == 6 and info["ai_images"] == 5 and info["brief"] == "ia"
    assert "Imagens geradas por IA." in caption
    assert (tmp_path / "c" / "legenda.txt").read_text(encoding="utf-8") == caption
