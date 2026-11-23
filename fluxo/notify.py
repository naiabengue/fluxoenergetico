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


def review_prs(prs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pedidos de revisão (ramos revisao/…), do mais antigo para o mais recente."""
    return sorted(_review_prs(prs), key=lambda p: p["number"])


def review_digest(prs: Iterable[dict[str, Any]], today: date,
                  links: dict[int, str] | None = None) -> tuple[str, str] | None:
    """Assunto e texto do email; None se não houver nada para rever.
    links: {número do pedido: ligação para a página de aprovação}; sem ligação, aprova-se no GitHub."""
    links = links or {}
    items = []
    for pr in review_prs(prs):
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
        if pr["number"] in links:
            lines += [f"  Ler e aprovar (sem entrar no GitHub): {links[pr['number']]}",
                      f"  O mesmo no GitHub: {pr['html_url']}/files", ""]
        else:
            lines += [f"  Ler o texto: {pr['html_url']}/files",
                      f"  Aprovar (Merge) ou rejeitar (Close): {pr['html_url']}", ""]
    if links:
        lines += ["Como validar: confirmar números e datas na fonte indicada no fim do texto. Na página, "
                  "«Aprovar e publicar» põe o artigo no site em 1–2 minutos; «Rejeitar» fecha o pedido sem publicar."]
    else:
        lines += ["Como validar: confirmar números e datas na fonte indicada no fim do texto; se estiver bem, "
                  "«Merge pull request» → «Confirm merge» e o artigo fica publicado em 1–2 minutos."]
    lines += ["", "— Fluxo Energético (mensagem automática)"]
    return subject, "\n".join(lines)


def _lisbon_hhmm(iso: str) -> str:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ZoneInfo("Europe/Lisbon")).strftime("%H:%M")


def no_news_alert(today: date, last_run: dict[str, Any] | None, failed_runs: Iterable[dict[str, Any]],
                  repo: str) -> tuple[str, str]:
    """Aviso de dia útil sem notícia: o que a última execução encontrou e que execuções falharam."""
    lines = ["Bom dia,", "", "Hoje é dia útil e ainda não há nenhuma notícia para rever.", ""]
    if last_run:
        n = last_run.get("news", {})
        detail = f"{n.get('candidates', 0)} candidatos, {n.get('attempted', 0)} tentados"
        if n.get("skipped"):
            detail += f", {n['skipped']}"
        lines.append(f"Última execução do diário ({_lisbon_hhmm(last_run['started'])}): {detail}.")
        for r in last_run.get("rejected", []):
            if r.get("kind") == "noticia":
                lines.append(f"• Rejeitada: {r['title']} — {'; '.join(r.get('errors', [])) or 'sem motivo'}")
        for e in last_run.get("errors", []):
            lines.append(f"• Aviso: {e}")
        lines.append("")
    failed = list(failed_runs)
    if failed:
        lines.append("O diário falhou hoje:")
        lines += [f"• {_lisbon_hhmm(r['created_at'])}: {r['html_url']}" for r in failed]
        lines.append("")
    lines += ["A tentativa automática das 11:15 volta a procurar; se abrir uma notícia, recebes outro email.",
              f"Registo das execuções: https://github.com/{repo}/actions", "",
              "— Fluxo Energético (mensagem automática)"]
    return f"Fluxo Energético: ainda sem notícia hoje ({today:%d/%m/%Y})", "\n".join(lines)


def recipients(to: str, cc: Iterable[str] | None = None) -> list[str]:
    """Destino principal (segredo REVIEW_EMAIL_TO, pode ter vários separados por vírgula) mais as cópias, sem repetidos."""
    out: list[str] = []
    for a in [*to.split(","), *(cc or [])]:
        a = a.strip()
        if a and a.lower() not in (x.lower() for x in out):
            out.append(a)
    return out


def send_email(subject: str, body: str, sender: str, password: str, to: str | list[str], smtp=smtplib.SMTP_SSL,
               host: str = "smtp.gmail.com", port: int = 465) -> None:
    msg = EmailMessage()
    to = ", ".join(to) if isinstance(to, list) else to
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
