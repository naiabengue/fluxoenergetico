"""Dias úteis em Lisboa: segunda a sexta, exceto feriados nacionais obrigatórios e o feriado municipal (13 de junho).

Feriados nacionais (Código do Trabalho, art. 234.º): 1 jan, Sexta-feira Santa, Domingo de Páscoa, 25 abr, 1 mai,
Corpo de Deus, 10 jun, 15 ago, 5 out, 1 nov, 1 dez, 8 dez, 25 dez. O Carnaval é facultativo e não conta.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

LISBON = ZoneInfo("Europe/Lisbon")
FIXED = [(1, 1), (4, 25), (5, 1), (6, 10), (6, 13), (8, 15), (10, 5), (11, 1), (12, 1), (12, 8), (12, 25)]


def easter(year: int) -> date:
    """Domingo de Páscoa (algoritmo anónimo gregoriano)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


@lru_cache(maxsize=16)
def holidays(year: int) -> frozenset[date]:
    e = easter(year)
    movable = {e - timedelta(days=2), e, e + timedelta(days=60)}   # Sexta-feira Santa, Páscoa, Corpo de Deus
    return frozenset({date(year, m, d) for m, d in FIXED} | movable)


def is_business_day(d: date) -> bool:
    return d.weekday() < 5 and d not in holidays(d.year)


def lisbon_date(now: datetime) -> date:
    return now.astimezone(LISBON).date()
