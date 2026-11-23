/**
 * Relógio do Fluxo Energético — Google Apps Script na conta naiabengue@gmail.com.
 * Os agendamentos do GitHub Actions chegaram com horas de atraso; este script lança os workflows à hora certa
 * (as ordens manuais/API arrancam logo). Precisão dos acionadores do Apps Script: ±15 minutos.
 *
 * Configuração (uma vez):
 *   1. Definições do projeto → Fuso horário: (GMT+00:00) Lisboa.
 *   2. Definições do projeto → Propriedades do script → GITHUB_TOKEN = token «fine-grained» só do repositório
 *      naiabengue/fluxoenergetico, permissão Actions: Read and write.
 *   3. Executar «testar» (confirma o token sem lançar nada) e depois «instalar» (cria os acionadores).
 *   4. Página de aprovação (botão do email): Implementar → Nova implementação → Aplicação Web,
 *      Executar como: eu; Quem tem acesso: Qualquer pessoa. O URL /exec vai para policy.approve_url
 *      em config/editorial.yaml. Depois de mudar o código: Implementar → Gerir implementações → editar →
 *      Versão: nova versão (o URL mantém-se).
 */
const REPO = 'naiabengue/fluxoenergetico';
const SITE = 'https://naiabengue.com/fluxoenergetico/news/';

// As duas primeiras funções são as que o editor escolhe por defeito: ambas são inofensivas
// (instalar só recria os acionadores; testar só lê). As que lançam workflows vêm depois.

/** Cria (ou recria) os acionadores diários. */
function instalar() {
  ScriptApp.getProjectTriggers().forEach(function (t) { ScriptApp.deleteTrigger(t); });
  const at = function (fn, h, m) {
    ScriptApp.newTrigger(fn).timeBased().atHour(h).nearMinute(m).everyDays(1).create();
  };
  at('diario', 6, 15);
  at('diarioExtra', 7, 15);
  at('diarioExtra', 7, 55);
  at('emailRevisao', 8, 30);
  at('instagram', 9, 40);
  at('diarioExtra', 11, 15);
  console.log('Acionadores: ' + ScriptApp.getProjectTriggers().length);
}

/** Confirma que o token funciona, sem lançar nenhum workflow. */
function testar() {
  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  const r = UrlFetchApp.fetch('https://api.github.com/repos/' + REPO + '/actions/workflows', {
    muteHttpExceptions: true,
    headers: { Authorization: 'Bearer ' + token, Accept: 'application/vnd.github+json' }
  });
  console.log('GitHub: HTTP ' + r.getResponseCode());
  if (r.getResponseCode() !== 200) throw new Error(r.getContentText().slice(0, 300));
  console.log('Token OK: ' + JSON.parse(r.getContentText()).total_count + ' workflows visíveis. Fuso: ' +
              Session.getScriptTimeZone());
  // A página de aprovação lê o pedido para mostrar o texto e confirmar o código; sem isto, só o workflow confirma.
  console.log('Leitura dos pedidos de revisão: HTTP ' + gh_('/pulls?state=open&per_page=1').getResponseCode());
}

