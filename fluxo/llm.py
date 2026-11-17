"""IA opcional com cadeia de fornecedores gratuitos. Sem chaves → devolve None e o sistema continua."""
from __future__ import annotations

import json
import os
import re
from typing import Any, Callable, Mapping

import requests

USAGE: dict[str, Any] = {"calls": 0, "ok": 0, "failed": 0, "by_provider": {}, "errors": []}


def reset_usage() -> None:
    USAGE.update({"calls": 0, "ok": 0, "failed": 0, "by_provider": {}, "errors": []})


class ModelUnavailable(RuntimeError):
    """O modelo não serve agora: não existe para este projeto (404), sem quota (429) ou sobrecarregado (503)."""


def _http_error(provider: str, model: str, r) -> str:
    try:
        msg = str(r.json().get("error", {}).get("message", ""))[:160]
    except Exception:
        msg = ""
    return f"{provider}/{model}: HTTP {r.status_code}" + (f" — {msg}" if msg else "")


def _parse_json(text: str) -> dict[str, Any] | None:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def _gemini_models(p: dict) -> list[str]:
    models = p.get("models") or [p.get("model", "gemini-3.5-flash-lite")]
    return [str(m) for m in models]


def _gemini_once(model: str, key: str, system: str, prompt: str, temp: float, timeout: int, post: Callable) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temp, "responseMimeType": "application/json"}}
    r = post(url, headers={"x-goog-api-key": key, "Content-Type": "application/json"}, json=body, timeout=timeout)
    if r.status_code in (404, 429, 503):   # retirado, sem quota ou sobrecarregado: as quotas são por modelo
        raise ModelUnavailable(_http_error("gemini", model, r))
    if r.status_code != 200:
        raise RuntimeError(_http_error("gemini", model, r))
    cands = r.json().get("candidates") or []
    if not cands:
        raise RuntimeError(f"gemini/{model}: sem candidatos na resposta")
    parts = (cands[0].get("content") or {}).get("parts") or []
    text = "".join(pt.get("text", "") for pt in parts if not pt.get("thought"))
    if not text.strip():
        raise RuntimeError(f"gemini/{model}: resposta vazia (finishReason={cands[0].get('finishReason')})")
    return text


def _gemini(p: dict, key: str, system: str, prompt: str, temp: float, timeout: int, post: Callable):
    last: Exception | None = None
    for model in _gemini_models(p):
        try:
            return _gemini_once(model, key, system, prompt, temp, timeout, post), model
        except ModelUnavailable as e:      # tenta o modelo seguinte da lista
            USAGE["errors"].append(str(e))
            last = e
    raise RuntimeError(f"gemini: nenhum modelo disponível ({last})")


def _openai_compatible(p: dict, key: str, system: str, prompt: str, temp: float, timeout: int,
                       post: Callable, env: Mapping[str, str]):
    base = env.get(p.get("base_url_env", ""), "") or p.get("base_url_default", "")
    model = env.get(p.get("model_env", ""), "") or p.get("model_default", "")
    body = {"model": model, "temperature": temp, "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}
    r = post(base.rstrip("/") + "/chat/completions", headers={"Authorization": f"Bearer {key}"},
             json=body, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(_http_error("openai_compatible", model, r))
    return r.json()["choices"][0]["message"]["content"], model


def generate_json(system: str, prompt: str, llm_cfg: dict[str, Any],
                  env: Mapping[str, str] | None = None, post: Callable = requests.post) -> dict[str, Any] | None:
    env = os.environ if env is None else env
    for p in llm_cfg.get("providers", []):
        key = env.get(p.get("key_env", ""), "")
        if not key:
            continue
        kind = p["kind"]
        USAGE["calls"] += 1
        USAGE["by_provider"][kind] = USAGE["by_provider"].get(kind, 0) + 1
        try:
            if kind == "gemini":
                text, model = _gemini(p, key, system, prompt, llm_cfg.get("temperature", 0.2),
                                      llm_cfg.get("timeout_s", 60), post)
            elif kind == "openai_compatible":
                text, model = _openai_compatible(p, key, system, prompt, llm_cfg.get("temperature", 0.2),
                                                 llm_cfg.get("timeout_s", 60), post, env)
            else:
                continue
            data = _parse_json(text)
            if data is None:
                raise ValueError(f"{kind}/{model}: resposta não é JSON")
            USAGE["ok"] += 1
            data["_provider"], data["_model"] = kind, model
            return data
        except Exception as e:  # nunca inclui a chave: as mensagens vêm só do estado HTTP e do corpo de erro
            USAGE["failed"] += 1
            msg = str(e) or e.__class__.__name__
            USAGE["errors"].append(msg.replace(key, "***") if key else msg)
            continue
    return None
