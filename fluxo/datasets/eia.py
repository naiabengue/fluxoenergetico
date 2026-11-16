"""EIA API v2 — Brent spot (série RBRTE). Requer chave gratuita (EIA_API_KEY). Domínio público."""
from __future__ import annotations

import json

from . import Obs

API = ("https://api.eia.gov/v2/petroleum/pri/spt/data/?frequency=daily&data[0]=value"
       "&facets[series][]=RBRTE&sort[0][column]=period&sort[0][direction]=desc&length={n}&api_key={key}")


def parse_eia(payload: dict) -> list[Obs]:
    rows = payload.get("response", {}).get("data", [])
    out = [Obs(date=r["period"], value=float(r["value"])) for r in rows if r.get("value") not in (None, "")]
    return sorted(out, key=lambda o: o.date, reverse=True)


def fetch_brent(fetcher, key: str, n: int = 30) -> list[Obs]:
    resp = fetcher.get(API.format(n=n, key=key), check_robots=False)
    return parse_eia(json.loads(resp.text)) if resp else []
