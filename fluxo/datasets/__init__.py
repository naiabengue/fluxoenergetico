"""Adaptadores de dados oficiais (sem IA) usados nas peças de dados."""
from dataclasses import dataclass


@dataclass
class Obs:
    date: str          # AAAA-MM-DD
    value: float
