# Manual de manutenção

Este manual cobre a primeira configuração e todas as tarefas de manutenção. Não é preciso instalar nada no computador: tudo se faz no site do GitHub ou na app GitHub do telemóvel.

## 1. Primeira configuração (uma vez, cerca de 1 hora)

O site é assumido em nome próprio (responsável: Pedro Camilo Ramos) e vive no domínio já existente `naiabengue.com`, sem comprar domínio novo:

| Repositório (conta GitHub `naiabengue`) | O que serve | Endereço |
| --- | --- | --- |
| `naiabengue/naiabengue.github.io` | página simples da Naiabengue; é o dono do domínio (ficheiro `CNAME` com `naiabengue.com`) | https://naiabengue.com/ |
| `naiabengue/fluxoenergetico` (este) | o pipeline e o site do Fluxo Energético | https://naiabengue.com/fluxoenergetico/news/ |

O GitHub Pages serve os repositórios de projeto de uma conta debaixo do domínio do site de utilizador dessa conta, por isso este repositório **não** tem `CNAME` (`domain: ""` em `config/site.yaml`). O site é gerado na subpasta `news` e a raiz `/fluxoenergetico/` redireciona para lá.

### 1.1 Repositórios
1. Com a conta GitHub `naiabengue`, criar dois repositórios **públicos**: `naiabengue.github.io` e `fluxoenergetico`. Repositório público é obrigatório para o GitHub Pages e dá minutos de Actions ilimitados no plano gratuito.
2. Enviar o conteúdo de cada pasta para o repositório respetivo (ou pedir ao Claude para o fazer, ligando os repositórios à sessão).
3. Em **ambos**: *Settings → Pages → Build and deployment → Source*. No `naiabengue.github.io`: **Deploy from a branch**, `main`, pasta `/ (root)`. No `fluxoenergetico`: **GitHub Actions**.
4. No `fluxoenergetico`: *Settings → Actions → General → Workflow permissions:* **Read and write permissions** e ativar **Allow GitHub Actions to create and approve pull requests**.

### 1.2 Domínio naiabengue.com (Hostinger)
1. Em hPanel → *Domínios → naiabengue.com → DNS / Nameservers*, apagar os registos de estacionamento (os **A** e **CNAME** de `@` e `www` que apontam para a página «parked» da Hostinger). Não mexer em registos **MX** ou **TXT** de email, se existirem.
2. Criar os registos do GitHub Pages:
   - `@`: quatro registos **A** para `185.199.108.153`, `185.199.109.153`, `185.199.110.153` e `185.199.111.153`;
   - `www`: registo **CNAME** para `naiabengue.github.io`.
3. No repositório `naiabengue.github.io`: *Settings → Pages → Custom domain* = `naiabengue.com` → *Save*. Quando o certificado estiver emitido (minutos a algumas horas), ativar **Enforce HTTPS**.
4. Recomendado: verificar o domínio em *Settings (da conta) → Pages → Add a domain*, com o registo **TXT** que o GitHub indicar. Evita que outra conta use o domínio.
5. Confirmar: https://naiabengue.com/ mostra a página da Naiabengue e https://naiabengue.com/fluxoenergetico/news/ mostra o Fluxo Energético (depois do primeiro *Publicar site*).

### 1.3 Chaves gratuitas (no `fluxoenergetico`: Settings → Secrets and variables → Actions)
As contas dos serviços de dados e IA ficam em nome de `naiabengue@gmail.com`.

| Segredo | Para quê | Onde obter | Obrigatório |
| --- | --- | --- | --- |
| `EIA_API_KEY` | Peça "Brent e câmbio" | registo gratuito em eia.gov/opendata | Recomendado |
| `AGSI_API_KEY` | Peça "Armazenamento de gás" | conta gratuita em agsi.gie.eu | Recomendado |
| `GEMINI_API_KEY` | Redação de notícias | aistudio.google.com/apikey, num projeto **sem faturação ativa** (assim nunca há cobrança) | Opcional |
| `LLM_API_KEY` + variáveis `LLM_BASE_URL`, `LLM_MODEL` | IA de reserva (ex.: Mistral) | console.mistral.ai; o plano gratuito pode exigir telemóvel e usar os pedidos para treino | Opcional |
| `CF_ACCOUNT_ID`, `CF_API_TOKEN` | Imagem de capa do carrossel gerada por IA | conta gratuita em dash.cloudflare.com → *AI → Workers AI → Use REST API*: copiar o *Account ID* e criar o token com o modelo *Workers AI* (permissões *Workers AI – Read* e *Edit*). Não ativar o plano Workers Paid | Opcional |
| `IG_ACCESS_TOKEN`, `IG_USER_ID` | Publicar no Instagram pela API | ver 1.5 | Recomendado |
| `GH_PAT` | Renovar o token do Instagram todos os meses (só no «login do Instagram»; o login unificado não precisa) | token *fine-grained* só deste repositório, permissão *Secrets: read and write* | Não necessário |

