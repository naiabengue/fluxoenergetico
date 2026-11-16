"""Carrossel 1080×1350 (4:5) em JPEG, com a identidade do site."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from matplotlib import font_manager
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
INK, TEXT, MUTED = (16, 50, 74), (36, 50, 61), (90, 104, 114)
PANEL, AMBER, WHITE = (238, 243, 241), (226, 160, 28), (255, 255, 255)
MARGIN = 90


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


def _canvas(page: int, total: int, site_label: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    im = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 14], fill=INK)
    d.rectangle([int(W * 0.18), 0, W, 14], fill=AMBER)
    d.text((MARGIN, 60), "Fluxo Energético", font=_font(True, True, 40), fill=INK)
    d.text((W - MARGIN, 66), f"{page}/{total}", font=_font(False, False, 30), fill=MUTED, anchor="ra")
    d.text((MARGIN, H - 90), site_label, font=_font(False, False, 30), fill=MUTED)
    return im, d


def _paragraph(d, text, font, y, fill, width=W - 2 * MARGIN, spacing=1.3) -> int:
    for line in _wrap(d, text, font, width):
        d.text((MARGIN, y), line, font=font, fill=fill)
        y += int(font.size * spacing)
    return y


def render_carousel(article: dict[str, Any], out_dir: Path, max_slides: int = 7,
                    site_label: str = "") -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    points = article.get("key_points", [])[: max(1, max_slides - 2)]
    total = len(points) + 2
    slides: list[Image.Image] = []

    im, d = _canvas(1, total, site_label)
    y = 260
    d.text((MARGIN, y), article.get("category_name", ""), font=_font(False, True, 34), fill=(31, 111, 99))
    y = _paragraph(d, article["title"], _font(True, True, 74), y + 80, INK, spacing=1.18)
    d.rectangle([MARGIN, y + 40, MARGIN + 120, y + 48], fill=AMBER)
    _paragraph(d, article.get("lead", "")[:260], _font(False, False, 36), y + 90, TEXT)
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
    y = _paragraph(d, "Leia o artigo completo, com todas as fontes", _font(True, True, 64), 330, INK, spacing=1.2)
    y = _paragraph(d, f"{site_label} (ligação na bio)", _font(False, True, 40), y + 40, (31, 111, 99))
    sources = "; ".join(s["name"] for s in article.get("sources", []))
    y = _paragraph(d, f"Fonte: {sources}", _font(False, False, 32), y + 80, MUTED)
    if (article.get("ai") or {}).get("used"):
        _paragraph(d, "Texto com apoio de inteligência artificial, verificado contra a fonte.",
                   _font(False, False, 30), y + 30, MUTED)
    elif article.get("type") == "dados":
        _paragraph(d, "Peça gerada a partir de dados oficiais.", _font(False, False, 30), y + 30, MUTED)
    slides.append(im)

    paths = []
    for i, im in enumerate(slides, start=1):
        p = out_dir / f"slide-{i}.jpg"
        im.save(p, "JPEG", quality=90, optimize=True)
        paths.append(p)
    return paths
