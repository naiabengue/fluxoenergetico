"""Gráficos estáticos (PNG) para as peças de dados. Cores validadas para daltonismo (contraste ≥ 3:1)."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

SERIES = ["#1f68c1", "#b8760a"]          # ordem fixa; validado com validate_palette.js (modo claro)
INK, MUTED, GRID = "#10324a", "#5a6872", "#e3e9e6"


def _num(v: float, d: int) -> str:
    return f"{v:,.{d}f}".replace(",", " ").replace(".", ",")


def line_chart(series: dict[str, list[tuple[str, float]]], path: Path, ylabel: str, decimals: int = 1,
               source: str = "") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
    for i, (label, pts) in enumerate(series.items()):
        pts = sorted(pts)
        xs = [date.fromisoformat(d) for d, _ in pts]
        ys = [v for _, v in pts]
        color = SERIES[i % len(SERIES)]
        ax.plot(xs, ys, color=color, linewidth=2, solid_capstyle="round", label=label)
        ax.plot(xs[-1], ys[-1], "o", color=color, markersize=6, markeredgecolor="white", markeredgewidth=2)
        ax.annotate(f"{label}: {_num(ys[-1], decimals)}", (xs[-1], ys[-1]), xytext=(8, 0),
                    textcoords="offset points", va="center", fontsize=9, color=INK)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.grid(axis="y", color=GRID, linewidth=1)
    ax.tick_params(colors=MUTED, labelsize=9, length=0)
    ax.set_ylabel(ylabel, color=MUTED, fontsize=9)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: _num(v, 0 if decimals == 0 else 1)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    ax.margins(x=0.02)
    if len(series) > 1:
        ax.legend(frameon=False, fontsize=9, labelcolor=INK, loc="upper left", ncols=len(series))
    if source:
        fig.text(0.01, 0.01, f"Fonte: {source}", fontsize=8, color=MUTED)
    fig.subplots_adjust(right=0.82, bottom=0.14)
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    return path
