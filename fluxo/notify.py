"""Aviso por email das notícias à espera de revisão (fase inicial, enquanto as notícias com IA não são automáticas)."""
from __future__ import annotations

import re
import smtplib
from html import escape
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
            link = links[pr["number"]]
            lines += [f"  Aprovar: {link}&acao=aprovar", f"  Modificar: {link}&modo=editar",
                      f"  Rejeitar: {link}&acao=rejeitar", f"  No GitHub: {pr['html_url']}/files", ""]
        else:
            lines += [f"  Ler o texto: {pr['html_url']}/files",
                      f"  Aprovar (Merge) ou rejeitar (Close): {pr['html_url']}", ""]
    if links:
        lines += ["Como validar: confirmar números e datas na fonte indicada no fim do texto. Aprovar e Rejeitar "
                  "abrem uma página para confirmares com um clique; Modificar abre o texto para corrigires antes de "
                  "publicar. O artigo fica no site em 1–2 minutos."]
    else:
        lines += ["Como validar: confirmar números e datas na fonte indicada no fim do texto; se estiver bem, "
                  "«Merge pull request» → «Confirm merge» e o artigo fica publicado em 1–2 minutos."]
    lines += ["", "— Fluxo Energético (mensagem automática)"]
    return subject, "\n".join(lines)


# ── Versão HTML do email de revisão: o texto da notícia e os botões Aprovar / Modificar / Rejeitar ────────────
INK, LINK, AMBER, MUTED, PANEL, LINE, RED = "#10324a", "#1f6f63", "#e2a01c", "#5a6872", "#eef3f1", "#d5dfdb", "#a3261b"
SANS, SERIF = "Arial,Helvetica,sans-serif", "Georgia,'Times New Roman',serif"


def _button(href: str, label: str, fg: str, bg: str, border: str) -> str:
    return (f'<td style="background:{bg};border:2px solid {border};border-radius:4px">'
            f'<a href="{escape(href)}" style="display:inline-block;padding:11px 16px;font:bold 15px {SANS};'
            f'color:{fg};text-decoration:none">{label}</a></td><td style="width:8px">&nbsp;</td>')


def _buttons(link: str) -> str:
    return ('<table role="presentation" cellpadding="0" cellspacing="0" style="margin:4px 0 20px"><tr>'
            + _button(f"{link}&acao=aprovar", "&#10003; Aprovar e publicar", "#ffffff", LINK, LINK)
            + _button(f"{link}&modo=editar", "&#9998; Modificar", LINK, "#ffffff", LINK)
            + _button(f"{link}&acao=rejeitar", "&#10005; Rejeitar", RED, "#ffffff", LINE)
            + "</tr></table>")


def _body_html(md: str) -> str:
    import markdown

    html = markdown.markdown(escape(md, quote=False))
    return (html.replace("<h2>", f'<h2 style="font:bold 18px/1.3 {SERIF};color:{INK};margin:20px 0 6px">')
                .replace("<h3>", f'<h3 style="font:bold 16px/1.3 {SANS};color:{INK};margin:16px 0 4px">')
                .replace("<p>", '<p style="margin:0 0 12px">'))