function gh_(path, opts) {
  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  return UrlFetchApp.fetch('https://api.github.com/repos/' + REPO + path, Object.assign({
    muteHttpExceptions: true,
    headers: { Authorization: 'Bearer ' + token, Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28' }
  }, opts || {}));
}

function dispatch_(workflow, inputs) {
  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('Falta a propriedade GITHUB_TOKEN');
  const r = UrlFetchApp.fetch('https://api.github.com/repos/' + REPO + '/actions/workflows/' + workflow + '/dispatches', {
    method: 'post',
    contentType: 'application/json',
    muteHttpExceptions: true,
    headers: {
      Authorization: 'Bearer ' + token,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28'
    },
    payload: JSON.stringify({ ref: 'main', inputs: inputs || {} })
  });
  if (r.getResponseCode() !== 204) {
    throw new Error(workflow + ': HTTP ' + r.getResponseCode() + ' ' + r.getContentText().slice(0, 300));
  }
  console.log('Lançado ' + workflow + ' ' + JSON.stringify(inputs || {}, function (k, v) { return k === 'token' ? '…' : v; }));
}

function weekday_() {
  return new Date().getDay();   // 0 = domingo … 6 = sábado, no fuso horário do projeto (Lisboa)
}

/** Diário completo: recolha, peças de dados e notícia. */
function diario() {
  dispatch_('diario.yml', {});
}

/** Tentativa extra nos dias de semana (os feriados de Lisboa são tratados no código do GitHub). */
function diarioExtra() {
  const d = weekday_();
  if (d >= 1 && d <= 5) dispatch_('diario.yml', { catch_up: 'true' });
}

/** Email com as notícias por rever (o código só envia até policy.review_email_until e se houver notícias). */
function emailRevisao() {
  dispatch_('email-revisao.yml', { teste: 'false' });
}

/** Carrossel do Instagram à terça e à sexta. */
function instagram() {
  const d = weekday_();
  if (d === 2 || d === 5) dispatch_('instagram.yml', {});
}

// ── Página de aprovação (botão «Ler e aprovar» do email de revisão) ─────────────────────────────────────────
// Abrir a página não altera nada (os antivírus do email abrem as ligações sozinhos); só os botões decidem.
// O código da ligação é confirmado contra o hash guardado no pedido; o workflow «Aprovar notícia» volta a confirmar.

function doGet(e) {
  const p = (e && e.parameter) || {};
  const pr = String(p.pr || ''), t = String(p.t || '');
  const v = verificar_(pr, t);
  const tpl = HtmlService.createTemplate(PAGINA_);
  tpl.pr = pr;
  tpl.t = t;
  tpl.erro = v.erro || '';
  tpl.gh = 'https://github.com/' + REPO + '/pull/' + pr;
  tpl.site = SITE;
  tpl.artigos = v.erro ? [] : artigos_(pr);
  return tpl.evaluate().setTitle('Fluxo Energético — rever notícia')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

/** Chamado pelos botões da página. */
function decidir(pr, t, acao) {
  if (acao !== 'aprovar' && acao !== 'rejeitar') return { ok: false, msg: 'Ação desconhecida.' };
  const v = verificar_(String(pr), String(t));
  if (v.erro) return { ok: false, msg: v.erro };
  const desde = new Date(Date.now() - 5000).toISOString();
  dispatch_('aprovar.yml', { pr: String(pr), token: String(t), acao: acao });
  return { ok: true, desde: desde,
           msg: acao === 'aprovar' ? 'Aprovada. A publicar no site (1 a 3 minutos)…' : 'A rejeitar…' };
}

/** A página pergunta de 5 em 5 segundos como correu a execução do workflow «Aprovar notícia». */
function estado(pr, acao, desde) {
  const r = gh_('/actions/workflows/aprovar.yml/runs?event=workflow_dispatch&per_page=20');
  if (r.getResponseCode() !== 200) return { fim: false };
  const nome = acao + ' #' + pr;
  const run = JSON.parse(r.getContentText()).workflow_runs
    .filter(function (w) { return w.display_title === nome && w.created_at >= desde.slice(0, 19); })
    .sort(function (a, b) { return a.created_at < b.created_at ? -1 : 1; })[0];
  if (!run || run.status !== 'completed') return { fim: false };
  if (run.conclusion === 'success') {
    return { fim: true, ok: true, msg: acao === 'aprovar'
      ? 'Publicada. Já está no site.' : 'Rejeitada: o pedido foi fechado e nada foi publicado.' };
  }
  return { fim: true, ok: false, msg: 'Não foi possível (' + run.conclusion + '). Detalhe: ' + run.html_url };
}

function sha256hex_(s) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, s, Utilities.Charset.UTF_8)
    .map(function (b) { return ('0' + (b & 0xff).toString(16)).slice(-2); }).join('');
}

function verificar_(pr, t) {
  if (!/^\d{1,6}$/.test(pr) || !/^[A-Za-z0-9_-]{20,64}$/.test(t)) {
    return { erro: 'Ligação inválida ou incompleta. Abre a ligação a partir do email.' };
  }
  const r = gh_('/pulls/' + pr);
  if (r.getResponseCode() === 404) return { erro: 'Este pedido não existe.' };
  if (r.getResponseCode() !== 200) return {};     // sem leitura dos pedidos: o workflow confirma o código
  const p = JSON.parse(r.getContentText());
  if (String(p.head.ref).indexOf('revisao/') !== 0) return { erro: 'Este pedido não é uma notícia para rever.' };
  if (p.merged_at) return { erro: 'Esta notícia já foi aprovada e publicada.' };
  if (p.state !== 'open') return { erro: 'Esta notícia já foi rejeitada (pedido fechado).' };
  const m = /<!--\s*aprovar:([0-9a-f\s]*)-->\s*$/.exec(p.body || '');
  if (!m || m[1].trim().split(/\s+/).indexOf(sha256hex_(t)) < 0) {
    return { erro: 'Esta ligação não corresponde a esta notícia. Usa a ligação do email.' };
  }
  return {};
}

function artigos_(pr) {
  const r = gh_('/pulls/' + pr + '/files?per_page=30');
  if (r.getResponseCode() !== 200) return [];
  return JSON.parse(r.getContentText())
    .filter(function (f) { return /^content\/articles\/.+\.md$/.test(f.filename) && f.status !== 'removed'; })
    .map(function (f) {
      const texto = UrlFetchApp.fetch(f.raw_url, { muteHttpExceptions: true }).getContentText('UTF-8');
      const m = /^title:\s*(.+(?:\n {2}.+)*)/m.exec(texto);
      return { titulo: m ? m[1].replace(/\s+/g, ' ').replace(/^'|'$/g, '') : f.filename, texto: texto };
    });
}

