"""Auditoria das fontes: testa cada fonte automática e sugere padrões quando nada é encontrado."""
from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Any

from .collect.html import parse_listing
from .collect.runner import collect_source, targets
from .config import Config


def run_audit(cfg: Config, fetcher, now: datetime) -> dict[str, Any]:
    report: dict[str, Any] = {}
    for s in cfg.sources:
        if s.method not in ("rss", "html"):
            continue
        try:
            items, errors = collect_source(s, fetcher, now)
        except Exception as exc:
            items, errors = [], [f"{type(exc).__name__}: {exc}"[:150]]
        dates = sorted(i.published for i in items if i.published)
        status = "ok" if items else ("erro" if errors else "sem itens")
        hint = []
        if s.method == "html" and not items and not errors:
            resp = fetcher.get(targets(s)[0])
            if resp:
                loose = dataclasses.replace(s, link_pattern=None, exclude_pattern=None)
                hint = [i.url for i in parse_listing(resp.text, loose, resp.url, now)[:8]]
        report[s.id] = {"bee": s.bee_number, "method": s.method, "enabled": s.enabled, "status": status,
                        "items": len(items), "latest": dates[-1][:10] if dates else "", "errors": errors,
                        "hint": hint}
    lines = [f"# Estado das fontes automáticas — {now:%Y-%m-%d %H:%M} UTC", "",
             "| Fonte | BEE | Método | Ativa | Estado | Itens | Mais recente | Observações |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for sid, r in report.items():
        obs = "; ".join(r["errors"])[:160] or ("links candidatos: " + ", ".join(r["hint"][:3]) if r["hint"] else "")
        lines.append(f"| {sid} | {r['bee'] or 'extra'} | {r['method']} | {'sim' if r['enabled'] else 'não'} | "
                     f"{r['status']} | {r['items']} | {r['latest']} | {obs.replace('|', '/')} |")
    out = cfg.root / "docs" / "ESTADO-FONTES.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report