Sem nenhuma chave de IA, o sistema publica as peças de dados e não publica notícias. Sem `CF_*`, a capa do carrossel é tipográfica.

### 1.4 Identificação e independência
`config/site.yaml` já tem o responsável (`owner`: Pedro Camilo Ramos, `pedrocamiloramos@gmail.com`, Lisboa; dever de identificação do prestador, DL 7/2004, art. 10.º) e a nota de independência (`disclaimer`), mostrada no rodapé e em «Sobre». Os temas em `excluded_keywords` (`config/editorial.yaml`) nunca entram na recolha editorial. O registo na ERC fica para tratar depois do lançamento.

### 1.5 Instagram (modo automático pela API)
Configurado a 17/11/2026 com o **login unificado**, a única opção que a Meta oferece às apps novas.
1. @fluxoenergetico.pt é uma conta profissional (*Empresa*, categoria «Site de notícias», categoria escondida no perfil). Não é preciso página do Facebook.
2. App da Meta **Fluxo Energetico Publicador** (developers.facebook.com, conta de programador de Pedro Camilo Ramos), caso de uso *Gerenciar mensagens e conteúdo no Instagram*, ligada ao portfólio empresarial «Pedro». Configuração *API do Instagram (login unificado)*: token de utilizador de sistema, **não expira**.
3. Em *Funções do app*, @fluxoenergetico.pt tem a função *Testador do Instagram* (convite aceite em Instagram → Definições → Apps e sites → Convites de teste). O acesso padrão chega para publicar na própria conta; não é preciso revisão da app.
4. Token: *Casos de uso → Personalizar → API setup with Unified login → 2. Gerar tokens de acesso → Gerar token* (abre uma janela da Meta; tem de ser o proprietário a clicar). Guardar como segredo `IG_ACCESS_TOKEN`. O ID da conta (`IG_USER_ID`) aparece na mesma tabela por baixo do nome.
5. Confirmar com o workflow manual **Verificar Instagram** (não publica nada; deve dizer «Token válido para a conta @fluxoenergetico.pt»). Depois mudar `instagram.auto_publish` para `true` em `config/editorial.yaml`.
6. O código chama `graph.facebook.com` (`instagram.login: unified`). O workflow *Renovar token do Instagram* não faz nada neste modo. Se um dia a app for trocada por uma com «login do Instagram», pôr `instagram.login: instagram`: passa a usar `graph.instagram.com` e a renovar o token de 60 dias (requer `GH_PAT`).
7. Se o token deixar de funcionar (palavra-passe alterada, app removida, testador retirado), gerar um novo no passo 4 e substituir o segredo.

As imagens do carrossel são servidas pelo próprio site (`https://naiabengue.com/fluxoenergetico/news/instagram/...`), que é o endereço público que a API do Instagram vai buscar. O ecrã da Meta muda com frequência: se os nomes dos menus forem outros, seguir a documentação oficial da API do Instagram com login unificado.

**Estilo (misto):** capa com o título como gancho e indicação para deslizar; miolo sóbrio com um ponto-chave por imagem; último diapositivo com «Guarda e partilha» e a ligação. A legenda tem no máximo 3 emojis (gancho, apelo a guardar e comentar, ligação), fontes, nota de IA e até 8 hashtags. Textos e emojis em `instagram` no `config/editorial.yaml`. Com `CF_*` configurado e `ai_cover: true`, a capa usa uma imagem gerada por IA (FLUX.1 [schnell], sem pessoas, texto nem logótipos) identificada na própria imagem («Imagem gerada por IA») e na legenda.

**Modo manual (se a API não estiver configurada):** à terça e sexta o sistema prepara o carrossel (imagens 1080×1350 e `legenda.txt` em `content/instagram/`) e abre um aviso no GitHub. Para publicar: descarregar as imagens, abrir o Meta Business Suite (ou a app Instagram) → *Criar publicação* → carregar as imagens pela ordem → colar a legenda → **Agendar**.

