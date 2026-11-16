// Pesquisa local: o índice é descarregado uma vez e filtrado no navegador.
(function () {
  var script = document.currentScript;
  var input = document.getElementById("q");
  var out = document.getElementById("results");
  var index = [];
  function norm(s) { return (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, ""); }
  function render(list, q) {
    out.innerHTML = "";
    if (!q) return;
    if (!list.length) { out.innerHTML = '<li class="empty">Nenhum artigo contém estas palavras. Experimente termos mais gerais.</li>'; return; }
    list.slice(0, 50).forEach(function (a) {
      var li = document.createElement("li"); li.className = "entry";
      var meta = document.createElement("p"); meta.className = "entry-meta"; meta.textContent = a.c + " " + a.d;
      var h = document.createElement("h2"); h.className = "entry-title";
      var link = document.createElement("a"); link.href = a.u; link.textContent = a.t; h.appendChild(link);
      var p = document.createElement("p"); p.className = "entry-lead"; p.textContent = a.s;
      li.appendChild(meta); li.appendChild(h); li.appendChild(p); out.appendChild(li);
    });
  }
  fetch(script.getAttribute("data-index")).then(function (r) { return r.json(); }).then(function (data) {
    index = data.map(function (a) { a._n = norm(a.t + " " + a.s + " " + a.c); return a; });
    input.addEventListener("input", function () {
      var words = norm(input.value).split(/\s+/).filter(Boolean);
      render(index.filter(function (a) { return words.every(function (w) { return a._n.indexOf(w) >= 0; }); }), words.length);
    });
  });
})();
