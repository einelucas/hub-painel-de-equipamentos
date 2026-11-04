from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import CurrentUser
from app.core.errors import ConflictError, DomainError, NotFoundError
from app.core.scope import (
    allowed_unit_ids,
    assert_context_allowed,
    assert_unit_allowed,
)
from app.core.storage import get_contract_file_storage
from app.domain.eap import EapLevel, validate_eap_node
from app.models.equipment import (
    Area,
    CriticalityLabel,
    Discipline,
    EapNode,
    Equipment,
    EquipmentComponent,
    EquipmentWorkPackage,
    ProjectContext,
    ProjectEap,
    Unit,
    WorkflowTransition,
    WorkPackage,
)
from app.models.master_catalog import MasterProjectCreation
from app.models.monday_import import (
    ExternalMapping,
    MondayApplyJob,
    MondayImportBatch,
    MondayImportIssue,
    MondayImportRecord,
    MondayMigrationRun,
)
from app.models.notification import EmailDelivery, NotificationEvent, UserNotification
from app.models.process import Contract, LegalProcess, Negotiation, PurchaseOrder, PurchaseRequest
from app.models.supplier import EquipmentSupplier
from app.models.sync import ContractFileCleanup
from app.models.workflow_extras import (
    Comment,
    OperationalStatusEvent,
    ReopenRequest,
    RequirementWaiver,
    WorkflowException,
)
from app.modules.sync.services import record_sync_event
from app.shared.audit import record_audit

logger = logging.getLogger(__name__)


async def _list(session: AsyncSession, model: type[Any], *filters: Any) -> list[Any]:
    stmt = select(model).where(*filters).order_by(model.name.asc())
    return list((await session.execute(stmt)).scalars().all())


def _situation(model: type[Any], include_inactive: bool) -> tuple[Any, ...]:
    """Padrão: só ativos (telas operacionais). Inativos só na visão de administração,
    cuja permissão é checada no controller."""
    return () if include_inactive else (model.active.is_(True),)


async def list_units(
    session: AsyncSession, actor: CurrentUser, *, include_inactive: bool = False
) -> list[Unit]:
    """Só as unidades que o usuário pode ver — a base do filtro global."""
    allowed = await allowed_unit_ids(session, actor)
    if allowed is None:
        return await _list(session, Unit, *_situation(Unit, include_inactive))
    if not allowed:
        return []
    return await _list(session, Unit, *_situation(Unit, include_inactive), Unit.id.in_(allowed))


async def list_project_contexts(
    session: AsyncSession, actor: CurrentUser, unit_id: str, *, include_inactive: bool = False
) -> list[ProjectContext]:
    if await session.get(Unit, unit_id) is None:
        raise NotFoundError("Unidade não encontrada")
    await assert_unit_allowed(session, actor, unit_id)
    return await _list(
        session,
        ProjectContext,
        ProjectContext.unit_id == unit_id,
        *_situation(ProjectContext, include_inactive),
    )


async def list_eap_nodes(
    session: AsyncSession, *, level: str | None, parent_id: str | None, active: bool | None
) -> list[EapNode]:
    """Catálogo corporativo: não pertence a uma unidade, então não há escopo."""
    stmt = select(EapNode).order_by(EapNode.code.asc())
    if level is not None:
        stmt = stmt.where(EapNode.level == level)
    if parent_id is not None:
        stmt = stmt.where(EapNode.parent_id == parent_id)
    if active is not None:
        stmt = stmt.where(EapNode.active.is_(active))
    return list((await session.execute(stmt)).scalars().all())


async def create_eap_node(
    session: AsyncSession,
    *,
    code: str,
    name: str,
    level: EapLevel,
    parent_id: str | None,
    actor: CurrentUser,
) -> EapNode:
    """Cria um nó global da árvore EAP sem inferir obra, unidade ou pai.

    A estrutura é validada com a mesma regra de domínio usada pelo catálogo
    oficial. Criar o nó não cria `ProjectEap`: esse vínculo continua explícito.
    """
    code = code.strip()
    name = name.strip()
    if not name:
        raise ConflictError("Nome da EAP é obrigatório")
    if await session.scalar(select(EapNode.id).where(EapNode.code == code)) is not None:
        raise ConflictError("Já existe um nó EAP com este código")

    parent = await session.get(EapNode, parent_id) if parent_id is not None else None
    if parent_id is not None and parent is None:
        raise NotFoundError("Nó pai da EAP não encontrado")
    errors = validate_eap_node(
        code=code,
        level=level,
        parent_code=parent.code if parent is not None else None,
        parent_level=EapLevel(parent.level) if parent is not None else None,
    )
    if errors:
        raise DomainError("; ".join(errors))

    item = EapNode(
        code=code,
        name=name,
        level=level.value,
        parent_id=parent_id,
    )
    session.add(item)
    await session.flush()
    await record_audit(
        session,
        user_id=actor.id,
        action="catalog.create",
        entity="EapNode",
        entity_id=item.id,
        new_data={
            "code": code,
            "name": name,
            "level": level.value,
            "parentId": parent_id,
        },
    )
    await session.commit()
    await session.refresh(item)
    return item


