"""Texto limpo de páginas HTML e PDF (para redação e verificação)."""
from __future__ import annotations

import io
import re

from bs4 import BeautifulSoup

MAX_CHARS = 20000


def extract_html_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form", "noscript", "svg"]):
        tag.decompose()
    root = soup.find("article") or soup.find("main") or soup.body or soup
    return re.sub(r"\s+", " ", root.get_text(" ", strip=True)).strip()[:MAX_CHARS]


def extract_pdf_text(content: bytes, max_pages: int = 12) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    parts = []
    for page in reader.pages[:max_pages]:
        parts.append(page.extract_text() or "")
    return re.sub(r"\s+", " ", " ".join(parts)).strip()[:MAX_CHARS]


def extract_text(resp) -> str:
    if "pdf" in resp.content_type or resp.url.lower().split("?")[0].endswith(".pdf"):
        return extract_pdf_text(resp.content)
    return extract_html_text(resp.text)
