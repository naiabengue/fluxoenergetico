"""GIE AGSI+ — armazenamento de gás. Requer chave gratuita (AGSI_API_KEY)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta

API = "https://agsi.gie.eu/api"


@dataclass
class Storage:
    date: str
    full: float            # % da capacidade
    stored_twh: float
    capacity_twh: float
    status: str = ""       # E = estimado, C = confirmado


def _f(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def parse_agsi(payload: dict) -> list[Storage]:
    rows = payload.get("data", []) if isinstance(payload, dict) else []
    out = [Storage(date=r.get("gasDayStart", ""), full=_f(r.get("full")), stored_twh=_f(r.get("gasInStorage")),
                   capacity_twh=_f(r.get("workingGasVolume")), status=str(r.get("status", "")))
           for r in rows if r.get("gasDayStart")]
    out = [s for s in out if s.full == s.full]   # remove NaN
    return sorted(out, key=lambda s: s.date, reverse=True)


def fetch_agsi(fetcher, key: str, area: str, days: int = 30, today: date | None = None) -> list[Storage]:
    """area: 'eu' (agregado UE) ou código de país ('PT', 'ES')."""
    today = today or date.today()
    start = (today - timedelta(days=days)).isoformat()
    scope = "type=eu" if area.lower() == "eu" else f"country={area}"
    url = f"{API}?{scope}&from={start}&to={today.isoformat()}&size={days + 5}"
    resp = fetcher.get(url, headers={"x-key": key}, check_robots=False)
    return parse_agsi(json.loads(resp.text)) if resp else []
