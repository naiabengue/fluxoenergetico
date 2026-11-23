"""Aprovar a partir do email: código só no email, hash no pedido, merge/fecho só com o código certo."""
import datetime as dt

import pytest

from fluxo import cli, notify, review
from fluxo.review import Refused, add_hash, decide, hashes, token_hash

TOKEN = "Abc_def-1234567890123456789012"
BODY = "Rascunhos gerados hoje.\n\n- **Eólica bate recorde** — pontuação 77; fonte: x\n"


def _pr(**kw):
    pr = {"number": 7, "title": "Revisão 2026-11-21", "state": "open", "merged_at": None,
          "html_url": "https://github.com/o/r/pull/7", "head": {"ref": "revisao/2026-11-21-0618", "sha": "abc"},
          "body": add_hash(BODY, token_hash(TOKEN))}
    pr.update(kw)
    return pr


class Resp:
    def __init__(self, data=None, status=200):
        self._data, self.status_code, self.text = data, status, ""

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise review.requests.HTTPError(str(self.status_code))


class FakeHTTP:
    def __init__(self, pr, merge_status=200):
        self.pr, self.merge_status, self.calls = pr, merge_status, []

    def get(self, url, **kw):
        self.calls.append(("GET", url, None))
        return Resp(self.pr)

    def put(self, url, **kw):
        self.calls.append(("PUT", url, kw.get("json")))
        return Resp({"message": "Pull Request is not mergeable"}, self.merge_status)

    def patch(self, url, **kw):
        self.calls.append(("PATCH", url, kw.get("json")))
        return Resp({})

    def post(self, url, **kw):
        self.calls.append(("POST", url, kw.get("json")))
        return Resp({})

    def delete(self, url, **kw):
        self.calls.append(("DELETE", url, None))
        return Resp(None, 204)


def test_hash_marker_is_invisible_kept_at_the_end_and_bounded():
    body = add_hash(BODY, "a" * 64)
    assert body.startswith(BODY.rstrip()) and body.rstrip().endswith("-->")
    body = add_hash(body, "b" * 64)
    assert hashes(body) == ["a" * 64, "b" * 64]                 # emails antigos continuam válidos
    for i in range(30):
        body = add_hash(body, f"{i:064x}")
    assert len(hashes(body)) == review.KEEP and body.count("<!--") == 1
    assert TOKEN not in add_hash(BODY, token_hash(TOKEN))       # o código nunca vai para o repositório público


def test_approve_merges_with_squash_and_cleans_branch():
    http = FakeHTTP(_pr())
    assert decide("o/r", 7, TOKEN, "aprovar", {}, http=http) == "merged"
    put = [c for c in http.calls if c[0] == "PUT"][0]
    assert put[1].endswith("/pulls/7/merge") and put[2]["merge_method"] == "squash" and put[2]["sha"] == "abc"
    assert put[2]["commit_title"] == "Publicar: revisão 2026-11-21 (#7)"
    assert http.calls[-1] == ("DELETE", "https://api.github.com/repos/o/r/git/refs/heads/revisao/2026-11-21-0618", None)


def test_reject_comments_and_closes_without_merging():
    http = FakeHTTP(_pr())
    assert decide("o/r", 7, TOKEN, "rejeitar", {}, http=http) == "closed"
    kinds = [c[0] for c in http.calls]
    assert "PUT" not in kinds and ("PATCH", "https://api.github.com/repos/o/r/pulls/7", {"state": "closed"}) in http.calls


@pytest.mark.parametrize("pr,token,why", [
    (_pr(), "Xyz_def-1234567890123456789012", "não corresponde"),       # código de outro pedido / inventado
    (_pr(), "curto", "formato"),
    (_pr(state="closed", merged_at="2026-11-22"), TOKEN, "integrado"),   # já aprovado antes
    (_pr(head={"ref": "deps", "sha": "x"}), TOKEN, "não é um pedido de revisão"),
])
def test_refuses_without_touching_anything(pr, token, why):
    http = FakeHTTP(pr)
    with pytest.raises(Refused, match=why):
        decide("o/r", 7, token, "aprovar", {}, http=http)
    assert [c[0] for c in http.calls] == ["GET"]


def test_unmergeable_request_is_reported():
    with pytest.raises(Refused, match="não conseguiu integrar"):
        decide("o/r", 7, TOKEN, "aprovar", {}, http=FakeHTTP(_pr(), merge_status=405), wait=0)


def test_digest_with_approval_link():
    subject, body = notify.review_digest([_pr()], dt.date(2026, 11, 23), {7: "https://script.example/exec?pr=7&t=x"})
    assert subject == "Fluxo Energético: 1 notícia para rever (23/11/2026)"
    assert "Aprovar: https://script.example/exec?pr=7&t=x&acao=aprovar" in body
    assert "Modificar: https://script.example/exec?pr=7&t=x&modo=editar" in body
    assert "Rejeitar: https://script.example/exec?pr=7&t=x&acao=rejeitar" in body
    assert "https://github.com/o/r/pull/7/files" in body


