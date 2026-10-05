"""Camada HTTP fina da importação Monday (P1.3).

Só autoriza, valida a requisição e chama o motor `app.modules.monday_import`
(parser, staging, mapping, plan, apply, reconciliation). Nenhuma regra de
importação é reimplementada aqui.

Esta etapa (análise) grava SOMENTE staging — MondayImportBatch, MondayImportRecord
e MondayImportIssue. Nenhum Equipment, componente, contrato, SC/OCI, OC ou vínculo
de fornecedor é criado ou alterado; isso só acontece no apply confirmado.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.errors import ConflictError, DomainError, NotFoundError
from app.core.scope import assert_context_allowed
from app.models.monday_import import MondayImportBatch, MondayImportIssue, MondayImportRecord
from app.modules.imports.schemas import (
    ImportApplyOut,
    ImportBatchOut,
    ImportDivergenceOut,
    ImportIssueOut,
    ImportPlanOut,
    ImportProfileOut,
    ImportProfileRef,
    ImportReconciliationOut,
    MappingIssueOut,
    PlanBlockedOut,
    PlanGroupOut,
    PlanIssueOut,
    SourceValuesOut,
)
from app.modules.monday_import.apply import PlanBlockedError, PlanStaleError, apply_plan
from app.modules.monday_import.domain_reconciliation import reconcile_domain
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
    summary = await _summary(session, batch, already_staged=not result.created)
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
            areas=_distinct([payload.get("area_name") for payload in equipments]),
            disciplines=_distinct([payload.get("discipline_name") for payload in equipments]),
            work_packages=_distinct(work_packages),
        ),
    )


# --- Checkpoint B: mapping + plan ------------------------------------------------------


async def _staged_batch_ready(session: AsyncSession, actor: CurrentUser, batch_id: str) -> MondayImportBatch:
    batch = await get_batch(session, actor, batch_id)
    has_errors = await session.scalar(
        select(MondayImportIssue.id)
        .where(MondayImportIssue.batch_id == batch.id, MondayImportIssue.severity == "error")
        .limit(1)
    )
    if has_errors is not None:
        raise DomainError("A análise da planilha tem erros: corrija o arquivo e envie novamente.")
    return batch


async def build_batch_plan(
    session: AsyncSession, actor: CurrentUser, batch_id: str, mapping: MappingFileSchema
) -> tuple[MondayImportBatch, ValidatedMapping, MigrationPlan]:
    """Mesmo caminho do motor (validate_mapping + build_plan); usado pelo plan E pelo apply,
    para que o apply sempre reconstrua o plano e compare o hash."""
    batch = await _staged_batch_ready(session, actor, batch_id)
    validated = await validate_mapping(session, mapping, project_context_id=batch.project_context_id)
    plan = await build_plan(
        session, project_context_id=batch.project_context_id, batch_ids=[batch.id], mapping=validated
    )
    return batch, validated, plan


async def _labels(session: AsyncSession, batch_id: str) -> dict[str, str]:
    """source_key -> nome legível (para listar bloqueios sem expor JSON bruto)."""
    records = (
        (await session.execute(select(MondayImportRecord).where(MondayImportRecord.batch_id == batch_id)))
        .scalars()
        .all()
    )
    return {
        record.source_key: str(record.normalized_payload.get("name") or record.source_key)
        for record in records
    }


_GROUP_LABELS = {
    "equipments": "Equipamentos",
    "components": "Componentes",
    "negotiations": "Negociações",
    "legalProcesses": "Processos jurídicos",
    "contracts": "Contratos",
    "purchaseRequests": "SC/OCI",
    "purchaseOrders": "OC",
}


async def plan_batch(
    session: AsyncSession, actor: CurrentUser, batch_id: str, mapping: MappingFileSchema
) -> ImportPlanOut:
    batch, validated, plan = await build_batch_plan(session, actor, batch_id, mapping)
    labels = await _labels(session, batch.id)
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
        "monday import planned batch=%s plan=%s blocked=%s mapping_errors=%s",
        batch.id,
        plan.plan_sha256,
        len(blocked),
        validated.has_errors,
    )
    return ImportPlanOut(
        batch_id=batch.id,
        project_context_id=batch.project_context_id,
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
        has_blocked=plan.has_blocked,
        can_apply=not plan.has_blocked and not validated.has_errors,
    )


# --- Checkpoint D: apply + reconciliation ----------------------------------------------


def _text(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


async def apply_batch(
    session: AsyncSession,
    actor: CurrentUser,
    batch_id: str,
    mapping: MappingFileSchema,
    expected_plan_sha256: str,
) -> ImportApplyOut:
    """Reconstrói o plano (mesmo caminho do `plan`), confere o hash e chama `apply_plan`.

    O ator é sempre o usuário autenticado; o escopo por unidade já foi validado
    ao carregar o batch. Auditoria, ExternalMapping e transação são do motor.
    """
    batch, validated, plan = await build_batch_plan(session, actor, batch_id, mapping)
    if validated.has_errors:
        raise DomainError("Mapping inválido: revise as associações antes de aplicar.")
    try:
        result = await apply_plan(session, plan=plan, expected_plan_sha256=expected_plan_sha256, actor=actor)
    except PlanStaleError as exc:
        raise ConflictError("PLAN_STALE: os dados mudaram desde o plano. Gere o plano novamente.") from exc
    except PlanBlockedError as exc:
        raise DomainError("O plano tem itens bloqueados e não pode ser aplicado.") from exc

    report = await reconcile_domain(session, project_context_id=batch.project_context_id, mapping=validated)
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
        "monday import applied batch=%s run=%s status=%s mismatches=%s",
        batch.id,
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
