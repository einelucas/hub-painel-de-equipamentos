"""Persistência apenas no staging; não cria registros definitivos do domínio."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.equipment import ProjectContext
from app.models.monday_import import (
    ExternalMapping,
    MondayImportBatch,
    MondayImportIssue,
    MondayImportRecord,
)
from app.modules.monday_import.dry_run import build_dry_run_report
from app.modules.monday_import.mappings import SOURCE_SYSTEM
from app.modules.monday_import.parser import PARSER_VERSION, parse_monday_xlsx
from app.modules.monday_import.profile import ImportProfile, default_profile
from app.modules.monday_import.schemas import ParsedWorkbook, StageImportResult


class StagedWithDifferentProfileError(ValueError):
    """O mesmo arquivo já foi staged neste contexto com outro ImportProfile."""


def _batch_profile(summary: dict | None) -> tuple[str, str]:
    """(profileId, sha256) usados no batch. Batches anteriores à P1.1 não registram
    profile: foram lidos pelo profile histórico."""
    recorded = (summary or {}).get("import_profiles") or []
    if recorded:
        return str(recorded[0].get("profileId")), str(recorded[0].get("sha256"))
    profile = default_profile()
    return profile.profile_id, profile.sha256


@dataclass(slots=True, frozen=True)
class ExternalMappingResult:
    mapping_id: str
    created: bool


async def _existing_batch_result(session: AsyncSession, batch_id: str) -> StageImportResult:
    records = (
        await session.execute(
            select(func.count(MondayImportRecord.id)).where(MondayImportRecord.batch_id == batch_id)
        )
    ).scalar_one()
    issues = (
        await session.execute(
            select(func.count(MondayImportIssue.id)).where(MondayImportIssue.batch_id == batch_id)
        )
    ).scalar_one()
    return StageImportResult(batch_id=batch_id, created=False, records=records, issues=issues)


async def stage_import(
    session: AsyncSession,
    *,
    project_context_id: str,
    source: bytes | bytearray | str | Path | BinaryIO,
    source_name: str | None = None,
    profile: ImportProfile | None = None,
) -> StageImportResult:
    """Grava raw + normalizado uma vez por contexto e SHA-256 do arquivo.

    O profile usado fica registrado no `summary` do batch (`import_profiles`),
    então plan/apply/reconcile não reinterpretam o arquivo com outro profile.
    """
    context_exists = await session.scalar(
        select(ProjectContext.id).where(ProjectContext.id == project_context_id)
    )
    if context_exists is None:
        raise ValueError("project_context não encontrado")

    profile = profile or default_profile()
    workbook = parse_monday_xlsx(source, source_name=source_name, profile=profile)
    report_payload = build_dry_run_report([workbook]).to_dict()
    report_payload.pop("issues", None)
    proposed_batch_id = str(uuid.uuid4())
    inserted_id = (
        await session.execute(
            insert(MondayImportBatch)
            .values(
                id=proposed_batch_id,
                project_context_id=project_context_id,
                source_system=SOURCE_SYSTEM,
                source_filename=workbook.source_file,
                file_sha256=workbook.file_sha256,
                board_title=workbook.board_title,
                sheet_name=workbook.sheet_name,
                parser_version=PARSER_VERSION,
                status="STAGED",
                summary=report_payload,
            )
            .on_conflict_do_nothing(index_elements=["project_context_id", "source_system", "file_sha256"])
            .returning(MondayImportBatch.id)
        )
    ).scalar_one_or_none()
    if inserted_id is None:
        existing = await session.scalar(
            select(MondayImportBatch).where(
                MondayImportBatch.project_context_id == project_context_id,
                MondayImportBatch.source_system == SOURCE_SYSTEM,
                MondayImportBatch.file_sha256 == workbook.file_sha256,
            )
        )
        if existing is None:  # pragma: no cover - defesa contra anomalia transacional
            raise RuntimeError("conflito de batch sem registro recuperável")
        staged_profile_id, staged_sha = _batch_profile(existing.summary)
        if staged_sha == profile.sha256 and existing.parser_version == PARSER_VERSION:
            return await _existing_batch_result(session, existing.id)
        if existing.status != "STAGED" or staged_profile_id != profile.profile_id:
            # Outro profile, ou batch já usado para escrever no domínio: reinterpretar
            # mudaria a evidência. Só uma NOVA VERSÃO do mesmo profile reanalisa.
            raise StagedWithDifferentProfileError(
                f"arquivo já staged no batch {existing.id} com outro ImportProfile; "
                "use o mesmo profile ou um contexto/arquivo novo"
            )
        # Batch nunca aplicado e nova versão do mesmo profile: a análise é refeita
        # no MESMO batch, substituindo só o staging.
        await session.execute(delete(MondayImportIssue).where(MondayImportIssue.batch_id == existing.id))
        await session.execute(delete(MondayImportRecord).where(MondayImportRecord.batch_id == existing.id))
        existing.source_filename = workbook.source_file
        existing.board_title = workbook.board_title
        existing.sheet_name = workbook.sheet_name
        existing.parser_version = PARSER_VERSION
        existing.summary = report_payload
        await session.flush()
        result = await _write_staging(session, existing.id, workbook)
        return StageImportResult(
            batch_id=existing.id, created=False, records=result.records, issues=result.issues, restaged=True
        )

    return await _write_staging(session, inserted_id, workbook)


async def _write_staging(session: AsyncSession, batch_id: str, workbook: ParsedWorkbook) -> StageImportResult:
    inserted_id = batch_id
    row_records: dict[int, str] = {}
    record_count = 0
    for equipment in workbook.equipments:
        equipment_record_id = str(uuid.uuid4())
        session.add(
            MondayImportRecord(
                id=equipment_record_id,
                batch_id=inserted_id,
                parent_record_id=None,
                record_kind="equipment",
                source_key=equipment.source_key,
                group_name=equipment.group_name,
                row_number=equipment.row_number,
                raw_payload=equipment.raw,
                normalized_payload=equipment.normalized,
            )
        )
        row_records[equipment.row_number] = equipment_record_id
        record_count += 1
        for component in equipment.components:
            component_record_id = str(uuid.uuid4())
            session.add(
                MondayImportRecord(
                    id=component_record_id,
                    batch_id=inserted_id,
                    parent_record_id=equipment_record_id,
                    record_kind="component",
                    source_key=component.source_key,
                    group_name=component.group_name,
                    row_number=component.row_number,
                    raw_payload=component.raw,
                    normalized_payload=component.normalized,
                )
            )
            row_records[component.row_number] = component_record_id
            record_count += 1

    # Registros antes das issues: issue.record_id é FK para monday_import_record.
    await session.flush()
    for issue in workbook.issues:
        session.add(
            MondayImportIssue(
                id=str(uuid.uuid4()),
                batch_id=inserted_id,
                record_id=row_records.get(issue.row_number) if issue.row_number is not None else None,
                severity=issue.severity,
                code=issue.code,
                field=issue.field,
                message=issue.message,
                raw_value=issue.raw_value,
                row_number=issue.row_number,
            )
        )
    await session.flush()
    return StageImportResult(
        batch_id=inserted_id,
        created=True,
        records=record_count,
        issues=len(workbook.issues),
    )


async def register_external_mapping(
    session: AsyncSession,
    *,
    project_context_id: str,
    source_entity_type: str,
    external_id: str,
    identity_strategy: str,
    target_entity_type: str,
    target_entity_id: str,
    raw_identity: dict | None = None,
) -> ExternalMappingResult:
    """Registra uma decisão de identidade sem sobrescrever conflito silenciosamente."""
    proposed_id = str(uuid.uuid4())
    inserted_id = (
        await session.execute(
            insert(ExternalMapping)
            .values(
                id=proposed_id,
                project_context_id=project_context_id,
                source_system=SOURCE_SYSTEM,
                source_entity_type=source_entity_type,
                external_id=external_id,
                identity_strategy=identity_strategy,
                target_entity_type=target_entity_type,
                target_entity_id=target_entity_id,
                raw_identity=raw_identity,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    "project_context_id",
                    "source_system",
                    "source_entity_type",
                    "external_id",
                ]
            )
            .returning(ExternalMapping.id)
        )
    ).scalar_one_or_none()
    if inserted_id is not None:
        return ExternalMappingResult(inserted_id, True)

    existing = (
        await session.execute(
            select(ExternalMapping).where(
                ExternalMapping.project_context_id == project_context_id,
                ExternalMapping.source_system == SOURCE_SYSTEM,
                ExternalMapping.source_entity_type == source_entity_type,
                ExternalMapping.external_id == external_id,
            )
        )
    ).scalar_one()
    if existing.target_entity_type != target_entity_type or existing.target_entity_id != target_entity_id:
        raise ValueError("external_id já está mapeado para outro registro")
    return ExternalMappingResult(existing.id, False)
