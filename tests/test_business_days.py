"""Uma notícia por dia útil em Lisboa: calendário, limiar de recurso e tentativas extra sem duplicar."""
from datetime import date, datetime, timezone

from fluxo.calendar_pt import is_business_day
from fluxo.config import load_config
from fluxo.pipeline import run_daily
from tests.test_pipeline import MONDAY, FakeFetcher, _only, _valid_llm_post

SATURDAY = datetime(2026, 11, 21, 6, 23, tzinfo=timezone.utc)


def test_lisbon_business_days():
    assert is_business_day(date(2026, 11, 18))            # quarta-feira
    assert not is_business_day(date(2026, 11, 21))        # sábado
    assert not is_business_day(date(2026, 12, 1))         # Restauração da Independência
    assert not is_business_day(date(2026, 12, 8))         # Imaculada Conceição
    assert not is_business_day(date(2026, 4, 3))          # Sexta-feira Santa 2026
    assert not is_business_day(date(2026, 6, 4))          # Corpo de Deus 2026
    assert not is_business_day(date(2026, 6, 13))         # Santo António (feriado municipal de Lisboa)
    assert not is_business_day(date(2027, 3, 26))         # Sexta-feira Santa 2027
    assert is_business_day(date(2027, 2, 9))              # Carnaval não é feriado obrigatório


def _counting(post):
    calls = []

    def wrapped(url, **kw):
        calls.append(url)
        return post(url, **kw)
    return wrapped, calls


def _below_threshold(cfg):
    cfg.editorial["scoring"]["thresholds"]["review"] = 999   # nenhum item chega ao limiar normal
    cfg.editorial["scoring"]["thresholds"]["publish"] = 1000


def test_business_day_uses_fallback_threshold_and_always_reviews(project, fixtures, tmp_path):
    cfg = load_config(project)
    _only(cfg, {"erse-comunicados"})
    _below_threshold(cfg)
    cfg.editorial["policy"]["business_day_min_score"] = 0
    cfg.editorial["policy"]["auto_publish_news"] = True      # mesmo assim, abaixo do limiar vai a revisão
    summary = run_daily(cfg, FakeFetcher(fixtures), MONDAY, {"GEMINI_API_KEY": "k"}, tmp_path / "d",
                        post=_valid_llm_post, data_pieces=[])
    assert [r["kind"] for r in summary["review"]] == ["noticia"], summary
    assert summary["published"] == []
    assert summary["news"]["business_day"] is True


def test_weekend_keeps_normal_threshold(project, fixtures, tmp_path):
    cfg = load_config(project)
    _only(cfg, {"erse-comunicados"})
    _below_threshold(cfg)
    cfg.editorial["policy"]["business_day_min_score"] = 0
    post, calls = _counting(_valid_llm_post)
    summary = run_daily(cfg, FakeFetcher(fixtures), SATURDAY, {"GEMINI_API_KEY": "k"}, tmp_path / "d",
                        post=post, data_pieces=[])
    assert calls == [] and summary["review"] == []
    assert summary["news"]["business_day"] is False


def test_catch_up_run_does_nothing_when_today_already_has_news(project, fixtures, tmp_path):
    cfg = load_config(project)
    _only(cfg, {"erse-comunicados"})
    run_daily(cfg, FakeFetcher(fixtures), MONDAY, {"GEMINI_API_KEY": "k"}, tmp_path / "d",
              post=_valid_llm_post, data_pieces=[])
    post, calls = _counting(_valid_llm_post)
    later = MONDAY.replace(hour=11)
    summary = run_daily(cfg, FakeFetcher(fixtures), later, {"GEMINI_API_KEY": "k"}, tmp_path / "d2",
                        post=post, data_pieces=[], catch_up=True)
    assert calls == []
    assert summary["news"]["skipped"] == "já há notícia hoje"


def test_business_day_without_news_is_flagged(project, fixtures, tmp_path):
    cfg = load_config(project)
    _only(cfg, {"erse-comunicados"})
    summary = run_daily(cfg, FakeFetcher(fixtures), MONDAY, {}, tmp_path / "d", data_pieces=[])   # sem IA
    assert any(e.startswith("Dia útil sem notícia") for e in summary["errors"]), summary["errors"]


def test_cli_catch_up_skips_data_pieces(project, monkeypatch):
    from fluxo import cli
    import fluxo.pipeline as pl

    seen = {}
    monkeypatch.setattr(pl, "run_daily", lambda *a, **k: seen.update(k) or {
        "collect": {"new": 0, "dup": 0, "ok": 0, "failed": 0}, "published": [], "review": [], "rejected": [],
        "data_pieces": {}, "llm": {}, "errors": []})
    assert cli.main(["daily", "--root", str(project), "--summary", "", "--catch-up"]) == 0
    assert seen["catch_up"] is True and seen["data_pieces"] == []


def test_late_morning_run_respects_daily_news_limit(project, fixtures, tmp_path):
    cfg = load_config(project)
    _only(cfg, {"erse-comunicados"})
    run_daily(cfg, FakeFetcher(fixtures), MONDAY, {"GEMINI_API_KEY": "k"}, tmp_path / "d",
              post=_valid_llm_post, data_pieces=[])
    post, calls = _counting(_valid_llm_post)
    late = MONDAY.replace(hour=16)                       # o agendamento das 06:23 a disparar 10 h depois
    summary = run_daily(cfg, FakeFetcher(fixtures), late, {"GEMINI_API_KEY": "k"}, tmp_path / "d2",
                        post=post, data_pieces=[])
    assert calls == [] and summary["review"] == []
    assert summary["news"]["skipped"] == "já há notícia hoje"
