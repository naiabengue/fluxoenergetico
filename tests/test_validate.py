import json
from datetime import date

from fluxo.config import load_config
from fluxo.datasets.agsi import parse_agsi
from fluxo.datasets.ecb import parse_ecb_csv
from fluxo.datasets.eia import parse_eia
from fluxo.extract import extract_html_text
from fluxo.llm import generate_json
from fluxo.models import Draft, Source
from fluxo.validate import number_values, validate
from fluxo.write.data_pieces import brent_fx_piece, gas_storage_piece
from fluxo.write.news import draft_news

BODY = (
    "## O que aconteceu\n\nA ERSE aprovou novas tarifas de gás natural para o mercado regulado, em vigor desde "
    "1 de outubro de 2026. A variação média para os clientes finais é de 6,4% face ao ano gás anterior.\n\n"
    "## Contexto\n\nPara um consumidor doméstico típico, com consumo anual de 1 600 kWh, a fatura sobe cerca de "
    "1,30 euros por mês. O regulador atribui a subida ao custo de compra de gás nos mercados grossistas.\n\n"
    "## Porque importa\n\nA decisão abrange cerca de 30 mil clientes que continuam no mercado regulado; os "
    "restantes consumidores têm contratos em mercado livre, com preços definidos por cada comercializador.\n\n"
    "O período de aplicação corresponde ao ano gás 2026-2027, de 1 de outubro de 2026 até 30 de setembro de 2027. "
    "Quem está no mercado livre não é abrangido diretamente por esta decisão, mas as condições do mercado "
    "grossista também pesam nas ofertas comerciais, pelo que vale a pena comparar contratos."
)


def _draft(**kw):
    d = Draft(kind="noticia", title="Tarifas reguladas de gás natural sobem 6,4% desde outubro",
              lead="A subida média aplica-se aos clientes que permanecem no mercado regulado.",
              body=BODY, category="eletricidade-gas",
              key_points=["Subida média de 6,4%", "Cerca de 1,30 euros por mês", "Cerca de 30 mil clientes"],
              sources=[{"name": "ERSE", "url": "https://www.erse.pt/x", "date": "2026-09-30"}],
              facts=[{"claim": "subida de 6,4%", "evidence": "a variação média das tarifas de venda a clientes finais é de 6,4%"},
                     {"claim": "30 mil clientes", "evidence": "Cerca de 30 mil clientes permanecem no mercado regulado"}])
    for k, v in kw.items():
        setattr(d, k, v)
    return d


def test_number_normalisation():
    assert number_values("subiu 3,8 % e 1.000,5 MW", lang="pt") == {3.8, 1000.5}
    assert 1000.5 in number_values("price was 1,000.5 dollars", lang="any")
    assert number_values("1 600 kWh e 30 mil", lang="pt") == {1600.0, 30.0, 30000.0}


def test_valid_draft_passes(project, fixtures):
    cfg = load_config(project)
    v = validate(_draft(), (fixtures / "erse_tarifas.txt").read_text(), cfg.editorial, published=[])
    assert v.ok, v.errors


def test_numbers_must_be_grounded(project, fixtures):
    cfg = load_config(project)
    d = _draft(title="Tarifas reguladas de gás natural sobem 7,4% desde outubro")
    v = validate(d, (fixtures / "erse_tarifas.txt").read_text(), cfg.editorial, published=[])
    assert not v.ok
    assert any("7,4" in e for e in v.errors)


def test_copy_detected(project, fixtures):
    cfg = load_config(project)
    copied = BODY + "\n\nA ERSE refere que a evolução resulta sobretudo do aumento dos custos de aquisição de gás natural nos mercados grossistas."
    v = validate(_draft(body=copied), (fixtures / "erse_tarifas.txt").read_text(), cfg.editorial, published=[])
    assert any("copiad" in e for e in v.errors)


def test_fact_without_evidence_rejected(project, fixtures):
    cfg = load_config(project)
    d = _draft(facts=[{"claim": "x", "evidence": "o governo anunciou um apoio extraordinário"},
                      {"claim": "y", "evidence": "Cerca de 30 mil clientes permanecem no mercado regulado"}])
    v = validate(d, (fixtures / "erse_tarifas.txt").read_text(), cfg.editorial, published=[])
    assert any("evidência" in e for e in v.errors)


def test_duplicate_of_recent_article_rejected(project, fixtures):
    cfg = load_config(project)
    pub = [{"title": "Tarifas reguladas de gás natural sobem 6,4% a partir de outubro", "date": "2026-11-10"}]
    v = validate(_draft(), (fixtures / "erse_tarifas.txt").read_text(), cfg.editorial, published=pub,
                 today=date(2026, 11, 16))
    assert any("repetid" in e for e in v.errors)


def test_daily_without_llm_returns_none(project):
    cfg = load_config(project)
    assert generate_json("sys", "prompt", cfg.editorial["llm"], env={}) is None
    src = Source(id="erse", name="ERSE", institution="ERSE", url="https://www.erse.pt", method="html")
    assert draft_news({"title": "t", "url": "u", "published": None}, src, "texto " * 300, cfg.editorial, env={}) is None


def test_llm_chain_falls_back_to_second_provider(project):
    cfg = load_config(project)
    calls = []

    class Resp:
        def __init__(self, code, payload):
            self.status_code, self._p = code, payload

        def json(self):
            return self._p

    def fake_post(url, **kw):
        calls.append(url)
        if "generativelanguage" in url:
            return Resp(429, {"error": "quota"})
        return Resp(200, {"choices": [{"message": {"content": json.dumps({"ok": True})}}]})

    out = generate_json("sys", "prompt", cfg.editorial["llm"],
                        env={"GEMINI_API_KEY": "a", "LLM_API_KEY": "b"}, post=fake_post)
    assert out["ok"] is True and out["_provider"] == "openai_compatible"
    assert len(calls) == 2


def test_extract_html_prefers_article_text():
    html = "<html><nav>Menu Início</nav><article><h1>Título</h1><p>Texto principal do comunicado.</p></article><footer>Rodapé</footer></html>"
    assert extract_html_text(html) == "Título Texto principal do comunicado."


def test_gas_storage_piece_validates(project, fixtures):
    cfg = load_config(project)
    eu = parse_agsi(json.loads((fixtures / "agsi_eu.json").read_text()))
    pt = parse_agsi(json.loads((fixtures / "agsi_pt.json").read_text()))
    draft, evidence = gas_storage_piece(eu, pt, None)
    assert "87,1%" in draft.title and "94,5%" in draft.title
    assert draft.ai["used"] is False and draft.kind == "dados"
    v = validate(draft, evidence, cfg.editorial, published=[])
    assert v.ok, v.errors


def test_brent_fx_piece_validates(project, fixtures):
    cfg = load_config(project)
    brent = parse_eia(json.loads((fixtures / "eia_brent.json").read_text()))
    fx = parse_ecb_csv((fixtures / "ecb_usd.csv").read_text())
    draft, evidence = brent_fx_piece(brent, fx)
    assert "63,42" in draft.title
    v = validate(draft, evidence, cfg.editorial, published=[])
    assert v.ok, v.errors
