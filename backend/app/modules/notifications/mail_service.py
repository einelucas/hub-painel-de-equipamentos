"""Regras editáveis, templates seguros e outbox com envios idempotentes.

Nenhuma mensagem é enviada na transação do workflow. O job de processamento
usa claim com SELECT FOR UPDATE SKIP LOCKED; o Graph responde ACCEPTED, não
confirma que a mensagem chegou ao destinatário.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from string import Formatter
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.errors import ConflictError, DomainError, NotFoundError
from app.models.common import utcnow
from app.models.equipment import Equipment, ProjectContext, WorkflowTransition
from app.models.notification import EmailDelivery, NotificationEvent, NotificationRule
from app.models.user import User
from app.modules.notifications.adapter import DeliveryError, graph_ready, send_mail
from app.modules.notifications.schemas import (
    MailDeliveryOut,
    MailRuleOut,
    MailRuleUpdate,
)
from app.shared.audit import record_audit

logger = logging.getLogger(__name__)
RULES: dict[str, tuple[str, str]] = {
    "KICKOFF": (
        "Contrato escriturado: {equipamento}",
        "Equipamento: {equipamento}\nObra: {obra}\nResponsável: {responsavel}\n"
        "Etapa: {fase}\nEvento: {evento}",
    ),
    "FUP": (
        "Ordem de compra aprovada: {equipamento}",
        "Equipamento: {equipamento}\nObra: {obra}\nResponsável: {responsavel}\n"
        "Etapa: {fase}\nEvento: {evento}",
    ),
    "STARTUP_REMINDER": (
        "Startup previsto: {equipamento}",
        "Equipamento: {equipamento}\nObra: {obra}\nStartup: {data}\n"
        "Responsável: {responsavel}\nEvento: {evento}",
    ),
}
_FIELDS = frozenset({"equipamento", "obra", "fase", "responsavel", "evento", "data"})


def validate_template(text: str) -> None:
    try:
        for _, field, spec, conversion in Formatter().parse(text):
            if field is not None and (field not in _FIELDS or spec or conversion):
                raise DomainError("O modelo contém uma variável não permitida.")
    except ValueError as exc:
        raise DomainError("O modelo contém chaves inválidas.") from exc


def _addresses(raw: str) -> list[str]:
    return [value for value in raw.split(";") if value]


def _public(rule: NotificationRule) -> MailRuleOut:
    return MailRuleOut(
        kind=rule.kind, enabled=rule.enabled, include_responsible=rule.include_responsible,
        days_before=rule.days_before, recipient_emails=_addresses(rule.recipient_emails),
        subject_template=rule.subject_template, body_template=rule.body_template,
    )


async def get_rule(session: AsyncSession, kind: str) -> NotificationRule:
    if kind not in RULES:
        raise NotFoundError("Regra de notificação não encontrada.")
    row = (
        await session.execute(select(NotificationRule).where(NotificationRule.kind == kind))
    ).scalar_one_or_none()
    if row is None:
        subject, body = RULES[kind]
        row = NotificationRule(kind=kind, enabled=False, include_responsible=True,
                               days_before=0, recipient_emails="", subject_template=subject,
                               body_template=body)
        session.add(row)
        await session.flush()
    return row


async def list_rules(session: AsyncSession) -> list[MailRuleOut]:
    return [_public(await get_rule(session, kind)) for kind in RULES]


async def update_rule(
    session: AsyncSession, actor: CurrentUser, kind: str, data: MailRuleUpdate
) -> MailRuleOut:
    if kind != "STARTUP_REMINDER" and data.days_before:
        raise DomainError("Antecedência aplica-se apenas ao lembrete de startup.")
    validate_template(data.subject_template)
    validate_template(data.body_template)
    row = await get_rule(session, kind)
    previous = _public(row).model_dump(mode="json")
    row.enabled = data.enabled
    row.include_responsible = data.include_responsible
    row.days_before = data.days_before
    row.recipient_emails = ";".join(data.recipient_emails)
    row.subject_template = data.subject_template
    row.body_template = data.body_template
    row.updated_at = utcnow()
    await record_audit(
        session, user_id=actor.id, action="notification.rule.update",
        entity="NotificationRule", entity_id=row.id,
        previous_data=previous, new_data=_public(row).model_dump(mode="json"),
    )
    await session.commit()
    return _public(row)


async def _context(session: AsyncSession, equipment: Equipment, kind: str) -> dict[str, str]:
    project = await session.get(ProjectContext, equipment.project_context_id)
    responsible = (
        await session.get(User, equipment.responsible_user_id)
        if equipment.responsible_user_id else None
    )
    return {
        "equipamento": equipment.name,
        "obra": project.name if project else "Não informada",
        "responsavel": responsible.name if responsible else "Não informado",
        "fase": str(equipment.current_stage),
        "evento": kind,
        "data": equipment.startup_at.strftime("%d/%m/%Y") if equipment.startup_at else "Não informada",
    }


async def _recipients(session: AsyncSession, equipment: Equipment, rule: NotificationRule) -> list[str]:
    addresses = _addresses(rule.recipient_emails)
    if rule.include_responsible and equipment.responsible_user_id:
        user = await session.get(User, equipment.responsible_user_id)
        if user and user.active:
            addresses.append(user.email.strip().lower())
    return list(dict.fromkeys(addresses))


async def enqueue_equipment(
    session: AsyncSession, equipment: Equipment, kind: str, key: str
) -> EmailDelivery | None:
    rule = await get_rule(session, kind)
    if not rule.enabled:
        return None
    already = (await session.execute(
        select(EmailDelivery).where(EmailDelivery.dedup_key == key)
    )).scalar_one_or_none()
    if already:
        return already
    values = await _context(session, equipment, kind)
    recipients = await _recipients(session, equipment, rule)
    settings = get_settings()
    status = "PENDING" if recipients or settings.notification_mode == "sandbox" else "SKIPPED"
    row = EmailDelivery(
        dedup_key=key, kind=kind, equipment_id=equipment.id, status=status,
        mode=settings.notification_mode, recipient_summary="; ".join(recipients),
        subject=rule.subject_template.format_map(values),
        body=rule.body_template.format_map(values),
        failure_reason=None if status == "PENDING" else "Sem destinatários configurados.",
    )
    session.add(row)
    await session.flush()
    return row


async def enqueue_transition(
    session: AsyncSession, equipment: Equipment, transition: WorkflowTransition, kind: str
) -> NotificationEvent:
    legacy = (await session.execute(
        select(NotificationEvent).where(
            NotificationEvent.workflow_transition_id == transition.id,
            NotificationEvent.kind == kind,
        )
    )).scalar_one_or_none()
    if legacy is None:
        legacy = NotificationEvent(
            equipment_id=equipment.id, workflow_transition_id=transition.id,
            kind=kind, status="PENDING",
        )
        session.add(legacy)
        await session.flush()
    delivery = await enqueue_equipment(session, equipment, kind, f"transition:{transition.id}:{kind}")
    if delivery:
        legacy.recipient_summary = delivery.recipient_summary
    return legacy


async def enqueue_startup_reminders(session: AsyncSession) -> int:
    rule = await get_rule(session, "STARTUP_REMINDER")
    if not rule.enabled:
        await session.commit()
        return 0
    try:
        today = datetime.now(ZoneInfo(get_settings().notification_timezone)).date()
    except ZoneInfoNotFoundError as exc:
        raise DomainError("NOTIFICATION_TIMEZONE inválido.") from exc
    target = today + timedelta(days=rule.days_before)
    rows = (await session.execute(
        select(Equipment).where(
            Equipment.startup_at == target,
            Equipment.operational_status == "ACTIVE",
        ).order_by(Equipment.id).limit(5000)
    )).scalars().all()
    created = 0
    for equipment in rows:
        key = f"startup:{equipment.id}:{target.isoformat()}:{rule.days_before}"
        if (await session.execute(
            select(EmailDelivery.id).where(EmailDelivery.dedup_key == key)
        )).scalar_one_or_none():
            continue
        if await enqueue_equipment(session, equipment, "STARTUP_REMINDER", key):
            created += 1
    await session.commit()
    return created


async def enqueue_test(session: AsyncSession, actor: CurrentUser, subject: str, body: str) -> EmailDelivery:
    config = get_settings()
    if not config.notification_test_inbox:
        raise DomainError("Configure NOTIFICATION_TEST_INBOX antes de enviar um teste.")
    # Em live, o teste continua restrito à caixa de testes. Em sandbox, Graph
    # redireciona para a mesma caixa independentemente dos destinatários.
    record = EmailDelivery(
        dedup_key=f"test:{uuid4()}", kind="TEST", status="PENDING",
        mode=config.notification_mode, recipient_summary=config.notification_test_inbox,
        subject="[TESTE DE CONFIGURAÇÃO] " + subject, body=body,
    )
    session.add(record)
    await session.flush()
    await record_audit(
        session, user_id=actor.id, action="notification.test.enqueue",
        entity="EmailDelivery", entity_id=record.id,
        new_data={"recipient": config.notification_test_inbox},
    )
    await session.commit()
    return record


async def deliver_pending(limit: int = 20, only_id: str | None = None) -> int:
    """Processa fila pendente. Claim transacional protege workers concorrentes.

    Falha/timeout exige retry manual: sem idempotência no Graph, um retry
    automático de timeout pode duplicar mensagens já aceitas pelo Microsoft 365.
    """
    processed = 0
    for _ in range(min(limit, 100)):
        async with SessionLocal() as session:
            query = select(EmailDelivery).where(EmailDelivery.status == "PENDING")
            if only_id is not None:
                query = query.where(EmailDelivery.id == only_id)
            item = (await session.execute(
                query.order_by(EmailDelivery.created_at, EmailDelivery.id)
                .limit(1).with_for_update(skip_locked=True)
            )).scalar_one_or_none()
            if item is None:
                break
            item.status = "PROCESSING"
            item.processed_at = utcnow()
            item.attempts += 1
            item_id = item.id
            mode = item.mode
            addresses = _addresses(item.recipient_summary.replace(", ", ";").replace("; ", ";"))
            subject, body, dedup_key = item.subject, item.body, item.dedup_key
            await session.commit()
        try:
            config = get_settings()
            # Nunca promover um item sandbox para live só porque o ambiente mudou.
            if mode != config.notification_mode:
                raise DeliveryError("Modo de envio mudou desde a criação do evento; revisão necessária.")
            if mode == "live" and dedup_key.startswith("test:"):
                if not config.notification_test_inbox:
                    raise DeliveryError("Caixa de teste não configurada.")
                addresses = [config.notification_test_inbox]
            result = await send_mail(addresses, subject, body, config)
            failure = None
        except DeliveryError as exc:
            result, failure = "FAILED", str(exc)
        except Exception:
            logger.exception("notification unexpected delivery error id=%s", item_id)
            result, failure = "FAILED", "Falha inesperada no provedor de e-mail."
        async with SessionLocal() as session:
            row = await session.get(EmailDelivery, item_id)
            if row and row.status == "PROCESSING":
                row.status = result
                row.failure_reason = failure
                row.processed_at = utcnow()
                if dedup_key.startswith("transition:"):
                    parts = dedup_key.split(":")
                    legacy = (await session.execute(
                        select(NotificationEvent).where(
                            NotificationEvent.workflow_transition_id == parts[1],
                            NotificationEvent.kind == parts[2],
                        )
                    )).scalar_one_or_none()
                    if legacy:
                        # Evento antigo só diz SENT quando Graph ACEITOU (não entrega).
                        if result == "ACCEPTED":
                            legacy.status = "SENT"
                            legacy.sent_at = utcnow()
                        elif result == "FAILED":
                            legacy.status = "FAILED"
                            legacy.failure_reason = failure
                await session.commit()
        processed += 1
    return processed


async def retry_delivery(session: AsyncSession, actor: CurrentUser, delivery_id: str) -> MailDeliveryOut:
    row = await session.get(EmailDelivery, delivery_id)
    if row is None:
        raise NotFoundError("Envio não encontrado.")
    if row.status != "FAILED":
        raise ConflictError("Somente envios com falha podem ser reenviados.")
    if row.attempts >= 3:
        raise ConflictError("Limite de três tentativas atingido.")
    if row.mode != get_settings().notification_mode:
        raise ConflictError("Modo mudou; reveja o envio antes de tentar novamente.")
    row.status = "PENDING"
    row.failure_reason = None
    row.processed_at = None
    await record_audit(
        session, user_id=actor.id, action="notification.delivery.retry",
        entity="EmailDelivery", entity_id=row.id, new_data={"attempt": row.attempts + 1},
    )
    await session.commit()
    return public_delivery(row)


def public_delivery(row: EmailDelivery) -> MailDeliveryOut:
    return MailDeliveryOut(
        id=row.id, kind=row.kind, equipment_id=row.equipment_id,
        status=row.status, mode=row.mode, recipient_summary=row.recipient_summary,
        subject=row.subject, failure_reason=row.failure_reason,
        attempts=row.attempts, created_at=row.created_at, processed_at=row.processed_at,
    )


def settings_summary() -> dict[str, str | bool | None]:
    config = get_settings()
    return {
        "mode": config.notification_mode,
        "provider": "Microsoft Graph" if config.notification_mode != "log" else "Simulação local",
        "configured": graph_ready(config) if config.notification_mode != "log" else True,
        "sender": config.notification_graph_sender,
        "test_inbox": config.notification_test_inbox,
    }


async def enqueue_startup_reminders_in_new_session() -> int:
    async with SessionLocal() as session:
        return await enqueue_startup_reminders(session)


async def mark_stale_processing() -> int:
    """Crash durante request Graph: resultado indeterminado, NUNCA retry automático."""
    cutoff = utcnow() - timedelta(minutes=15)
    async with SessionLocal() as session:
        rows = (await session.execute(
            select(EmailDelivery).where(
                EmailDelivery.status == "PROCESSING",
                EmailDelivery.processed_at < cutoff,
            ).with_for_update(skip_locked=True)
        )).scalars().all()
        for row in rows:
            row.status = "FAILED"
            row.failure_reason = (
                "Resultado indeterminado após interrupção. Verifique no Graph antes de reenviar."
            )
        await session.commit()
        return len(rows)
