"""Aviso por email das notícias à espera de revisão (fase inicial, enquanto as notícias com IA não são automáticas)."""
from __future__ import annotations

import re
import smtplib
from datetime import date
from email.message import EmailMessage
from typing import Any, Iterable

RE_TITLE = re.compile(r"^- \*\*(.+?)\*\*", re.M)


def _review_prs(prs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [p for p in prs if str(p.get("head", {}).get("ref", "")).startswith("revisao/")]


def email_due(editorial: dict[str, Any], today: date) -> bool:
    policy = editorial["policy"]
    until = policy.get("review_email_until")
    if not until or policy.get("auto_publish_news"):
        return False
    return today <= date.fromisoformat(str(until))


def review_digest(prs: Iterable[dict[str, Any]], today: date) -> tuple[str, str] | None:
    """Assunto e texto do email; None se não houver nada para rever."""
    items = []
    for pr in sorted(_review_prs(prs), key=lambda p: p["number"]):
        titles = RE_TITLE.findall(pr.get("body") or "") or [pr["title"]]
        items.append((pr, titles))
    if not items:
        return None
    n = sum(len(t) for _, t in items)
    subject = f"Fluxo Energético: {n} notícia{'s' if n != 1 else ''} para rever ({today:%d/%m/%Y})"
    lines = ["Bom dia,", "", "Há notícias à espera da tua revisão antes de serem publicadas:", ""]
    for pr, titles in items:
        for t in titles:
            lines.append(f"• {t}")
        lines += [f"  Ler o texto: {pr['html_url']}/files",
                  f"  Aprovar (Merge) ou rejeitar (Close): {pr['html_url']}", ""]
    lines += ["Como validar: confirmar números e datas na fonte indicada no fim do texto; se estiver bem, "
              "«Merge pull request» → «Confirm merge» e o artigo fica publicado em 1–2 minutos.",
              "", "— Fluxo Energético (mensagem automática)"]
    return subject, "\n".join(lines)


def send_email(subject: str, body: str, sender: str, password: str, to: str, smtp=smtplib.SMTP_SSL,
               host: str = "smtp.gmail.com", port: int = 465) -> None:
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, f"Fluxo Energético <{sender}>", to
    msg.set_content(body)
    with smtp(host, port, timeout=30) as s:
        s.login(sender, password)
        s.send_message(msg)


def seconds_until(now, hhmm: str, tz: str = "Europe/Lisbon", cap: int = 1800) -> int:
    """Segundos até à hora local pedida (o agendamento do GitHub pode disparar mais cedo); máximo de 30 min."""
    from zoneinfo import ZoneInfo

    local = now.astimezone(ZoneInfo(tz))
    h, m = (int(x) for x in hhmm.split(":"))
    target = local.replace(hour=h, minute=m, second=0, microsecond=0)
    return max(0, min(cap, int((target - local).total_seconds())))
