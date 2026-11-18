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
  console.log('Lançado ' + workflow + ' ' + JSON.stringify(inputs || {}));
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
