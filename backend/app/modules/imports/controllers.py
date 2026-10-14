"""Rotas HTTP da importação Monday pelo Hub (P1.3 / P1.3.1).

Toda rota exige `equipments:write` (importar é escrita de Equipment) e o escopo
por unidade do ProjectContext é validado no backend — nunca só na UI.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_permission
from app.core.config import get_settings
from app.core.database import get_session
from app.core.permissions import Permission
from app.modules.imports import apply_jobs, services
from app.modules.imports.schemas import (
    ImportApplyIn,
    ImportApplyJobOut,
    ImportBatchOut,
    ImportPlanIn,
    ImportPlanOut,
    ImportProfileListOut,
)

router = APIRouter(prefix="/imports/monday", tags=["importação"])
_write = require_permission(Permission.EQUIPMENTS_WRITE)


@router.get("/profiles", response_model=ImportProfileListOut)
async def get_profiles(_: CurrentUser = Depends(_write)) -> ImportProfileListOut:
    """Formatos de planilha disponíveis no runtime (só metadados)."""
    return ImportProfileListOut(items=services.list_profiles())


@router.post("/batches", response_model=ImportBatchOut)
async def post_batch(
    project_context_id: str = Form(alias="projectContextId"),
    profile_id: str = Form(alias="profileId"),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_write),
) -> ImportBatchOut:
    """Analisa o XLSX e grava SOMENTE o staging (idempotente por obra + hash do arquivo).

    O arquivo é lido em memória e descartado: os bytes nunca são persistidos.
    """
    max_bytes = get_settings().import_max_upload_bytes
    content = await file.read(max_bytes + 1)
    file_name = services.validate_upload(file.filename, len(content), max_bytes)
    return await services.stage_upload(
        session,
        actor,
        project_context_id=project_context_id,
        profile_id=profile_id,
        file_name=file_name,
        content=content,
    )


@router.get("/batches/{batch_id}", response_model=ImportBatchOut)
async def get_batch(
    batch_id: str,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_write),
) -> ImportBatchOut:
    return await services.batch_summary(session, actor, batch_id)


@router.post("/plan", response_model=ImportPlanOut)
async def post_plan(
    body: ImportPlanIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_write),
) -> ImportPlanOut:
    """Plano ÚNICO para o conjunto de batches (ex.: um XLSX por fase ocupada).

    Valida o mapping e monta o plano — somente leitura: nada é gravado no domínio."""
    return await services.plan_batches(
        session, actor, body.batch_ids, body.mapping, auto_select_suppliers=body.auto_select_suppliers
    )


@router.post("/apply", response_model=ImportApplyJobOut, status_code=status.HTTP_202_ACCEPTED)
async def post_apply(
    body: ImportApplyIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_write),
) -> ImportApplyJobOut:
    """Valida e inicia o apply em segundo plano (202 + job). 409 APPLY_IN_PROGRESS se a obra
    já tem um apply rodando; PLAN_STALE (plano mudou) chega pelo job (`errorCode`)."""
    job, _ = await apply_jobs.start_apply(session, actor, body.batch_ids, body.mapping, body.plan_sha256)
    return apply_jobs.to_out(job)


@router.get("/apply/{job_id}", response_model=ImportApplyJobOut)
async def get_apply(
    job_id: str,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_write),
) -> ImportApplyJobOut:
    """Estado, progresso e (quando concluído) o resultado do apply."""
    return apply_jobs.to_out(await apply_jobs.get_job(session, actor, job_id))
