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
| `CF_ACCOUNT_ID`, `CF_API_TOKEN` | Imagens do carrossel geradas por IA consoante o tema | conta gratuita em dash.cloudflare.com (naiabengue@gmail.com) → *AI → Workers AI → Use REST API*: copiar o *Account ID* e criar o token com o modelo *Workers AI* (permissões *Workers AI – Read* e *Edit*). Não ativar o plano Workers Paid | Opcional |
| `IG_ACCESS_TOKEN`, `IG_USER_ID` | Publicar no Instagram pela API | ver 1.5 | Recomendado |
| `GH_PAT` | Renovar o token do Instagram todos os meses (só no «login do Instagram»; o login unificado não precisa) | token *fine-grained* só deste repositório, permissão *Secrets: read and write* | Não necessário |

Sem nenhuma chave de IA, o sistema publica as peças de dados e não publica notícias. Sem `CF_*`, os diapositivos do carrossel são tipográficos.

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

**Estilo (misto):** capa com o título como gancho e indicação para deslizar; miolo sóbrio com um ponto-chave por imagem; último diapositivo com «Guarda e partilha» e a ligação. A legenda tem no máximo 3 emojis (gancho, apelo a guardar e comentar, ligação), fontes, nota de IA e até 8 hashtags. Textos e emojis em `instagram` no `config/editorial.yaml`. **Imagens consoante o tema (`instagram.ai_images`):** com `CF_*` configurado, a capa e cada ponto-chave levam uma imagem gerada por IA (Cloudflare Workers AI; `model: flux-1-schnell` ou `flux-2-klein-4b`). A IA de texto (`llm`) lê o artigo e descreve uma cena concreta por diapositivo, em inglês, sem pessoas, texto, números, logótipos, bandeiras, mapas nem nomes reais; sem IA de texto, usa cenas fixas por categoria e palavras-chave. Depois vê cada imagem e recusa as que tenham letras, pessoas, bandeiras, logótipos ou mapas (nova tentativa com outra semente; `max_attempts`). Sem imagem válida, o diapositivo fica tipográfico: nunca bloqueia a publicação. O texto é sempre escrito pelo código (acentos e números exatos). Nas peças de dados entra também um diapositivo com o gráfico real («Em gráfico»). Cada imagem é identificada no próprio diapositivo («Imagem gerada por IA»), na legenda («Imagens geradas por IA.») e nos metadados IPTC do JPEG (*compositeWithTrainedAlgorithmicMedia*, que a Meta lê). `slides: cover` volta a pôr imagem só na capa; `enabled: false` desliga tudo.

**Imagem de topo nas notícias do site (`article_images`, desde 27/11/2026):** quando o diário redige uma notícia, gera também uma imagem do tema (mesmo modelo, cenas e verificação do carrossel; até `max_attempts` + 1 tentativas). Fica em `content/media/AAAAMMDD-<slug>.jpg`, com metadados IPTC *trainedAlgorithmicMedia*, aparece no topo do artigo com a legenda «Imagem gerada por inteligência artificial (ilustração, não é uma fotografia)» e serve de `og:image`. Nas notícias por rever vai no pedido de revisão e aparece no email das 8h30; o botão «Modificar» não lhe mexe. O carrossel usa-a como capa (não gera outra). Peças de dados ficam sem imagem (já têm o gráfico real). Sem `CF_*`, ou se falhar, a notícia sai sem imagem: nunca a bloqueia.

**Testar sem publicar:** workflow manual **Instagram — teste de imagens** (escolher artigo e modelo; «ambos» compara FLUX.1 [schnell] e FLUX.2 [klein] 4B). As imagens ficam no artefacto `carrossel-teste` e no ramo `teste/carrossel-ia` (`folha.jpg` mostra o carrossel inteiro; `imagens.json` tem as cenas e o registo). Corre também a cada envio para um ramo `instagram/…`. Em linha de comandos: `python -m fluxo instagram-preview --slug <slug> --model flux-2-klein-4b --out out/teste`.

**Modo manual (se a API não estiver configurada):** todos os dias (`instagram.weekdays`) o sistema prepara o carrossel (imagens 1080×1350 e `legenda.txt` em `content/instagram/`) e abre um aviso no GitHub. Para publicar: descarregar as imagens, abrir o Meta Business Suite (ou a app Instagram) → *Criar publicação* → carregar as imagens pela ordem → colar a legenda → **Agendar**.

