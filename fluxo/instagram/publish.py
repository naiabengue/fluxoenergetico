"""Publicação pela API de conteúdos do Instagram (conta profissional, acesso padrão à própria conta).

Desde 2026 as apps novas da Meta só oferecem o «login unificado»: token de utilizador de sistema (não expira)
e chamadas em graph.facebook.com. Apps antigas com «login do Instagram» usam graph.instagram.com e um token
de 60 dias que se renova. O mesmo fluxo de contentor → media_publish serve para os dois."""
from __future__ import annotations

import time
from typing import Any, Callable, Mapping

import requests

GRAPH = "https://graph.instagram.com"
HOSTS = {"unified": "https://graph.facebook.com", "instagram": GRAPH}


def graph_host(editorial: dict[str, Any]) -> str:
    return HOSTS[editorial["instagram"].get("login", "unified")]


def check_account(ig_user_id: str, token: str, api_version: str, host: str, get: Callable = requests.get) -> str:
    """Confirma que o token dá acesso à conta e devolve o nome de utilizador (sem publicar nada)."""
    base = f"{host}/{api_version}" if api_version else host
    return _ok(get(f"{base}/{ig_user_id}", params={"fields": "id,username", "access_token": token},
                   timeout=30))["username"]


def slide_urls(base: str, folder: str, n: int) -> list[str]:
    """URLs públicos das imagens do carrossel, servidas pelo site (content/instagram → <base>/instagram)."""
    return [f"{base.rstrip('/')}/{folder.strip('/')}/slide-{i}.jpg" for i in range(1, n + 1)]


def publish_enabled(editorial: dict[str, Any], env: Mapping[str, str]) -> bool:
    return bool(editorial["instagram"].get("auto_publish") and env.get("IG_ACCESS_TOKEN") and env.get("IG_USER_ID"))


def _ok(resp) -> dict:
    data = resp.json()
    if resp.status_code != 200 or "error" in data:
        err = data.get("error") or {}
        if isinstance(err, dict):   # nunca repete o pedido (que leva o token): só código e mensagem da Meta
            raise RuntimeError(f"Instagram API: HTTP {resp.status_code}, código {err.get('code')} — {err.get('message')}")
        raise RuntimeError(f"Instagram API: HTTP {resp.status_code}")
    return data


def publish_carousel(image_urls: list[str], caption: str, ig_user_id: str, token: str, api_version: str,
                     post: Callable = requests.post, get: Callable = requests.get,
                     sleep: Callable = time.sleep, host: str = GRAPH) -> str:
    """Cria os contentores, espera que fiquem prontos e publica. Devolve o id da publicação."""
    base = f"{host}/{api_version}" if api_version else host
    if len(image_urls) == 1:
        container = _ok(post(f"{base}/{ig_user_id}/media", data={"image_url": image_urls[0], "caption": caption,
                                                                  "access_token": token}, timeout=60))["id"]
    else:
        children = [_ok(post(f"{base}/{ig_user_id}/media",
                             data={"image_url": u, "is_carousel_item": "true", "access_token": token},
                             timeout=60))["id"] for u in image_urls[:10]]
        container = _ok(post(f"{base}/{ig_user_id}/media",
                             data={"media_type": "CAROUSEL", "children": ",".join(children), "caption": caption,
                                   "access_token": token}, timeout=60))["id"]
    for _ in range(12):
        status = _ok(get(f"{base}/{container}", params={"fields": "status_code", "access_token": token},
                         timeout=30)).get("status_code")
        if status == "FINISHED":
            break
        if status == "ERROR":
            raise RuntimeError("Instagram recusou o contentor (formato ou URL da imagem)")
        sleep(10)
    return _ok(post(f"{base}/{ig_user_id}/media_publish", data={"creation_id": container, "access_token": token},
                    timeout=60))["id"]


def refresh_token(token: str, get: Callable = requests.get) -> tuple[str, int]:
    """Renova o token de longa duração (válido 60 dias). Devolve (novo_token, segundos_de_validade)."""
    data = _ok(get(f"{GRAPH}/refresh_access_token", params={"grant_type": "ig_refresh_token",
                                                             "access_token": token}, timeout=30))
    return data["access_token"], int(data.get("expires_in", 0))
