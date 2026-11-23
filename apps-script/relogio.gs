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
 *   4. Aprovação pelo email: Implantar → Nova implantação → App da Web, Executar como: eu;
 *      Quem pode acessar: Qualquer pessoa. O URL /exec vai para policy.approve_api em config/editorial.yaml.
 *      Depois de mudar o código: Implantar → Gerenciar implantações → editar → Versão: nova versão (o URL mantém-se).
 */
const REPO = 'naiabengue/fluxoenergetico';

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
  // A aprovação pelo email lê o pedido para confirmar o código; sem isto, só o workflow confirma.
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

// ── Aprovação pelo email ──────────────────────────────────────────────────────────────────────────────────
// A página fica no site (/aprovar/, fluxo/site/static/aprovar.js); aqui só se recebe a decisão e se responde em JSON.
// Os pedidos chegam sem cookies, por isso não caem no erro do Google com várias contas abertas no browser.
// O código da ligação é confirmado contra o hash guardado no pedido; o workflow «Aprovar notícia» volta a confirmar.

/** GET ?op=estado&pr=…&acao=…&desde=… — como correu a execução do workflow. Sem op: só diz que está ativo. */
function doGet(e) {
  const p = (e && e.parameter) || {};
  if (p.op === 'estado') return json_(estado(String(p.pr || ''), String(p.acao || ''), String(p.desde || '')));
  return json_({ ok: true, servico: 'Fluxo Energético — aprovação pelo email' });
}

/** POST {op: 'decidir', pr, t, acao} (corpo em texto simples). */
function doPost(e) {
  try {
    const d = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    if (d.op !== 'decidir') return json_({ ok: false, msg: 'Pedido desconhecido.' });
    return json_(decidir(String(d.pr || ''), String(d.t || ''), String(d.acao || '')));
  } catch (err) {
    return json_({ ok: false, msg: 'Erro: ' + err.message });
  }
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function decidir(pr, t, acao) {
  if (acao !== 'aprovar' && acao !== 'rejeitar') return { ok: false, msg: 'Ação desconhecida.' };
  const v = verificar_(pr, t);
  if (v.erro) return { ok: false, msg: v.erro };
  const desde = new Date(Date.now() - 5000).toISOString();
  dispatch_('aprovar.yml', { pr: pr, token: t, acao: acao });
  return { ok: true, desde: desde,
           msg: acao === 'aprovar' ? 'Aprovada. A publicar no site (1 a 3 minutos)…' : 'A rejeitar…' };
}

function estado(pr, acao, desde) {
  if (!/^\d{1,6}$/.test(pr) || !/^\d{4}-\d\d-\d\dT/.test(desde)) return { fim: true, ok: false, msg: 'Pedido inválido.' };
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
