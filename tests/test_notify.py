"""Email diário de revisão nas primeiras semanas: só quando há notícias à espera, só até à data definida."""
from datetime import date

from fluxo.config import load_config
from fluxo.notify import email_due, review_digest, send_email

PRS = [
    {"number": 2, "title": "Revisão 2026-11-17", "html_url": "https://github.com/o/r/pull/2",
     "head": {"ref": "revisao/2026-11-17"},
     "body": "Rascunhos gerados hoje.\n\n- **Energia eólica lidera produção renovável** — pontuação 81; fonte: x\n"},
    {"number": 9, "title": "Atualizar dependências", "html_url": "https://github.com/o/r/pull/9",
     "head": {"ref": "deps"}, "body": "- **não é revisão**"},
]


def test_digest_lists_review_prs_with_links():
    subject, body = review_digest(PRS, date(2026, 11, 18))
    assert subject == "Fluxo Energético: 1 notícia para rever (18/11/2026)"
    assert "Energia eólica lidera produção renovável" in body
    assert "https://github.com/o/r/pull/2/files" in body       # onde se lê a notícia
    assert "https://github.com/o/r/pull/2" in body             # onde se aprova (Merge) ou fecha
    assert "/pull/9" not in body and "não é revisão" not in body


def test_digest_is_none_without_review_prs():
    assert review_digest([PRS[1]], date(2026, 11, 18)) is None
    assert review_digest([], date(2026, 11, 18)) is None


def test_email_only_until_end_of_review_period(project):
    ed = load_config(project).editorial
    assert ed["policy"]["review_email_until"] == "2026-12-15"
    assert email_due(ed, date(2026, 12, 15)) is True
    assert email_due(ed, date(2026, 12, 16)) is False
    ed["policy"]["auto_publish_news"] = True                   # notícias já automáticas: nada para rever
    assert email_due(ed, date(2026, 11, 20)) is False


def test_send_email_uses_ssl_login_and_never_echoes_password():
    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            sent["server"] = (host, port)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def login(self, user, password):
            sent["login"] = (user, password)

        def send_message(self, msg):
            sent["to"], sent["from"], sent["subject"] = msg["To"], msg["From"], msg["Subject"]
            sent["text"] = msg.get_content()

    send_email("Assunto", "Corpo", "remetente@gmail.com", "app-pass", "destino@exemplo.pt", smtp=FakeSMTP)
    assert sent["server"] == ("smtp.gmail.com", 465)
    assert sent["login"] == ("remetente@gmail.com", "app-pass")
    assert sent["to"] == "destino@exemplo.pt" and sent["subject"] == "Assunto"
    assert "app-pass" not in sent["text"]


def test_wait_until_send_time_lisbon():
    from datetime import datetime, timezone
    from fluxo.notify import seconds_until

    # 17/11 é inverno: Lisboa = UTC
    assert seconds_until(datetime(2026, 11, 18, 8, 15, tzinfo=timezone.utc), "08:30") == 900
    assert seconds_until(datetime(2026, 11, 18, 8, 40, tzinfo=timezone.utc), "08:30") == 0      # atrasado: envia já
    assert seconds_until(datetime(2026, 11, 18, 6, 0, tzinfo=timezone.utc), "08:30") == 1800    # nunca espera > 30 min


def test_cli_without_email_config_sends_nothing(project, monkeypatch, capsys):
    from fluxo import cli

    for k in ["SMTP_USER", "SMTP_PASSWORD", "REVIEW_EMAIL_TO"]:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(cli, "_now", lambda: __import__("datetime").datetime(2026, 11, 18, 8, 30,
                                                                              tzinfo=__import__("datetime").timezone.utc))
    assert cli.main(["notify-review", "--root", str(project)]) == 0
    assert "Sem configuração de email" in capsys.readouterr().out
