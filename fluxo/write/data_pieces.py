"""Peças de dados escritas por regras (sem IA): cada número vem diretamente da fonte oficial."""
from __future__ import annotations

from datetime import date, timedelta

from ..datasets import Obs
from ..datasets.agsi import Storage
from ..models import Draft

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
         "outubro", "novembro", "dezembro"]


def fmt(x: float, d: int = 1) -> str:
    """Número no formato português: espaço nos milhares, vírgula decimal."""
    s = f"{x:,.{d}f}"
    return s.replace(",", " ").replace(".", ",")


def data_pt(iso: str) -> str:
    d = date.fromisoformat(iso[:10])
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def _week_before(series: list, days: int = 7):
    """Primeira observação pelo menos `days` dias antes da mais recente (séries em ordem decrescente)."""
    last = date.fromisoformat(series[0].date)
    for o in series[1:]:
        if date.fromisoformat(o.date) <= last - timedelta(days=days):
            return o
    return series[-1]


def _evidence(values: dict[str, float]) -> str:
    lines = [f"{k}: {v} | {fmt(v, 2)} | {fmt(v, 1)}" for k, v in values.items()]
    return "Valores oficiais usados nesta peça (gerados automaticamente a partir dos dados):\n" + "\n".join(lines)


def _variou(delta: float) -> str:
    return "subiram" if delta > 0 else ("desceram" if delta < 0 else "mantiveram-se")


def gas_storage_piece(eu: list[Storage], pt: list[Storage], es: list[Storage] | None) -> tuple[Draft, str]:
    e0, p0 = eu[0], pt[0]
    e7, p7 = _week_before(eu), _week_before(pt)
    de, dp = round(e0.full - e7.full, 2), round(p0.full - p7.full, 2)
    title = f"Armazenamento de gás: UE a {fmt(e0.full)}% e Portugal a {fmt(p0.full)}% da capacidade"
    lead = (f"No dia de gás {data_pt(e0.date)}, as reservas da União Europeia {_variou(de)} "
            f"{fmt(abs(de), 2)} pontos percentuais face a {data_pt(e7.date)}; em Portugal {_variou(dp)} "
            f"{fmt(abs(dp), 2)} pontos.")
    body = [
        "## Nível das reservas",
        f"Segundo a plataforma AGSI+ da Gas Infrastructure Europe, os armazenamentos subterrâneos da UE tinham "
        f"{fmt(e0.stored_twh)} TWh de gás no dia {data_pt(e0.date)}, o equivalente a {fmt(e0.full, 2)}% da capacidade "
        f"útil de {fmt(e0.capacity_twh)} TWh. Uma semana antes, a {data_pt(e7.date)}, o nível era de {fmt(e7.full, 2)}%.",
        "## Portugal",
        f"Em Portugal, o armazenamento estava a {fmt(p0.full, 2)}% da capacidade, com {fmt(p0.stored_twh, 2)} TWh "
        f"armazenados para uma capacidade útil de {fmt(p0.capacity_twh, 2)} TWh. A {data_pt(p7.date)}, o valor era de "
        f"{fmt(p7.full, 2)}%.",
    ]
    values = {"eu_full": e0.full, "eu_full_week_before": e7.full, "eu_delta_pp": abs(de), "eu_twh": e0.stored_twh,
              "eu_capacity": e0.capacity_twh, "pt_full": p0.full, "pt_full_week_before": p7.full,
              "pt_delta_pp": abs(dp), "pt_twh": p0.stored_twh, "pt_capacity": p0.capacity_twh}
    if es:
        s0 = es[0]
        body += [f"Em Espanha, o outro lado do mercado ibérico, o nível era de {fmt(s0.full, 2)}% na mesma data."]
        values["es_full"] = s0.full
    body += [
        "## Como ler estes dados",
        "A percentagem compara o gás armazenado com a capacidade útil declarada pelos operadores. Os valores do "
        "dia mais recente podem ser estimativas e ser revistos pela GIE nos dias seguintes. As reservas de gás são "
        "um indicador de segurança de abastecimento acompanhado pela Comissão Europeia ao longo do inverno.",
    ]
    key_points = [f"UE: {fmt(e0.full)}% da capacidade ({fmt(e0.stored_twh)} TWh)",
                  f"Portugal: {fmt(p0.full)}% da capacidade",
                  f"Variação semanal na UE: {'+' if de >= 0 else '−'}{fmt(abs(de), 2)} pontos percentuais"]
    draft = Draft(kind="dados", title=title, lead=lead, body="\n\n".join(body), category="eletricidade-gas",
                  key_points=key_points, tags=["gás natural", "armazenamento", "segurança energética"],
                  sources=[{"name": "Gas Infrastructure Europe — AGSI+", "url": "https://agsi.gie.eu/",
                            "date": e0.date}],
                  ai={"used": False}, event_date=e0.date)
    return draft, _evidence(values)


