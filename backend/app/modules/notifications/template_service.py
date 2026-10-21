"""Persistência e pré-visualização dos modelos de e-mail por tipo de notificação."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.core.scope import assert_equipment_allowed
from app.domain.equipment_calculations import (
    aggregate_component_deadlines,
    component_deadline_values,
)
from app.models.common import utcnow
from app.models.equipment import (
    CriticalityLabel,
    Equipment,
    EquipmentComponent,
    ProjectContext,
    Unit,
)
from app.models.notification import EmailDelivery, EmailTemplate
from app.models.supplier import EquipmentSupplier, Supplier
from app.models.user import User
from app.modules.notifications.adapter import MailProvider
from app.modules.notifications.html_sanitizer import sanitize_email_html
from app.modules.notifications.schemas import (
    EmailTemplateContent,
    EmailTemplateOut,
    EmailTemplatePreviewOut,
)
from app.modules.notifications.template_renderer import (
    DEFAULT_TEMPLATES,
    KIND_ACCENTS,
    KIND_LABELS,
    KINDS,
    EmailContext,
    RenderedEmail,
    TemplateContent,
    default_content,
    render_email,
    sample_context,
    validate_content,
)
from app.shared.audit import record_audit

_STATUS_LABELS = {
    "ACTIVE": "Ativo",
    "STANDBY": "Em stand-by",
    "CANCELLED": "Cancelado",
    "IN_SANITATION": "Em saneamento",
}


def sample_required(use_sample: bool, mode: str) -> bool:
    """Sandbox nunca envia dados corporativos a provedores externos."""
    return use_sample or mode == "sandbox"


def content_from_row(row: EmailTemplate) -> TemplateContent:
    return TemplateContent(
        kind=row.kind,
        subject=row.subject_template,
        title=row.title_template,
        intro=row.intro_template,
        body=row.body_template,
        button_label=row.button_label,
        footer=row.footer_template,
        custom_html=row.custom_html,
        use_custom_html=row.use_custom_html,
        show_details=row.show_details,
        show_alert=row.show_alert,
        show_button=row.show_button,
        show_footer=row.show_footer,
    )


def public_template(row: EmailTemplate, content: TemplateContent | None = None) -> EmailTemplateOut:
    value = content or content_from_row(row)
    return EmailTemplateOut(
        kind=row.kind,
        subject=value.subject,
        title=value.title,
        intro=value.intro,
        body=value.body,
        button_label=value.button_label,
        footer=value.footer,
        custom_html=value.custom_html,
        use_custom_html=value.use_custom_html,
        show_details=value.show_details,
        show_alert=value.show_alert,
        show_button=value.show_button,
        show_footer=value.show_footer,
        updated_at=row.updated_at,
    )


def _require_kind(kind: str) -> None:
    if kind not in KINDS:
        raise NotFoundError("Tipo de notificação não encontrado.")


def _incoming(data: EmailTemplateContent) -> TemplateContent:
    content = TemplateContent(
        kind="",  # preenchido pelo chamador
        subject=data.subject.strip(),
        title=data.title.strip(),
        intro=data.intro,
        body=data.body,
        button_label=data.button_label.strip(),
        footer=data.footer,
        custom_html=sanitize_email_html(data.custom_html) if data.custom_html else None,
        use_custom_html=data.use_custom_html,
        show_details=data.show_details,
        show_alert=data.show_alert,
        show_button=data.show_button,
        show_footer=data.show_footer,
    )
    validate_content(content)
    return content


async def get_template(session: AsyncSession, kind: str) -> EmailTemplate:
    _require_kind(kind)
    row = (
        await session.execute(select(EmailTemplate).where(EmailTemplate.kind == kind))
    ).scalar_one_or_none()
    if row is not None:
        return row
    # Import tardio evita ciclo: `mail_service` usa este módulo ao enfileirar.
    from app.modules.notifications.mail_service import get_rule

    # Primeira leitura: herda os textos já configurados na regra para não
    # perder personalizações feitas antes da existência dos modelos HTML.
    rule = await get_rule(session, kind)
    defaults = DEFAULT_TEMPLATES[kind]
    await session.execute(
        insert(EmailTemplate)
        .values(
            id=str(uuid4()),
            kind=kind,
            subject_template=rule.subject_template or str(defaults["subject"]),
            title_template=str(defaults["title"]),
            intro_template=str(defaults["intro"]),
            body_template=rule.body_template or str(defaults["body"]),
            button_label=str(defaults["button_label"]),
            footer_template=str(defaults["footer"]),
            custom_html=None,
            use_custom_html=False,
            show_details=bool(defaults["show_details"]),
            show_alert=bool(defaults["show_alert"]),
            show_button=bool(defaults["show_button"]),
            show_footer=bool(defaults["show_footer"]),
            updated_at=utcnow(),
        )
        .on_conflict_do_nothing(index_elements=[EmailTemplate.kind])
    )
    return (
        await session.execute(select(EmailTemplate).where(EmailTemplate.kind == kind))
    ).scalar_one()


async def list_templates(session: AsyncSession) -> list[EmailTemplateOut]:
    return [public_template(await get_template(session, kind)) for kind in KINDS]


async def update_template(
    session: AsyncSession,
    actor: CurrentUser,
    kind: str,
    data: EmailTemplateContent,
) -> EmailTemplateOut:
    row = await get_template(session, kind)
    content = _incoming(data)
    previous = public_template(row).model_dump(mode="json")
    row.subject_template = content.subject
    row.title_template = content.title
    row.intro_template = content.intro
    row.body_template = content.body
    row.button_label = content.button_label
    row.footer_template = content.footer
    row.custom_html = content.custom_html
    row.use_custom_html = content.use_custom_html
    row.show_details = content.show_details
    row.show_alert = content.show_alert
    row.show_button = content.show_button
    row.show_footer = content.show_footer
    row.updated_at = utcnow()
    await record_audit(
        session,
        user_id=actor.id,
        action="notification.template.update",
        entity="EmailTemplate",
        entity_id=row.id,
        previous_data=previous,
        new_data=public_template(row).model_dump(mode="json"),
    )
    await session.commit()
    return public_template(row)


async def reset_template(
    session: AsyncSession, actor: CurrentUser, kind: str
) -> EmailTemplateOut:
    row = await get_template(session, kind)
    previous = public_template(row).model_dump(mode="json")
    defaults = default_content(kind)
    row.subject_template = defaults.subject
    row.title_template = defaults.title
    row.intro_template = defaults.intro
    row.body_template = defaults.body
    row.button_label = defaults.button_label
    row.footer_template = defaults.footer
    row.custom_html = None
    row.use_custom_html = False
    row.show_details = defaults.show_details
    row.show_alert = defaults.show_alert
    row.show_button = defaults.show_button
    row.show_footer = defaults.show_footer
    row.updated_at = utcnow()
    await record_audit(
        session,
        user_id=actor.id,
        action="notification.template.reset",
        entity="EmailTemplate",
        entity_id=row.id,
        previous_data=previous,
        new_data=public_template(row).model_dump(mode="json"),
    )
    await session.commit()
    return public_template(row)


async def _tag(session: AsyncSession, equipment_id: str) -> str:
    value = (
        await session.execute(
            select(EquipmentComponent.tag)
            .where(
                EquipmentComponent.equipment_id == equipment_id,
                EquipmentComponent.tag.is_not(None),
                EquipmentComponent.tag != "",
            )
            .order_by(EquipmentComponent.created_at, EquipmentComponent.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    return value or ""


async def _supplier(session: AsyncSession, equipment_id: str) -> str:
    row = (
        await session.execute(
            select(Supplier.trade_name, Supplier.legal_name)
            .join(EquipmentSupplier, EquipmentSupplier.supplier_id == Supplier.id)
            .where(
                EquipmentSupplier.equipment_id == equipment_id,
                EquipmentSupplier.ended_at.is_(None),
            )
            .limit(1)
        )
    ).first()
    if row is None:
        return ""
    trade_name, legal_name = row
    return (trade_name or "").strip() or (legal_name or "").strip()


async def build_equipment_context(
    session: AsyncSession,
    equipment: Equipment,
    kind: str,
    event_date: date | None = None,
) -> EmailContext:
    """Monta o mesmo contexto para envio real e para pré-visualização."""
    settings = get_settings()
    project = await session.get(ProjectContext, equipment.project_context_id)
    unit = await session.get(Unit, project.unit_id) if project else None
    responsible = (
        await session.get(User, equipment.responsible_user_id)
        if equipment.responsible_user_id
        else None
    )
    criticality_label = (
        await session.get(CriticalityLabel, equipment.criticality_label_id)
        if equipment.criticality_label_id
        else None
    )
    components = (
        await session.execute(
            select(EquipmentComponent).where(
                EquipmentComponent.equipment_id == equipment.id
            )
        )
    ).scalars().all()
    deadlines = aggregate_component_deadlines(
        component_deadline_values(
            startup_at=component.startup_at,
            pre_start_days=component.pre_start_days,
            freight_days=component.freight_days,
            lead_time_days=component.lead_time_days,
        )
        for component in components
    )
    delivery_deadline = (
        event_date
        or deadlines.min_delivery_deadline
        or equipment.contractual_delivery_end
    )
    try:
        today = datetime.now(ZoneInfo(settings.notification_timezone)).date()
    except ZoneInfoNotFoundError:
        today = date.today()

    tag = await _tag(session, equipment.id)
    supplier = await _supplier(session, equipment.id)
    criticality = ""
    criticality_color: str | None = None
    if criticality_label is not None:
        criticality = criticality_label.name
        criticality_color = criticality_label.color
    elif equipment.criticality:
        criticality = equipment.criticality

    public_url = (settings.public_app_url or "").strip().rstrip("/")
    url = f"{public_url}/equipamentos/{equipment.id}" if public_url else None
    event_date_value = event_date or equipment.startup_at
    values = {
        "equipamento": equipment.name,
        "tag": tag,
        "unidade": unit.name if unit else "Não informada",
        "obra": project.name if project else "Não informada",
        "responsavel": responsible.name if responsible else "Não informado",
        "fase": str(equipment.current_stage),
        "evento": KIND_LABELS.get(kind, kind),
        "data": event_date_value.strftime("%d/%m/%Y") if event_date_value else "Não informada",
        "fornecedor": supplier or "Não informado",
        "prazo_entrega": (
            delivery_deadline.strftime("%d/%m/%Y") if delivery_deadline else "Não informado"
        ),
        "dias_restantes": (
            str((delivery_deadline - today).days) if delivery_deadline else ""
        ),
        "status": _STATUS_LABELS.get(equipment.operational_status, equipment.operational_status),
        "url_equipamento": url or "",
        "criticidade": criticality or "Não informada",
    }
    present = {
        "equipamento", "obra", "responsavel", "fase", "evento", "data",
        "unidade", "status",
    }
    for field_name in (
        "tag", "fornecedor", "prazo_entrega", "dias_restantes", "criticidade",
    ):
        if values[field_name] not in {"", "Não informado", "Não informada"}:
            present.add(field_name)
    if url:
        present.add("url_equipamento")
    return EmailContext(
        values=values,
        present=frozenset(present),
        alert_label=KIND_LABELS.get(kind, kind),
        alert_color=KIND_ACCENTS.get(kind, "#304f7e"),
        criticality=criticality,
        criticality_color=criticality_color,
        url=url,
    )


async def _context_for(
    session: AsyncSession,
    actor: CurrentUser,
    kind: str,
    equipment_id: str | None,
    *,
    force_sample: bool,
) -> EmailContext:
    if force_sample or not equipment_id:
        return sample_context(kind, get_settings().public_app_url)
    equipment = await session.get(Equipment, equipment_id)
    if equipment is None:
        raise NotFoundError("Equipamento não encontrado.")
    await assert_equipment_allowed(session, actor, equipment_id)
    return await build_equipment_context(session, equipment, kind)


async def _preview_content(
    content: TemplateContent, kind: str, context: EmailContext
) -> RenderedEmail:
    return render_email(replace(content, kind=kind), context)


async def preview(
    session: AsyncSession,
    actor: CurrentUser,
    kind: str,
    data: EmailTemplateContent,
    *,
    equipment_id: str | None,
    use_sample: bool,
) -> EmailTemplatePreviewOut:
    _require_kind(kind)
    content = _incoming(data)
    context = await _context_for(
        session, actor, kind, equipment_id, force_sample=use_sample
    )
    rendered = await _preview_content(content, kind, context)
    return EmailTemplatePreviewOut(
        subject=rendered.subject,
        html=rendered.html,
        text=rendered.text,
        sample=use_sample or not equipment_id,
    )


async def test_send(
    session: AsyncSession,
    actor: CurrentUser,
    kind: str,
    data: EmailTemplateContent,
    *,
    provider: MailProvider | None,
    equipment_id: str | None,
    use_sample: bool,
) -> tuple[EmailTemplatePreviewOut, EmailDelivery]:
    _require_kind(kind)
    content = _incoming(data)
    config = get_settings()
    # Caixas externas/pessoais só recebem dados fictícios em sandbox.
    sample = sample_required(use_sample, config.notification_mode)
    context = await _context_for(
        session, actor, kind, equipment_id, force_sample=sample
    )
    rendered = await _preview_content(content, kind, context)
    from app.modules.notifications import mail_service

    delivery = await mail_service.enqueue_test(
        session,
        actor,
        rendered.subject,
        rendered.text,
        html=rendered.html,
        provider=provider,
    )
    await mail_service.deliver_pending(only_id=delivery.id)
    await session.refresh(delivery)
    preview_out = EmailTemplatePreviewOut(
        subject=rendered.subject,
        html=rendered.html,
        text=rendered.text,
        sample=sample or not equipment_id,
    )
    return preview_out, delivery
