# Fluxo Energético — MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pipeline diário a custo zero que recolhe as fontes BEE, seleciona, redige (dados sem IA; notícias com IA opcional), valida, publica um site estático e prepara carrosséis de Instagram.

**Architecture:** Repositório GitHub público (organização da marca). GitHub Actions corre `python -m fluxo` em cron; dados em JSONL/JSON versionados; artigos em Markdown com front matter; site estático gerado por `fluxo.site.build` e servido pelo GitHub Pages. Revisão humana = pull request diário.

**Tech Stack:** Python 3.11+, requests, feedparser, beautifulsoup4, pypdf, PyYAML, Jinja2, Markdown, Pillow, matplotlib, pytest.

**Spec:** Doc "Fluxo Energético — Auditoria, arquitetura e plano (custo zero)" (secções 3–6) + `docs/ARQUITETURA.md`.

## Global Constraints

- Custo 0 €: nenhuma dependência paga; IA sempre opcional (sem chave → só artigos de dados).
- Nunca publicar sem: URL da fonte primária, data, validação aprovada. Verificabilidade é bloqueio, não peso.
- Texto com IA leva rótulo visível (AI Act art. 50.º n.º 4); `ai.reviewed` só passa a true por merge humano.
- Respeitar robots.txt; User-Agent identificado; máx. 1 pedido/s por domínio.
- Nenhum excerto ≥ 12 palavras seguidas copiado da fonte (originalidade).
- Português europeu em todo o conteúdo e interface.

## Review Focus

1. Fonte em baixo/HTML alterado → recolha continua com as outras e regista falha (test_collect_survives_source_failure).
2. Número no texto que não existe na fonte → rejeitado (test_numbers_must_be_grounded).
3. Mesmo acontecimento em 2 fontes no mesmo dia → 1 só candidato (test_cluster_same_event).
4. Sem chave de IA → pipeline corre, publica dados, não publica notícias (test_daily_without_llm).
5. Datas "1.000,5" vs "1,000.5" e percentagens "3,8 %" → normalização correta (test_number_normalisation).

---

### Task 1: Configuração, modelos e armazenamento
**Files:** `fluxo/config.py`, `fluxo/models.py`, `fluxo/store.py`, `config/*.yaml`, `tests/test_store.py`
**Produces:** `load_config(root) -> Config`; `Source`, `Item` dataclasses; `Store(root).add_items(items) -> tuple[int,int]`, `.recent_items(days) -> list[Item]`, `.log_run(dict)`, `.published_articles() -> list[dict]`.
- [ ] test_add_items_dedups_by_canonical_url; test_items_persist_by_month; test_run_log_appends → implementar → passar.

### Task 2: HTTP educado + coletores RSS/HTML/JSON
**Files:** `fluxo/http.py`, `fluxo/collect/{rss,html,jsonfeed,runner}.py`, `tests/test_collect.py`, `tests/fixtures/*`
**Produces:** `Fetcher.get(url) -> Response|None` (robots, retries, offline fixtures); `collect_all(cfg, store, fetcher, now) -> dict` (stats por fonte).
- [ ] test_rss_parses_items_with_dates; test_html_listing_uses_link_pattern_and_dates; test_collect_survives_source_failure.

### Task 3: Deduplicação e pontuação
**Files:** `fluxo/dedup.py`, `fluxo/scoring.py`, `tests/test_scoring.py`
**Produces:** `canonical_url`, `cluster(items) -> list[list[Item]]`, `score(item, source, editorial, now) -> Score`.
- [ ] test_cluster_same_event; test_blocked_without_url_or_date; test_weights_sum_to_100.

### Task 4: Extração, IA opcional, redação e validação
**Files:** `fluxo/extract.py`, `fluxo/llm.py`, `fluxo/write/{news,data_pieces}.py`, `fluxo/datasets/{agsi,eia,ecb}.py`, `fluxo/validate.py`, `tests/test_validate.py`
**Produces:** `generate_json(system, prompt, cfg) -> dict|None`; `draft_news(...) -> Draft|None`; `validate(draft, evidence, cfg, published) -> Validation`.
- [ ] test_numbers_must_be_grounded; test_number_normalisation; test_copy_detected; test_daily_without_llm.

### Task 5: Publicação e site estático
**Files:** `fluxo/publish.py`, `fluxo/site/build.py`, `fluxo/site/templates/*`, `fluxo/site/static/*`, `tests/test_site.py`
**Produces:** `write_article(draft, meta, root) -> Path`; `build_site(root, out) -> dict`.
- [ ] test_build_creates_index_article_category_feed_sitemap; test_ai_label_rendered; test_cname_written_when_domain_set.

### Task 6: Instagram
**Files:** `fluxo/instagram/{select,render,caption,publish}.py`, `tests/test_instagram.py`
- [ ] test_render_jpeg_1080x1350_max_10; test_caption_under_2200_chars; test_publish_skipped_without_token.

### Task 7: CLI, workflows, auditoria de fontes, documentação
**Files:** `fluxo/cli.py`, `.github/workflows/{diario,deploy,instagram,auditoria}.yml`, `README.md`, `docs/MANUAL.md`, `docs/ARQUITETURA.md`
- [ ] `python -m fluxo daily --offline` end-to-end com fixtures; `python -m fluxo build` gera `_site/`; YAML dos workflows válido.

Execução: nativa (implementação nesta sessão, revisão final independente), por instrução do proprietário para não interromper.
