"""Acesso HTTP educado: robots.txt, User-Agent identificado, pausas e repetições."""
from __future__ import annotations

import time
import urllib.robotparser
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import requests

USER_AGENT = "FluxoEnergeticoBot/0.1 (+https://github.com/fluxoenergetico; recolha de fontes públicas)"


@dataclass
class Response:
    url: str
    status: int
    text: str
    content: bytes
    headers: dict = field(default_factory=dict)

    @property
    def content_type(self) -> str:
        return str(self.headers.get("content-type", self.headers.get("Content-Type", ""))).lower()


class Fetcher:
    def __init__(self, session=None, timeout: int = 25, retries: int = 2, min_interval: float = 1.0,
                 user_agent: str = USER_AGENT):
        self.session = session or requests.Session()
        self.timeout = timeout
        self.retries = retries
        self.min_interval = min_interval
        self.user_agent = user_agent
        self.errors: dict[str, str] = {}
        self.requests = 0
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._last_hit: dict[str, float] = {}

    def _raw_get(self, url: str, headers: dict | None = None):
        host = urlsplit(url).netloc
        wait = self.min_interval - (time.monotonic() - self._last_hit.get(host, 0.0))
        if wait > 0:
            time.sleep(wait)
        self._last_hit[host] = time.monotonic()
        self.requests += 1
        hdrs = {"User-Agent": self.user_agent, "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8"}
        hdrs.update(headers or {})
        return self.session.get(url, headers=hdrs, timeout=self.timeout)

    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}"
        if base not in self._robots:
            parser = urllib.robotparser.RobotFileParser()
            try:
                r = self._raw_get(base + "/robots.txt")
                if r.status_code == 200:
                    parser.parse(r.text.splitlines())
                    self._robots[base] = parser
                else:
                    self._robots[base] = None      # sem robots.txt → permitido
            except Exception:
                self._robots[base] = None
        parser = self._robots[base]
        return True if parser is None else parser.can_fetch(self.user_agent, url)

    def get(self, url: str, headers: dict | None = None, check_robots: bool = True) -> Response | None:
        """check_robots=False só para APIs oficiais de dados (feitas para acesso programático)."""
        if check_robots and not self.allowed(url):
            self.errors[url] = "bloqueado por robots.txt"
            return None
        last = ""
        for attempt in range(self.retries + 1):
            try:
                r = self._raw_get(url, headers)
                if r.status_code == 200:
                    return Response(url=str(getattr(r, "url", url)), status=200, text=r.text,
                                    content=r.content, headers=dict(r.headers))
                last = f"HTTP {r.status_code}"
                if r.status_code in (401, 403, 404, 410):
                    break
            except Exception as exc:  # rede, TLS, timeout
                last = f"{type(exc).__name__}: {exc}"[:200]
            time.sleep(min(2 ** attempt, 5) if self.min_interval else 0)
        self.errors[url] = last
        return None
