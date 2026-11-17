from datetime import datetime, timezone

from fluxo.collect.html import parse_listing, parse_pagehash
from fluxo.collect.rss import parse_feed
from fluxo.collect.runner import collect_all
from fluxo.config import load_config
from fluxo.http import Fetcher, Response
from fluxo.models import Source
from fluxo.store import Store

NOW = datetime(2026, 11, 16, 6, 17, tzinfo=timezone.utc)


def _src(**kw):
    base = dict(id="x", name="X", institution="X", url="https://www.erse.pt/", method="html")
    base.update(kw)
    return Source(**base)


def test_rss_parses_items_with_dates(fixtures):
    items = parse_feed((fixtures / "adene_feed.xml").read_text(), _src(id="adene", method="rss"), NOW)
    assert len(items) == 2
    assert items[0].title.startswith("ADENE e CIG")
    assert items[0].published.startswith("2026-11-05T17:48:31")
    assert items[0].summary == "Debate em Lisboa sobre o papel das mulheres na transição energética."
    assert items[0].date_inferred is False


def test_rss_title_filter_keeps_only_energy_datasets(fixtures):
    src = _src(id="eurostat-data-updates", method="rss", title_filter=r"(?i)\bnrg_|energy|electricity")
    items = parse_feed((fixtures / "eurostat_updates.rss").read_text(), src, NOW)
    assert [i.title[:10] for i in items] == ["nrg_pc_204"]


def test_html_listing_uses_link_pattern_and_dates(fixtures):
    src = _src(id="erse", link_pattern=r"(/comunicacao/comunicados/[a-z0-9-]+/$|/media/[a-z0-9]+/[^/]+\.pdf$)")
    items = parse_listing((fixtures / "erse_comunicados.html").read_text(), src,
                          "https://www.erse.pt/comunicacao/comunicados/", NOW)
    assert len(items) == 3
    assert items[0].url == "https://www.erse.pt/media/j0gjukgx/balanco-sancionatorio-3-trimestre2026.pdf"
    assert items[0].published.startswith("2026-11-10")
    assert items[2].title.startswith("Tarifas de gás natural aumentam 6,4%")


def test_html_date_from_url_when_configured(fixtures):
    src = _src(id="imf", url="https://www.imf.org/", date_in_url=True,
               link_pattern=r"/en/news/articles/20\d\d/\d\d/\d\d/[a-z0-9-]+")
    items = parse_listing((fixtures / "imf_news.html").read_text(), src, "https://www.imf.org/en/news", NOW)
    assert [i.published[:10] for i in items] == ["2026-10-07", "2026-09-29"]


def test_html_without_date_marks_inferred():
    html = '<a href="https://www.dgeg.gov.pt/pt/destaques/estatisticas-rapidas-das-renovaveis-setembro-2026/">Estatísticas rápidas das renováveis - setembro de 2026</a>'
    src = _src(id="dgeg", url="https://www.dgeg.gov.pt/", link_pattern=r"/pt/destaques/[a-z0-9-]+/$")
    items = parse_listing(html, src, "https://www.dgeg.gov.pt/pt/destaques/", NOW)
    assert items[0].date_inferred is True
    assert items[0].published is None


def test_pagehash_creates_item_only_when_text_changes():
    src = _src(id="ap2h2", url="https://www.ap2h2.pt/", mode="pagehash")
    a = parse_pagehash("<main>04.11.2026 CarbonWise 2026</main>", src, "https://www.ap2h2.pt/noticias.php", NOW)
    b = parse_pagehash("<main>04.11.2026 CarbonWise 2026</main>", src, "https://www.ap2h2.pt/noticias.php", NOW)
    c = parse_pagehash("<main>20.11.2026 Novo evento</main>", src, "https://www.ap2h2.pt/noticias.php", NOW)
    assert a[0].url == b[0].url != c[0].url


class FakeFetcher:
    def __init__(self, pages):
        self.pages = pages
        self.errors = {}

    def get(self, url):
        if url not in self.pages:
            self.errors[url] = "HTTP 503"
            return None
        return Response(url=url, status=200, text=self.pages[url], content=self.pages[url].encode(), headers={})


def test_collect_survives_source_failure(project, fixtures):
    cfg = load_config(project)
    for s in cfg.sources:
        s.enabled = s.id in {"adene", "apren"}
    fetcher = FakeFetcher({"https://www.adene.pt/feed/": (fixtures / "adene_feed.xml").read_text()})
    stats = collect_all(cfg, Store(project), fetcher, NOW)
    assert stats["sources"]["adene"]["status"] == "ok"
    assert stats["sources"]["adene"]["new"] == 2
    assert stats["sources"]["apren"]["status"] == "erro"
    assert stats["new"] == 2 and stats["failed"] == 1


class StubSession:
    def __init__(self, robots):
        self.robots = robots
        self.calls = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append(url)
        body = self.robots if url.endswith("/robots.txt") else "<html>ok</html>"

        class R:
            status_code = 200
            text = body
            content = body.encode()
            headers = {"content-type": "text/html"}
        R.url = url
        return R()


def test_fetcher_respects_robots_txt():
    session = StubSession("User-agent: *\nDisallow: /pt/\n")
    f = Fetcher(session=session, min_interval=0)
    assert f.get("https://gee.gov.pt/pt/indicadores") is None
    assert "robots" in f.errors["https://gee.gov.pt/pt/indicadores"]
    assert f.get("https://gee.gov.pt/outra") is not None


def test_rss_link_drops_fragment():
    feed = ('<?xml version="1.0"?><rss version="2.0"><channel><title>A</title><item>'
            '<title>Outubro: energia eólica lidera a produção renovável</title>'
            '<link>https://www.apren.pt/wp-content/uploads/2026/11/Outubro.pdf#new_tab</link>'
            '<pubDate>Thu, 12 Nov 2026 10:00:00 +0000</pubDate></item></channel></rss>')
    items = parse_feed(feed, _src(id="apren", method="rss"), NOW)
    assert items[0].url == "https://www.apren.pt/wp-content/uploads/2026/11/Outubro.pdf"
