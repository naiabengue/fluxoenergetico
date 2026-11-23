/* Leitura do cabeçalho (front matter) dos artigos, só para o que a página de aprovação precisa de editar:
 * title, lead e key_points. O cabeçalho é escrito pelo PyYAML (yaml.safe_dump, allow_unicode, largura 80):
 * escalares simples ou entre aspas, dobrados em várias linhas com 2 espaços de recuo, e listas «- item».
 * Se aparecer outra forma, devolve null e a página manda editar no GitHub. Testado contra o PyYAML em
 * tests/test_frontmatter_js.py. */
(function (root) {
  'use strict';

  function trim(s) { return s.replace(/^[ \t]+|[ \t]+$/g, ''); }   // o YAML só corta espaços e tabulações

  function fold(lines) {
    // Regras de dobragem do YAML: linhas seguidas juntam-se com um espaço; cada linha vazia vale uma quebra.
    var out = '', pendingBreaks = 0;
    for (var i = 0; i < lines.length; i++) {
      var l = trim(lines[i]);
      if (l === '') { pendingBreaks++; continue; }
      if (out === '') out = l;
      else out += pendingBreaks ? new Array(pendingBreaks + 1).join('\n') + l : ' ' + l;
      pendingBreaks = 0;
    }
    return out;
  }

  function foldDouble(lines) {
    // Aspas duplas: uma linha acabada em «\» continua sem espaço; o resto segue as regras normais.
    var out = '', pendingBreaks = 0, glue = false;
    for (var i = 0; i < lines.length; i++) {
      var raw = lines[i], l = i === 0 ? raw.replace(/[ \t]+$/, '') : trim(raw);
      if (l === '') { pendingBreaks++; continue; }
      if (i > 0 && glue) out += l.replace(/^\\/, '');
      else if (out === '') out = l;
      else out += pendingBreaks ? new Array(pendingBreaks + 1).join('\n') + l : ' ' + l;
      pendingBreaks = 0;
      glue = /(^|[^\\])(\\\\)*\\$/.test(l);
      if (glue) out = out.slice(0, -1);
    }
    return out;
  }

  function scalar(lines) {
    var first = trim(lines[0]);
    if (first === '' && lines.length === 1) return '';
    if (/^[|>]/.test(first)) return null;                       // blocos literais: o PyYAML não os escreve
    if (first.charAt(0) === "'") {
      var s = fold(lines);
      if (s.length < 2 || s.charAt(s.length - 1) !== "'") return null;
      return s.slice(1, -1).replace(/''/g, "'");
    }
    if (first.charAt(0) === '"') {
      var d = foldDouble(lines);
      try { return JSON.parse(d.replace(/\\x([0-9a-fA-F]{2})/g, '\\u00$1').replace(/\\U([0-9a-fA-F]{8})/g, function (m, h) {
        return String.fromCodePoint(parseInt(h, 16)).split('').map(function (c) { return '\\u' + ('000' + c.charCodeAt(0).toString(16)).slice(-4); }).join('');
      }).replace(/\\([ \/_N LP])/g, function (m, c) { return { ' ': ' ', '/': '/', _: ' ', N: '\u0085', L: ' ', P: ' ' }[c]; })); }
      catch (e) { return null; }
    }
    if (/^[\[{&*!%@`]/.test(first)) return null;
    return fold(lines);
  }

  function parse(text) {
    var m = /^---\n([\s\S]*?)\n---\n?([\s\S]*)$/.exec(String(text).replace(/\r\n/g, '\n'));
    if (!m) return null;
    var lines = m[1].split('\n'), entries = {}, order = [], key = null;
    for (var i = 0; i < lines.length; i++) {
      var l = lines[i], k = /^([A-Za-z_][\w-]*):(?: (.*)|)$/.exec(l);
      if (k) { key = k[1]; entries[key] = [k[2] || '']; order.push(key); }
      else if (key) entries[key].push(l);
      else return null;
    }
    var meta = { _keys: order };
    if (entries.title) meta.title = scalar(entries.title);
    if (entries.lead) meta.lead = scalar(entries.lead);
    if (entries.key_points) {
      var items = [], cur = null, ls = entries.key_points;
      if (trim(ls[0]) === '[]') items = [];
      else {
        for (var j = 1; j < ls.length; j++) {
          var it = /^- (.*)$/.exec(ls[j]);
          if (it) { if (cur) items.push(cur); cur = [it[1]]; }
          else if (cur && /^ {2}/.test(ls[j])) cur.push(ls[j]);
          else if (cur && trim(ls[j]) === '') cur.push('');
          else return null;
        }
        if (cur) items.push(cur);
        items = items.map(scalar);
      }
      if (items.some(function (x) { return x === null; })) return null;
      meta.key_points = items;
    }
    if (meta.title === null || meta.lead === null) return null;
    return { meta: meta, body: m[2].replace(/^\n+/, '') };
  }

  root.FrontMatter = { parse: parse };
  if (typeof module !== 'undefined') module.exports = root.FrontMatter;
})(typeof window !== 'undefined' ? window : this);
