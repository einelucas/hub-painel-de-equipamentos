"""Renderização dos e-mails: layout padrão do Hub, texto alternativo e variáveis.

O HTML gerado usa tabelas e CSS inline (compatível com Gmail, Outlook e
Microsoft 365), sem JavaScript. Modelos avançados são sanitizados antes de
serem armazenados e novamente no momento da renderização.

Variáveis só existem quando o dado existe no banco: campos opcionais são
omitidos do layout e substituídos por um fallback neutro no texto.

A logo INPASA pode ser exibida por URL HTTPS pública usando a variável
INPASA_EMAIL_LOGO_URL. Sem ela, é exibido um cabeçalho tipográfico.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from html import escape
from urllib.parse import urlsplit

from app.core.errors import DomainError
from app.modules.notifications.html_sanitizer import safe_url, sanitize_email_html

# Referências oficiais fornecidas: azul #304F7E, dourado #EAA239, grafite #1E1E1E.
NAVY = "#304F7E"
NAVY_DARK = "#223D63"
GOLD = "#EAA239"
INK = "#1E1E1E"
TEXT = "#344054"
MUTED = "#667085"
BORDER = "#E4E9F0"
BACKGROUND = "#F2F5F8"

KINDS: tuple[str, ...] = (
    "KICKOFF", "FUP", "STARTUP_REMINDER", "NEGOTIATION_OVERDUE",
    "DELIVERY_REMINDER", "COMPLETED",
)

KIND_LABELS: dict[str, str] = {
    "KICKOFF": "Kickoff",
    "FUP": "FUP",
    "STARTUP_REMINDER": "Startup próximo",
    "NEGOTIATION_OVERDUE": "Negociação atrasada",
    "DELIVERY_REMINDER": "Entrega próxima",
    "COMPLETED": "Equipamento concluído",
}

KIND_ACCENTS: dict[str, str] = {
    "KICKOFF": NAVY,
    "FUP": "#3B5F93",
    "STARTUP_REMINDER": "#b0730f",
    "NEGOTIATION_OVERDUE": "#B02F20",
    "DELIVERY_REMINDER": "#B45309",
    "COMPLETED": "#2b6c3b",
}

# Cor clara de preenchimento para alertas, com contraste adequado no texto.
KIND_TINTS: dict[str, str] = {
    "KICKOFF": "#F0F5FB",
    "FUP": "#F0F5FB",
    "STARTUP_REMINDER": "#FFF8EA",
    "NEGOTIATION_OVERDUE": "#FFF2F0",
    "DELIVERY_REMINDER": "#FFF7EC",
    "COMPLETED": "#ECF8F1",
}
KIND_NOTICE_TITLES: dict[str, str] = {
    "KICKOFF": "MARCO REGISTRADO",
    "FUP": "PROCESSO ATUALIZADO",
    "STARTUP_REMINDER": "ATENÇÃO AO CRONOGRAMA",
    "NEGOTIATION_OVERDUE": "AÇÃO NECESSÁRIA",
    "DELIVERY_REMINDER": "PRAZO EM APROXIMAÇÃO",
    "COMPLETED": "ETAPA CONCLUÍDA",
}

ALLOWED_FIELDS = frozenset({
    "equipamento", "tag", "unidade", "obra", "responsavel", "fase", "evento",
    "data", "fornecedor", "prazo_entrega", "dias_restantes", "status",
    "url_equipamento", "criticidade",
})

_DETAIL_FIELDS: tuple[tuple[str, str], ...] = (
    ("equipamento", "Equipamento"),
    ("tag", "TAG"),
    ("unidade", "Unidade"),
    ("obra", "Obra"),
    ("responsavel", "Responsável"),
    ("fase", "Fase"),
    ("criticidade", "Criticidade"),
    ("fornecedor", "Fornecedor"),
    ("prazo_entrega", "Prazo de entrega"),
    ("dias_restantes", "Dias restantes"),
    ("status", "Status"),
)

_KIND_DEFAULT_BODY: dict[str, str] = {
    "KICKOFF": "O contrato do equipamento foi escriturado e a etapa correspondente foi concluída.",
    "FUP": "A ordem de compra foi aprovada e o processo avançou no Hub.",
    "STARTUP_REMINDER": "O startup deste equipamento está programado. Revise o plano e os prazos no Hub.",
    "NEGOTIATION_OVERDUE": "A negociação ultrapassou o prazo calculado e segue pendente.",
    "DELIVERY_REMINDER": "O prazo de entrega em obra se aproxima. Confirme o andamento com o fornecedor.",
    "COMPLETED": "A aquisição do equipamento foi concluída no processo.",
}

DEFAULT_TEMPLATES: dict[str, dict[str, str | bool]] = {
    kind: {
        "subject": f"{KIND_LABELS[kind]}: {{equipamento}}",
        "title": KIND_LABELS[kind],
        "intro": "Atualização automática do processo de aquisição do equipamento.",
        "body": _KIND_DEFAULT_BODY[kind],
        "button_label": "Abrir equipamento no Hub",
        "footer": (
            "Notificação gerada automaticamente pelo Hub de Automação · "
            "Planejamento / Painel de Equipamentos. Não responda a este e-mail."
        ),
        "show_details": True,
        "show_alert": True,
        "show_button": True,
        "show_footer": True,
    }
    for kind in KINDS
}

_PLACEHOLDER = re.compile(r"\{([^{}]*)\}")
_TOKEN = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass(frozen=True, slots=True)
class TemplateContent:
    kind: str
    subject: str
    title: str
    intro: str
    body: str
    button_label: str
    footer: str
    custom_html: str | None = None
    use_custom_html: bool = False
    show_details: bool = True
    show_alert: bool = True
    show_button: bool = True
    show_footer: bool = True


@dataclass(frozen=True, slots=True)
class EmailContext:
    values: dict[str, str]
    present: frozenset[str]
    alert_label: str
    alert_color: str
    criticality: str = ""
    criticality_color: str | None = None
    url: str | None = None

    def has(self, field_name: str) -> bool:
        return field_name in self.present and bool(self.values.get(field_name))


@dataclass(frozen=True, slots=True)
class RenderedEmail:
    subject: str
    html: str
    text: str
    sample: bool = False
    context: EmailContext | None = field(default=None, compare=False)


def default_content(kind: str, *, sample: bool = False) -> TemplateContent:
    raw = DEFAULT_TEMPLATES.get(kind)
    if raw is None:
        raise DomainError("Tipo de notificação desconhecido.")
    return TemplateContent(
        kind=kind,
        subject=str(raw["subject"]),
        title=str(raw["title"]),
        intro=str(raw["intro"]),
        body=str(raw["body"]),
        button_label=str(raw["button_label"]),
        footer=str(raw["footer"]),
        custom_html=None,
        use_custom_html=False,
        show_details=bool(raw["show_details"]),
        show_alert=bool(raw["show_alert"]),
        show_button=bool(raw["show_button"]),
        show_footer=bool(raw["show_footer"]),
    )


def validate_template(text: str) -> None:
    if text.count("{") != text.count("}"):
        raise DomainError("O modelo contém chaves inválidas.")
    for content in _PLACEHOLDER.findall(text):
        field_name = content.strip()
        if field_name not in ALLOWED_FIELDS:
            raise DomainError(f"Variável não permitida: {{{field_name}}}.")


def validate_custom_html(text: str) -> None:
    for field_name in _TOKEN.findall(text):
        if field_name not in ALLOWED_FIELDS:
            raise DomainError(f"Variável não permitida: {{{field_name}}}.")


def validate_content(content: TemplateContent) -> None:
    for value in (
        content.subject, content.title, content.intro, content.body,
        content.button_label, content.footer,
    ):
        validate_template(value)
    if content.use_custom_html:
        if not (content.custom_html or "").strip():
            raise DomainError("Informe o HTML do modelo avançado ou desative o modo avançado.")
        validate_custom_html(content.custom_html or "")


def render_string(text: str, values: Mapping[str, str], *, as_html: bool = False) -> str:
    def replace(match: re.Match[str]) -> str:
        value = values.get(match.group(1), "")
        return escape(value, quote=True) if as_html else value
    return _TOKEN.sub(replace, text)


def sample_context(kind: str, public_app_url: str | None) -> EmailContext:
    today = date.today()
    deadline = today + timedelta(days=15)
    url = public_app_url.rstrip("/") + "/equipamentos" if public_app_url else None
    values = {
        "equipamento": "Bomba centrífuga de exemplo",
        "tag": "TAG-EXEMPLO-001",
        "unidade": "Unidade Exemplo",
        "obra": "Obra Exemplo",
        "responsavel": "Responsável Exemplo",
        "fase": "4",
        "evento": KIND_LABELS.get(kind, kind),
        "data": deadline.strftime("%d/%m/%Y"),
        "fornecedor": "Fornecedor Exemplo",
        "prazo_entrega": deadline.strftime("%d/%m/%Y"),
        "dias_restantes": "15",
        "status": "Ativo",
        "url_equipamento": url or "",
        "criticidade": "Alta",
    }
    return EmailContext(
        values=values,
        present=frozenset(values),
        alert_label=KIND_LABELS.get(kind, kind),
        alert_color=KIND_ACCENTS.get(kind, NAVY),
        criticality="Alta",
        criticality_color="#B02F20",
        url=url,
    )


def _html_text(text: str, values: Mapping[str, str]) -> str:
    return escape(render_string(text, values), quote=False).replace("\r\n", "\n").replace("\n", "<br />")


def _validated_color(value: str | None, fallback: str) -> str:
    return value if value and _HEX_COLOR.fullmatch(value) else fallback


def _detail_rows(context: EmailContext) -> str:
    fields = [(field, label) for field, label in _DETAIL_FIELDS if context.has(field)]
    rows: list[str] = []
    for index, (field_name, label) in enumerate(fields):
        divider = f"border-bottom:1px solid {BORDER};" if index < len(fields) - 1 else ""
        rows.append(
            '<tr>'
            f'<td class="detail-label" width="37%" style="padding:12px 0;{divider}'
            'font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:19px;'
            f'color:{MUTED};vertical-align:top;">{escape(label)}</td>'
            f'<td class="detail-value" style="padding:12px 0;{divider}'
            'font-family:Arial,Helvetica,sans-serif;font-size:13px;line-height:19px;'
            f'color:{INK};font-weight:600;vertical-align:top;word-break:break-word;">'
            f'{escape(context.values[field_name])}</td>'
            '</tr>'
        )
    return "".join(rows)


def _button(url: str, label: str) -> str:
    # Tabela + link: boa compatibilidade com Gmail, Outlook e Microsoft 365.
    return (
        '<table role="presentation" class="button-table" cellpadding="0" cellspacing="0" border="0" '
        'style="margin:23px 0 0;border-collapse:separate;">'
        f'<tr><td align="center" bgcolor="{NAVY}" style="background:{NAVY};border-radius:7px;">'
        f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer" '
        'style="display:inline-block;box-sizing:border-box;padding:15px 23px;'
        'font-family:Arial,Helvetica,sans-serif;font-size:13px;line-height:19px;'
        'font-weight:700;letter-spacing:.1px;color:#FFFFFF;text-decoration:none;'
        f'border-radius:7px;">{escape(label)}&nbsp;&nbsp;&nbsp;<span aria-hidden="true" '
        'style="color:#F2B544;font-size:16px;">&#8594;</span></a></td></tr></table>'
    )


def _brand_header(logo_url: str | None) -> str:
    """Real SVG é oferecido para uso web; e-mail usa PNG por URL HTTPS."""
    image_src = safe_url(logo_url)
    if image_src and urlsplit(image_src).scheme.lower() != "https":
        image_src = None
    if image_src:
        wordmark = (
            f'<img src="{escape(image_src, quote=True)}" alt="INPASA - Mais que Energia" '
            'width="205" style="display:block;width:205px;max-width:100%;height:auto;border:0;" />'
        )
    else:
        # Fallback legível se a logo ainda não tiver sido hospedada.
        wordmark = (
            f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:29px;line-height:30px;'
            f'font-weight:900;letter-spacing:-1.5px;font-style:italic;color:{NAVY};">INPASA</div>'
            f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:9px;line-height:14px;'
            f'font-weight:800;letter-spacing:.7px;color:{GOLD};">MAIS QUE ENERGIA</div>'
        )
    return (
        '<tr><td class="email-padding" style="padding:25px 32px 22px;background:#FFFFFF;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        '<tr><td class="brand-cell" valign="middle" style="width:48%;vertical-align:middle;">'
        f'{wordmark}</td>'
        '<td class="header-info" align="right" valign="middle" '
        f'style="width:52%;padding-left:20px;vertical-align:middle;border-left:1px solid {BORDER};">'
        f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:17px;'
        f'font-weight:800;letter-spacing:.3px;color:{NAVY_DARK};">HUB DE AUTOMAÇÃO</div>'
        f'<div style="padding-top:4px;font-family:Arial,Helvetica,sans-serif;font-size:11px;'
        f'line-height:17px;color:{MUTED};">Planejamento <span style="color:{GOLD};">/</span> '
        'Painel de Equipamentos</div>'
        '</td></tr></table></td></tr>'
    )


def _notice(content: TemplateContent, context: EmailContext, accent: str) -> str:
    """Aviso semântico; mantém conteúdo editável e tags condicionais."""
    body = _html_text(content.body, context.values) if content.body.strip() else ""
    if not content.show_alert:
        return (
            f'<p style="margin:0 0 22px;font-family:Arial,Helvetica,sans-serif;font-size:14px;'
            f'line-height:23px;color:{TEXT};">{body}</p>' if body else ""
        )
    tint = KIND_TINTS.get(content.kind, "#F0F5FB")
    # Não repetir a manchete dentro do aviso quando ambas possuem o mesmo texto.
    rendered_title = render_string(content.title, context.values).strip().casefold()
    show_alert_label = bool(context.alert_label.strip()) and context.alert_label.strip().casefold() != rendered_title
    notice_title = KIND_NOTICE_TITLES.get(content.kind, "ATUALIZAÇÃO DE PROCESSO")
    critical = ""
    if context.criticality:
        severity_color = _validated_color(context.criticality_color, accent)
        critical = (
            '<tr><td style="padding:10px 0 0;">'
            '<span style="font-family:Arial,Helvetica,sans-serif;font-size:11px;'
            f'line-height:17px;color:{severity_color};font-weight:700;">'
            f'CRITICIDADE: {escape(context.criticality.upper())}</span></td></tr>'
        )
    return (
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" '
        f'bgcolor="{tint}" style="background:{tint};border-collapse:separate;margin:0 0 24px;">'
        '<tr>'
        f'<td width="5" bgcolor="{accent}" style="width:5px;background:{accent};font-size:0;line-height:0;">&nbsp;</td>'
        '<td style="padding:18px 20px;">'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">'
        '<tr><td>'
        f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:10px;line-height:16px;'
        f'font-weight:800;letter-spacing:1.1px;color:{accent};">{escape(notice_title)}</div>'
        + (f'<div style="margin:4px 0 0;font-family:Arial,Helvetica,sans-serif;font-size:14px;'
           f'line-height:21px;font-weight:700;color:{NAVY_DARK};">{escape(context.alert_label)}</div>'
           if show_alert_label else '')
        + '</td></tr>'
        + (
            '<tr><td style="padding:11px 0 0;font-family:Arial,Helvetica,sans-serif;'
            f'font-size:13px;line-height:21px;color:{TEXT};">{body}</td></tr>' if body else ""
        ) + critical +
        '</table></td></tr></table>'
    )


def _deadline_metric(content: TemplateContent, context: EmailContext) -> str:
    if content.kind not in {"STARTUP_REMINDER", "DELIVERY_REMINDER"} or not context.has("dias_restantes"):
        return ""
    raw_days = context.values["dias_restantes"].strip()
    try:
        days = int(raw_days)
    except (TypeError, ValueError):
        return ""
    if days < 0:
        return ""  # Não apresentar contagem positiva em um registro vencido.
    text_days = "HOJE" if days == 0 else f"{days} {'DIA RESTANTE' if days == 1 else 'DIAS RESTANTES'}"
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="margin:0 0 26px;border-bottom:1px solid {BORDER};">'
        '<tr><td style="padding:0 0 17px;">'
        f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:11px;line-height:17px;'
        f'font-weight:700;letter-spacing:.7px;color:{MUTED};">CONTAGEM DE PRAZO</div>'
        f'<div style="padding-top:5px;font-family:Arial,Helvetica,sans-serif;font-size:22px;'
        f'line-height:28px;font-weight:800;color:{NAVY_DARK};">{escape(text_days)}</div>'
        '</td>'
        '<td align="right" style="padding:0 0 17px;font-family:Arial,Helvetica,sans-serif;'
        f'font-size:12px;line-height:18px;color:{MUTED};vertical-align:bottom;">'
        + (f'Entrega: {escape(context.values["prazo_entrega"])}' if context.has("prazo_entrega") else "") +
        '</td></tr></table>'
    )


def _details(context: EmailContext) -> str:
    rows = _detail_rows(context)
    if not rows:
        return ""
    return (
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" '
        f'style="border:1px solid {BORDER};border-collapse:separate;border-radius:8px;">'
        '<tr><td style="padding:18px 21px 8px;">'
        f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:10px;line-height:16px;'
        f'letter-spacing:1.25px;font-weight:800;color:{NAVY};">DADOS DO EQUIPAMENTO</div>'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" '
        f'style="margin:9px 0 0;">{rows}</table>'
        '</td></tr></table>'
    )


def _layout(content: TemplateContent, context: EmailContext) -> str:
    accent = _validated_color(context.alert_color, KIND_ACCENTS.get(content.kind, NAVY))
    # A imagem deve estar publicada em HTTPS; clientes de e-mail normalmente bloqueiam data: e SVG.
    logo = os.getenv("INPASA_EMAIL_LOGO_URL", "").strip()
    title = _html_text(content.title, context.values)
    intro = (
        f'<p style="margin:0 0 22px;font-family:Arial,Helvetica,sans-serif;font-size:14px;'
        f'line-height:23px;color:{MUTED};">{_html_text(content.intro, context.values)}</p>'
        if content.intro.strip() else ""
    )
    alert = _notice(content, context, accent)
    deadline = _deadline_metric(content, context)
    details = _details(context) if content.show_details else ""
    url = safe_url(context.url)
    button = _button(url, render_string(content.button_label, context.values)) if (
        content.show_button and url and content.button_label.strip()
    ) else ""
    footer = ""
    if content.show_footer and content.footer.strip():
        footer = (
            f'<tr><td class="email-padding" bgcolor="#F9FAFC" style="padding:21px 32px;'
            f'background:#F9FAFC;border-top:1px solid {BORDER};">'
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
            '<tr><td style="vertical-align:top;">'
            f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:11px;line-height:17px;'
            f'font-weight:800;letter-spacing:.4px;color:{NAVY};">INPASA &nbsp;/&nbsp; COMUNICAÇÃO AUTOMÁTICA</div>'
            f'<p style="margin:6px 0 0;font-family:Arial,Helvetica,sans-serif;font-size:11px;'
            f'line-height:18px;color:{MUTED};">{_html_text(content.footer, context.values)}</p>'
            '</td></tr></table></td></tr>'
        )

    return (
        '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" '
        '"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">'
        '<html xmlns="http://www.w3.org/1999/xhtml" lang="pt-BR">'
        '<head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0" />'
        f'<title>{escape(render_string(content.title, context.values))}</title>'
        '<style type="text/css">'
        'body,table,td,a{-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;}'
        'table,td{mso-table-lspace:0pt;mso-table-rspace:0pt;}'
        'img{-ms-interpolation-mode:bicubic;}'
        '@media only screen and (max-width:620px){'
        '.email-container{width:100%!important;max-width:100%!important;border-radius:0!important;}'
        '.email-padding{padding-left:20px!important;padding-right:20px!important;}'
        '.email-title{font-size:25px!important;line-height:32px!important;}'
        '.brand-cell{width:43%!important;}'
        '.header-info{width:57%!important;padding-left:11px!important;}'
        '.detail-label{width:37%!important;}'
        '.detail-value{width:63%!important;}'
        '.button-table{width:100%!important;}'
        '.button-table a{display:block!important;text-align:center!important;}'
        '}'
        '</style></head>'
        f'<body style="margin:0;padding:0;background:{BACKGROUND};">'
        f'<div style="display:none;font-size:1px;line-height:1px;color:{BACKGROUND};max-height:0;'
        'max-width:0;opacity:0;overflow:hidden;mso-hide:all;">'
        f'{escape(render_string(content.intro or content.title, context.values))}</div>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'bgcolor="{BACKGROUND}" style="background:{BACKGROUND};border-collapse:collapse;">'
        '<tr><td align="center" style="padding:30px 12px 44px;">'
        '<table role="presentation" class="email-container" width="620" cellspacing="0" '
        'cellpadding="0" border="0" bgcolor="#FFFFFF" '
        f'style="width:620px;max-width:620px;background:#FFFFFF;border:1px solid {BORDER};'
        'border-collapse:separate;border-radius:11px;overflow:hidden;">'
        f'<tr><td height="5" bgcolor="{NAVY}" style="height:5px;background:{NAVY};font-size:0;line-height:0;">'
        '&nbsp;</td></tr>'
        f'{_brand_header(logo)}'
        f'<tr><td bgcolor="{BORDER}" height="1" style="height:1px;background:{BORDER};font-size:0;line-height:0;">&nbsp;</td></tr>'
        '<tr><td class="email-padding" style="padding:34px 32px 36px;">'
        f'<div style="margin:0 0 12px;font-family:Arial,Helvetica,sans-serif;'
        f'font-size:10px;line-height:16px;font-weight:800;letter-spacing:1.6px;color:{NAVY};">'
        'PAINEL DE EQUIPAMENTOS &nbsp; <span style="color:#D3A04F;">/</span> &nbsp; NOTIFICAÇÃO</div>'
        f'<h1 class="email-title" style="margin:0 0 12px;font-family:Arial,Helvetica,sans-serif;'
        f'font-size:29px;line-height:36px;font-weight:800;letter-spacing:-.6px;color:{NAVY_DARK};">{title}</h1>'
        f'{intro}{alert}{deadline}{details}{button}'
        '</td></tr>'
        f'{footer}'
        '</table>'
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:18px 0 0;">'
        '<tr><td align="center" style="font-family:Arial,Helvetica,sans-serif;font-size:10px;'
        f'line-height:16px;color:#98A2B3;">INPASA &nbsp;&middot;&nbsp; MAIS QUE ENERGIA</td></tr></table>'
        '</td></tr></table></body></html>'
    )


def render_email(content: TemplateContent, context: EmailContext) -> RenderedEmail:
    validate_content(content)
    subject = render_string(content.subject, context.values).strip()
    if not subject:
        subject = render_string(content.title, context.values).strip()
    subject = subject.replace("\r", " ").replace("\n", " ")
    if content.use_custom_html and content.custom_html:
        substituted = render_string(content.custom_html, context.values, as_html=True)
        html = sanitize_email_html(substituted)
        if not html.strip():
            raise DomainError("O HTML do modelo avançado ficou vazio após a sanitização.")
    else:
        html = _layout(content, context)
    text = render_text(content, context)
    return RenderedEmail(subject=subject, html=html, text=text, context=context)


def render_text(content: TemplateContent, context: EmailContext) -> str:
    lines: list[str] = [render_string(content.title, context.values)]
    if content.intro.strip():
        lines.extend(("", render_string(content.intro, context.values)))
    if content.show_details:
        rows = [
            f"{label}: {context.values[field_name]}"
            for field_name, label in _DETAIL_FIELDS if context.has(field_name)
        ]
        if rows:
            lines.append("")
            lines.extend(rows)
    if content.body.strip():
        lines.extend(("", render_string(content.body, context.values)))
    url = safe_url(context.url)
    if content.show_button and url and content.button_label.strip():
        lines.extend(("", f"{render_string(content.button_label, context.values)}: {url}"))
    if content.show_footer and content.footer.strip():
        lines.extend(("", render_string(content.footer, context.values)))
    return "\n".join(lines).strip() + "\n"
