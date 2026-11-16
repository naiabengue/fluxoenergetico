"""IA opcional com cadeia de fornecedores gratuitos. Sem chaves → devolve None e o sistema continua."""
from __future__ import annotations

import json
import os
import re
from typing import Any, Callable, Mapping

import requests

USAGE: dict[str, Any] = {"calls": 0, "ok": 0, "failed": 0, "by_provider": {}}


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


def _gemini(p: dict, key: str, system: str, prompt: str, temp: float, timeout: int, post: Callable):
    model = p.get("model", "gemini-2.5-flash-lite")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temp, "responseMimeType": "application/json"}}
    r = post(url, headers={"x-goog-api-key": key, "Content-Type": "application/json"}, json=body, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"gemini HTTP {r.status_code}")
    text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    return text, model


def _openai_compatible(p: dict, key: str, system: str, prompt: str, temp: float, timeout: int,
                       post: Callable, env: Mapping[str, str]):
    base = env.get(p.get("base_url_env", ""), "") or p.get("base_url_default", "")
    model = env.get(p.get("model_env", ""), "") or p.get("model_default", "")
    body = {"model": model, "temperature": temp, "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}
    r = post(base.rstrip("/") + "/chat/completions", headers={"Authorization": f"Bearer {key}"},
             json=body, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"openai_compatible HTTP {r.status_code}")
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
                raise ValueError("resposta não é JSON")
            USAGE["ok"] += 1
            data["_provider"], data["_model"] = kind, model
            return data
        except Exception:
            USAGE["failed"] += 1
            continue
    return None
