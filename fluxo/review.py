"""Aprovar ou rejeitar uma notícia a partir do email, sem entrar no GitHub.

O email leva, para cada pedido de revisão, uma ligação para a página de aprovação (Google Apps Script) com um
código aleatório. No corpo do pedido fica só o SHA-256 desse código, num comentário HTML invisível: o
repositório é público, por isso o código em si nunca lá aparece. A página e o workflow «Aprovar notícia»
confirmam o código antes de fazer merge (aprovar) ou fechar o pedido (rejeitar).
"""
from __future__ import annotations

import base64
import hashlib
import re
import secrets
import time
from typing import Any
from urllib.parse import urlencode

import requests
import yaml

MARK = re.compile(r"\n*<!--\s*aprovar:([0-9a-f\s]*)-->[ \t]*")   # em qualquer ponto da descrição
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


RE_FM = re.compile(r"\A---\n(.*?)\n---\n?(.*)\Z", re.S)
LIMITS = {"title": (10, 200), "lead": (20, 800), "body": (200, 30000)}


def split(text: str) -> tuple[dict[str, Any], str]:
    m = RE_FM.match(text.replace("\r\n", "\n"))
    if not m:
        raise Refused("o artigo não tem cabeçalho")
    return yaml.safe_load(m.group(1)) or {}, m.group(2).lstrip("\n")


def apply_edit(text: str, edit: dict[str, Any]) -> str:
    """Novo conteúdo do artigo com o título, a entrada, os pontos-chave e o texto alterados na página.
    O resto do cabeçalho (slug, data, fontes, IA) fica igual, para o endereço e a nota de IA não mudarem."""
    meta, _ = split(text)
    clean: dict[str, Any] = {}
    for field in ("title", "lead", "body"):
        value = edit.get(field)
        if not isinstance(value, str):
            raise Refused(f"falta o campo {field}")
        value = value.replace("\r\n", "\n").strip()
        if field != "body":
            value = " ".join(value.split())
        lo, hi = LIMITS[field]
        if not lo <= len(value) <= hi:
            raise Refused(f"{field}: {len(value)} caracteres (aceites {lo}–{hi})")
        clean[field] = value
    points = edit.get("key_points")
    if not isinstance(points, list) or not all(isinstance(p, str) for p in points):
        raise Refused("pontos-chave inválidos")
    points = [" ".join(p.split()) for p in points if p.strip()]
    if len(points) > 8 or any(len(p) > 400 for p in points):
        raise Refused("até 8 pontos-chave, cada um com até 400 caracteres")
    meta.update(title=clean["title"], lead=clean["lead"], key_points=points)
    fm = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False)
    return f"---\n{fm}---\n\n{clean['body']}\n"


def article_paths(repo: str, number: int, headers: dict[str, str], http=requests) -> list[str]:
    r = http.get(f"{API.format(repo=repo)}/pulls/{number}/files", params={"per_page": 50}, headers=headers, timeout=30)
    r.raise_for_status()
    return [f["filename"] for f in r.json()
            if f["filename"].startswith("content/articles/") and f["filename"].endswith(".md") and f.get("status") != "removed"]


def fetch_articles(prs: list[dict[str, Any]], repo: str, headers: dict[str, str], http=requests) -> dict[int, list[dict]]:
    """Artigos de cada pedido, lidos do ramo de revisão, para o email mostrar o texto. Falhas: lista vazia."""
    raw = dict(headers, Accept="application/vnd.github.raw+json")
    out: dict[int, list[dict]] = {}
    for pr in prs:
        try:
            items = []
            for path in article_paths(repo, pr["number"], headers, http):
                r = http.get(f"{API.format(repo=repo)}/contents/{path}", params={"ref": pr["head"]["sha"]},
                             headers=raw, timeout=30)
                r.raise_for_status()
                meta, body = split(r.text)
                image = str(meta.get("image") or "")
                items.append({"path": path, "title": str(meta.get("title", "")), "lead": str(meta.get("lead", "")),
                              "key_points": [str(p) for p in meta.get("key_points") or []], "body": body,
                              "sources": meta.get("sources") or [], "score": meta.get("score"),
                              # repositório público: a imagem do ramo de revisão abre no email sem credenciais
                              "image_url": f"https://raw.githubusercontent.com/{repo}/{pr['head']['sha']}/content/{image}"
                              if image else ""})
            out[pr["number"]] = items
        except (requests.RequestException, Refused, yaml.YAMLError, KeyError) as e:
            print(f"::warning::Pedido #{pr['number']}: texto não incluído no email ({e})")
            out[pr["number"]] = []
    return out


def _save_edits(repo: str, pr: dict[str, Any], edits: list[dict[str, Any]], headers: dict[str, str], http) -> str:
    """Grava no ramo do pedido os artigos alterados (um commit por artigo). Devolve o sha do novo topo do ramo."""
    base, ref, head = API.format(repo=repo), pr["head"]["ref"], pr["head"]["sha"]
    allowed = set(article_paths(repo, pr["number"], headers, http))
    if not edits:
        raise Refused("nada para alterar")
    for e in edits:
        path = e.get("ficheiro")
        if path not in allowed:
            raise Refused(f"ficheiro fora deste pedido: {path}")
        r = http.get(f"{base}/contents/{path}", params={"ref": ref}, headers=headers, timeout=30)
        r.raise_for_status()
        cur = r.json()
        old = base64.b64decode(cur["content"]).decode("utf-8")
        new = apply_edit(old, e)
        if new == old:
            continue
        r = http.put(f"{base}/contents/{path}", headers=headers, timeout=30,
                     json={"message": "revisão: texto alterado a partir do email", "branch": ref, "sha": cur["sha"],
                           "content": base64.b64encode(new.encode("utf-8")).decode("ascii")})
        r.raise_for_status()
        head = r.json()["commit"]["sha"]
    return head


def decide(repo: str, number: int, token: str, action: str, headers: dict[str, str], http=requests,
           edits: list[dict[str, Any]] | None = None, wait: float = 3.0) -> str:
    """Aprova (squash merge), modifica e aprova, ou rejeita (fecha) o pedido. Devolve 'merged' ou 'closed'.
    Refused se não puder; só depois de gravar alterações é que um merge recusado deixa o ramo diferente."""
    if action not in ("aprovar", "rejeitar", "modificar"):
        raise Refused(f"ação desconhecida: {action}")
    base = API.format(repo=repo)
    r = http.get(f"{base}/pulls/{number}", headers=headers, timeout=30)
    if r.status_code == 404:
        raise Refused(f"o pedido #{number} não existe")
    r.raise_for_status()
    pr = r.json()
    check(pr, token)
    ref = pr["head"]["ref"]
    note = "Aprovada a partir do email de revisão."
    if action == "modificar":
        pr["head"]["sha"] = _save_edits(repo, pr, edits or [], headers, http)
        action, note = "aprovar", "Alterada e aprovada a partir do email de revisão."
    if action == "aprovar":
        title = pr.get("title") or f"pedido {number}"
        for attempt in range(4):        # logo a seguir a gravar uma alteração, o GitHub pode ainda não aceitar o merge
            r = http.put(f"{base}/pulls/{number}/merge", headers=headers, timeout=30,
                         json={"merge_method": "squash", "sha": pr["head"]["sha"],
                               "commit_title": f"Publicar: {title[:1].lower()}{title[1:]} (#{number})",
                               "commit_message": note})
            if r.status_code not in (405, 409) or attempt == 3:
                break
            time.sleep(wait)
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
