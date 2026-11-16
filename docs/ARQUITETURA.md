# Arquitetura

Um só fornecedor (GitHub), um só idioma (Python), dados em ficheiros de texto versionados. Nada corre fora do GitHub e nada depende de um serviço pago.

## Componentes e onde vivem

| Etapa | Ferramenta | Onde ficam os dados |
| --- | --- | --- |
| Agendamento | GitHub Actions (cron) — `.github/workflows/diario.yml` | — |
| Recolha | `fluxo/collect` (RSS com feedparser; páginas HTML por padrão de URL; deteção de alteração de página) | `data/items/AAAA-MM.jsonl`, `data/state/seen.json` |
| Deduplicação | `fluxo/dedup.py` (URL canónico + semelhança de títulos) | `data/state/seen.json`, `data/state/processed.json` |
| Pontuação | `fluxo/scoring.py` (5 critérios, 100 pontos, bloqueios) | em memória; decisão registada em `processed.json` |
| Investigação | `fluxo/extract.py` (texto integral da página ou PDF da fonte) | em memória |
| Redação | Peças de dados: `fluxo/write/data_pieces.py` (regras). Notícias: `fluxo/write/news.py` + `fluxo/llm.py` (Gemini → compatível OpenAI → nenhum) | — |
| Validação | `fluxo/validate.py` | rejeições em `data/rejected/AAAA-MM.jsonl` |
| Publicação | `fluxo/publish.py` | `content/articles/AAAA/MM/<slug>.md`, gráficos em `content/media/` |
| Revisão humana | pull request diário `revisao/AAAA-MM-DD` | ramo do pull request |
| Site | `fluxo/site/build.py` + Jinja2 → GitHub Pages (`publicar.yml`) | `_site/` (gerado, não versionado) |
| Instagram | `fluxo/instagram` (seleção, legenda, carrossel JPEG, API) | `content/instagram/`, `data/state/instagram.json` |
| Monitorização | `data/runs/AAAA-MM.jsonl`, `docs/ESTADO.md`, `docs/ESTADO-FONTES.md`, avisos (issues) | repositório |

## Regras que o código garante

1. Uma fonte em baixo nunca para a recolha das outras; a falha fica registada.
2. `robots.txt` é respeitado em todas as páginas; as APIs oficiais de dados são usadas com chave própria.
3. Nenhum artigo sai sem: fonte com ligação, texto da fonte recuperado (≥ 200 caracteres), todos os números presentes na fonte, nenhuma sequência de 12 palavras copiada, factos com evidência literal, título e corpo dentro dos limites, e sem repetir um artigo dos últimos 30 dias.
4. Sem chave de IA, o sistema continua: publica peças de dados e não publica notícias.
5. Texto com IA leva sempre rótulo visível; diz "revisto" apenas quando entrou por pull request aprovado.
6. No máximo 1 notícia por dia e 6 pedidos de IA por execução (configurável).

## Decisões e alternativas

- **GitHub Pages em vez de WordPress/Blogger:** domínio próprio, controlo de SEO, publicação por commit e alojamento das imagens que a API do Instagram exige. O Cloudflare Pages é a saída se o site passar a ter receitas (as Pages não podem servir um negócio online).
- **Ficheiros em vez de base de dados:** histórico completo no git, cópia de segurança com um `git clone`, nenhum serviço extra.
- **Pull request como fila de revisão:** gratuito, com notificação por email e aprovação no telemóvel (app GitHub).
- **IA intercambiável:** o GitHub Models foi retirado em 30/07/2026; a cadeia aceita Gemini e qualquer API compatível com OpenAI (Mistral, Groq, OpenRouter) através de segredos, sem alterar código.