def test_recipients_adds_copy_without_duplicates():
    assert notify.recipients("trabalho@ense.pt", ["pedro@gmail.com"]) == ["trabalho@ense.pt", "pedro@gmail.com"]
    assert notify.recipients("a@x.pt, Pedro@gmail.com", ["pedro@gmail.com"]) == ["a@x.pt", "Pedro@gmail.com"]
    assert notify.recipients("a@x.pt", None) == ["a@x.pt"]


def test_cli_email_carries_button_link_and_goes_to_both_addresses(project, monkeypatch, capsys):
    import yaml

    path = project / "config" / "editorial.yaml"
    ed = yaml.safe_load(path.read_text(encoding="utf-8"))
    ed["policy"]["approve_url"] = "https://script.example/exec"
    ed["policy"]["review_email_cc"] = ["copia@gmail.com"]
    path.write_text(yaml.safe_dump(ed, allow_unicode=True), encoding="utf-8")
    for k, v in {"GITHUB_REPOSITORY": "o/r", "GITHUB_TOKEN": "t", "SMTP_USER": "a@gmail.com",
                 "SMTP_PASSWORD": "p", "REVIEW_EMAIL_TO": "trabalho@exemplo.pt"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(cli, "_now", lambda: dt.datetime(2026, 11, 23, 8, 30, tzinfo=dt.timezone.utc))
    pr = _pr(body=BODY)
    monkeypatch.setattr(cli.requests, "get", lambda *a, **k: Resp([pr]))
    patched = []
    monkeypatch.setattr(review.requests, "patch", lambda url, **k: patched.append((url, k["json"])) or Resp({}))
    sent, sent_kw = [], []
    monkeypatch.setattr(notify, "send_email", lambda *a, **k: sent.append(a) or sent_kw.append(k))

    assert cli.main(["notify-review", "--root", str(project)]) == 0
    (subject, body, _, _, to), = sent
    html = sent_kw[0]["html"]
    assert "Aprovar e publicar" in html and "Modificar" in html and "&amp;modo=editar" in html
    assert to == ["trabalho@exemplo.pt", "copia@gmail.com"]
    link = next(line.split(": ", 1)[1] for line in body.splitlines() if line.strip().startswith("Aprovar:"))
    token = link.split("t=", 1)[1].split("&", 1)[0]
    (url, data), = patched
    assert url.endswith("/pulls/7") and hashes(data["body"]) == [token_hash(token)] and token not in data["body"]
    assert "1 com botão de aprovação" in capsys.readouterr().out


def test_cli_decision_writes_output_for_publishing(monkeypatch, tmp_path):
    out = tmp_path / "out.txt"
    for k, v in {"GITHUB_REPOSITORY": "o/r", "GITHUB_TOKEN": "t", "APPROVE_TOKEN": TOKEN,
                 "GITHUB_OUTPUT": str(out)}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(review, "decide", lambda repo, n, t, a, h, **k: decide(repo, n, t, a, h, http=FakeHTTP(_pr()), **k))
    assert cli.main(["review-decision", "--pr", "7", "--action", "aprovar"]) == 0
    assert out.read_text() == "merged=true\n"
    monkeypatch.setenv("APPROVE_TOKEN", "errado_errado_errado_errado")
    assert cli.main(["review-decision", "--pr", "7"]) == 1


def test_marker_found_even_with_text_after_it():
    body = add_hash(BODY, token_hash(TOKEN)) + "\n_Rodapé acrescentado por outra ferramenta_\n"
    assert hashes(body) == [token_hash(TOKEN)]
    body = add_hash(body, "c" * 64)                         # volta a ficar um só marcador, no fim
    assert body.count("<!--") == 1 and hashes(body) == [token_hash(TOKEN), "c" * 64] and "Rodapé" in body


ARTICLE = """---
title: Armazenamento de gás natural nos Estados Unidos encerra época de injeção acima
  do normal
slug: armazenamento-de-gas
date: '2026-11-21'
type: noticia
lead: As reservas terminaram acima da média.
key_points:
- Um ponto.
- Outro ponto com 3,0%.
sources:
- name: EIA
  url: https://www.eia.gov/x
  date: '2026-11-18'
ai:
  used: true
  review: pr
---

## O que aconteceu
""" + "Texto original. " * 20 + "\n"

EDIT = {"ficheiro": "content/articles/2026/11/armazenamento-de-gas.md", "title": "Reservas de gás dos EUA acima da média: 3 810 mil milhões de pés³",
        "lead": "  As reservas   terminaram a época acima da média de cinco anos. ",
        "key_points": ["Ponto novo.", "", "  Segundo ponto  "], "body": "## O que aconteceu\n\n" + "Texto corrigido. " * 20}


def test_apply_edit_changes_only_the_editable_fields():
    import yaml as y

    from fluxo.review import apply_edit, split

    new = apply_edit(ARTICLE, EDIT)
    meta, body = split(new)
    assert meta["title"] == EDIT["title"] and meta["lead"] == "As reservas terminaram a época acima da média de cinco anos."
    assert meta["key_points"] == ["Ponto novo.", "Segundo ponto"]
    assert meta["slug"] == "armazenamento-de-gas" and meta["sources"][0]["name"] == "EIA" and meta["ai"]["review"] == "pr"
    assert body.startswith("## O que aconteceu") and "Texto corrigido." in body and "Texto original" not in body
    assert y.safe_load(new.split("---\n")[1])["title"] == EDIT["title"]


@pytest.mark.parametrize("change,why", [({"body": "curto"}, "body"), ({"title": "x"}, "title"),
                                        ({"key_points": ["a"] * 9}, "até 8"), ({"lead": None}, "falta")])
def test_apply_edit_refuses_bad_input(change, why):
    from fluxo.review import apply_edit

    with pytest.raises(Refused, match=why):
        apply_edit(ARTICLE, dict(EDIT, **change))


class EditHTTP(FakeHTTP):
    def get(self, url, **kw):
        self.calls.append(("GET", url, kw.get("params")))
        if url.endswith("/files"):
            return Resp([{"filename": EDIT["ficheiro"], "status": "added"}, {"filename": "data/x.json", "status": "added"}])
        if "/contents/" in url:
            import base64

            return Resp({"sha": "blob1", "content": base64.b64encode(ARTICLE.encode()).decode()})
        return Resp(self.pr)

    def put(self, url, **kw):
        self.calls.append(("PUT", url, kw.get("json")))
        if "/contents/" in url:
            return Resp({"commit": {"sha": "novo123"}})
        return Resp({"merged": True})


def test_modify_commits_to_the_review_branch_then_merges_that_commit():
    import base64

    http = EditHTTP(_pr())
    assert decide("o/r", 7, TOKEN, "modificar", {}, http=http, edits=[EDIT]) == "merged"
    puts = [c for c in http.calls if c[0] == "PUT"]
    assert puts[0][1].endswith("/contents/" + EDIT["ficheiro"]) and puts[0][2]["branch"] == "revisao/2026-11-21-0618"
    assert puts[0][2]["sha"] == "blob1" and "Texto corrigido." in base64.b64decode(puts[0][2]["content"]).decode()
    assert puts[1][1].endswith("/pulls/7/merge") and puts[1][2]["sha"] == "novo123"
    assert "Alterada" in puts[1][2]["commit_message"]


def test_modify_refuses_files_outside_the_request_and_wrong_codes():
    http = EditHTTP(_pr())
    with pytest.raises(Refused, match="fora deste pedido"):
        decide("o/r", 7, TOKEN, "modificar", {}, http=http, edits=[dict(EDIT, ficheiro="config/editorial.yaml")])
    assert not [c for c in http.calls if c[0] == "PUT"]
    http = EditHTTP(_pr())
    with pytest.raises(Refused, match="não corresponde"):
        decide("o/r", 7, "Xyz_def-1234567890123456789012", "modificar", {}, http=http, edits=[EDIT])
    assert [c[0] for c in http.calls] == ["GET"]


def test_html_email_shows_the_article_and_three_buttons():
    pr = _pr()
    arts = {7: [{"title": "Título <b>", "lead": "Entrada & mais", "key_points": ["Um 3%"], "body": "## Contexto\n\nTexto <script>x</script>.",
                 "sources": [{"name": "EIA", "url": "https://www.eia.gov/x", "date": "2026-11-18"}], "score": 77}]}
    html = notify.review_html([pr], dt.date(2026, 11, 23), {7: "https://site/aprovar/?pr=7&t=abc"}, arts)
    assert "Título &lt;b&gt;" in html and "Entrada &amp; mais" in html and "<script>" not in html
    assert html.count("&amp;acao=aprovar") == 2 and html.count("&amp;modo=editar") == 2      # botões em cima e em baixo
    assert "&amp;acao=rejeitar" in html and "Pontos-chave" in html and "Contexto</h2>" in html and "pontuação 77" in html


def test_send_email_with_html_alternative():
    sent = {}

    class FakeSMTP:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def login(self, *a):
            pass

        def send_message(self, msg):
            sent["types"] = [p.get_content_type() for p in msg.iter_parts()]

    notify.send_email("A", "texto", "a@gmail.com", "p", ["b@x.pt"], smtp=FakeSMTP, html="<p>olá</p>")
    assert sent["types"] == ["text/plain", "text/html"]
