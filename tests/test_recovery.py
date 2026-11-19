"""Recuperação automática: se o pedido de revisão não abrir, a notícia do dia volta a ficar livre para a
tentativa seguinte, e o email das 8h30 avisa quando um dia útil está sem notícia."""
import datetime as dt
import json

from fluxo import cli, notify
from fluxo.config import load_config
from fluxo.notify import no_news_alert
from fluxo.pipeline import run_daily
from fluxo.store import Store
from tests.test_pipeline import MONDAY, FakeFetcher, _only, _valid_llm_post

ENV = {"GITHUB_REPOSITORY": "o/r", "GITHUB_TOKEN": "t", "SMTP_USER": "a@gmail.com",
       "SMTP_PASSWORD": "p", "REVIEW_EMAIL_TO": "b@exemplo.pt"}


def _review_run(project, fixtures, tmp_path, when=MONDAY):
    cfg = load_config(project)
    _only(cfg, {"erse-comunicados"})
    summary = run_daily(cfg, FakeFetcher(fixtures), when, {"GEMINI_API_KEY": "k"}, tmp_path / "drafts",
                        post=_valid_llm_post, data_pieces=[])
    return cfg, summary


# ---- o pedido de revisão não abriu: libertar a notícia do dia ---------------------------------

def test_review_entries_carry_the_item_id(project, fixtures, tmp_path):
    _, summary = _review_run(project, fixtures, tmp_path)
    (entry,) = summary["review"]
    assert Store(project).processed()[entry["id"]]["decision"] == "rever"


def test_release_review_lets_the_catch_up_redo_the_news(project, fixtures, tmp_path):
    cfg, summary = _review_run(project, fixtures, tmp_path)
    path = tmp_path / "summary.json"
    path.write_text(json.dumps(summary), encoding="utf-8")

    # como no 19/11: sem a correção, a tentativa extra diz «já há notícia hoje» e o dia fica sem notícia
    assert cli.main(["release-review", "--root", str(project), "--summary", str(path)]) == 0
    assert summary["review"][0]["id"] not in Store(project).processed()

    retry = run_daily(cfg, FakeFetcher(fixtures), MONDAY.replace(hour=7, minute=15), {"GEMINI_API_KEY": "k"},
                      tmp_path / "drafts2", post=_valid_llm_post, data_pieces=[], catch_up=True)
    assert retry["news"]["skipped"] is None
    assert [r["kind"] for r in retry["review"]] == ["noticia"]


def test_release_review_leaves_other_decisions_alone(project, tmp_path):
    store = Store(project)
    store.mark_processed("a", "rever", "2026-11-19T06:16:00")
    store.mark_processed("b", "rejeitado", "2026-11-19T06:16:00")
    path = tmp_path / "summary.json"
    path.write_text(json.dumps({"review": [{"kind": "noticia", "title": "A", "id": "a"},
                                           {"kind": "noticia", "title": "B", "id": "b"},
                                           {"kind": "dados", "title": "Brent"}]}), encoding="utf-8")
    assert cli.main(["release-review", "--root", str(project), "--summary", str(path)]) == 0
    assert set(Store(project).processed()) == {"b"}


def test_release_review_without_summary_is_harmless(project, tmp_path):
    assert cli.main(["release-review", "--root", str(project), "--summary", str(tmp_path / "nada.json")]) == 0


# ---- email: dia útil sem notícia --------------------------------------------------------------

LAST_RUN = {"started": "2026-11-19T07:54:45+00:00", "review": [], "published": [],
            "rejected": [{"kind": "noticia", "title": "Roteiro COP31", "errors": ["texto da fonte indisponível"]}],
            "news": {"candidates": 114, "attempted": 0, "skipped": "já há notícia hoje", "business_day": True},
            "errors": []}
FAILED = [{"created_at": "2026-11-19T06:15:46Z", "html_url": "https://github.com/o/r/actions/runs/9"}]


def test_alert_explains_why_and_links_the_failed_run():
    subject, body = no_news_alert(dt.date(2026, 11, 19), LAST_RUN, FAILED, "o/r")
    assert subject == "Fluxo Energético: ainda sem notícia hoje (19/11/2026)"
    assert "07:54" in body and "114 candidatos" in body and "já há notícia hoje" in body
    assert "Roteiro COP31 — texto da fonte indisponível" in body
    assert "06:15" in body and "https://github.com/o/r/actions/runs/9" in body
    assert "11:15" in body                                    # diz que ainda há uma tentativa automática
    assert "https://github.com/o/r/actions" in body


def test_alert_in_summer_shows_lisbon_time():
    run = dict(LAST_RUN, started="2026-07-15T05:16:00+00:00")
    _, body = no_news_alert(dt.date(2026, 7, 15), run, [], "o/r")
    assert "06:16" in body and "falhou" not in body


class _Resp:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


def _cli_env(monkeypatch, now, prs=(), failed=()):
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(cli, "_now", lambda: now)

    def fake_get(url, **kw):
        if url.endswith("/pulls"):
            return _Resp(list(prs))
        assert "/actions/workflows/diario.yml/runs" in url
        return _Resp({"workflow_runs": [dict(r, conclusion="failure") for r in failed]})
    monkeypatch.setattr(cli.requests, "get", fake_get)
    sent = []
    monkeypatch.setattr(notify, "send_email", lambda *a, **k: sent.append(a))
    return sent


def test_cli_alerts_on_business_day_without_news(project, monkeypatch, capsys):
    Store(project).log_run(LAST_RUN)
    sent = _cli_env(monkeypatch, dt.datetime(2026, 11, 19, 8, 30, tzinfo=dt.timezone.utc), failed=FAILED)
    assert cli.main(["notify-review", "--root", str(project)]) == 0
    assert len(sent) == 1 and sent[0][0].startswith("Fluxo Energético: ainda sem notícia hoje")
    assert "actions/runs/9" in sent[0][1]


def test_cli_stays_quiet_on_weekends(project, monkeypatch, capsys):
    sent = _cli_env(monkeypatch, dt.datetime(2026, 11, 21, 8, 30, tzinfo=dt.timezone.utc))
    assert cli.main(["notify-review", "--root", str(project)]) == 0
    assert sent == [] and "sem email hoje" in capsys.readouterr().out


def test_cli_stays_quiet_when_todays_news_is_already_handled(project, monkeypatch, capsys):
    Store(project).mark_processed("x", "rever", "2026-11-19T06:16:00")    # já revista e publicada (PR fechado)
    sent = _cli_env(monkeypatch, dt.datetime(2026, 11, 19, 8, 30, tzinfo=dt.timezone.utc))
    assert cli.main(["notify-review", "--root", str(project)]) == 0
    assert sent == []