### 1.5.1 Email diário de revisão (até 15/12/2026)
Enquanto as notícias com IA passam por revisão, o workflow **Email de revisão**, lançado às 8h30 pelo relógio externo (1.5.2), envia um email com a ligação para cada notícia à espera. Cada notícia vem com o texto e os botões **Aprovar e publicar**, **Modificar** e **Rejeitar** (1.5.3), que funcionam sem entrar no GitHub; o email traz também a ligação do pedido no GitHub (*Merge* ou *Close* continuam a funcionar). O email vai para o segredo `REVIEW_EMAIL_TO` e, em cópia, para `policy.review_email_cc` (pedrocamiloramos@gmail.com): entre 20 e 23/11/2026 o email do trabalho descartou os avisos sem devolver erro. Num dia útil sem nenhuma notícia (nem por rever, nem já tratada), envia antes um aviso «ainda sem notícia hoje» com o que a última execução encontrou e a ligação para as execuções do diário que falharam. Ao fim de semana, sem notícias por rever, não envia nada. Se um pedido de revisão abrir depois de o email do dia ter corrido (por exemplo, na tentativa das 11:15), o diário lança o email outra vez. A data final está em `policy.review_email_until` (`config/editorial.yaml`); também deixa de enviar se `auto_publish_news` passar a `true`.
Segredos: `SMTP_USER` (naiabengue@gmail.com), `SMTP_PASSWORD` (palavra-passe de app do Google: myaccount.google.com/apppasswords, exige verificação em dois passos) e `REVIEW_EMAIL_TO` (destino; fica em segredo porque o repositório é público). Para testar: *Actions → Email de revisão → Run workflow* com a caixa *teste* marcada.

### 1.5.2 Relógio externo (Google Apps Script)
Os agendamentos do GitHub Actions chegaram com horas de atraso (17–18/11/2026). Os workflows com hora marcada são lançados pelo projeto Apps Script **Fluxo Energético — relógio** na conta naiabengue@gmail.com (script.google.com), com o código de `apps-script/relogio.gs`. Precisão: ±15 minutos.
- 06:15 diário; 07:15, 07:55 e 11:15 tentativas extra (seg–sex; feriados tratados no código); 08:30 email de revisão; 09:40 Instagram (todos os dias; o código decide pelos dias de `instagram.weekdays` e salta o dia se não houver artigo novo).
- Propriedade do script `GITHUB_TOKEN`: token *fine-grained* do GitHub (conta naiabengue, só `fluxoenergetico`, *Actions: Read and write*). Expira ao fim de 1 ano: criar outro e substituir a propriedade.
- O GitHub mantém só a reserva das 06:23 do diário (o limite diário impede duplicados). Auditoria (domingo) continua no GitHub.
- Se algo falhar, a Google envia email à conta naiabengue com o erro; o registo fica em *Execuções* no editor do Apps Script.

### 1.5.3 Aprovar, modificar ou rejeitar pelo email
- **Email:** em HTML (com versão só de texto). Cada notícia aparece com título, entrada, pontos-chave, texto e fonte, e três botões: **Aprovar e publicar**, **Modificar** e **Rejeitar**. O texto vem do ramo do pedido de revisão (`fluxo/review.py`, `fetch_articles`); se não for possível lê-lo, o email mostra só o título e os botões.
- **Página:** `https://naiabengue.com/fluxoenergetico/news/aprovar/?pr=N&t=CÓDIGO` (`policy.approve_url`; `fluxo/site/templates/aprovar.html`, `fluxo/site/static/aprovar.js`). Os botões do email acrescentam `&acao=aprovar`, `&modo=editar` ou `&acao=rejeitar`. Aprovar e Rejeitar pedem um clique de confirmação na página (abrir a página não altera nada: os antivírus do email abrem as ligações sozinhos). Modificar abre um formulário com título, entrada, pontos-chave (um por linha) e texto (Markdown); **Guardar e publicar** grava as alterações no ramo do pedido e aprova. O cabeçalho do artigo é lido por `fluxo/site/static/frontmatter.js` (testado contra o PyYAML em `tests/test_frontmatter_js.py`); se não o conseguir ler, a página manda editar no GitHub. Tem `noindex` e não entra no sitemap.
- **Código:** cada email gera, por pedido de revisão, um código aleatório que só existe nas ligações do email; no pedido fica apenas o SHA-256 desse código (comentário invisível na descrição). Os códigos dos últimos 20 emails continuam válidos.
- **Caminho da decisão:** a página envia-a, sem cookies, para a aplicação Web do Apps Script (`policy.approve_api`, mesmo projeto do relógio, executa como naiabengue, acesso: qualquer pessoa). O Apps Script confirma o código e lança o workflow *Aprovar notícia* (`aprovar.yml`, ação `aprovar`, `modificar` ou `rejeitar`; as alterações seguem em `edicao`, JSON em base64). O workflow volta a confirmar o código; em `modificar` grava cada artigo alterado no ramo (só título, entrada, pontos-chave e texto; slug, data, fontes e nota de IA ficam iguais; limites: título 10–200, entrada 20–800, texto 200–30 000 caracteres, até 8 pontos-chave). Depois faz *squash merge* (ou comenta e fecha), apaga o ramo e publica o site. A página acompanha a execução até «Publicada».
- **Porque a página não está no Apps Script:** as páginas do Apps Script dão erro 404 («não é possível abrir o ficheiro») quando o browser tem várias contas Google abertas.
- O merge feito pelo workflow não lança *Publicar site* sozinho (regra do GitHub para o token dos workflows); por isso *Aprovar notícia* chama-o no fim.
- Depois de alterar `relogio.gs`: *Implantar → Nova implantação* (App da Web, executar como eu, qualquer pessoa) e pôr o novo URL `/exec` em `policy.approve_api`; ou *Gerenciar implantações → editar → Versão: nova versão*, que mantém o URL.

