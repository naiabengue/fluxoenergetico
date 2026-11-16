# Manual de manutenção

Este manual cobre a primeira configuração e todas as tarefas de manutenção. Não é preciso instalar nada no computador: tudo se faz no site do GitHub ou na app GitHub do telemóvel.

## 1. Primeira configuração (uma vez, cerca de 1 hora)

### 1.1 Conta e repositório
1. Com a conta GitHub pessoal, criar uma **organização gratuita** com o nome da marca (ex.: `fluxoenergetico`). Em *Settings → Member privileges*, manter a lista de membros privada. Assim o site não fica associado ao nome pessoal.
2. Na organização, criar um repositório **público** chamado `fluxoenergetico.github.io` (o nome `<organização>.github.io` faz o site ficar na raiz do endereço). Repositório público é obrigatório para o GitHub Pages e para minutos de Actions ilimitados no plano gratuito.
3. Enviar o conteúdo desta pasta para o repositório (ou pedir ao Claude para o fazer, ligando o repositório à sessão).
4. *Settings → Pages → Build and deployment → Source:* **GitHub Actions**.
5. *Settings → Actions → General → Workflow permissions:* **Read and write permissions** e ativar **Allow GitHub Actions to create and approve pull requests**. Numa organização, ativar a mesma opção em *Organization settings → Actions → General*.

### 1.2 Chaves gratuitas (Settings → Secrets and variables → Actions)
| Segredo | Para quê | Onde obter | Obrigatório |
| --- | --- | --- | --- |
| `EIA_API_KEY` | Peça "Brent e câmbio" | registo gratuito em eia.gov/opendata | Recomendado |
| `AGSI_API_KEY` | Peça "Armazenamento de gás" | conta gratuita em agsi.gie.eu | Recomendado |
| `GEMINI_API_KEY` | Redação de notícias | aistudio.google.com/apikey, num projeto **sem faturação ativa** (assim nunca há cobrança) | Opcional |
| `LLM_API_KEY` + variáveis `LLM_BASE_URL`, `LLM_MODEL` | IA de reserva (ex.: Mistral) | console.mistral.ai; o plano gratuito pode exigir telemóvel e usar os pedidos para treino | Opcional |
| `IG_ACCESS_TOKEN`, `IG_USER_ID` | Publicar no Instagram pela API | ver 1.4 | Opcional |
| `GH_PAT` | Renovar o token do Instagram todos os meses | token *fine-grained* só deste repositório, permissão *Secrets: read and write* | Opcional |

Sem nenhuma chave de IA, o sistema publica as peças de dados e não publica notícias.

### 1.3 Identificação e domínio
1. Editar `config/site.yaml`: `owner` (nome, email, endereço; dever de identificação do prestador, DL 7/2004, art. 10.º), `base_url` e, quando existir, `domain`.
2. No registador do domínio, criar os registos DNS do GitHub Pages:
   - domínio de topo (`fluxoenergetico.pt`): quatro registos **A** para `185.199.108.153`, `185.199.109.153`, `185.199.110.153` e `185.199.111.153`;
   - `www`: registo **CNAME** para `fluxoenergetico.github.io`.
3. Em *Settings → Pages*, escrever o domínio e ativar **Enforce HTTPS** quando o certificado estiver emitido. Verificar o domínio em *Organization settings → Pages* (evita que terceiros o usem).

### 1.4 Instagram
**Modo manual (predefinido, sem configuração):** à terça e sexta o sistema prepara o carrossel (imagens 1080×1350 e `legenda.txt` em `content/instagram/`) e abre um aviso no GitHub. Para publicar: descarregar as imagens, abrir o Meta Business Suite (ou a app Instagram) → *Criar publicação* → carregar as imagens pela ordem → colar a legenda → **Agendar**.

**Modo automático (opcional):**
1. Na app Instagram: *Definições → Tipo de conta e ferramentas → Mudar para conta profissional* (Criador ou Empresa). Não é preciso página do Facebook.
2. Em developers.facebook.com, criar uma app do tipo *Instagram API com início de sessão do Instagram*, adicionar a conta @fluxoenergetico.pt como utilizador com função na app (acesso padrão chega para a própria conta; não é preciso revisão da app).
3. Gerar um token com as permissões `instagram_business_basic` e `instagram_business_content_publish`, trocá-lo por um token de longa duração (60 dias) e obter o `user_id` em `https://graph.instagram.com/me?fields=user_id,username`.
4. Guardar `IG_ACCESS_TOKEN` e `IG_USER_ID` como segredos e mudar `instagram.auto_publish` para `true` em `config/editorial.yaml`.
5. Com `GH_PAT` configurado, o workflow *Renovar token do Instagram* renova o token no dia 1 de cada mês. Sem ele, repetir o passo 3 antes de passarem 60 dias.

O ecrã da Meta muda com frequência: seguir a documentação oficial "Instagram API with Instagram Login" se os nomes dos menus forem outros.

### 1.5 Primeiro arranque
1. *Actions → Auditoria das fontes → Run workflow*. Ver `docs/ESTADO-FONTES.md`: fontes com "sem itens" precisam de ajuste do `link_pattern` (secção 3.1).
2. *Actions → Diário → Run workflow*, com `brent_fx,gas_storage` no campo de peças, para ver o primeiro artigo publicado.
3. Abrir o site no endereço indicado no passo *deploy* do workflow.