async def list_project_eap_nodes(
    session: AsyncSession, actor: CurrentUser, project_context_id: str
) -> list[ProjectEap]:
    await assert_context_allowed(session, actor, project_context_id)
    stmt = (
        select(ProjectEap)
        .join(EapNode, ProjectEap.eap_node_id == EapNode.id)
        .where(
            ProjectEap.project_context_id == project_context_id,
            ProjectEap.active.is_(True),
            EapNode.active.is_(True),
        )
        .options(selectinload(ProjectEap.eap_node))
        .order_by(EapNode.code.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def list_areas(
    session: AsyncSession, actor: CurrentUser, unit_id: str, *, include_inactive: bool = False
) -> list[Area]:
    await assert_unit_allowed(session, actor, unit_id)
    return await _list(session, Area, Area.unit_id == unit_id, *_situation(Area, include_inactive))


async def list_disciplines(session: AsyncSession, *, include_inactive: bool = False) -> list[Discipline]:
    """Disciplinas são globais: não pertencem a uma unidade."""
    return await _list(session, Discipline, *_situation(Discipline, include_inactive))


async def list_criticality_labels(
    session: AsyncSession, *, include_inactive: bool = False
) -> list[CriticalityLabel]:
    """Etiquetas globais, independentes de unidade e obra."""
    return await _list(session, CriticalityLabel, *_situation(CriticalityLabel, include_inactive))


async def list_work_packages(
    session: AsyncSession, *, include_inactive: bool = False
) -> list[WorkPackage]:
    """Catálogo corporativo global, assim como EAP e disciplinas."""
    return await _list(session, WorkPackage, *_situation(WorkPackage, include_inactive))


async def create_catalog(
    session: AsyncSession,
    model: type[Any],
    *,
    values: dict[str, object],
    actor: CurrentUser,
) -> Any:
    values = {key: value.strip() if isinstance(value, str) else value for key, value in values.items()}
    if not values.get("name"):
        raise ConflictError("Nome do catálogo é obrigatório")

    if model in (ProjectContext, Area):
        parent_id = str(values["unit_id"])
        if await session.get(Unit, parent_id) is None:
            raise NotFoundError("Unidade não encontrada")
        await assert_unit_allowed(session, actor, parent_id)
    elif model is WorkPackage:
        # Clientes antigos ainda podem enviar projectContextId. Ele não define
        # identidade nem escopo e não é persistido em novos registros.
        values.pop("project_context_id", None)

    conditions = []
    if "code" in values:
        conditions.append(model.code == values["code"])
    else:
        conditions.append(model.name == values["name"])
    if "unit_id" in values:
        conditions.append(model.unit_id == values["unit_id"])
    if "project_context_id" in values and model is not WorkPackage:
        conditions.append(model.project_context_id == values["project_context_id"])
    if (await session.execute(select(model.id).where(*conditions))).scalar_one_or_none() is not None:
        raise ConflictError("Já existe um registro equivalente neste catálogo")

    item = model(**values)
    session.add(item)
    await session.flush()
    await record_audit(
        session,
        user_id=actor.id,
        action="catalog.create",
        entity=model.__name__,
        entity_id=item.id,
        new_data=values,
    )
    if model is ProjectContext:
        await record_sync_event(
            session,
            event_type="created",
            entity_type="project_context",
            entity_id=item.id,
            unit_id=item.unit_id,
            project_context_id=item.id,
            actor_user_id=actor.id,
            payload={"name": item.name, "code": item.code},
        )
    await session.commit()
    await session.refresh(item)
    return item


async def update_catalog(
    session: AsyncSession,
    model: type[Any],
    *,
    item_id: str,
    changes: dict[str, object],
    actor: CurrentUser,
) -> Any:
    """Edição e ativação/desativação. Exclusão física fica em delete_catalog."""
    item = await session.get(model, item_id)
    if item is None:
        raise NotFoundError("Registro de catálogo não encontrado")
    if model is ProjectContext:
        await assert_unit_allowed(session, actor, item.unit_id)
    changes = {
        key: value.strip() if isinstance(value, str) else value for key, value in changes.items()
    }
    if "name" in changes and not changes["name"]:
        raise ConflictError("Nome do catálogo é obrigatório")

    for field in ("code", "name"):
        if field not in changes or not hasattr(model, field) or changes[field] is None:
            continue
        conditions = [getattr(model, field) == changes[field], model.id != item_id]
        if hasattr(model, "unit_id"):
            conditions.append(model.unit_id == item.unit_id)
        if hasattr(model, "project_context_id") and model is not WorkPackage:
            conditions.append(model.project_context_id == item.project_context_id)
        duplicated = (
            await session.execute(select(model.id).where(*conditions))
        ).scalar_one_or_none()
        if duplicated is not None:
            raise ConflictError("Já existe um registro equivalente neste catálogo")

    previous: dict[str, object] = {}
    changed: dict[str, object] = {}
    for field, value in changes.items():
        if getattr(item, field) != value:
            previous[field] = getattr(item, field)
            changed[field] = value
            setattr(item, field, value)
    if changed:
        await record_audit(
            session,
            user_id=actor.id,
            action="catalog.update",
            entity=model.__name__,
            entity_id=item.id,
            previous_data=previous,
            new_data=changed,
        )
        if model is ProjectContext:
            await record_sync_event(
                session,
                event_type="updated",
                entity_type="project_context",
                entity_id=item.id,
                unit_id=item.unit_id,
                project_context_id=item.id,
                actor_user_id=actor.id,
                payload={"changedFields": sorted(changed)},
            )
    await session.commit()
    await session.refresh(item)
    return item


async def _count(session: AsyncSession, stmt: Any) -> int:
    return int((await session.execute(stmt)).scalar_one())


async def project_context_deletion_impact(
    session: AsyncSession, *, item_id: str, actor: CurrentUser
) -> dict[str, object]:
    context = await assert_context_allowed(session, actor, item_id)
    equipment_ids = select(Equipment.id).where(Equipment.project_context_id == item_id)
    batch_ids = select(MondayImportBatch.id).where(MondayImportBatch.project_context_id == item_id)

    scoped_counts: tuple[tuple[str, type[Any], Any], ...] = (
        ("equipments", Equipment, Equipment.project_context_id == item_id),
        ("components", EquipmentComponent, EquipmentComponent.equipment_id.in_(equipment_ids)),
        ("negotiations", Negotiation, Negotiation.equipment_id.in_(equipment_ids)),
        ("legalProcesses", LegalProcess, LegalProcess.equipment_id.in_(equipment_ids)),
        ("contracts", Contract, Contract.equipment_id.in_(equipment_ids)),
        ("purchaseRequests", PurchaseRequest, PurchaseRequest.equipment_id.in_(equipment_ids)),
        ("purchaseOrders", PurchaseOrder, PurchaseOrder.equipment_id.in_(equipment_ids)),
        ("supplierLinks", EquipmentSupplier, EquipmentSupplier.equipment_id.in_(equipment_ids)),
        ("workPackageLinks", EquipmentWorkPackage, EquipmentWorkPackage.equipment_id.in_(equipment_ids)),
        ("workflowTransitions", WorkflowTransition, WorkflowTransition.equipment_id.in_(equipment_ids)),
        ("workflowEvents", OperationalStatusEvent, OperationalStatusEvent.equipment_id.in_(equipment_ids)),
        ("workflowExceptions", WorkflowException, WorkflowException.equipment_id.in_(equipment_ids)),
        ("reopenRequests", ReopenRequest, ReopenRequest.equipment_id.in_(equipment_ids)),
        ("requirementWaivers", RequirementWaiver, RequirementWaiver.equipment_id.in_(equipment_ids)),
        ("comments", Comment, Comment.equipment_id.in_(equipment_ids)),
        ("notificationEvents", NotificationEvent, NotificationEvent.equipment_id.in_(equipment_ids)),
        ("userNotifications", UserNotification, UserNotification.equipment_id.in_(equipment_ids)),
        ("emailDeliveries", EmailDelivery, EmailDelivery.equipment_id.in_(equipment_ids)),
        ("projectEapLinks", ProjectEap, ProjectEap.project_context_id == item_id),
        ("importBatches", MondayImportBatch, MondayImportBatch.project_context_id == item_id),
        ("importRecords", MondayImportRecord, MondayImportRecord.batch_id.in_(batch_ids)),
        ("importIssues", MondayImportIssue, MondayImportIssue.batch_id.in_(batch_ids)),
        ("migrationRuns", MondayMigrationRun, MondayMigrationRun.project_context_id == item_id),
        ("applyJobs", MondayApplyJob, MondayApplyJob.project_context_id == item_id),
        ("externalMappings", ExternalMapping, ExternalMapping.project_context_id == item_id),
        ("creationRequests", MasterProjectCreation, MasterProjectCreation.project_context_id == item_id),
    )
    records: dict[str, int] = {}
    for label, model, condition in scoped_counts:
        records[label] = await _count(
            session, select(func.count()).select_from(model).where(condition)
        )
    contract_files = await _count(
        session,
        select(func.count())
        .select_from(Contract)
        .where(Contract.equipment_id.in_(equipment_ids), Contract.file_storage_key.is_not(None)),
    )
    return {
        "project_context_id": context.id,
        "project_context_name": context.name,
        "records": records,
        "total_records": sum(records.values()),
        "contract_files": contract_files,
    }


async def _try_contract_file_cleanup(session: AsyncSession, cleanup_ids: list[str]) -> None:
    """Tenta limpar storage depois do commit; falhas permanecem na outbox."""
    if not cleanup_ids:
        return
    try:
        storage = get_contract_file_storage()
    except Exception as exc:
        logger.warning("contract cleanup provider unavailable: %s", exc)
        return
    for cleanup_id in cleanup_ids:
        cleanup = await session.get(ContractFileCleanup, cleanup_id)
        if cleanup is None:
            continue
        try:
            await storage.delete(cleanup.storage_key)
            await session.delete(cleanup)
        except Exception as exc:  # storage externo: a fila durável preserva o retry
            cleanup.last_error = str(exc)[:2000]
            logger.warning("contract cleanup deferred key=%s: %s", cleanup.storage_key, exc)
    await session.commit()


async def delete_project_context_cascade(
    session: AsyncSession,
    *,
    item_id: str,
    confirmation_name: str,
    actor: CurrentUser,
) -> None:
    """Remove uma obra e somente sua subárvore exclusiva, atomicamente."""
    context = (
        await session.execute(
            select(ProjectContext).where(ProjectContext.id == item_id).with_for_update()
        )
    ).scalar_one_or_none()
    if context is None:
        raise NotFoundError("Contexto de projeto não encontrado")
    await assert_unit_allowed(session, actor, context.unit_id)
    if confirmation_name.strip() != context.name:
        raise ConflictError("Digite exatamente o nome da obra para confirmar a exclusão")

    impact = await project_context_deletion_impact(session, item_id=item_id, actor=actor)
    equipment_ids = select(Equipment.id).where(Equipment.project_context_id == item_id)
    file_keys = [
        key
        for key in
        (
            await session.execute(
                select(Contract.file_storage_key).where(
                    Contract.equipment_id.in_(equipment_ids),
                    Contract.file_storage_key.is_not(None),
                )
            )
        ).scalars()
        if key is not None
    ]
    cleanup_ids: list[str] = []
    for key in sorted(set(file_keys)):
        cleanup = ContractFileCleanup(storage_key=key, reason="PROJECT_CONTEXT_DELETED")
        session.add(cleanup)
        await session.flush()
        cleanup_ids.append(cleanup.id)

    # Estas caixas/outboxes usam SET NULL para preservar histórico quando um
    # equipamento isolado some. Na exclusão integral da obra são dados
    # exclusivamente ligados à subárvore e não devem virar avisos órfãos.
    await session.execute(delete(UserNotification).where(UserNotification.equipment_id.in_(equipment_ids)))
    await session.execute(delete(EmailDelivery).where(EmailDelivery.equipment_id.in_(equipment_ids)))
    await session.execute(
        update(WorkPackage)
        .where(WorkPackage.project_context_id == item_id)
        .values(project_context_id=None)
    )

    previous = {
        "name": context.name,
        "code": context.code,
        "active": context.active,
        "unitId": context.unit_id,
    }
    await record_audit(
        session,
        user_id=actor.id,
        action="project_context.delete_cascade",
        entity="ProjectContext",
        entity_id=context.id,
        previous_data=previous,
        metadata={"impact": impact["records"], "totalRecords": impact["total_records"]},
    )
    await record_sync_event(
        session,
        event_type="deleted",
        entity_type="project_context",
        entity_id=context.id,
        unit_id=context.unit_id,
        project_context_id=context.id,
        actor_user_id=actor.id,
        payload={"name": context.name, "impact": impact["records"]},
    )
    await session.delete(context)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    await _try_contract_file_cleanup(session, cleanup_ids)


async def delete_catalog(
    session: AsyncSession,
    model: type[Any],
    *,
    item_id: str,
    actor: CurrentUser,
) -> None:
    """Exclusão física de um registro de catálogo ainda sem vínculos.

    Registros em uso são preservados: a mensagem orienta a desativar em vez de
    apagar, evitando perder classificação/histórico dos equipamentos. Vínculos
    que só existem por causa do próprio registro (EAP da obra e idempotência da
    criação via Catálogo Mestre) são removidos junto com a obra.
    """
    item = await session.get(model, item_id)
    if item is None:
        raise NotFoundError("Registro de catálogo não encontrado")

    reasons: list[str] = []
    if model is Unit:
        contexts = await _count(
            session, select(func.count()).select_from(ProjectContext).where(ProjectContext.unit_id == item_id)
        )
        areas = await _count(session, select(func.count()).select_from(Area).where(Area.unit_id == item_id))
        if contexts:
            reasons.append(f"{contexts} obra(s) vinculada(s)")
        if areas:
            reasons.append(f"{areas} área(s) vinculada(s)")
    elif model is ProjectContext:
        equipments = await _count(
            session,
            select(func.count()).select_from(Equipment).where(Equipment.project_context_id == item_id),
        )
        if equipments:
            reasons.append(f"{equipments} equipamento(s) vinculado(s)")
    elif model is Area:
        equipments = await _count(
            session, select(func.count()).select_from(Equipment).where(Equipment.area_id == item_id)
        )
        if equipments:
            reasons.append(f"{equipments} equipamento(s) usando esta área")
    elif model is Discipline:
        equipments = await _count(
            session, select(func.count()).select_from(Equipment).where(Equipment.discipline_id == item_id)
        )
        if equipments:
            reasons.append(f"{equipments} equipamento(s) usando esta disciplina")
    elif model is CriticalityLabel:
        equipments = await _count(
            session,
            select(func.count()).select_from(Equipment).where(Equipment.criticality_label_id == item_id),
        )
        if equipments:
            reasons.append(f"{equipments} equipamento(s) usando esta criticidade")
    elif model is WorkPackage:
        equipments = await _count(
            session, select(func.count()).select_from(Equipment).where(Equipment.work_package_id == item_id)
        )
        links = await _count(
            session,
            select(func.count())
            .select_from(EquipmentWorkPackage)
            .where(EquipmentWorkPackage.work_package_id == item_id),
        )
        if equipments:
            reasons.append(f"{equipments} equipamento(s) usando esta WP")
        if links:
            reasons.append(f"{links} vínculo(s) de equipamento")
    elif model is EapNode:
        children = await _count(
            session, select(func.count()).select_from(EapNode).where(EapNode.parent_id == item_id)
        )
        project_links = await _count(
            session, select(func.count()).select_from(ProjectEap).where(ProjectEap.eap_node_id == item_id)
        )
        equipments = await _count(
            session, select(func.count()).select_from(Equipment).where(Equipment.eap_node_id == item_id)
        )
        if children:
            reasons.append(f"{children} nó(s) filho(s) na árvore")
        if project_links:
            reasons.append(f"{project_links} vínculo(s) com obras")
        if equipments:
            reasons.append(f"{equipments} equipamento(s) usando este nó")
    else:
        raise DomainError("Tipo de catálogo desconhecido")

    name = item.name
    if reasons:
        raise ConflictError(
            f'Não é possível excluir "{name}": '
            + ", ".join(reasons)
            + ". Desative o registro em vez de excluí-lo."
        )

    previous: dict[str, object] = {"name": name, "active": item.active}
    if hasattr(item, "code"):
        previous["code"] = item.code
    await record_audit(
        session,
        user_id=actor.id,
        action="catalog.delete",
        entity=model.__name__,
        entity_id=item.id,
        previous_data=previous,
    )

    if model is ProjectContext:
        # Vínculos que existem apenas por causa desta obra; se houver histórico
        # de importação (monday_import_*) o FK RESTRICT aborta e preserva tudo.
        await session.execute(delete(ProjectEap).where(ProjectEap.project_context_id == item_id))
        await session.execute(
            delete(MasterProjectCreation).where(MasterProjectCreation.project_context_id == item_id)
        )
        await session.execute(
            update(WorkPackage)
            .where(WorkPackage.project_context_id == item_id)
            .values(project_context_id=None)
        )

    await session.delete(item)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(
            f'Não é possível excluir "{name}": existem registros vinculados. '
            "Desative o registro em vez de excluí-lo."
        ) from exc
