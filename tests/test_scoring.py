from datetime import datetime, timezone

from fluxo.config import load_config
from fluxo.dedup import cluster
from fluxo.models import Item
from fluxo.scoring import score

NOW = datetime(2026, 11, 16, 6, 17, tzinfo=timezone.utc)


def _it(src, title, published="2026-11-15T10:00:00+00:00", summary="", inferred=False, url=None):
    return Item(source_id=src, title=title, url=url or f"https://ex.pt/{abs(hash(title))}",
                published=None if inferred else published, collected_at=NOW.isoformat(),
                summary=summary, date_inferred=inferred)


def test_weights_sum_to_100(project):
    cfg = load_config(project)
    assert sum(cfg.editorial["scoring"]["weights"].values()) == 100


def test_cluster_same_event():
    a = _it("erse-comunicados", "Tarifas de gás natural aumentam 6,4% no mercado regulado a partir de 1 de outubro")
    b = _it("dgeg-destaques", "Tarifas do gás natural no mercado regulado aumentam 6,4% a 1 de outubro")
    c = _it("apren", "Energia eólica lidera e assegura mais de um terço da produção renovável")
    groups = cluster([a, b, c], threshold=0.5)
    assert [len(g) for g in groups] == [2, 1]


def test_pt_energy_news_scores_as_candidate(project):
    cfg = load_config(project)
    it = _it("erse-comunicados", "ERSE: proposta de tarifas e preços para a energia elétrica em 2027",
             summary="Tarifas de eletricidade para clientes em Portugal")
    s = score(it, cfg.source("erse-comunicados"), cfg.editorial, NOW)
    assert s.category == "eletricidade-gas"
    assert s.total >= 80 and s.decision == "candidato"
    assert s.parts["credibilidade"] == 25 and s.parts["geografia"] == 15


def test_off_topic_item_is_rejected(project):
    cfg = load_config(project)
    it = _it("imf-news", "IMF Executive Board Concludes 2026 Article IV Consultation with Macao SAR")
    s = score(it, cfg.source("imf-news"), cfg.editorial, NOW)
    assert s.decision == "rejeitar"


def test_blocked_when_title_too_short(project):
    cfg = load_config(project)
    s = score(_it("adene", "Notícia"), cfg.source("adene"), cfg.editorial, NOW)
    assert s.blocked and s.decision == "rejeitar"


def test_inferred_date_reduces_verifiability_and_old_items_lose_freshness(project):
    cfg = load_config(project)
    src = cfg.source("dgeg-destaques")
    fresh = score(_it("dgeg-destaques", "Estatísticas rápidas dos combustíveis em Portugal", inferred=True),
                  src, cfg.editorial, NOW)
    old = score(_it("dgeg-destaques", "Estatísticas rápidas dos combustíveis em Portugal",
                    published="2026-10-01T10:00:00+00:00"), src, cfg.editorial, NOW)
    assert fresh.parts["verificabilidade"] == 5
    assert old.parts["novidade"] == 0


def test_excluded_keywords_block_items(project):
    cfg = load_config(project)
    ed = cfg.editorial
    assert "ENSE" in ed["excluded_keywords"]
    src = cfg.source("dgeg-destaques")
    hit = score(_it("dgeg-destaques", "ENSE publica preços médios dos combustíveis em Portugal"), src, ed, NOW)
    assert "tema excluído" in hit.blocked and hit.decision == "rejeitar"
    full = score(_it("dgeg-destaques", "Relatório da Entidade Nacional para o Setor Energético sobre combustíveis"),
                 src, ed, NOW)
    assert "tema excluído" in full.blocked
    # «ense» dentro de outra palavra não bloqueia
    ok = score(_it("dgeg-destaques", "Licenses for intense expense in fuel supply in Portugal"), src, ed, NOW)
    assert "tema excluído" not in ok.blocked


def test_monetary_policy_paper_is_not_energy(project):
    from fluxo.config import load_config
    from fluxo.scoring import score

    cfg = load_config(project)
    src = cfg.source("ecb-wp")
    it = Item(id="x", source_id="ecb-wp", title="Monetary policy, capital market segmentation and innovation",
              url="https://www.ecb.europa.eu/pub/pdf/scpwps/ecb.wp3311.en.pdf",
              published=NOW.isoformat(), collected_at=NOW.isoformat(),
              summary="We study how monetary policy affects firm innovation through financing constraints, "
                      "investment and capital markets in the euro area.")
    sc = score(it, src, cfg.editorial, NOW)
    assert "sem relação com energia" in sc.blocked and sc.decision == "rejeitar"


def test_energy_policy_still_counts(project):
    from fluxo.config import load_config
    from fluxo.scoring import score

    cfg = load_config(project)
    src = cfg.source("ecb-wp")
    it = Item(id="y", source_id="ecb-wp", title="Energy prices and monetary policy in the euro area",
              url="https://www.ecb.europa.eu/pub/x.pdf", published=NOW.isoformat(), collected_at=NOW.isoformat(),
              summary="How the surge in natural gas and electricity prices shaped inflation.")
    assert "sem relação com energia" not in score(it, src, cfg.editorial, NOW).blocked
