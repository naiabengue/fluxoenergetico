"""O leitor de cabeçalhos da página de aprovação (frontmatter.js) lê o que o PyYAML escreve.

Gera muitos artigos com textos difíceis (aspas, dois pontos, cardinais, percentagens, acentos, linhas longas)
pelo mesmo caminho que fluxo.publish.write_article e confirma que o JavaScript devolve o mesmo que o yaml.
"""
import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

JS = Path(__file__).resolve().parents[1] / "fluxo" / "site" / "static" / "frontmatter.js"
PIECES = ["Preços", "na", "produção", "industrial", "sobem", "10,2%", "em", "outubro:", "o", "gás", "#1", "'aspas'",
          '"duplas"', "Brent", "a", "92,14", "USD", "—", "«citação»", "€", "km²", "- traço", "? pergunta", ": dois",
          "[parênteses]", "{chaves}", "&e", "*", "!", "%", "@", "`", "1.ª", "3.810", "mil", "milhões", "pés",
          "cúbicos", "ENSE?", "não", "–", "…", "ção", "ã", "Ü", " ", "tab\tdentro", "yes", "null", "true", "0x1F",
          "2026-11-23", "~", "|", ">", ",", "a: b", "a #b", "x'y", "fim."]


def _text(rnd: random.Random, n: int) -> str:
    return " ".join(rnd.choice(PIECES) for _ in range(n)).strip()


def _articles(seed=7, count=300):
    rnd = random.Random(seed)
    out = []
    for i in range(count):
        meta = {"title": _text(rnd, rnd.randint(3, 22)), "slug": f"artigo-{i}", "date": "2026-11-23",
                "type": "noticia", "category": "eletricidade-gas", "tags": ["gas natural"],
                "lead": _text(rnd, rnd.randint(5, 60)),
                "key_points": [_text(rnd, rnd.randint(2, 30)) for _ in range(rnd.randint(0, 5))],
                "sources": [{"name": "EIA", "url": "https://www.eia.gov/x", "date": "2026-11-18"}],
                "ai": {"used": True, "review": "pr"}}
        if rnd.random() < 0.1:
            meta["lead"] = meta["lead"] + "\n" + _text(rnd, 4)        # quebra de linha dentro do texto
        if rnd.random() < 0.05:
            meta["key_points"] = []
        fm = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False)
        out.append((f"---\n{fm}---\n\n## Corpo\n\nTexto {i}.\n", meta))
    return out


@pytest.mark.skipif(not shutil.which("node"), reason="precisa de node")
def test_js_reads_what_pyyaml_writes(tmp_path):
    cases = _articles()
    data = tmp_path / "casos.json"
    data.write_text(json.dumps([c[0] for c in cases], ensure_ascii=False), encoding="utf-8")
    script = ("const fm=require(process.argv[1]);const fs=require('fs');"
              "const casos=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));"
              "console.log(JSON.stringify(casos.map(t=>fm.parse(t))));")
    res = subprocess.run(["node", "-e", script, str(JS), str(data)], capture_output=True, text=True, check=True)
    parsed = json.loads(res.stdout)
    failures = []
    for (text, meta), got in zip(cases, parsed):
        want = {k: meta[k] for k in ("title", "lead", "key_points")}
        if got is None or {k: got["meta"].get(k) for k in want} != want:
            failures.append((want, got and got["meta"], text.split("---")[1]))
        elif not got["body"].startswith("## Corpo"):
            failures.append(("corpo", got["body"][:30], ""))
    assert not failures, failures[:3]