## 2. Operação normal
- **Todos os dias às 06:23 UTC:** recolha, peças de dados do dia (segunda: Brent e câmbio; quinta: armazenamento de gás), até 1 notícia. O site é atualizado sozinho.
- **Notícias redigidas com IA (fase 1):** chegam como pull request "Revisão AAAA-MM-DD", com um email do GitHub. No telemóvel: app GitHub → *Pull requests* → *Files changed* para ler. Para corrigir: editar o ficheiro no próprio pull request. Para publicar: **Merge**. Para rejeitar: **Close**. Rever de verdade: o rótulo passa a dizer "revisto pela redação".
- **Domingo:** auditoria das fontes; se alguma fonte ativa falhar, abre um aviso (*Issues*).
- **Terça e sexta:** carrossel do Instagram.

## 3. Tarefas de manutenção

### 3.1 Atualizar fontes (`config/sources.yaml`)
- **Desativar/ativar:** `enabled: false` / `true`.
- **Feed RSS:** `method: rss` e a lista `feeds`.
- **Página sem feed:** `method: html`, `listing_url` (página que lista as novidades) e `link_pattern` (expressão regular que os endereços dos artigos cumprem). Quando a auditoria indica "sem itens", a coluna *Observações* mostra links candidatos para escrever o padrão.
- **Nova fonte:** copiar um bloco existente, dar um `id` novo, `bee: null` e `extra: true` (fica identificada como fonte adicional).
- Depois de alterar: correr *Auditoria das fontes* para confirmar.

### 3.2 Alterar a frequência
- Hora do diário: `cron` em `.github/workflows/diario.yml` (hora UTC). Instagram: `instagram.yml`. Auditoria: `auditoria.yml`.
- Número de notícias por dia: `policy.max_news_per_day`. Pedidos de IA por execução: `llm.max_calls_per_run`.
- Dia das peças de dados: `data_pieces.<peça>.weekday` (0 = segunda).

### 3.3 Modificar categorias e critérios (`config/editorial.yaml`)
- `categories`: nome e palavras-chave (sem acentos ou com, tanto faz). `core_categories`: o núcleo do lançamento; as restantes perdem `non_core_penalty` pontos.
- `scoring.weights` (somam 100) e `scoring.thresholds` (publicar ≥ 80; rever 65–79).
- `validation`: limites de tamanho, palavras copiadas, expressões proibidas.

### 3.4 Política de publicação
- Passar notícias com IA a publicação automática (fase 2): `policy.auto_publish_news: true`. Recomendado só depois de 4 semanas de revisões sem correções relevantes. Os artigos continuam com o rótulo de IA.

### 3.5 Corrigir ou retirar um artigo
- Corrigir: abrir `content/articles/AAAA/MM/<slug>.md` no GitHub → editar → *Commit*. O site atualiza-se em 1–2 minutos. Acrescentar no fim uma linha "**Correção (data):** …".
- Retirar: apagar o ficheiro e fazer *Commit*.

### 3.6 Reexecutar
*Actions* → escolher o workflow → **Run workflow**. O diário aceita o campo de peças para forçar `brent_fx` e/ou `gas_storage`. Um item já tratado não volta a ser redigido; para o repetir, apagar a sua linha em `data/state/processed.json`.

### 3.7 Consultar registos
- Cada execução: *Actions* → execução → passo "Recolher, redigir e validar".
- Histórico: `docs/ESTADO.md` (resumo), `data/runs/AAAA-MM.jsonl` (detalhe: fontes com erro, novos, publicados, revisão, rejeitados, pedidos de IA), `data/rejected/AAAA-MM.jsonl` (motivo de cada rejeição).

### 3.8 Alterar o aspeto do site
Modelos em `fluxo/site/templates/`, estilos em `fluxo/site/static/style.css`. Antes de enviar: `python -m pytest -q` e `python -m fluxo build`, e abrir `_site/index.html` com `python -m http.server -d _site`.

### 3.9 Recuperar o serviço
- **O diário deixou de correr:** o GitHub desativa agendamentos ao fim de 60 dias sem atividade no repositório. Em *Actions*, abrir o workflow e carregar em **Enable workflow**.
- **IA sem resposta (quota):** o sistema tenta o fornecedor seguinte e, sem nenhum, continua sem notícias. Ver o aviso no registo; volta a tentar no dia seguinte.
- **Site em baixo:** *Actions → Publicar site → Run workflow*. Se o GitHub Pages ficar indisponível ou o site passar a ter receitas, publicar no Cloudflare Pages (plano gratuito): ligar o repositório, comando de build `pip install -r requirements.txt && python -m fluxo build`, pasta `_site`.
- **Fonte mudou de estrutura:** ver 3.1.

### 3.10 Cópias de segurança e exportação
Todo o projeto (código, fontes, dados, artigos, registos) está no repositório. Cópia completa: *Code → Download ZIP* ou `git clone`. Os artigos são Markdown com metadados e importam-se em qualquer outro sistema; os dados recolhidos são JSON Lines.

## 4. Limites gratuitos a vigiar
| Serviço | Limite | O que acontece se for excedido |
| --- | --- | --- |
| GitHub Actions (repositório público) | sem limite de minutos | — |
| GitHub Pages | site até 1 GB; ~100 GB/mês de tráfego (limite flexível); 10 builds/hora | aviso do GitHub; migrar para Cloudflare Pages |
| Gemini (quota gratuita) | limites por projeto não publicados nem garantidos (ver aistudio.google.com) | pedido falha → fornecedor seguinte → sem notícia nesse dia |
| API do Instagram | 100 publicações por API em 24 h | irrelevante (2 por semana) |
| Token do Instagram | 60 dias | publicação falha até renovar (1.4) |
