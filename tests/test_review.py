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
        decide("o/r", 7, TOKEN, "aprovar", {}, http=FakeHTTP(_pr(), merge_status=405))


def test_digest_with_approval_link():
    subject, body = notify.review_digest([_pr()], dt.date(2026, 11, 23), {7: "https://script.example/exec?pr=7&t=x"})
    assert subject == "Fluxo Energético: 1 notícia para rever (23/11/2026)"
    assert "Ler e aprovar (sem entrar no GitHub): https://script.example/exec?pr=7&t=x" in body
    assert "https://github.com/o/r/pull/7/files" in body and "Aprovar e publicar" in body


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
    sent = []
    monkeypatch.setattr(notify, "send_email", lambda *a, **k: sent.append(a))

    assert cli.main(["notify-review", "--root", str(project)]) == 0
    (subject, body, _, _, to), = sent
    assert to == ["trabalho@exemplo.pt", "copia@gmail.com"]
    link = next(line.split(": ", 1)[1] for line in body.splitlines() if "sem entrar no GitHub" in line)
    token = link.split("t=", 1)[1]
    (url, data), = patched
    assert url.endswith("/pulls/7") and hashes(data["body"]) == [token_hash(token)] and token not in data["body"]
    assert "1 com botão de aprovação" in capsys.readouterr().out


def test_cli_decision_writes_output_for_publishing(monkeypatch, tmp_path):
    out = tmp_path / "out.txt"
    for k, v in {"GITHUB_REPOSITORY": "o/r", "GITHUB_TOKEN": "t", "APPROVE_TOKEN": TOKEN,
                 "GITHUB_OUTPUT": str(out)}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(review, "decide", lambda repo, n, t, a, h: decide(repo, n, t, a, h, http=FakeHTTP(_pr())))
    assert cli.main(["review-decision", "--pr", "7", "--action", "aprovar"]) == 0
    assert out.read_text() == "merged=true\n"
    monkeypatch.setenv("APPROVE_TOKEN", "errado_errado_errado_errado")
    assert cli.main(["review-decision", "--pr", "7"]) == 1


def test_marker_found_even_with_text_after_it():
    body = add_hash(BODY, token_hash(TOKEN)) + "\n_Rodapé acrescentado por outra ferramenta_\n"
    assert hashes(body) == [token_hash(TOKEN)]
    body = add_hash(body, "c" * 64)                         # volta a ficar um só marcador, no fim
    assert body.count("<!--") == 1 and hashes(body) == [token_hash(TOKEN), "c" * 64] and "Rodapé" in body
