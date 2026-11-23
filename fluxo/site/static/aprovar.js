/* Página de aprovação do email de revisão (/aprovar/?pr=N&t=CÓDIGO).
 * Lê o pedido de revisão na API pública do GitHub, mostra o texto e confirma o código (o pedido guarda só o
 * SHA-256). Os botões chamam o Google Apps Script (sem cookies, para não cair no erro das várias contas Google),
 * que lança o workflow «Aprovar notícia»; a página acompanha a execução até ao fim.
 * Abrir a página não altera nada: os antivírus do email abrem as ligações sozinhos. */
(function () {
  'use strict';
  var box = document.getElementById('aprovacao');
  if (!box) return;
  var API = box.dataset.api, REPO = box.dataset.repo, SITE = box.dataset.site;
  var q = new URLSearchParams(location.search);
  var pr = q.get('pr') || '', t = q.get('t') || '';
  var $ = function (id) { return document.getElementById(id); };
  var estado = $('ap-estado'), artigos = $('ap-artigos'), decisao = $('ap-decisao'), msg = $('ap-msg');
  var bA = $('ap-aprovar'), bR = $('ap-rejeitar');
  var GH = 'https://github.com/' + REPO + '/pull/' + pr;

  function linha(texto, ligacao, rotulo) {
    estado.textContent = texto + (ligacao ? ' ' : '');
    if (ligacao) {
      var a = document.createElement('a');
      a.href = ligacao; a.textContent = rotulo; estado.appendChild(a);
    }
  }
  function dizer(texto, erro) { msg.textContent = texto; msg.className = 'ap-msg' + (erro ? ' ap-erro' : ''); }
  function bloquear(sim) { bA.disabled = bR.disabled = sim; }
  function sha256hex(s) {
    return crypto.subtle.digest('SHA-256', new TextEncoder().encode(s)).then(function (b) {
      return Array.prototype.map.call(new Uint8Array(b), function (x) { return ('0' + x.toString(16)).slice(-2); }).join('');
    });
  }
  function gh(path) {
    return fetch('https://api.github.com/repos/' + REPO + path, { headers: { Accept: 'application/vnd.github+json' } })
      .then(function (r) { if (!r.ok) throw new Error('GitHub ' + r.status); return r.json(); });
  }
  function api(dados) {      // text/plain: pedido simples, sem pré-verificação CORS; sem cookies
    return fetch(API, { method: 'POST', credentials: 'omit', body: JSON.stringify(dados),
                        headers: { 'Content-Type': 'text/plain;charset=utf-8' } })
      .then(function (r) { return r.json(); });
  }

  if (!/^\d{1,6}$/.test(pr) || !/^[A-Za-z0-9_-]{20,64}$/.test(t)) {
    linha('Ligação inválida ou incompleta. Abre a ligação a partir do email de revisão.');
    return;
  }
  if (!API) { linha('A aprovação pelo email ainda não está ativa. Aprova no GitHub:', GH, 'pedido #' + pr); return; }

  function mostrar(p) {
    return gh('/pulls/' + pr + '/files?per_page=30').then(function (files) {
      var md = files.filter(function (f) { return /^content\/articles\/.+\.md$/.test(f.filename) && f.status !== 'removed'; });
      return Promise.all(md.map(function (f) {
        return fetch('https://raw.githubusercontent.com/' + REPO + '/' + p.head.sha + '/' + f.filename)
          .then(function (r) { return r.text(); });
      }));
    }).then(function (textos) {
      textos.forEach(function (texto) {
        var m = /^title:\s*(.+(?:\n {2}.+)*)/m.exec(texto);
        var h = document.createElement('h2');
        h.className = 'ap-titulo';
        h.textContent = m ? m[1].replace(/\s+/g, ' ').replace(/^'|'$/g, '') : 'Artigo';
        var pre = document.createElement('pre');
        pre.className = 'ap-texto';
        pre.textContent = texto;
        artigos.appendChild(h); artigos.appendChild(pre);
      });
      if (!textos.length) linha('Pedido #' + pr + ' (sem artigos para mostrar) ·', GH + '/files', 'ver no GitHub');
    });
  }

  gh('/pulls/' + pr).then(function (p) {
    if (String(p.head.ref).indexOf('revisao/') !== 0) { linha('Este pedido não é uma notícia para rever.'); return; }
    if (p.merged_at) { linha('Esta notícia já foi aprovada e publicada.', SITE, 'Abrir o site'); return; }
    if (p.state !== 'open') { linha('Esta notícia já foi rejeitada (pedido fechado).'); return; }
    var m = /<!--\s*aprovar:([0-9a-f\s]*)-->\s*$/.exec(p.body || '');
    return sha256hex(t).then(function (h) {
      if (!m || m[1].trim().split(/\s+/).indexOf(h) < 0) {
        linha('Esta ligação não corresponde a esta notícia. Usa a ligação do email.');
        return;
      }
      linha('Pedido #' + pr + ' ·', GH + '/files', 'ver no GitHub');
      decisao.hidden = false;
      return mostrar(p);
    });
  }).catch(function () {
    // Sem a API do GitHub (limite de pedidos, rede): os botões funcionam na mesma; o servidor confirma o código.
    linha('Não foi possível mostrar o texto aqui.', GH + '/files', 'Ler no GitHub');
    decisao.hidden = false;
  });

  function acompanhar(acao, desde, n) {
    fetch(API + '?op=estado&pr=' + pr + '&acao=' + acao + '&desde=' + encodeURIComponent(desde), { credentials: 'omit' })
      .then(function (r) { return r.json(); })
      .then(function (r) {
        if (r.fim) {
          dizer(r.msg, !r.ok);
          if (r.ok && acao === 'aprovar') { var a = document.createElement('a'); a.href = SITE; a.textContent = ' Abrir o site'; msg.appendChild(a); }
          if (!r.ok) bloquear(false);
        } else if (n < 60) setTimeout(function () { acompanhar(acao, desde, n + 1); }, 5000);
        else dizer('Ainda a correr. Confirma daqui a pouco no site.');
      })
      .catch(function () { if (n < 60) setTimeout(function () { acompanhar(acao, desde, n + 1); }, 5000); });
  }
  function decidir(acao) {
    bloquear(true);
    dizer(acao === 'aprovar' ? 'A aprovar…' : 'A rejeitar…');
    api({ op: 'decidir', pr: pr, t: t, acao: acao }).then(function (r) {
      dizer(r.msg, !r.ok);
      if (r.ok) acompanhar(acao, r.desde, 0); else bloquear(false);
    }).catch(function (e) { dizer('Erro de ligação: ' + e.message + '. Tenta outra vez.', true); bloquear(false); });
  }
  var confirmar = false;
  bA.addEventListener('click', function () { decidir('aprovar'); });
  bR.addEventListener('click', function () {
    if (!confirmar) { confirmar = true; bR.textContent = 'Confirmar: rejeitar'; return; }
    decidir('rejeitar');
  });
})();
