# Fluxo Energético

Publicação digital sobre energia em Portugal e na União Europeia. Este repositório contém tudo o que é preciso: o código, as 41 fontes, os dados recolhidos, os artigos e o site. A operação é automática e custa **0 €** (só o domínio, já existente, tem custo próprio).

## Como funciona

```
Fontes BEE (41) ─► Recolha diária (GitHub Actions) ─► data/items/*.jsonl
                                │
                                ├─► Peças de dados (EIA, BCE, GIE) ─► sem IA ─► publicação automática
                                │
                                └─► Pontuação + deduplicação ─► Redação com IA (Gemini/Mistral, opcional)
                                                                   │
                                                          Validação bloqueante
                                                    (números, cópia, evidência, repetição)
                                                                   │
                                          ┌────────────────────────┴───────────────┐
                                    publicar (fase 2)                   pull request para revisão (fase 1)
                                          └────────────────────────┬───────────────┘
                                                      content/articles/*.md
                                                                   │
                                                    Site estático ─► GitHub Pages
                                                                   │
                                           Carrossel semanal ─► Instagram (API ou Meta Business Suite)
```

## Comandos

```bash
pip install -r requirements.txt
python -m pytest -q                  # testes
python -m fluxo daily                # recolha + peças de dados + notícias
python -m fluxo build                # gera o site em _site/
python -m fluxo audit                # testa as fontes e escreve docs/ESTADO-FONTES.md
python -m fluxo instagram            # prepara o carrossel da semana
python -m fluxo status               # resumo das últimas execuções (docs/ESTADO.md)
```

## Documentação

- [Manual de manutenção e primeira configuração](docs/MANUAL.md)
- [Arquitetura](docs/ARQUITETURA.md)
- [Estado das fontes](docs/ESTADO-FONTES.md) e [estado das execuções](docs/ESTADO.md) (gerados automaticamente)
- Configuração editorial: [`config/editorial.yaml`](config/editorial.yaml); fontes: [`config/sources.yaml`](config/sources.yaml); site: [`config/site.yaml`](config/site.yaml)