### 1.6 Primeiro arranque
1. *Actions → Auditoria das fontes → Run workflow*. Ver `docs/ESTADO-FONTES.md`: fontes com "sem itens" precisam de ajuste do `link_pattern` (secção 3.1).
2. *Actions → Diário → Run workflow*, com `brent_fx,gas_storage` no campo de peças, para ver o primeiro artigo publicado.
3. Abrir https://naiabengue.com/fluxoenergetico/news/ (ou o endereço indicado no passo *deploy* do workflow).

## 2. Operação normal
- **Todos os dias às 06:23 UTC:** recolha, peças de dados do dia (segunda: Brent e câmbio; quinta: armazenamento de gás), até 1 notícia. O site é atualizado sozinho.
- **Dias úteis em Lisboa (seg–sex, exceto feriados nacionais e 13 de junho):** tem de haver uma notícia. Se nada chegar ao limiar normal (65), o sistema aceita candidatos até `policy.business_day_min_score` (50), sempre com revisão humana, e pode usar até `llm.business_day_max_calls` (10) pedidos de IA. Se de manhã não sair nenhuma, repete às 07:23, 08:03 e 11:23 UTC (só notícias; não repete se já houver). Um dia útil sem notícia fica registado como «Dia útil sem notícia» no registo e em `docs/ESTADO.md`.
- **Notícias redigidas com IA (fase 1):** chegam como pull request "Revisão AAAA-MM-DD" (e, até 15/12/2026, no email das 8h30), com um email do GitHub. Forma rápida: botões do email **Aprovar e publicar**, **Modificar** ou **Rejeitar** (1.5.3). No GitHub: *Pull requests* → *Files changed* para ler; para corrigir, editar o ficheiro no próprio pull request e só depois aprovar; **Merge** publica, **Close** rejeita. Rever de verdade: o rótulo passa a dizer "revisto pela redação".
- **Domingo:** auditoria das fontes; se alguma fonte ativa falhar, abre um aviso (*Issues*).
- **Todos os dias:** carrossel do Instagram com o melhor artigo ainda não publicado lá (desde 27/11/2026; antes, terça e sexta). Para voltar aos dias úteis: `instagram.weekdays: [0, 1, 2, 3, 4]` (também salta feriados). Para forçar num dia fora da lista: workflow **Instagram** com a caixa «forcar».

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
- **O pedido de revisão não abriu:** o GitHub recusa de vez em quando um envio sem dar motivo (aconteceu a 19/11/2026). Cada envio tenta 3 vezes. Se mesmo assim falhar, o diário guarda os rascunhos como artefacto da execução (14 dias: *Actions* → execução → *Artifacts*) e liberta a notícia do dia (`python -m fluxo release-review`), para que a tentativa extra seguinte a volte a escrever. Não é preciso fazer nada; o email das 8h30 indica a execução que falhou. Se já não houver tentativa extra nesse dia: *Actions → Diário → Run workflow* com a caixa *catch_up* marcada.

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
| Cloudflare Workers AI (plano gratuito) | 10 000 «neurons» por dia (00:00 UTC); FLUX.1 [schnell] com 8 passos ≈ 96 por imagem, FLUX.2 [klein] 4B 1024×1024 ≈ 104; teto de 14 imagens por carrossel (≈ 1 400) | o pedido falha (sem cobrança no plano gratuito) e o diapositivo fica tipográfico; um erro 4xx para os pedidos seguintes desse carrossel |