def brent_fx_piece(brent: list[Obs], fx: list[Obs]) -> tuple[Draft, str]:
    b0, f0 = brent[0], fx[0]
    b7, f7 = _week_before(brent), _week_before(fx)
    window = [o.value for o in brent if date.fromisoformat(o.date) >= date.fromisoformat(b0.date) - timedelta(days=14)]
    b_chg = (b0.value / b7.value - 1) * 100
    f_chg = (f0.value / f7.value - 1) * 100
    b_eur, b7_eur = b0.value / f0.value, b7.value / f7.value
    title = f"Brent a {fmt(b0.value, 2)} dólares e euro a {fmt(f0.value, 4)} dólares"
    lead = (f"O petróleo Brent fechou a {data_pt(b0.date)} a {fmt(b0.value, 2)} dólares por barril, "
            f"{'mais' if b_chg >= 0 else 'menos'} {fmt(abs(b_chg), 1)}% do que a {data_pt(b7.date)}.")
    body = [
        "## Petróleo",
        f"O preço spot do Brent publicado pela EIA foi de {fmt(b0.value, 2)} dólares por barril a {data_pt(b0.date)}, "
        f"contra {fmt(b7.value, 2)} dólares a {data_pt(b7.date)}. Nas duas semanas mais recentes, o preço oscilou "
        f"entre {fmt(min(window), 2)} e {fmt(max(window), 2)} dólares.",
        "## Câmbio",
        f"O câmbio de referência do Banco Central Europeu fixou o euro em {fmt(f0.value, 4)} dólares a "
        f"{data_pt(f0.date)}, uma variação de {fmt(f_chg, 1)}% face a {data_pt(f7.date)}. Em euros, o barril de "
        f"Brent custava {fmt(b_eur, 2)} euros, contra {fmt(b7_eur, 2)} euros uma semana antes.",
        "## Porque importa",
        "A cotação internacional dos produtos petrolíferos e a taxa de câmbio estão entre os fatores que "
        "influenciam os preços de venda ao público dos combustíveis em Portugal, a par dos impostos e das margens "
        "de comercialização. As variações nos mercados não chegam às bombas de forma imediata nem integral.",
    ]
    values = {"brent": b0.value, "brent_week_before": b7.value, "brent_chg_pct": abs(b_chg), "brent_min": min(window),
              "brent_max": max(window), "eurusd": f0.value, "eurusd_week_before": f7.value, "eurusd_chg_pct": f_chg,
              "eurusd_chg_pct_abs": abs(f_chg), "brent_eur": b_eur, "brent_eur_week_before": b7_eur,
              "eurusd_4": round(f0.value, 4)}
    key_points = [f"Brent: {fmt(b0.value, 2)} USD/barril ({'+' if b_chg >= 0 else '−'}{fmt(abs(b_chg), 1)}% numa semana)",
                  f"EUR/USD: {fmt(f0.value, 4)}",
                  f"Brent em euros: {fmt(b_eur, 2)} EUR/barril"]
    draft = Draft(kind="dados", title=title, lead=lead, body="\n\n".join(body), category="combustiveis-petroleo",
                  key_points=key_points, tags=["brent", "câmbio", "petróleo"],
                  sources=[{"name": "U.S. Energy Information Administration — Brent spot",
                            "url": "https://www.eia.gov/dnav/pet/hist/RBRTED.htm", "date": b0.date},
                           {"name": "Banco Central Europeu — câmbio de referência EUR/USD",
                            "url": "https://data.ecb.europa.eu/data/datasets/EXR/EXR.D.USD.EUR.SP00.A",
                            "date": f0.date}],
                  ai={"used": False}, event_date=b0.date)
    return draft, _evidence(values)
