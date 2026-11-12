"""Prévia, aplicação atômica e recibo idempotente do modo de edição em lote.

Nenhuma edição de workflow, nomes, contratos, SC/OCI ou OC é possível neste
módulo. Cada lote atua em um único ProjectContext ou equipamento pai.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import CurrentUser
from app.core.errors import ConflictError, DomainError, NotFoundError
from app.core.scope import assert_context_allowed, assert_equipment_allowed, user_can_access_unit
from app.models.bulk_edit import BulkEditBatch
from app.models.equipment import Equipment, EquipmentComponent
from app.modules.equipments import services as equipment_services
from app.modules.equipments.bulk_edit_components import (
    ComponentBulkApplyIn,
    ComponentBulkPreviewIn,
    ComponentBulkPreviewOut,
    ComponentFieldDiffOut,
)
from app.modules.equipments.bulk_edit_contracts import (
    EquipmentBulkApplyIn,
    EquipmentBulkApplyOut,
    EquipmentBulkPreviewIn,
    EquipmentBulkPreviewOut,
)
from app.modules.equipments.bulk_edit_preview import preview_equipment_changes
from app.modules.sync.services import record_equipment_sync_event
from app.shared.audit import record_audit

_PREVIEW_TTL = timedelta(minutes=15)
_MAX_ROWS = 100
_COMPONENT_FIELDS = {
    "tag", "sector", "startup_at", "lead_time_days", "pre_start_days",
    "contract_delivery_at", "freight_days",
}


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _ms(value: datetime) -> datetime:
    naive = value.replace(tzinfo=None)
    return naive.replace(microsecond=(naive.microsecond // 1000) * 1000)


def _assert_version(actual: datetime, expected: datetime) -> None:
    if _ms(actual) != _ms(expected):
        raise ConflictError("Registro alterado desde a leitura. Atualize a prévia antes de salvar.")


def _payload(request: Any) -> dict[str, Any]:
    return request.model_dump(mode="json", by_alias=True, exclude={"preview_token", "idempotency_key"})


def _changed(diffs: list[Any]) -> tuple[int, int]:
    changed = {diff.equipment_id if hasattr(diff, "equipment_id") else diff.component_id
               for diff in diffs if diff.skipped_reason is None}
    return len(changed), sum(diff.skipped_reason is not None for diff in diffs)


async def _equipments(
    session: AsyncSession, ids: list[str], context_id: str, *, lock: bool
) -> dict[str, Equipment]:
    stmt = (
        select(Equipment)
        .where(Equipment.id.in_(ids))
        .order_by(Equipment.id)
        .options(selectinload(Equipment.work_package_links))
    )
    if lock:
        stmt = stmt.with_for_update(of=Equipment)
    rows = list((await session.execute(stmt)).scalars().all())
    if len(rows) != len(ids) or any(row.project_context_id != context_id for row in rows):
        raise NotFoundError("Um ou mais equipamentos não pertencem à obra selecionada")
    return {row.id: row for row in rows}


async def _equipment_diffs(
    session: AsyncSession,
    body: EquipmentBulkPreviewIn,
    actor: CurrentUser,
    *,
    lock: bool = False,
) -> tuple[list[Any], dict[str, Equipment]]:
    context = await assert_context_allowed(session, actor, body.project_context_id)
    if not context.active:
        raise DomainError("Obra inativa")
    models = await _equipments(
        session, [row.equipment_id for row in body.items], context.id, lock=lock
    )
    diffs: list[Any] = []
    for row in body.items:
        equipment = models[row.equipment_id]
        _assert_version(equipment.updated_at, row.expected_updated_at)
        current: dict[str, Any] = {}
        for change in row.changes:
            field = change.field
            if field == "work_package_ids":
                current[field] = [link.work_package_id for link in equipment.work_package_links]
            else:
                current[field] = getattr(equipment, field)
        row_diffs = preview_equipment_changes(
            equipment_id=equipment.id, current_values=current, changes=row.changes
        )
        values = {diff.field: diff.proposed_value for diff in row_diffs
                  if diff.skipped_reason is None}
        if values:
            await equipment_services._validate_relations(
                session,
                project_context_id=context.id,
                eap_node_id=values.get("eap_node_id"),
                area_id=None,
                discipline_id=values.get("discipline_id"),
                criticality_label_id=values.get("criticality_label_id"),
                responsible_user_id=values.get("responsible_user_id"),
            )
            if values.get("responsible_user_id") and not await user_can_access_unit(
                session, values["responsible_user_id"], context.unit_id
            ):
                raise DomainError("O responsável não tem acesso à unidade selecionada")
            if "work_package_ids" in values:
                await equipment_services._validate_work_packages(
                    session, work_package_ids=values["work_package_ids"]
                )
        diffs.extend(row_diffs)
    return diffs, models


async def _components(
    session: AsyncSession, equipment_id: str, ids: list[str], *, lock: bool
) -> dict[str, EquipmentComponent]:
    stmt = (
        select(EquipmentComponent)
        .where(EquipmentComponent.id.in_(ids))
        .order_by(EquipmentComponent.id)
    )
    if lock:
        stmt = stmt.with_for_update(of=EquipmentComponent)
    rows = list((await session.execute(stmt)).scalars().all())
    if len(rows) != len(ids) or any(row.equipment_id != equipment_id for row in rows):
        raise NotFoundError("Um ou mais componentes não pertencem ao equipamento")
    return {row.id: row for row in rows}


async def _component_diffs(
    session: AsyncSession, equipment_id: str, body: ComponentBulkPreviewIn,
    actor: CurrentUser, *, lock: bool = False
) -> tuple[list[ComponentFieldDiffOut], dict[str, EquipmentComponent], Equipment]:
    equipment = await assert_equipment_allowed(session, actor, equipment_id)
    rows = await _components(
        session, equipment_id, [item.component_id for item in body.items], lock=lock
    )
    diffs: list[ComponentFieldDiffOut] = []
    for item in body.items:
        component = rows[item.component_id]
        _assert_version(component.updated_at, item.expected_updated_at)
        for change in item.changes:
            field = change.field
            if field not in _COMPONENT_FIELDS:
                raise DomainError("Campo não permitido na edição de componentes")
            before = getattr(component, field)
            empty = before is None or (isinstance(before, str) and not before.strip())
            skipped_reason = None
            proposed = None if change.operation == "CLEAR" else change.value
            if change.operation == "FILL_EMPTY" and not empty:
                proposed = before
                skipped_reason = "ALREADY_FILLED"
            elif proposed == before:
                skipped_reason = "UNCHANGED"
            diffs.append(
                ComponentFieldDiffOut(
                    component_id=component.id, field=field,
                    previous_value=before, proposed_value=proposed,
                    skipped_reason=skipped_reason,
                )
            )
    return diffs, rows, equipment


async def _store_preview(
    session: AsyncSession, *, actor: CurrentUser, context_id: str,
    target: str, request: dict[str, Any], preview: dict[str, Any],
    equipment_id: str | None = None,
) -> str:
    token = secrets.token_urlsafe(40)
    batch = BulkEditBatch(
        preview_token=token,
        actor_user_id=actor.id,
        project_context_id=context_id,
        equipment_id=equipment_id,
        target=target,
        request_payload=request,
        preview_payload=preview,
        expires_at=_now() + _PREVIEW_TTL,
        status="PREVIEW",
        created_at=_now(),
    )
    session.add(batch)
    await session.commit()
    return token


async def preview_equipments(
    session: AsyncSession, body: EquipmentBulkPreviewIn, actor: CurrentUser
) -> EquipmentBulkPreviewOut:
    diffs, _ = await _equipment_diffs(session, body, actor)
    changed, skipped = _changed(diffs)
    data = EquipmentBulkPreviewOut(
        preview_token="pending", requested_count=len(body.items),
        changed_count=changed, skipped_count=skipped, diffs=diffs,
    )
    token = await _store_preview(
        session, actor=actor, context_id=body.project_context_id,
        target="equipment", request=_payload(body),
        preview=data.model_dump(mode="json", by_alias=True),
    )
    data.preview_token = token
    return data


async def preview_components(
    session: AsyncSession, equipment_id: str, body: ComponentBulkPreviewIn, actor: CurrentUser
) -> ComponentBulkPreviewOut:
    diffs, _, equipment = await _component_diffs(session, equipment_id, body, actor)
    changed, skipped = _changed(diffs)
    data = ComponentBulkPreviewOut(
        preview_token="pending", requested_count=len(body.items),
        changed_count=changed, skipped_count=skipped, diffs=diffs,
    )
    token = await _store_preview(
        session, actor=actor, context_id=equipment.project_context_id,
        target="component", equipment_id=equipment_id, request=_payload(body),
        preview=data.model_dump(mode="json", by_alias=True),
    )
    data.preview_token = token
    return data


async def _locked_batch(
    session: AsyncSession, *, token: str, actor: CurrentUser,
    target: str, request: dict[str, Any], idempotency_key: str,
    equipment_id: str | None = None,
) -> BulkEditBatch:
    batch = (await session.execute(
        select(BulkEditBatch).where(BulkEditBatch.preview_token == token).with_for_update()
    )).scalar_one_or_none()
    if (
        batch is None or batch.actor_user_id != actor.id or batch.target != target
        or batch.equipment_id != equipment_id
    ):
        raise NotFoundError("Prévia não encontrada para este usuário e operação")
    if batch.request_payload != request:
        raise ConflictError("As alterações foram modificadas após a prévia")
    if batch.status == "APPLIED":
        if batch.idempotency_key != idempotency_key:
            raise ConflictError("A prévia já foi utilizada por outra confirmação")
        return batch
    if batch.status != "PREVIEW" or batch.expires_at <= _now():
        raise ConflictError("Prévia expirada. Revise novamente antes de salvar")
    existing = (await session.execute(
        select(BulkEditBatch).where(
            BulkEditBatch.actor_user_id == actor.id,
            BulkEditBatch.idempotency_key == idempotency_key,
        )
    )).scalar_one_or_none()
    if existing is not None and existing.id != batch.id:
        raise ConflictError("Esta chave de idempotência já foi usada em outro lote")
    return batch


async def apply_equipments(
    session: AsyncSession, body: EquipmentBulkApplyIn, actor: CurrentUser
) -> EquipmentBulkApplyOut:
    preview_request = EquipmentBulkPreviewIn.model_validate(_payload(body))
    batch = await _locked_batch(
        session, token=body.preview_token, actor=actor, target="equipment",
        request=_payload(preview_request), idempotency_key=body.idempotency_key,
    )
    if batch.status == "APPLIED":
        return EquipmentBulkApplyOut.model_validate(batch.result_payload)
    if batch.project_context_id != body.project_context_id:
        raise ConflictError("A obra não corresponde à prévia")
    diffs, models = await _equipment_diffs(session, preview_request, actor, lock=True)
    recorded = batch.preview_payload.get("diffs")
    fresh = [diff.model_dump(mode="json", by_alias=True) for diff in diffs]
    if fresh != recorded:
        raise ConflictError("Os dados foram alterados depois da prévia")
    touched: set[str] = set()
    for row in preview_request.items:
        relevant = [diff for diff in diffs if diff.equipment_id == row.equipment_id
                    and diff.skipped_reason is None]
        if not relevant:
            continue
        equipment = models[row.equipment_id]
        previous: dict[str, Any] = {}
        changed: dict[str, Any] = {}
        for diff in relevant:
            field = diff.field
            previous[field] = equipment_services._json_value(diff.previous_value)
            changed[field] = equipment_services._json_value(diff.proposed_value)
            if field == "work_package_ids":
                await equipment_services._sync_work_packages(
                    session, equipment=equipment, work_package_ids=diff.proposed_value
                )
            else:
                setattr(equipment, field, diff.proposed_value)
                if field == "criticality_label_id":
                    from app.models.equipment import CriticalityLabel

                    label = await session.get(CriticalityLabel, diff.proposed_value) if (
                        diff.proposed_value is not None
                    ) else None
                    equipment.criticality = label.name if label else None
        equipment.updated_at = _now()
        await record_audit(
            session, user_id=actor.id, action="equipment.bulk_update",
            entity="Equipment", entity_id=equipment.id,
            previous_data=previous, new_data=changed, metadata={"batchId": batch.id},
        )
        await record_equipment_sync_event(
            session, equipment_id=equipment.id,
            actor_user_id=actor.id, changed_fields=sorted(changed),
        )
        touched.add(equipment.id)
    result = EquipmentBulkApplyOut(
        batch_id=batch.id, updated_count=len(touched),
        skipped_count=len(preview_request.items) - len(touched),
    )
    batch.status = "APPLIED"
    batch.idempotency_key = body.idempotency_key
    batch.result_payload = result.model_dump(mode="json", by_alias=True)
    await session.commit()
    return result


async def apply_components(
    session: AsyncSession, equipment_id: str, body: ComponentBulkApplyIn, actor: CurrentUser
) -> EquipmentBulkApplyOut:
    preview_request = ComponentBulkPreviewIn.model_validate(_payload(body))
    batch = await _locked_batch(
        session, token=body.preview_token, actor=actor, target="component",
        equipment_id=equipment_id, request=_payload(preview_request),
        idempotency_key=body.idempotency_key,
    )
    if batch.status == "APPLIED":
        return EquipmentBulkApplyOut.model_validate(batch.result_payload)
    diffs, models, equipment = await _component_diffs(
        session, equipment_id, preview_request, actor, lock=True
    )
    if equipment.project_context_id != batch.project_context_id:
        raise ConflictError("Obra do equipamento mudou desde a prévia")
    fresh = [diff.model_dump(mode="json", by_alias=True) for diff in diffs]
    if fresh != batch.preview_payload.get("diffs"):
        raise ConflictError("Os componentes foram alterados depois da prévia")
    touched: set[str] = set()
    for row in preview_request.items:
        relevant = [diff for diff in diffs if diff.component_id == row.component_id
                    and diff.skipped_reason is None]
        if not relevant:
            continue
        component = models[row.component_id]
        previous: dict[str, Any] = {}
        changed: dict[str, Any] = {}
        for diff in relevant:
            previous[diff.field] = equipment_services._json_value(diff.previous_value)
            changed[diff.field] = equipment_services._json_value(diff.proposed_value)
            setattr(component, diff.field, diff.proposed_value)
        component.updated_at = _now()
        await record_audit(
            session, user_id=actor.id, action="component.bulk_update",
            entity="EquipmentComponent", entity_id=component.id,
            previous_data=previous, new_data=changed, metadata={"batchId": batch.id},
        )
        touched.add(component.id)
    if touched:
        await record_equipment_sync_event(
            session, equipment_id=equipment_id,
            actor_user_id=actor.id, changed_fields=["components"],
        )
    result = EquipmentBulkApplyOut(
        batch_id=batch.id, updated_count=len(touched),
        skipped_count=len(preview_request.items) - len(touched),
    )
    batch.status = "APPLIED"
    batch.idempotency_key = body.idempotency_key
    batch.result_payload = result.model_dump(mode="json", by_alias=True)
    await session.commit()
    return result


async def resolve_filtered_equipments(
    session: AsyncSession, actor: CurrentUser, *,
    project_context_id: str, equipment_id: str | None = None, stage: int | None = None,
    discipline_id: str | None = None, responsible_user_id: str | None = None,
    eap_node_id: str | None = None, work_package_id: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    """Materializa no servidor os IDs/versões de todos os resultados filtrados."""
    await assert_context_allowed(session, actor, project_context_id)
    stmt = equipment_services._apply_filters(
        select(Equipment.id, Equipment.updated_at),
        allowed_units=None, unit_id=None,
        project_context_id=project_context_id, equipment_id=equipment_id,
        search=search, stage=stage, discipline_id=discipline_id,
        responsible_user_id=responsible_user_id, area_id=None,
        eap_node_id=eap_node_id, work_package_id=work_package_id,
    )
    rows = (await session.execute(
        stmt.order_by(Equipment.id).limit(_MAX_ROWS + 1)
    )).all()
    if len(rows) > _MAX_ROWS:
        raise DomainError(
            "Mais de 100 equipamentos encontrados. Refine os filtros para um lote de até 100."
        )
    return {
        "total": len(rows),
        "items": [
            {"equipmentId": equipment_id, "expectedUpdatedAt": stamp.isoformat()}
            for equipment_id, stamp in rows
        ],
    }
