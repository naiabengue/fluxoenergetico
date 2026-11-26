"""Carrossel 1080×1350 (4:5) em JPEG, com a identidade do site."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from matplotlib import font_manager
from PIL import Image, ImageDraw, ImageFont, ImageOps

W, H = 1080, 1350
INK, TEXT, MUTED = (16, 50, 74), (36, 50, 61), (90, 104, 114)
PANEL, AMBER, WHITE = (238, 243, 241), (226, 160, 28), (255, 255, 255)
TEAL, LIGHT = (31, 111, 99), (225, 232, 236)
MARGIN = 90
IMG_TOP, IMG_BOTTOM = 130, 830       # faixa da imagem nos diapositivos dos pontos-chave
AI_IMAGE_LABEL = "Imagem gerada por IA"
XMP_AI = ('<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
          '<rdf:Description rdf:about="" xmlns:Iptc4xmpExt="http://iptc.org/std/Iptc4xmpExt/2008-02-29/">'
          "<Iptc4xmpExt:DigitalSourceType>http://cv.iptc.org/newscodes/digitalsourcetype/"
          "compositeWithTrainedAlgorithmicMedia</Iptc4xmpExt:DigitalSourceType>"
          "</rdf:Description></rdf:RDF></x:xmpmeta>").encode()
DEFAULT_STYLE = {"cta_slide": "Guarda e partilha", "cover_hint": "Desliza para ver os números →"}


def _font(serif: bool, bold: bool, size: int) -> ImageFont.FreeTypeFont:
    family = "DejaVu Serif" if serif else "DejaVu Sans"
    path = font_manager.findfont(font_manager.FontProperties(family=family, weight="bold" if bold else "normal"))
    return ImageFont.truetype(path, size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _canvas(page: int, total: int, site_label: str,
            background: Image.Image | None = None) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    dark = background is not None
    im = background if dark else Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 14], fill=INK)
    d.rectangle([int(W * 0.18), 0, W, 14], fill=AMBER)
    d.text((MARGIN, 60), "Fluxo Energético", font=_font(True, True, 40), fill=WHITE if dark else INK)
    d.text((W - MARGIN, 66), f"{page}/{total}", font=_font(False, False, 30), fill=LIGHT if dark else MUTED, anchor="ra")
    d.text((MARGIN, H - 90), site_label, font=_font(False, False, 30), fill=LIGHT if dark else MUTED)
    return im, d


def _veiled(cover: Image.Image) -> Image.Image:
    """Imagem a toda a área, com véu escuro (mais denso em baixo) para o texto ler bem."""
    bg = ImageOps.fit(cover.convert("RGB"), (W, H), method=Image.LANCZOS)
    bg = Image.blend(bg, Image.new("RGB", (W, H), INK), 0.6)
    shade = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(shade)
    for y in range(H // 2, H):
        sd.line([(0, y), (W, y)], fill=int(150 * (y - H // 2) / (H // 2)))
    return Image.composite(Image.new("RGB", (W, H), (6, 20, 30)), bg, shade)


def closing_lines(article: dict[str, Any], site_label: str, cta: str) -> list[tuple[str, str]]:
    """Texto do último diapositivo, de cima para baixo: apelo, convite, ligação, fonte, notas."""
    lines = [("cta", cta), ("title", "Lê o artigo completo, com todas as fontes"),
             ("link", f"{site_label} (ligação na bio)")]
    sources = "; ".join(s["name"] for s in article.get("sources", []))
    if sources:
        lines.append(("source", f"Fonte: {sources}"))
    if (article.get("ai") or {}).get("used"):
        lines.append(("note", "Texto com apoio de inteligência artificial, verificado contra a fonte."))
    elif article.get("type") == "dados":
        lines.append(("note", "Peça gerada a partir de dados oficiais."))
    return lines


def _paragraph(d, text, font, y, fill, width=W - 2 * MARGIN, spacing=1.3) -> int:
    for line in _wrap(d, text, font, width):
        d.text((MARGIN, y), line, font=font, fill=fill)
        y += int(font.size * spacing)
    return y


def carousel_points(article: dict[str, Any], max_slides: int = 7, chart: bool = False) -> list[str]:
    """Pontos-chave que cabem no carrossel: capa + [gráfico] + pontos + apelo final ≤ max_slides."""
    return article.get("key_points", [])[: max(1, max_slides - 2 - int(chart))]


def _ai_label(d: ImageDraw.ImageDraw, right: int, cy: int) -> None:
    label_font = _font(False, True, 26)
    lw = int(d.textlength(AI_IMAGE_LABEL, font=label_font))
    d.rounded_rectangle([right - lw - 28, cy - 24, right, cy + 24], radius=8, fill=(6, 20, 30))
    d.text((right - 14, cy), AI_IMAGE_LABEL, font=label_font, fill=WHITE, anchor="rm")


TEXT_TOP = IMG_BOTTOM + 95
TEXT_ROOM = H - 130 - TEXT_TOP


def point_font_size(points: list[str]) -> int:
    """Maior letra (igual em todos os diapositivos) que deixa cada ponto inteiro na área de texto."""
    d = ImageDraw.Draw(Image.new("RGB", (W, 10)))
    for size in range(58, 33, -4):
        font = _font(True, True, size)
        if all(len(_wrap(d, p, font, W - 2 * MARGIN)) * int(size * 1.22) <= TEXT_ROOM for p in points):
            return size
    return 34


def _image_point_slide(page: int, total: int, site_label: str, point: str, image: Image.Image,
                       size: int = 58) -> Image.Image:
    """Imagem do tema em cima (largura total) e o ponto-chave em baixo, escrito pelo código."""
    im, d = _canvas(page, total, site_label)
    im.paste(ImageOps.fit(image.convert("RGB"), (W, IMG_BOTTOM - IMG_TOP), method=Image.LANCZOS), (0, IMG_TOP))
    _ai_label(d, W - 24, IMG_BOTTOM - 40)
    d.rectangle([MARGIN, IMG_BOTTOM + 50, MARGIN + 120, IMG_BOTTOM + 58], fill=AMBER)
    font = _font(True, True, size)
    lines = _wrap(d, point, font, W - 2 * MARGIN)
    y = TEXT_TOP
    for line in lines:
        d.text((MARGIN, y), line, font=font, fill=INK)
        y += int(font.size * 1.22)
    return im


def _chart_slide(page: int, total: int, site_label: str, chart_path: Path, sources: str) -> Image.Image:
    """Gráfico real da peça de dados (charts.py), nunca uma ilustração de números."""
    im, d = _canvas(page, total, site_label)
    d.text((MARGIN, 260), "Em gráfico", font=_font(False, True, 34), fill=TEAL)
    with Image.open(chart_path) as ch:
        chart = ch.convert("RGB")
    chart.thumbnail((W - 2 * MARGIN, 760), Image.LANCZOS)
    im.paste(chart, ((W - chart.width) // 2, 340))
    if sources:
        _paragraph(d, f"Dados: {sources}", _font(False, False, 30), 340 + chart.height + 40, MUTED)
    return im


def render_carousel(article: dict[str, Any], out_dir: Path, max_slides: int = 7,
                    site_label: str = "", cover_image: Image.Image | None = None,
                    style: dict[str, Any] | None = None, point_images: list[Image.Image | None] | None = None,
                    chart_path: Path | None = None) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    style = {**DEFAULT_STYLE, **(style or {})}
    chart_path = Path(chart_path) if chart_path and Path(chart_path).is_file() else None
    points = carousel_points(article, max_slides, chart=chart_path is not None)
    images = list(point_images or [])[: len(points)]
    images += [None] * (len(points) - len(images))
    total = len(points) + 2 + int(chart_path is not None)
    slides: list[Image.Image] = []
    ai_slides: set[int] = set()

    # Capa: título e entrada; com imagem IA, o texto fica em branco sobre o véu e a imagem é identificada.
    dark = cover_image is not None
    im, d = _canvas(1, total, site_label, _veiled(cover_image) if dark else None)
    y = 260
    d.text((MARGIN, y), article.get("category_name", ""), font=_font(False, True, 34), fill=AMBER if dark else TEAL)
    y = _paragraph(d, article["title"], _font(True, True, 74), y + 80, WHITE if dark else INK, spacing=1.18)
    d.rectangle([MARGIN, y + 40, MARGIN + 120, y + 48], fill=AMBER)
    _paragraph(d, article.get("lead", "")[:260], _font(False, False, 36), y + 90, LIGHT if dark else TEXT)
    hint_font = _font(False, True, 34)
    d.text((W - MARGIN, H - 200), style["cover_hint"], font=hint_font, fill=AMBER if dark else TEAL, anchor="ra")
    if dark:
        _ai_label(d, W - MARGIN, 142)
        ai_slides.add(0)
    slides.append(im)

    first = 2
    if chart_path is not None:
        sources = "; ".join(s["name"] for s in article.get("sources", []))
        slides.append(_chart_slide(2, total, site_label, chart_path, sources))
        first = 3

    size = point_font_size([p for p, img in zip(points, images) if img is not None] or ["x"])
    for i, (point, image) in enumerate(zip(points, images), start=first):
        if image is not None:
            ai_slides.add(len(slides))
            slides.append(_image_point_slide(i, total, site_label, point, image, size))
            continue
        im, d = _canvas(i, total, site_label)
        d.rectangle([MARGIN, 300, MARGIN + 10, 760], fill=AMBER)
        d.rectangle([MARGIN + 10, 300, W - MARGIN, 760], fill=PANEL)
        font = _font(True, True, 62 if len(point) < 70 else 50)
        lines = _wrap(d, point, font, W - 2 * MARGIN - 80)
        y = 530 - len(lines) * int(font.size * 1.2) // 2
        for line in lines:
            d.text((MARGIN + 50, y), line, font=font, fill=INK)
            y += int(font.size * 1.2)
        slides.append(im)

    im, d = _canvas(total, total, site_label)
    y = 260
    for kind, text in closing_lines(article, site_label, style["cta_slide"]):
        if kind == "cta":
            d.rectangle([MARGIN, y, MARGIN + 10, y + 70], fill=AMBER)
            d.text((MARGIN + 34, y + 35), text, font=_font(False, True, 48), fill=TEAL, anchor="lm")
            y += 150
        elif kind == "title":
            y = _paragraph(d, text, _font(True, True, 64), y, INK, spacing=1.2)
        elif kind == "link":
            y = _paragraph(d, text, _font(False, True, 40), y + 40, TEAL) + 40
        elif kind == "source":
            y = _paragraph(d, text, _font(False, False, 32), y + 40, MUTED)
        else:
            y = _paragraph(d, text, _font(False, False, 30), y + 30, MUTED)
    slides.append(im)

    paths = []
    for i, im in enumerate(slides, start=1):
        p = out_dir / f"slide-{i}.jpg"
        extra = {"xmp": XMP_AI} if (i - 1) in ai_slides else {}   # IPTC: composto com imagem gerada por IA
        im.save(p, "JPEG", quality=90, optimize=True, **extra)
        paths.append(p)
    return paths