def review_html(prs: Iterable[dict[str, Any]], today: date, links: dict[int, str],
                articles: dict[int, list[dict[str, Any]]]) -> str:
    """Email em HTML: cada notícia com título, entrada, pontos-chave, texto, fonte e os três botões."""
    blocks, n = [], 0
    for pr in review_prs(prs):
        link = links.get(pr["number"])
        arts = articles.get(pr["number"]) or [{"title": t, "lead": "", "key_points": [], "body": "", "sources": []}
                                              for t in RE_TITLE.findall(pr.get("body") or "") or [pr["title"]]]
        for a in arts:
            n += 1
            kp = "".join(f"<li>{escape(p)}</li>" for p in a.get("key_points") or [])
            src = " · ".join(f'<a href="{escape(str(s.get("url", "")))}" style="color:{LINK}">{escape(str(s.get("name", "fonte")))}</a>'
                             + (f" ({escape(str(s['date']))})" if s.get("date") else "") for s in a.get("sources") or [])
            score = f" · pontuação {a['score']}" if a.get("score") else ""
            actions = _buttons(link) if link else (
                f'<p><a href="{escape(pr["html_url"])}" style="color:{LINK}">Aprovar (Merge) ou rejeitar (Close) no GitHub</a></p>')
            blocks.append(
                f'<tr><td style="padding:24px 24px 4px;font:15px/1.6 {SANS};color:#24323d">'
                f'<p style="margin:0 0 6px;font:12px {SANS};color:{MUTED};text-transform:uppercase;letter-spacing:.04em">'
                f'Por rever · pedido #{pr["number"]}{score}</p>'
                f'<h2 style="margin:0 0 10px;font:bold 22px/1.25 {SERIF};color:{INK}">{escape(a["title"])}</h2>'
                + (f'<p style="margin:0 0 14px;font-size:16px;line-height:1.5;color:{INK}">{escape(a["lead"])}</p>' if a.get("lead") else "")
                + actions
                + (f'<div style="background:{PANEL};border-left:3px solid {AMBER};padding:10px 14px;margin:0 0 16px">'
                   f'<p style="margin:0 0 4px;font-weight:bold;font-size:14px;color:{INK}">Pontos-chave</p>'
                   f'<ul style="margin:0;padding-left:18px;font-size:14px;line-height:1.5">{kp}</ul></div>' if kp else "")
                + (_body_html(a["body"]) if a.get("body") else "")
                + (f'<p style="margin:12px 0 16px;font-size:13px;color:{MUTED}">Fonte: {src}</p>' if src else "")
                + (actions if link and a.get("body") else "")
                + f'<p style="margin:0 0 8px;font-size:12px"><a href="{escape(pr["html_url"])}/files" style="color:{MUTED}">Ver no GitHub</a></p>'
                + f'</td></tr><tr><td style="padding:0 24px"><div style="border-top:1px solid {LINE}"></div></td></tr>')
    head = f"{n} notícia{'s' if n != 1 else ''} à espera da tua revisão · {today:%d/%m/%Y}"
    return (f'<!doctype html><html lang="pt-PT"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"></head>'
            f'<body style="margin:0;padding:0;background:#f3f5f4">'
            f'<div style="display:none;max-height:0;overflow:hidden">{escape(head)}</div>'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f5f4">'
            f'<tr><td align="center" style="padding:20px 10px">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="max-width:640px;background:#ffffff;border:1px solid {LINE};border-radius:6px">'
            f'<tr><td style="padding:20px 24px 4px;font:bold 22px {SERIF};color:{INK}">Fluxo Energético</td></tr>'
            f'<tr><td style="padding:0 24px 16px;font:14px {SANS};color:{MUTED}">{escape(head)}</td></tr>'
            f'<tr><td style="height:3px;background:{AMBER};font-size:0;line-height:0">&nbsp;</td></tr>'
            + "".join(blocks)
            + f'<tr><td style="padding:16px 24px 24px;font:12px/1.5 {SANS};color:{MUTED}">«Aprovar» e «Rejeitar» abrem '
              f'uma página para confirmares com um clique (assim, os antivírus que abrem as ligações dos emails não '
              f'decidem por ti). «Modificar» abre o título, a entrada, os pontos-chave e o texto para corrigires antes '
              f'de publicar. Antes de aprovar: os números e as datas batem certo com a fonte?<br><br>'
              f'— Fluxo Energético (mensagem automática)</td></tr>'
            f'</table></td></tr></table></body></html>')


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
               host: str = "smtp.gmail.com", port: int = 465, html: str | None = None) -> None:
    msg = EmailMessage()
    to = ", ".join(to) if isinstance(to, list) else to
    msg["Subject"], msg["From"], msg["To"] = subject, f"Fluxo Energético <{sender}>", to
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")
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
