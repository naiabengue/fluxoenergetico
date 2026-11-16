import json
from datetime import datetime, timezone

from fluxo.config import load_config
from fluxo.models import Item
from fluxo.store import Store


def _item(url, title="ERSE publica tarifas de eletricidade para 2027", src="erse"):
    return Item(source_id=src, title=title, url=url,
                published="2026-11-12T10:00:00+00:00",
                collected_at="2026-11-16T06:00:00+00:00")


def test_config_loads_all_41_bee_sources(project):
    cfg = load_config(project)
    bee = [s for s in cfg.sources if s.bee_number is not None]
    assert len(bee) == 41
    assert sorted(s.bee_number for s in bee) == list(range(1, 42))
    assert all(s.method in {"rss", "html", "json", "api", "manual", "tool"} for s in cfg.sources)


def test_add_items_dedups_by_canonical_url(project):
    store = Store(project)
    new, dup = store.add_items([
        _item("https://www.erse.pt/comunicados/x/?utm_source=a"),
        _item("https://www.erse.pt/comunicados/x"),
    ])
    assert (new, dup) == (1, 1)
    new, dup = store.add_items([_item("https://www.erse.pt/comunicados/x/")])
    assert (new, dup) == (0, 1)


def test_items_persist_by_month(project):
    store = Store(project)
    store.add_items([_item("https://a.pt/1"), _item("https://a.pt/2", title="Outro título sobre gás natural")])
    path = project / "data" / "items" / "2026-11.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["url"] == "https://a.pt/1"
    now = datetime(2026, 11, 16, 12, tzinfo=timezone.utc)
    assert len(Store(project).recent_items(days=7, now=now)) == 2


def test_run_log_appends(project):
    store = Store(project)
    store.log_run({"started": "2026-11-16T06:00:00+00:00", "new": 3})
    store.log_run({"started": "2026-11-17T06:00:00+00:00", "new": 1})
    lines = (project / "data" / "runs" / "2026-11.jsonl").read_text().splitlines()
    assert [json.loads(l)["new"] for l in lines] == [3, 1]


def test_published_articles_reads_front_matter(project):
    d = project / "content" / "articles" / "2026" / "11"
    d.mkdir(parents=True)
    (d / "teste.md").write_text(
        "---\ntitle: Título de teste\nslug: teste\ndate: '2026-11-16'\ncategory: eletricidade-gas\n---\n\nCorpo.\n",
        encoding="utf-8")
    arts = Store(project).published_articles()
    assert arts[0]["title"] == "Título de teste"
    assert arts[0]["body"].strip() == "Corpo."