const PAGINA_ = `<!DOCTYPE html>
<html><head><base target="_top">
<style>
  body { font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; max-width: 760px; margin: 0 auto;
         padding: 16px 16px 0; color: #1b1f24; line-height: 1.5; }
  h1 { font-size: 1.15rem; margin: 0 0 4px; } h2 { font-size: 1.1rem; margin: 24px 0 8px; }
  .sub { color: #57606a; margin: 0 0 12px; } a { color: #0969da; }
  pre { white-space: pre-wrap; word-wrap: break-word; background: #f6f8fa; border: 1px solid #d0d7de;
        border-radius: 8px; padding: 12px; font: 0.88rem/1.5 ui-monospace, SFMono-Regular, Menlo, monospace; }
  .check { background: #fff8c5; border: 1px solid #d4a72c66; border-radius: 8px; padding: 10px 12px; }
  .acoes { position: sticky; bottom: 0; background: #fff; padding: 12px 0 16px; border-top: 1px solid #d0d7de;
           display: flex; gap: 12px; flex-wrap: wrap; }
  button { font: inherit; font-weight: 600; padding: 12px 20px; border-radius: 8px; border: 1px solid transparent; cursor: pointer; }
  button:disabled { opacity: .5; cursor: default; }
  .ok { background: #1f883d; color: #fff; } .nao { background: #fff; color: #cf222e; border-color: #d0d7de; }
  #msg { font-weight: 600; margin: 8px 0 0; flex-basis: 100%; } .erro { color: #cf222e; }
</style></head><body>
<h1>Fluxo Energético · notícia para rever</h1>
<? if (erro) { ?>
  <p class="erro"><b><?= erro ?></b></p>
  <p class="sub"><a href="<?= site ?>">Abrir o site</a> · <a href="<?= gh ?>">Ver o pedido no GitHub</a></p>
<? } else { ?>
  <p class="sub">Pedido #<?= pr ?> · <a href="<?= gh ?>/files">ver no GitHub</a></p>
  <? for (var i = 0; i < artigos.length; i++) { ?>
    <h2><?= artigos[i].titulo ?></h2><pre><?= artigos[i].texto ?></pre>
  <? } ?>
  <? if (!artigos.length) { ?><p>O texto não abriu aqui: <a href="<?= gh ?>/files">ler no GitHub</a>.</p><? } ?>
  <p class="check">Antes de aprovar: os números e as datas batem certo com a fonte indicada no fim? Nenhuma conclusão
    vai além do que a fonte diz? O título não exagera?</p>
  <div class="acoes">
    <button class="ok" id="aprovar">Aprovar e publicar</button>
    <button class="nao" id="rejeitar">Rejeitar</button>
    <p id="msg"></p>
  </div>
  <div id="dados" data-pr="<?= pr ?>" data-t="<?= t ?>"></div>
  <script>
    var d = document.getElementById('dados').dataset, msg = document.getElementById('msg');
    var bA = document.getElementById('aprovar'), bR = document.getElementById('rejeitar'), confirmar = false;
    function dizer(texto, erro) { msg.textContent = texto; msg.className = erro ? 'erro' : ''; }
    function bloquear(sim) { bA.disabled = bR.disabled = sim; }
    function acompanhar(acao, desde, n) {
      google.script.run.withSuccessHandler(function (r) {
        if (r.fim) { dizer(r.msg, !r.ok); if (!r.ok) bloquear(false); }
        else if (n < 60) setTimeout(function () { acompanhar(acao, desde, n + 1); }, 5000);
        else dizer('Ainda a correr. Confirma daqui a pouco no site.');
      }).withFailureHandler(function () {
        if (n < 60) setTimeout(function () { acompanhar(acao, desde, n + 1); }, 5000);
      }).estado(d.pr, acao, desde);
    }
    function decidir(acao) {
      bloquear(true); dizer(acao === 'aprovar' ? 'A aprovar…' : 'A rejeitar…');
      google.script.run.withSuccessHandler(function (r) {
        dizer(r.msg, !r.ok);
        if (r.ok) acompanhar(acao, r.desde, 0); else bloquear(false);
      }).withFailureHandler(function (e) { dizer('Erro: ' + e.message, true); bloquear(false); })
        .decidir(d.pr, d.t, acao);
    }
    bA.onclick = function () { decidir('aprovar'); };
    bR.onclick = function () {
      if (!confirmar) { confirmar = true; bR.textContent = 'Confirmar: rejeitar'; return; }
      decidir('rejeitar');
    };
  </script>
<? } ?>
</body></html>`;
