"""Falhas reais da primeira execução em produção (17/11/2026): modelo indisponível, recusa da IA e corrida de git."""
import json
from pathlib import Path

import yaml

from fluxo import llm
from fluxo.cli import format_summary
from fluxo.config import load_config
from fluxo.pipeline import run_daily
from fluxo.store import Store
from tests.test_pipeline import MONDAY, FakeFetcher, _only

ROOT = Path(__file__).resolve().parents[1]


class Resp:
    def __init__(self, code, payload):
        self.status_code, self._p = code, payload

    def json(self):
        return self._p


def _gemini_ok(payload):
    return Resp(200, {"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]})


def test_gemini_tries_next_model_when_one_is_unavailable(project):
    cfg = load_config(project)
    llm.reset_usage()
    seen = []

    def post(url, **kw):
        seen.append(url)
        if "gemini-3.5-flash-lite" in url:
            return Resp(404, {"error": {"message": "model not found"}})
        return _gemini_ok({"ok": True})

    out = llm.generate_json("s", "p", cfg.editorial["llm"], env={"GEMINI_API_KEY": "segredo"}, post=post)
    assert out["ok"] is True and out["_model"] == "gemini-3.1-flash-lite"
    assert len(seen) == 2
    assert any("404" in e for e in llm.USAGE["errors"])


def test_gemini_ignores_thought_parts(project):
    cfg = load_config(project)

    def post(url, **kw):
        return Resp(200, {"candidates": [{"content": {"parts": [
            {"text": "a pensar…", "thought": True}, {"text": json.dumps({"ok": 1})}]}}]})

    assert llm.generate_json("s", "p", cfg.editorial["llm"], env={"GEMINI_API_KEY": "k"}, post=post)["ok"] == 1


def test_llm_errors_are_recorded_without_the_key(project):
    cfg = load_config(project)
    llm.reset_usage()
    out = llm.generate_json("s", "p", cfg.editorial["llm"], env={"GEMINI_API_KEY": "segredo-123"},
                            post=lambda url, **kw: Resp(403, {"error": {"message": "API key not valid"}}))
    assert out is None
    assert llm.USAGE["errors"] and all("segredo-123" not in e for e in llm.USAGE["errors"])
    assert "403" in llm.USAGE["errors"][0] and "gemini" in llm.USAGE["errors"][0]


def test_item_refused_by_ai_is_marked_and_not_retried(project, fixtures, tmp_path):
    cfg = load_config(project)
    _only(cfg, {"erse-comunicados"})
    calls = []

    def post(url, **kw):
        calls.append(url)
        return _gemini_ok({"suitable": False, "reason": "comunicado sem facto noticioso"})

    env = {"GEMINI_API_KEY": "k"}
    summary = run_daily(cfg, FakeFetcher(fixtures), MONDAY, env, tmp_path / "d", post=post, data_pieces=[])
    assert not any("sem resposta" in e for e in summary["errors"]), summary["errors"]
    refused = [r for r in summary["rejected"] if r["kind"] == "noticia"]
    assert refused and "comunicado sem facto noticioso" in " ".join(refused[0]["errors"])
    n = len(calls)
    run_daily(cfg, FakeFetcher(fixtures), MONDAY.replace(day=17), env, tmp_path / "d2", post=post, data_pieces=[])
    assert len(calls) == n          # o mesmo item não volta a ser pedido à IA


def test_provider_failure_is_reported_with_reason(project, fixtures, tmp_path):
    cfg = load_config(project)
    _only(cfg, {"erse-comunicados"})
    summary = run_daily(cfg, FakeFetcher(fixtures), MONDAY, {"GEMINI_API_KEY": "k"}, tmp_path / "d",
                        post=lambda url, **kw: Resp(429, {"error": {"message": "quota"}}), data_pieces=[])
    assert any("429" in e for e in summary["errors"]), summary["errors"]
    assert Store(project).processed() == {}     # falha do fornecedor: tenta-se no dia seguinte


def test_summary_lines_show_reasons():
    summary = {"collect": {"new": 3, "dup": 0, "ok": 2, "failed": 1}, "published": [{"kind": "dados", "title": "A"}],
               "review": [], "rejected": [{"kind": "noticia", "title": "B", "errors": ["número 7% não está na fonte"]}],
               "data_pieces": {"brent_fx": "publicar", "gas_storage": "dados insuficientes (AGSI)"},
               "llm": {"calls": 1, "ok": 0, "failed": 1, "errors": ["gemini/x: HTTP 404"]}, "errors": []}
    text = "\n".join(format_summary(summary))
    assert "gas_storage: dados insuficientes (AGSI)" in text
    assert "B" in text and "número 7% não está na fonte" in text
    assert "gemini/x: HTTP 404" in text


def test_workflows_that_push_to_main_share_one_queue_and_rebase_first():
    for wf in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        doc = yaml.safe_load(wf.read_text())
        runs = [s.get("run", "") for job in doc.get("jobs", {}).values() for s in job.get("steps", [])]
        main_pushes = []
        for r in runs:
            lines = [l.strip() for l in r.splitlines()]
            main_pushes += [(lines, i) for i, l in enumerate(lines) if l in ("git push", "git push origin main")]
        if not main_pushes:
            continue
        assert (doc.get("concurrency") or {}).get("group") == "pipeline", wf.name
        for lines, i in main_pushes:
            assert any("git pull --rebase" in l for l in lines[:i]), f"{wf.name}: falta git pull --rebase antes de git push"


def test_gemini_moves_to_next_model_when_busy(project):
    cfg = load_config(project)
    llm.reset_usage()

    def post(url, **kw):
        if "gemini-3.5-flash-lite" in url:
            return Resp(503, {"error": {"message": "This model is currently experiencing high demand."}})
        return _gemini_ok({"ok": True})

    out = llm.generate_json("s", "p", cfg.editorial["llm"], env={"GEMINI_API_KEY": "k"}, post=post)
    assert out["_model"] == "gemini-3.1-flash-lite"
    assert any("503" in e for e in llm.USAGE["errors"])


def test_data_piece_reason_includes_http_error(project, fixtures, tmp_path):
    cfg = load_config(project)
    _only(cfg, set())

    class Blocked(FakeFetcher):
        def get(self, url, headers=None, check_robots=True):
            if "agsi.gie.eu" in url:
                self.errors[url] = "HTTP 403"
                return None
            return super().get(url, headers, check_robots)

    summary = run_daily(cfg, Blocked(fixtures), MONDAY, {"AGSI_API_KEY": "k"}, tmp_path / "d",
                        data_pieces=["gas_storage"])
    assert "HTTP 403" in summary["data_pieces"]["gas_storage"], summary["data_pieces"]