### 1.5.1 Email diário de revisão (até 15/12/2026)
Enquanto as notícias com IA passam por revisão, o workflow **Email de revisão** envia às 8h30 (Lisboa) um email com a ligação para cada notícia à espera (separador *Files changed* para ler; página do pedido para *Merge* ou *Close*). Sem notícias por rever, não envia nada. A data final está em `policy.review_email_until` (`config/editorial.yaml`); também deixa de enviar se `auto_publish_news` passar a `true`.
Segredos: `SMTP_USER` (naiabengue@gmail.com), `SMTP_PASSWORD` (palavra-passe de app do Google: myaccount.google.com/apppasswords, exige verificação em dois passos) e `REVIEW_EMAIL_TO` (destino; fica em segredo porque o repositório é público). Para testar: *Actions → Email de revisão → Run workflow* (envia logo, sem esperar pelas 8h30).

### 1.6 Primeiro arranque
1. *Actions → Auditoria das fontes → Run workflow*. Ver `docs/ESTADO-FONTES.md`: fontes com "sem itens" precisam de ajuste do `link_pattern` (secção 3.1).
2. *Actions → Diário → Run workflow*, com `brent_fx,gas_storage` no campo de peças, para ver o primeiro artigo publicado.
3. Abrir https://naiabengue.com/fluxoenergetico/news/ (ou o endereço indicado no passo *deploy* do workflow).

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
Modelos em `fluxo/site/templates/`, estilos em `fluxo/site/static/style.css`. Antes de enviar: `python -m pytest -q` e `python -m fluxo build --out _site --subdir news`, depois `python -m http.server -d _site` e abrir http://localhost:8000/news/ (as ligações internas usam o prefixo `/fluxoenergetico/news`, por isso a navegação completa só funciona publicada).

### 3.9 Recuperar o serviço
- **O diário deixou de correr:** o GitHub desativa agendamentos ao fim de 60 dias sem atividade no repositório. Em *Actions*, abrir o workflow e carregar em **Enable workflow**.
- **IA sem resposta (quota):** o sistema tenta o fornecedor seguinte e, sem nenhum, continua sem notícias. Ver o aviso no registo; volta a tentar no dia seguinte.
- **Site em baixo:** *Actions → Publicar site → Run workflow*. Se o GitHub Pages ficar indisponível ou o site passar a ter receitas, publicar no Cloudflare Pages (plano gratuito): ligar o repositório, comando de build `pip install -r requirements.txt && python -m fluxo build --out _site --subdir news`, pasta `_site`, e ajustar `base_url` ao novo endereço.
- **Fonte mudou de estrutura:** ver 3.1.

### 3.10 Cópias de segurança e exportação
Todo o projeto (código, fontes, dados, artigos, registos) está no repositório. Cópia completa: *Code → Download ZIP* ou `git clone`. Os artigos são Markdown com metadados e importam-se em qualquer outro sistema; os dados recolhidos são JSON Lines.

## 4. Limites gratuitos a vigiar
| Serviço | Limite | O que acontece se for excedido |
| --- | --- | --- |
| GitHub Actions (repositório público) | sem limite de minutos | — |
| GitHub Pages | site até 1 GB; ~100 GB/mês de tráfego (limite flexível); 10 builds/hora | aviso do GitHub; migrar para Cloudflare Pages |
| Gemini (quota gratuita) | limites por projeto não publicados nem garantidos (ver aistudio.google.com); modelos tentados por ordem: gemini-3.5-flash-lite → gemini-3.1-flash-lite → gemini-2.5-flash-lite (os 2.5 só para projetos que já os usavam) | modelo indisponível (404) → modelo seguinte; outra falha → fornecedor seguinte → sem notícia nesse dia; o motivo aparece no registo como «IA: …» |
| API do Instagram | 100 publicações por API em 24 h | irrelevante (2 por semana) |
| Token do Instagram | login unificado: não expira; login do Instagram: 60 dias | publicação falha até gerar novo token (1.5) |
| Cloudflare Workers AI (plano gratuito) | 10 000 «neurons» por dia; cada capa FLUX.1 [schnell] gasta cerca de 58 | o pedido falha (sem cobrança no plano gratuito) e a capa fica tipográfica |
