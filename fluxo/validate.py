"""Validação bloqueante: um artigo só é publicado se passar todas as verificações de erro."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from .dedup import similarity, strip_accents
from .models import Draft

NUM = re.compile(r"(?<![\w.,])(\d{1,3}(?:[  .,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)(?![\w])")
MONTHS_PT = ("janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro")
DAY_OF_MONTH = re.compile(rf"^\s*(de\s+)?({MONTHS_PT})\b", re.I)
MULTIPLIERS = [(re.compile(r"^\s*mil\s+milh(ões|oes)"), 1e9), (re.compile(r"^\s*milh(ões|ão|oes|ao)"), 1e6),
               (re.compile(r"^\s*mil\b"), 1e3), (re.compile(r"^\s*(billion|bn)\b", re.I), 1e9),
               (re.compile(r"^\s*(million|mn)\b", re.I), 1e6)]


@dataclass
class Validation:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _interpret(token: str, lang: str) -> set[float]:
    t = token.replace(" ", " ")
    out: set[float] = set()
    if lang in ("pt", "any"):
        try:
            out.add(float(t.replace(" ", "").replace(".", "").replace(",", ".")))
        except ValueError:
            pass
    if lang in ("en", "any"):
        try:
            out.add(float(t.replace(" ", "").replace(",", "")))
        except ValueError:
            pass
    return out


def _decimals(token: str, lang: str) -> int:
    sep = "," if lang == "pt" else "."
    m = re.search(rf"\{sep}(\d+)$", token)
    return len(m.group(1)) if m and not re.search(r"\d{3}$", token[: m.start()] or "x") or (m and len(m.group(1)) != 3) else 0


def number_tokens(text: str) -> list[tuple[str, str]]:
    """Lista (token, texto seguinte) para cada número."""
    return [(m.group(1), text[m.end(): m.end() + 25]) for m in NUM.finditer(text)]


def number_values(text: str, lang: str = "pt") -> set[float]:
    values: set[float] = set()
    for token, after in number_tokens(text):
        vals = _interpret(token, lang)
        values |= vals
        for rx, mult in MULTIPLIERS:
            if rx.match(after):
                values |= {v * mult for v in vals}
                break
    return values


def _norm_words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", strip_accents(text.lower()))


def _shingles(words: list[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(words[i:i + n]) for i in range(max(0, len(words) - n + 1))}


def _norm_text(text: str) -> str:
    return " ".join(_norm_words(text))


def _grounded(token: str, source_values: set[float], allowed_years: set[int]) -> bool:
    vals = _interpret(token, "pt")
    if not vals:
        return True
    v = next(iter(vals))
    if v.is_integer() and 1990 <= v <= 2040 and int(v) in allowed_years:
        return True
    d = _decimals(token, "pt")
    return any(abs(round(sv, d) - v) < 1e-9 or abs(sv - v) < 1e-9 for sv in source_values)


def validate(draft: Draft, evidence: str, editorial: dict[str, Any], published: list[dict[str, Any]],
             today: date | None = None) -> Validation:
    cfg = editorial["validation"]
    today = today or date.today()
    errors: list[str] = []
    warnings: list[str] = []
    kind_cfg = cfg["data" if draft.kind == "dados" else "news"]

    # 1. Estrutura mínima
    if not (cfg["title_min_chars"] <= len(draft.title) <= cfg["title_max_chars"]):
        errors.append(f"título com {len(draft.title)} caracteres (limites {cfg['title_min_chars']}–{cfg['title_max_chars']})")
    if not (kind_cfg["min_body_chars"] <= len(draft.body) <= kind_cfg["max_body_chars"]):
        errors.append(f"corpo com {len(draft.body)} caracteres (limites {kind_cfg['min_body_chars']}–{kind_cfg['max_body_chars']})")
    if not draft.lead.strip():
        errors.append("falta o lead")
    if not (cfg["min_key_points"] <= len(draft.key_points) <= cfg["max_key_points"]):
        errors.append(f"{len(draft.key_points)} pontos-chave (esperado {cfg['min_key_points']}–{cfg['max_key_points']})")
    if draft.category not in editorial["categories"]:
        errors.append(f"categoria desconhecida: {draft.category}")

    # 2. Fonte primária obrigatória (bloqueio)
    if not draft.sources or not all(s.get("url", "").startswith("http") for s in draft.sources):
        errors.append("sem fonte primária com ligação")
    if len(evidence.strip()) < 200:
        errors.append("texto da fonte insuficiente para verificar o artigo")

    visible = "\n".join([draft.title, draft.lead, draft.body, *draft.key_points])

    # 3. Todos os números têm de existir na fonte
    source_values = number_values(evidence, lang="any")
    allowed_years = {today.year} | {int(v) for v in source_values if v.is_integer() and 1990 <= v <= 2040}
    if draft.event_date:
        allowed_years.add(int(draft.event_date[:4]))
    bad = []
    for token, after in number_tokens(visible):
        if DAY_OF_MONTH.match(after) or after.startswith((".º", ".ª", "º", "ª")):
            continue
        if not _grounded(token, source_values, allowed_years):
            bad.append(token)
    if bad:
        errors.append("números sem correspondência na fonte: " + ", ".join(sorted(set(bad))))

    # 4. Originalidade: nenhum excerto longo copiado
    n = cfg["max_copied_words"]
    copied = _shingles(_norm_words(visible), n) & _shingles(_norm_words(evidence), n)
    if copied and draft.kind != "dados":
        errors.append("excerto copiado da fonte: \"" + " ".join(sorted(copied)[0]) + "\"")

    # 5. Factos com evidência literal na fonte (notícias)
    if draft.kind == "noticia":
        if len(draft.facts) < 2:
            errors.append("menos de 2 factos com evidência")
        norm_src = _norm_text(evidence)
        for f in draft.facts:
            ev = _norm_text(f.get("evidence", ""))
            if not ev or ev not in norm_src:
                errors.append("evidência não encontrada na fonte: " + f.get("evidence", "")[:80])

    # 6. Linguagem proibida
    low = visible.lower()
    for phrase in cfg.get("forbidden_phrases", []):
        if phrase.lower() in low:
            errors.append(f"expressão não permitida: {phrase}")

    # 7. Repetição de artigo recente
    window = timedelta(days=editorial["scoring"].get("duplicate_window_days", 30))
    for art in published:
        try:
            d = date.fromisoformat(str(art.get("date", ""))[:10])
        except ValueError:
            continue
        if today - d <= window and similarity(art.get("title", ""), draft.title) >= 0.6:
            errors.append(f"artigo repetido de \"{art['title']}\" ({d.isoformat()})")

    if draft.ai.get("used") and not draft.ai.get("model"):
        warnings.append("modelo de IA não registado")
    return Validation(ok=not errors, errors=errors, warnings=warnings)
