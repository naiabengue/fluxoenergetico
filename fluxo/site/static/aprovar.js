/* Página de aprovação do email de revisão: /aprovar/?pr=N&t=CÓDIGO[&acao=aprovar|rejeitar][&modo=editar]
 * Lê o pedido de revisão na API pública do GitHub, mostra o texto e confirma o código (o pedido guarda só o
 * SHA-256). Os botões chamam o Google Apps Script sem cookies (para não cair no erro das várias contas Google),
 * que lança o workflow «Aprovar notícia»; a página acompanha a execução até ao fim.
 * Abrir a página não altera nada: os antivírus do email abrem as ligações sozinhos. */
(function () {
  'use strict';
  var box = document.getElementById('aprovacao');
  if (!box) return;
  var API = box.dataset.api, REPO = box.dataset.repo, SITE = box.dataset.site;
  var q = new URLSearchParams(location.search);
  var pr = q.get('pr') || '', t = q.get('t') || '', acaoPedida = q.get('acao'), modo = q.get('modo');
  var $ = function (id) { return document.getElementById(id); };
  var estado = $('ap-estado'), lista = $('ap-artigos'), decisao = $('ap-decisao'), msg = $('ap-msg');
  var form = $('ap-editar'), campos = $('ap-campos'), msgEd = $('ap-msg-ed');
  var bA = $('ap-aprovar'), bM = $('ap-modificar'), bR = $('ap-rejeitar'), bG = $('ap-guardar'), bV = $('ap-voltar');
  var GH = 'https://github.com/' + REPO + '/pull/' + pr;
  var artigos = [], confirmarRejeicao = false;
  var LIM = { title: [10, 200], lead: [20, 800], body: [200, 30000] };

  function el(tag, attrs, text) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    if (text != null) e.textContent = text;
    return e;
  }
  function linha(texto, ligacao, rotulo) {
    estado.textContent = texto + (ligacao ? ' ' : '');
    if (ligacao) estado.appendChild(el('a', { href: ligacao }, rotulo));
  }
  function dizer(alvo, texto, erro) { alvo.textContent = texto; alvo.className = 'ap-msg' + (erro ? ' ap-erro' : ''); }
  function bloquear(sim) { [bA, bM, bR, bG, bV].forEach(function (b) { b.disabled = sim; }); }
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

  // ── Ver ────────────────────────────────────────────────────────────────────────────────────────────────────
  function mostrar() {
    form.hidden = true; lista.hidden = false; decisao.hidden = false;
    $('ap-h1').textContent = 'Rever notícia';
    if (lista.childNodes.length) return;
    artigos.forEach(function (a) {
      lista.appendChild(el('h2', { 'class': 'ap-titulo' }, a.fm && a.fm.meta.title || a.path.split('/').pop()));
      lista.appendChild(el('pre', { 'class': 'ap-texto' }, a.texto));
    });
  }

  // ── Editar ─────────────────────────────────────────────────────────────────────────────────────────────────
  function editar() {
    var falhou = artigos.filter(function (a) { return !a.fm; });
    if (!artigos.length || falhou.length) {
      mostrar();
      dizer(msg, 'Não consegui preparar o formulário para este artigo. Edita-o no GitHub e depois aprova aqui.', true);
      msg.appendChild(el('a', { href: GH + '/files' }, ' Abrir no GitHub'));
      return;
    }
    $('ap-h1').textContent = 'Modificar notícia';
    lista.hidden = true; decisao.hidden = true; form.hidden = false;
    if (!campos.childNodes.length) {
      artigos.forEach(function (a, i) {
        var m = a.fm.meta, fs = el('fieldset', { 'class': 'ap-campos' });
        if (artigos.length > 1) fs.appendChild(el('legend', {}, 'Artigo ' + (i + 1)));
        [['title', 'Título', 'input', m.title, 2], ['lead', 'Entrada', 'textarea', m.lead, 3],
         ['key_points', 'Pontos-chave (um por linha)', 'textarea', (m.key_points || []).join('\n'), 5],
         ['body', 'Texto', 'textarea', a.fm.body.replace(/\n+$/, ''), 18]].forEach(function (c) {
          var id = 'ap-' + c[0] + '-' + i, f = el(c[2], { id: id, name: c[0] });
          if (c[2] === 'textarea') f.rows = c[4]; else f.type = 'text';
          f.value = c[3] || '';
          fs.appendChild(el('label', { 'for': id }, c[1]));
          fs.appendChild(f);
        });
        campos.appendChild(fs);
      });
    }
    window.scrollTo(0, 0);
  }

  function recolher() {
    var erros = [], nomes = { title: 'Título', lead: 'Entrada', body: 'Texto' };
    var out = artigos.map(function (a, i) {
      var v = function (n) { return document.getElementById('ap-' + n + '-' + i).value; };
      var e = { ficheiro: a.path, title: v('title').replace(/\s+/g, ' ').trim(), lead: v('lead').replace(/\s+/g, ' ').trim(),
                key_points: v('key_points').split('\n').map(function (s) { return s.trim(); }).filter(Boolean),
                body: v('body').trim() };
      ['title', 'lead', 'body'].forEach(function (k) {
        var n = e[k].length;
        if (n < LIM[k][0] || n > LIM[k][1]) erros.push(nomes[k] + ': ' + n + ' caracteres (aceites ' + LIM[k][0] + '–' + LIM[k][1] + ').');
      });
      if (e.key_points.length > 8) erros.push('Até 8 pontos-chave.');
      return e;
    });
    return { artigos: out, erros: erros };
  }

  // ── Decidir e acompanhar ───────────────────────────────────────────────────────────────────────────────────
  function acompanhar(alvo, acao, desde, n) {
    fetch(API + '?op=estado&pr=' + pr + '&acao=' + acao + '&desde=' + encodeURIComponent(desde), { credentials: 'omit' })
      .then(function (r) { return r.json(); })
      .then(function (r) {
        if (r.fim) {
          dizer(alvo, r.msg, !r.ok);
          if (r.ok && acao !== 'rejeitar') alvo.appendChild(el('a', { href: SITE }, ' Abrir o site'));
          if (!r.ok) bloquear(false);
        } else if (n < 60) setTimeout(function () { acompanhar(alvo, acao, desde, n + 1); }, 5000);
        else dizer(alvo, 'Ainda a correr. Confirma daqui a pouco no site.');
      })
      .catch(function () { if (n < 60) setTimeout(function () { acompanhar(alvo, acao, desde, n + 1); }, 5000); });
  }
  function decidir(acao, alvo, edicao) {
    bloquear(true);
    dizer(alvo, { aprovar: 'A aprovar…', modificar: 'A enviar as alterações…', rejeitar: 'A rejeitar…' }[acao]);
    var dados = { op: 'decidir', pr: pr, t: t, acao: acao };
    if (edicao) dados.edicao = edicao;
    api(dados).then(function (r) {
      dizer(alvo, r.msg, !r.ok);
      if (r.ok) acompanhar(alvo, acao, r.desde, 0); else bloquear(false);
    }).catch(function (e) { dizer(alvo, 'Erro de ligação: ' + e.message + '. Tenta outra vez.', true); bloquear(false); });
  }

  bA.addEventListener('click', function () { decidir('aprovar', msg); });
  bM.addEventListener('click', editar);
  bV.addEventListener('click', function () { mostrar(); dizer(msg, ''); });
  bR.addEventListener('click', function () {
    if (!confirmarRejeicao) { confirmarRejeicao = true; bR.textContent = 'Confirmar: rejeitar'; return; }
    decidir('rejeitar', msg);
  });
  form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    var r = recolher();
    if (r.erros.length) { dizer(msgEd, r.erros.join(' '), true); return; }
    decidir('modificar', msgEd, { artigos: r.artigos });
  });

  // ── Carregar ───────────────────────────────────────────────────────────────────────────────────────────────
  function carregar(p) {
    return gh('/pulls/' + pr + '/files?per_page=50').then(function (files) {
      var md = files.filter(function (f) { return /^content\/articles\/.+\.md$/.test(f.filename) && f.status !== 'removed'; });
      return Promise.all(md.map(function (f) {
        return fetch('https://raw.githubusercontent.com/' + REPO + '/' + p.head.sha + '/' + f.filename)
          .then(function (r) { if (!r.ok) throw new Error('texto ' + r.status); return r.text(); })
          .then(function (texto) { return { path: f.filename, texto: texto, fm: window.FrontMatter.parse(texto) }; });
      }));
    });
  }

  gh('/pulls/' + pr).then(function (p) {
    if (String(p.head.ref).indexOf('revisao/') !== 0) { linha('Este pedido não é uma notícia para rever.'); return; }
    if (p.merged_at) { linha('Esta notícia já foi aprovada e publicada.', SITE, 'Abrir o site'); return; }
    if (p.state !== 'open') { linha('Esta notícia já foi rejeitada (pedido fechado).'); return; }
    var m = /<!--\s*aprovar:([0-9a-f\s]*)-->/.exec(p.body || '');
    return sha256hex(t).then(function (h) {
      if (!m || m[1].trim().split(/\s+/).indexOf(h) < 0) {
        linha('Esta ligação não corresponde a esta notícia. Usa a ligação do email.');
        return;
      }
      linha('Pedido #' + pr + ' ·', GH + '/files', 'ver no GitHub');
      return carregar(p).then(function (a) {
        artigos = a;
        if (modo === 'editar') { editar(); return; }
        mostrar();
        if (acaoPedida === 'aprovar') { bA.textContent = 'Confirmar: aprovar e publicar'; bA.focus(); }
        if (acaoPedida === 'rejeitar') { confirmarRejeicao = true; bR.textContent = 'Confirmar: rejeitar'; bR.focus(); }
        if (!artigos.length) { bM.hidden = true; linha('Pedido #' + pr + ' (sem artigos para mostrar) ·', GH + '/files', 'ver no GitHub'); }
      });
    });
  }).catch(function () {
    // Sem a API do GitHub (limite de pedidos, rede): aprovar e rejeitar funcionam na mesma; o servidor confirma.
    linha('Não foi possível mostrar o texto aqui.', GH + '/files', 'Ler no GitHub');
    decisao.hidden = false;
    bM.hidden = true;
  });
})();
