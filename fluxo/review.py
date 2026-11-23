"""Aprovar ou rejeitar uma notícia a partir do email, sem entrar no GitHub.

O email leva, para cada pedido de revisão, uma ligação para a página de aprovação (Google Apps Script) com um
código aleatório. No corpo do pedido fica só o SHA-256 desse código, num comentário HTML invisível: o
repositório é público, por isso o código em si nunca lá aparece. A página e o workflow «Aprovar notícia»
confirmam o código antes de fazer merge (aprovar) ou fechar o pedido (rejeitar).
"""
from __future__ import annotations

import hashlib
import re
import secrets
from typing import Any
from urllib.parse import urlencode

import requests

MARK = re.compile(r"\n*<!--\s*aprovar:([0-9a-f\s]*)-->\s*$")
RE_TOKEN = re.compile(r"^[A-Za-z0-9_-]{20,64}$")
KEEP = 20          # códigos aceites por pedido (um por email; os emails antigos continuam a funcionar)
API = "https://api.github.com/repos/{repo}"


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hashes(body: str | None) -> list[str]:
    m = MARK.search(body or "")
    return m.group(1).split() if m else []


def add_hash(body: str | None, h: str, keep: int = KEEP) -> str:
    known = [x for x in hashes(body) if x != h][-(keep - 1):] + [h]
    text = MARK.sub("", body or "").rstrip()
    return f"{text}\n\n<!-- aprovar: {' '.join(known)} -->\n"


def approval_link(base_url: str, pr_number: int, token: str) -> str:
    return f"{base_url}?{urlencode({'pr': pr_number, 't': token})}"


def issue_links(prs: list[dict[str, Any]], base_url: str, repo: str, headers: dict[str, str]) -> dict[int, str]:
    """Um código novo por pedido: guarda o hash no corpo do pedido e devolve {número: ligação}.
    Se o GitHub recusar a gravação, esse pedido fica só com a ligação do GitHub (o email segue na mesma)."""
    links: dict[int, str] = {}
    for pr in prs:
        token = secrets.token_urlsafe(24)
        body = add_hash(pr.get("body"), token_hash(token))
        try:
            r = requests.patch(f"{API.format(repo=repo)}/pulls/{pr['number']}", json={"body": body},
                               headers=headers, timeout=30)
            r.raise_for_status()
        except requests.RequestException as e:
            print(f"::warning::Pedido #{pr['number']}: não foi possível gravar o código de aprovação ({e})")
            continue
        pr["body"] = body
        links[pr["number"]] = approval_link(base_url, pr["number"], token)
    return links


class Refused(Exception):
    """Decisão recusada (código errado, pedido já fechado, etc.): nada foi alterado."""


def check(pr: dict[str, Any], token: str) -> None:
    if not RE_TOKEN.match(token or ""):
        raise Refused("código com formato inválido")
    if not str(pr.get("head", {}).get("ref", "")).startswith("revisao/"):
        raise Refused(f"o pedido #{pr.get('number')} não é um pedido de revisão")
    if pr.get("state") != "open":
        raise Refused(f"o pedido #{pr['number']} já não está aberto ({'integrado' if pr.get('merged_at') else 'fechado'})")
    if token_hash(token) not in hashes(pr.get("body")):
        raise Refused("código não corresponde a este pedido (ligação antiga ou alterada)")


def decide(repo: str, number: int, token: str, action: str, headers: dict[str, str], http=requests) -> str:
    """Aprova (squash merge) ou rejeita (fecha) o pedido. Devolve 'merged' ou 'closed'; Refused se não puder."""
    if action not in ("aprovar", "rejeitar"):
        raise Refused(f"ação desconhecida: {action}")
    base = API.format(repo=repo)
    r = http.get(f"{base}/pulls/{number}", headers=headers, timeout=30)
    if r.status_code == 404:
        raise Refused(f"o pedido #{number} não existe")
    r.raise_for_status()
    pr = r.json()
    check(pr, token)
    ref = pr["head"]["ref"]
    if action == "aprovar":
        title = pr.get("title") or f"pedido {number}"
        r = http.put(f"{base}/pulls/{number}/merge", headers=headers, timeout=30,
                     json={"merge_method": "squash", "sha": pr["head"]["sha"],
                           "commit_title": f"Publicar: {title[:1].lower()}{title[1:]} (#{number})",
                           "commit_message": "Aprovada a partir do email de revisão."})
        if r.status_code in (405, 409):
            raise Refused(f"o GitHub não conseguiu integrar o pedido #{number}: {r.json().get('message', r.text)}")
        r.raise_for_status()
        result = "merged"
    else:
        http.post(f"{base}/issues/{number}/comments", headers=headers, timeout=30,
                  json={"body": "Rejeitada a partir do email de revisão."}).raise_for_status()
        http.patch(f"{base}/pulls/{number}", headers=headers, timeout=30, json={"state": "closed"}).raise_for_status()
        result = "closed"
    http.delete(f"{base}/git/refs/heads/{ref}", headers=headers, timeout=30)    # arrumação: se falhar, não faz mal
    return result
