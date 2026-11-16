import json
from datetime import datetime, timezone

from fluxo.audit import run_audit
from fluxo.cli import main
from fluxo.config import load_config
from fluxo.http import Response
from fluxo.pipeline import run_daily
from fluxo.store import Store

MONDAY = datetime(2026, 11, 16, 6, 23, tzinfo=timezone.utc)
ERSE_PR = "https://www.erse.pt/comunicacao/comunicados/tarifas-gas-natural-2026-2027/"
LISTING = f'<ul><li>15/11/2026 <a href="{ERSE_PR}">Tarifas de gás natural aumentam 6,4% no mercado regulado a partir de 1 de outubro</a></li></ul>'


class FakeFetcher:
    def __init__(self, fixtures):
        f = fixtures
        self.pages = {
            "https://www.adene.pt/feed/": (f / "adene_feed.xml").read_text(),
            "https://www.erse.pt/comunicacao/comunicados/": LISTING,
            ERSE_PR: (f / "erse_tarifas.html").read_text(),
            "eia": (f / "eia_brent.json").read_text(),
            "ecb": (f / "ecb_usd.csv").read_text(),
            "agsi-eu": (f / "agsi_eu.json").read_text(),
            "agsi-PT": (f / "agsi_pt.json").read_text(),
        }
        self.errors = {}

    def get(self, url, headers=None, check_robots=True):
        key = url
        if "api.eia.gov" in url:
            key = "eia"
        elif "data-api.ecb" in url:
            key = "ecb"
        elif "agsi.gie.eu/api" in url:
            key = "agsi-eu" if "type=eu" in url else ("agsi-PT" if "country=PT" in url else "none")
        if key not in self.pages:
            self.errors[url] = "HTTP 404"
            return None
        return Response(url=url, status=200, text=self.pages[key], content=self.pages[key].encode(),
                        headers={"content-type": "text/html"})


def _only(cfg, ids):
    for s in cfg.sources:
        s.enabled = s.id in ids


def _valid_llm_post(url, **kw):
    body = (
        "## O que aconteceu\n\nO regulador aprovou novas tarifas de gás natural para o mercado regulado. A variação média "
        "para os clientes finais é de 6,4% face ao ano gás anterior, com efeitos desde 1 de outubro de 2026.\n\n"
        "## Contexto\n\nPara um consumidor doméstico típico, com consumo anual de 1 600 kWh, a fatura sobe cerca de 1,30 "
        "euros por mês. A ERSE explica a subida com o custo de compra de gás nos mercados grossistas. O ano gás começa "
        "a 1 de outubro e termina a 30 de setembro do ano seguinte, pelo que as novas tarifas cobrem todo o inverno, "
        "a época em que o consumo doméstico de gás é mais elevado.\n\n"
        "## Porque importa para Portugal e a UE\n\nA decisão abrange cerca de 30 mil clientes que continuam no mercado "
        "regulado. Os restantes consumidores têm contratos em mercado livre, com preços fixados por cada comercializador, "
        "e não são abrangidos diretamente, embora as condições grossistas também pesem nas ofertas comerciais.")
    payload = {"title": "Tarifas reguladas de gás natural sobem 6,4% desde outubro",
               "lead": "A ERSE aprovou uma subida média de 6,4% nas tarifas de gás natural para os clientes que permanecem no mercado regulado.",
               "body_markdown": body, "key_points": ["Subida média de 6,4%", "Cerca de 1,30 euros por mês", "Cerca de 30 mil clientes"],
               "category": "eletricidade-gas", "tags": ["gás natural", "tarifas"],
               "facts": [{"claim": "6,4%", "evidence": "a variação média das tarifas de venda a clientes finais é de 6,4%"},
                         {"claim": "30 mil", "evidence": "Cerca de 30 mil clientes permanecem no mercado regulado"}],
               "event_date": "2026-10-01", "suitable": True}

    class R:
        status_code = 200

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": json.dumps(payload, ensure_ascii=False)}]}}]}
    return R()


def test_daily_without_llm_publishes_data_piece_only(project, fixtures, tmp_path):
    cfg = load_config(project)
    _only(cfg, {"adene", "erse-comunicados"})
    env = {"EIA_API_KEY": "k", "AGSI_API_KEY": "k"}
    summary = run_daily(cfg, FakeFetcher(fixtures), MONDAY, env, tmp_path / "drafts")
    assert summary["collect"]["new"] == 3
    assert [p["kind"] for p in summary["published"]] == ["dados"]            # segunda-feira: Brent e câmbio
    assert summary["news"]["skipped"] == "sem IA configurada"
    arts = Store(project).published_articles()
    assert len(arts) == 1 and arts[0]["chart"].startswith("media/")
    assert (project / "content" / arts[0]["chart"]).exists()
    assert len(Store(project).runs()) == 1


def test_daily_with_llm_sends_news_to_review(project, fixtures, tmp_path):
    cfg = load_config(project)
    _only(cfg, {"erse-comunicados"})
    env = {"GEMINI_API_KEY": "k"}
    summary = run_daily(cfg, FakeFetcher(fixtures), MONDAY, env, tmp_path / "drafts", post=_valid_llm_post,
                        data_pieces=[])
    assert len(summary["review"]) == 1, summary
    draft = next((tmp_path / "drafts").rglob("*.md")).read_text()
    assert "review: pr" in draft and "6,4%" in draft
    assert Store(project).published_articles() == []
    # o mesmo item não volta a ser redigido no dia seguinte
    again = run_daily(cfg, FakeFetcher(fixtures), MONDAY.replace(day=17), env, tmp_path / "drafts2",
                      post=_valid_llm_post, data_pieces=[])
    assert again["review"] == []


def test_forced_gas_piece(project, fixtures, tmp_path):
    cfg = load_config(project)
    _only(cfg, set())
    summary = run_daily(cfg, FakeFetcher(fixtures), MONDAY, {"AGSI_API_KEY": "k"}, tmp_path / "d",
                        data_pieces=["gas_storage"])
    assert summary["published"][0]["title"].startswith("Armazenamento de gás")


def test_audit_reports_each_collectable_source(project, fixtures):
    cfg = load_config(project)
    report = run_audit(cfg, FakeFetcher(fixtures), MONDAY)
    assert report["adene"]["status"] == "ok" and report["adene"]["items"] == 2
    assert report["apren"]["status"] == "erro"
    md = (project / "docs" / "ESTADO-FONTES.md").read_text()
    assert "| adene |" in md


def test_cli_build(project, fixtures):
    code = main(["build", "--root", str(project), "--out", str(project / "_site")])
    assert code == 0 and (project / "_site" / "index.html").exists()
