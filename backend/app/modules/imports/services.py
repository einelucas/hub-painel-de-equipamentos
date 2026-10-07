"""Camada HTTP fina da importação Monday (P1.3 / P1.3.1).

Só autoriza, valida a requisição e chama o motor `app.modules.monday_import`
(parser, staging, mapping, plan, apply, reconciliation). Nenhuma regra de
importação é reimplementada aqui.

Esta etapa (análise) grava SOMENTE staging — MondayImportBatch, MondayImportRecord
e MondayImportIssue. Nenhum Equipment, componente, contrato, SC/OCI, OC ou vínculo
de fornecedor é criado ou alterado; isso só acontece no apply confirmado.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.errors import ConflictError, DomainError, NotFoundError
from app.core.scope import assert_context_allowed
from app.models.monday_import import MondayImportBatch, MondayImportIssue, MondayImportRecord
from app.modules.imports.schemas import (
    CatalogItemOut,
    EapSummaryOut,
    ImportApplyOut,
    ImportBatchOut,
    ImportDivergenceOut,
    ImportIssueOut,
    ImportPlanOut,
    ImportProfileOut,
    ImportProfileRef,
    ImportReconciliationOut,
    LocationValueOut,
    MappingIssueOut,
    PlanBlockedOut,
    PlanGroupOut,
    PlanIssueOut,
    ResponsibleSummaryOut,
    SourceValuesOut,
    SupplierSuggestionOut,
)
from app.modules.monday_import.apply import (
    PlanBlockedError,
    PlanStaleError,
    apply_plan,
)
from app.modules.monday_import.catalog_planner import CatalogPlanItem
from app.modules.monday_import.catalog_sources import default_catalog_evidence
from app.modules.monday_import.domain_reconciliation import reconcile_domain
from app.modules.monday_import.eap_resolution import EapResolver
from app.modules.monday_import.mapping_file import MappingFileSchema, ValidatedMapping, validate_mapping
from app.modules.monday_import.normalization import canonical_text
from app.modules.monday_import.plan import MigrationPlan, build_plan
from app.modules.monday_import.profile import (
    ImportProfileError,
    load_runtime_profile,
    runtime_profiles,
)
from app.modules.monday_import.service import StagedWithDifferentProfileError, stage_import
from app.modules.monday_import.xlsx import XlsxReadError
from app.modules.suppliers.suggestions import SupplierSuggestionResolver

logger = logging.getLogger(__name__)

ALLOWED_EXTENSION = ".xlsx"


def list_profiles() -> list[ImportProfileOut]:
    return [
        ImportProfileOut(
            profile_id=profile.profile_id,
            version=profile.version,
            source_system=profile.source_system,
            description=profile.description,
        )
        for profile in runtime_profiles()
    ]


async def _context_for_import(session: AsyncSession, actor: CurrentUser, project_context_id: str) -> None:
    """Escopo por unidade (nunca só a UI) e só contextos ativos recebem nova importação."""
    context = await assert_context_allowed(session, actor, project_context_id)
    if not context.active:
        raise DomainError("Contexto de projeto inativo: reative-o na administração antes de importar.")


def validate_upload(file_name: str | None, size: int, max_bytes: int) -> str:
    name = (file_name or "").strip()
    if not name.lower().endswith(ALLOWED_EXTENSION):
        raise DomainError("Envie um arquivo .xlsx exportado do Monday.")
    if size == 0:
        raise DomainError("Arquivo vazio.")
    if size > max_bytes:
        raise DomainError(f"Arquivo excede o limite de {max_bytes // (1024 * 1024)} MB.")
    return name


async def stage_upload(
    session: AsyncSession,
    actor: CurrentUser,
    *,
    project_context_id: str,
    profile_id: str,
    file_name: str,
    content: bytes,
) -> ImportBatchOut:
    await _context_for_import(session, actor, project_context_id)
    try:
        profile = load_runtime_profile(profile_id)
    except ImportProfileError as exc:
        raise DomainError("Formato de planilha (profile) desconhecido.") from exc
    try:
        result = await stage_import(
            session,
            project_context_id=project_context_id,
            source=content,
            source_name=file_name,
            profile=profile,
        )
    except XlsxReadError as exc:
        raise DomainError(f"Arquivo não é um XLSX válido: {exc}") from exc
    except StagedWithDifferentProfileError as exc:
        raise ConflictError(
            "Este arquivo já foi analisado nesta obra com outro formato de planilha."
        ) from exc
    batch = await session.get(MondayImportBatch, result.batch_id)
    assert batch is not None
    summary = await _summary(session, batch, already_staged=not result.created and not result.restaged)
    # Só identificadores e contagens: nunca conteúdo de células.
    logger.info(
        "monday import staged batch=%s sha256=%s profile=%s created=%s equipments=%s components=%s errors=%s",
        batch.id,
        batch.file_sha256,
        profile.profile_id,
        result.created,
        summary.equipments,
        summary.components,
        summary.errors,
    )
    return summary


async def get_batch(session: AsyncSession, actor: CurrentUser, batch_id: str) -> MondayImportBatch:
    batch = await session.get(MondayImportBatch, batch_id)
    if batch is None:
        raise NotFoundError("Análise de importação não encontrada")
    # Mesmo escopo da obra: fora da unidade autorizada o batch "não existe".
    await assert_context_allowed(session, actor, batch.project_context_id)
    return batch


async def batch_summary(session: AsyncSession, actor: CurrentUser, batch_id: str) -> ImportBatchOut:
    return await _summary(session, await get_batch(session, actor, batch_id), already_staged=True)


def _distinct(values: list[Any]) -> list[str]:
    seen: dict[str, str] = {}
    for value in values:
        if isinstance(value, str) and value.strip():
            seen.setdefault(canonical_text(value), value.strip())
    return sorted(seen.values(), key=canonical_text)


async def _summary(
    session: AsyncSession, batch: MondayImportBatch, *, already_staged: bool
) -> ImportBatchOut:
    records = (
        (await session.execute(select(MondayImportRecord).where(MondayImportRecord.batch_id == batch.id)))
        .scalars()
        .all()
    )
    issues = (
        (
            await session.execute(
                select(MondayImportIssue)
                .where(MondayImportIssue.batch_id == batch.id)
                .order_by(MondayImportIssue.severity.asc(), MondayImportIssue.row_number.asc().nulls_first())
            )
        )
        .scalars()
        .all()
    )
    equipments = [record.normalized_payload for record in records if record.record_kind == "equipment"]
    groups = sorted(
        {record.group_name for record in records if record.record_kind == "equipment" and record.group_name}
    )
    operational = Counter(
        str(payload["operational_status"]) for payload in equipments if payload.get("operational_status")
    )
    locations = await _locations(session, [payload.get("area_name") for payload in equipments])
    work_packages: list[Any] = []
    for payload in equipments:
        codes = payload.get("work_package_codes")
        if isinstance(codes, list):
            work_packages.extend(codes)
    summary = batch.summary or {}
    profiles = summary.get("import_profiles") or []
    profile = profiles[0] if profiles else None
    errors = sum(1 for issue in issues if issue.severity == "error")
    return ImportBatchOut(
        batch_id=batch.id,
        already_staged=already_staged,
        status=batch.status,
        project_context_id=batch.project_context_id,
        file_name=batch.source_filename,
        file_sha256=batch.file_sha256,
        board_title=batch.board_title,
        sheet_name=batch.sheet_name,
        groups=groups,
        profile=(
            ImportProfileRef(
                profile_id=profile["profileId"], version=profile["version"], sha256=profile["sha256"]
            )
            if profile
            else None
        ),
        equipments=len(equipments),
        components=sum(1 for record in records if record.record_kind == "component"),
        warnings=sum(1 for issue in issues if issue.severity == "warning"),
        errors=errors,
        unknown_fields=list(summary.get("unknown_fields") or []),
        fragile_identities=sum(1 for issue in issues if issue.code == "fragile_equipment_identity"),
        unknown_statuses=sum(1 for issue in issues if issue.code == "unknown_status_value"),
        operational_statuses=dict(operational),
        can_proceed=errors == 0,
        issues=[
            ImportIssueOut(
                severity=issue.severity,
                code=issue.code,
                message=issue.message,
                row_number=issue.row_number,
                field=issue.field,
            )
            for issue in issues
        ],
        source_values=SourceValuesOut(
            responsibles=_distinct([payload.get("responsible_name") for payload in equipments]),
            disciplines=_distinct([payload.get("discipline_name") for payload in equipments]),
            work_packages=_distinct(work_packages),
            locations=locations,
        ),
    )


async def _locations(session: AsyncSession, values: list[Any]) -> list[LocationValueOut]:
    """Valores de localização distintos e a EAP resolvida automaticamente (sem mapping),
    com as mesmas evidências do plan (catálogo oficial, rótulos do Monday, LGE)."""
    evidence = default_catalog_evidence(
        [{"area_name": value} for value in values if isinstance(value, str)],
        ValidatedMapping(project_context_id="", sha256=""),
    )
    resolver = await EapResolver.load(session, evidence=evidence)
    counts: Counter[str] = Counter()
    originals: dict[str, str] = {}
    for value in values:
        if isinstance(value, str) and value.strip():
            key = canonical_text(value)
            counts[key] += 1
            originals.setdefault(key, value.strip())
    result = []
    for key in sorted(counts):
        resolution = resolver.resolve(originals[key])
        node = resolution.node
        planned = resolution.creates[-1] if resolution.creates else None
        result.append(
            LocationValueOut(
                value=originals[key],
                status=resolution.status,
                candidates=list(resolution.codes),
                eap_node_id=node.id if node else None,
                eap_code=node.code if node else None,
                eap_name=node.name if node else None,
                equipments=counts[key],
                planned_eap_code=planned.code if planned else None,
                planned_eap_name=planned.name if planned else None,
                evidence_source=planned.evidence_source if planned else None,
                issue_code=resolution.issue_code,
                issue_message=resolution.issue_message,
            )
        )
    return result


def _catalog_item_out(item: CatalogPlanItem) -> CatalogItemOut:
    payload = item.payload
    if item.kind == "eap_node" and payload.get("name"):
        label = f"{item.key} · {payload['name']}"
    elif item.kind == "discipline" and payload.get("code"):
        label = f"{item.key} ({payload['code']})"
    elif item.kind == "work_package" and payload.get("name"):
        label = f"{item.key} · {payload['name']}"
    elif item.kind == "supplier" and payload.get("legal_name"):
        label = f"{item.key} · {payload['legal_name']}"
    else:
        label = item.key
    return CatalogItemOut(
        kind=item.kind,
        key=item.key,
        action=item.action.value,
        label=label,
        evidence_source=item.evidence_source,
        issue_code=item.issue_code,
        message=item.message,
        detail=dict(item.detail),
    )


# --- mapping + plan (conjunto de batches) ----------------------------------------------


async def _staged_batch_ready(session: AsyncSession, actor: CurrentUser, batch_id: str) -> MondayImportBatch:
    batch = await get_batch(session, actor, batch_id)
    has_errors = await session.scalar(
        select(MondayImportIssue.id)
        .where(MondayImportIssue.batch_id == batch.id, MondayImportIssue.severity == "error")
        .limit(1)
    )
    if has_errors is not None:
        raise DomainError(
            f"A análise de '{batch.source_filename}' tem erros: corrija o arquivo e envie novamente."
        )
    return batch


async def build_batches_plan(
    session: AsyncSession, actor: CurrentUser, batch_ids: list[str], mapping: MappingFileSchema
) -> tuple[str, list[str], ValidatedMapping, MigrationPlan]:
    """Mesmo caminho do motor (validate_mapping + build_plan com N batches); usado pelo
    plan E pelo apply, para que o apply sempre reconstrua o plano e compare o hash."""
    unique_ids = list(dict.fromkeys(batch_ids))
    batches = [await _staged_batch_ready(session, actor, batch_id) for batch_id in unique_ids]
    contexts = {batch.project_context_id for batch in batches}
    if len(contexts) != 1:
        raise DomainError("Todos os arquivos de uma importação devem ser da mesma obra.")
    [project_context_id] = contexts
    validated = await validate_mapping(session, mapping, project_context_id=project_context_id)
    plan = await build_plan(
        session, project_context_id=project_context_id, batch_ids=unique_ids, mapping=validated
    )
    return project_context_id, unique_ids, validated, plan


async def _labels(session: AsyncSession, batch_ids: list[str]) -> dict[str, str]:
    """source_key -> nome legível (para listar bloqueios sem expor JSON bruto)."""
    records = (
        (await session.execute(select(MondayImportRecord).where(MondayImportRecord.batch_id.in_(batch_ids))))
        .scalars()
        .all()
    )
    return {
        record.source_key: str(record.normalized_payload.get("name") or record.source_key)
        for record in records
    }


async def _supplier_suggestions(
    session: AsyncSession,
    batch_ids: list[str],
    mapping: ValidatedMapping,
) -> list[SupplierSuggestionOut]:
    records = (
        await session.scalars(
            select(MondayImportRecord).where(
                MondayImportRecord.batch_id.in_(batch_ids),
                MondayImportRecord.record_kind == "equipment",
            )
        )
    ).all()
    resolver = await SupplierSuggestionResolver.load(session)
    result: list[SupplierSuggestionOut] = []
    for record in sorted(records, key=lambda item: item.source_key):
        payload = record.normalized_payload
        equipment_name = str(payload.get("name") or record.source_key)
        raw_names = [str(value) for value in payload.get("suppliers_raw") or [] if value]
        source_name = raw_names[0] if len(raw_names) == 1 else None
        source_code = payload.get("supplier_corporate_code")
        source_value = str(source_code) if source_code else ("; ".join(raw_names) or None)
        suggestion = resolver.suggest(
            equipment_name,
            source_code=str(source_code) if source_code else None,
            source_name=source_name,
        )
        selected = mapping.supplier_selections.get(record.source_key)
        result.append(
            SupplierSuggestionOut(
                source_key=record.source_key,
                equipment_name=equipment_name,
                source_value=source_value,
                supplier_id=suggestion.supplier_id if suggestion else None,
                supplier_name=suggestion.supplier_name if suggestion else None,
                corporate_code=suggestion.corporate_code if suggestion else None,
                confidence=suggestion.confidence if suggestion else "NONE",
                evidence=suggestion.evidence if suggestion else ["Nenhuma evidência controlada encontrada."],
                requires_registration=suggestion.requires_registration if suggestion else False,
                source_matched=suggestion.source_matched if suggestion else False,
                selected_action=selected.action if selected else None,
                selected_supplier_id=selected.supplier_id if selected else None,
            )
        )
    return result


_GROUP_LABELS = {
    "equipments": "Equipamentos",
    "components": "Componentes",
    "negotiations": "Negociações",
    "legalProcesses": "Processos jurídicos",
    "contracts": "Contratos",
    "purchaseRequests": "SC/OCI",
    "purchaseOrders": "OC",
}


async def plan_batches(
    session: AsyncSession, actor: CurrentUser, batch_ids: list[str], mapping: MappingFileSchema
) -> ImportPlanOut:
    project_context_id, unique_ids, validated, plan = await build_batches_plan(
        session, actor, batch_ids, mapping
    )
    labels = await _labels(session, unique_ids)
    groups = []
    blocked = []
    for name, items in plan.all_groups.items():
        counts = {"CREATE": 0, "UPDATE": 0, "NOOP": 0, "BLOCKED": 0}
        for item in items:
            counts[item.action] += 1
            if item.action == "BLOCKED":
                blocked.append(
                    PlanBlockedOut(
                        group=_GROUP_LABELS.get(name, name),
                        source_key=item.source_key,
                        label=labels.get(item.source_key, item.source_key),
                        issues=[
                            PlanIssueOut(code=issue.code, message=issue.message) for issue in item.issues
                        ],
                    )
                )
        groups.append(
            PlanGroupOut(
                name=_GROUP_LABELS.get(name, name),
                create=counts["CREATE"],
                update=counts["UPDATE"],
                noop=counts["NOOP"],
                blocked=counts["BLOCKED"],
            )
        )
    logger.info(
        "monday import planned batches=%s plan=%s blocked=%s mapping_errors=%s",
        len(unique_ids),
        plan.plan_sha256,
        len(blocked),
        validated.has_errors,
    )
    return ImportPlanOut(
        batch_ids=unique_ids,
        project_context_id=project_context_id,
        mapping_sha256=validated.sha256,
        plan_sha256=plan.plan_sha256,
        mapping_issues=[
            MappingIssueOut(
                code=issue.code,
                category=issue.category,
                section=issue.section,
                message=issue.message,
                source_value=issue.source_value,
            )
            for issue in validated.issues
        ],
        groups=groups,
        blocked=blocked,
        warnings=[PlanIssueOut(code=issue.code, message=issue.message) for issue in plan.warnings],
        equipment_warnings=[
            PlanBlockedOut(
                group=_GROUP_LABELS.get("equipments", "equipments"),
                source_key=item.source_key,
                label=labels.get(item.source_key, item.source_key),
                issues=[PlanIssueOut(code=issue.code, message=issue.message) for issue in item.issues],
            )
            for item in plan.equipments
            if item.action != "BLOCKED" and item.issues
        ],
        catalog_counts=plan.catalog_counts,
        eap=EapSummaryOut(
            resolved=plan.eap_summary.get("RESOLVED", 0),
            multiple=plan.eap_summary.get("MULTIPLE", 0),
            none=plan.eap_summary.get("NONE", 0),
            not_found=plan.eap_summary.get("NOT_FOUND", 0),
            create=plan.eap_summary.get("CREATE", 0),
            conflict=plan.eap_summary.get("CONFLICT", 0),
            unresolved=plan.eap_summary.get("UNRESOLVED", 0),
        ),
        catalogs=[_catalog_item_out(item) for item in plan.catalog_items],
        responsibles=ResponsibleSummaryOut(**plan.responsible_summary),
        supplier_suggestions=await _supplier_suggestions(session, unique_ids, validated),
        has_blocked=plan.has_blocked,
        can_apply=not plan.has_blocked and not validated.has_errors,
    )


# --- apply + reconciliation ------------------------------------------------------------


def _text(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


async def apply_batches(
    session: AsyncSession,
    actor: CurrentUser,
    batch_ids: list[str],
    mapping: MappingFileSchema,
    expected_plan_sha256: str,
) -> ImportApplyOut:
    """Reconstrói o plano (mesmo caminho do `plan`), confere o hash e chama `apply_plan`.

    O ator é sempre o usuário autenticado; o escopo por unidade já foi validado
    ao carregar cada batch. Auditoria, ExternalMapping e transação são do motor.
    """
    project_context_id, unique_ids, validated, plan = await build_batches_plan(
        session, actor, batch_ids, mapping
    )
    if validated.has_errors:
        raise DomainError("Mapping inválido: revise as associações antes de aplicar.")
    try:
        result = await apply_plan(session, plan=plan, expected_plan_sha256=expected_plan_sha256, actor=actor)
    except PlanStaleError as exc:
        raise ConflictError("PLAN_STALE: os dados mudaram desde o plano. Gere o plano novamente.") from exc
    except PlanBlockedError as exc:
        raise DomainError("O plano tem itens bloqueados e não pode ser aplicado.") from exc

    report = await reconcile_domain(session, project_context_id=project_context_id, mapping=validated)
    divergences = [
        ImportDivergenceOut(
            equipment=item.equipment_name,
            field=field.field,
            hub_value=_text(field.hub_value),
            source_value=_text(field.source_value),
        )
        for item in report.equipments
        for field in item.fields
        if field.status == "MISMATCH"
    ]
    totals = report.field_totals
    counts = result.counts
    logger.info(
        "monday import applied batches=%s run=%s status=%s mismatches=%s",
        len(unique_ids),
        result.migration_run_id,
        result.status,
        totals["MISMATCH"],
    )
    return ImportApplyOut(
        migration_run_id=result.migration_run_id,
        status=result.status,
        created=sum(group.get("create", 0) for group in counts.values()),
        updated=sum(group.get("update", 0) for group in counts.values()),
        unchanged=sum(group.get("noop", 0) for group in counts.values()),
        reconciliation=ImportReconciliationOut(
            equipments_compared=report.equipments_compared,
            components_compared=report.components_compared,
            mismatches=totals["MISMATCH"],
            pending_mapping=totals["PENDING_MAPPING"],
            divergences=divergences,
        ),
        has_divergences=totals["MISMATCH"] > 0,
    )
