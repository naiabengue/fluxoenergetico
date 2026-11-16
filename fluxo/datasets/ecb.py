"""BCE Data Portal — câmbio de referência EUR/USD (série EXR.D.USD.EUR.SP00.A). Sem chave."""
from __future__ import annotations

import csv
import io

from . import Obs

API = "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?lastNObservations={n}&format=csvdata"


def parse_ecb_csv(text: str) -> list[Obs]:
    rows = csv.DictReader(io.StringIO(text))
    out = [Obs(date=r["TIME_PERIOD"], value=float(r["OBS_VALUE"])) for r in rows if r.get("OBS_VALUE")]
    return sorted(out, key=lambda o: o.date, reverse=True)


def fetch_usd(fetcher, n: int = 30) -> list[Obs]:
    resp = fetcher.get(API.format(n=n), check_robots=False)
    return parse_ecb_csv(resp.text) if resp else []
