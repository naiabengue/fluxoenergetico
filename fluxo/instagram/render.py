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
AI_IMAGE_LABEL = "Imagem gerada por IA"
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


def render_carousel(article: dict[str, Any], out_dir: Path, max_slides: int = 7,
                    site_label: str = "", cover_image: Image.Image | None = None,
                    style: dict[str, Any] | None = None) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    style = {**DEFAULT_STYLE, **(style or {})}
    points = article.get("key_points", [])[: max(1, max_slides - 2)]
    total = len(points) + 2
    slides: list[Image.Image] = []

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
        label_font = _font(False, True, 26)
        lw = int(d.textlength(AI_IMAGE_LABEL, font=label_font))
        x1 = W - MARGIN
        d.rounded_rectangle([x1 - lw - 28, 118, x1, 166], radius=8, fill=(6, 20, 30))
        d.text((x1 - 14, 142), AI_IMAGE_LABEL, font=label_font, fill=WHITE, anchor="rm")
    slides.append(im)

    for i, point in enumerate(points, start=2):
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
        im.save(p, "JPEG", quality=90, optimize=True)
        paths.append(p)
    return paths
