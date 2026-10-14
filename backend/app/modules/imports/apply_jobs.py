"""Apply da importação Monday em segundo plano (task in-process + registro em `monday_apply_job`).

O proxy corta requisições longas, então o POST `/apply` só valida, grava o job (commit) e
devolve 202; a task roda `services.apply_batches` com sessão PRÓPRIA (mesma transação única
do apply de antes) e grava o resultado no job. O front consulta `GET /apply/{job_id}`.

Premissa de deploy: processo de vida longa (uvicorn em container, ver Dockerfile). Se o
processo morrer no meio, a transação do apply é revertida pelo banco e o job RUNNING é
considerado interrompido depois de `STALE_AFTER` sem atualização.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.database import SessionLocal
from app.core.errors import ConflictError, DomainError, NotFoundError
from app.core.scope import assert_context_allowed
from app.models.common import utcnow
from app.models.monday_import import MondayApplyJob
from app.modules.imports import services
from app.modules.imports.schemas import ImportApplyJobOut, ImportApplyOut
from app.modules.monday_import.mapping_file import MappingFileSchema

logger = logging.getLogger(__name__)

STALE_AFTER = timedelta(minutes=30)
_PROGRESS = {"QUEUED": 5, "APPLYING": 15, "RECONCILING": 85, "DONE": 100}
_ERROR_LIMIT = 2000

# Referência forte: o loop só guarda referência fraca às tasks.
_TASKS: set[asyncio.Task[None]] = set()


def to_out(job: MondayApplyJob) -> ImportApplyJobOut:
    return ImportApplyJobOut(
        job_id=job.id,
        status=job.status,
        stage=job.stage,
        progress=_PROGRESS.get(job.stage, 0),
        project_context_id=job.project_context_id,
        error=job.error,
        error_code=job.error_code,
        result=ImportApplyOut.model_validate(job.result) if job.result is not None else None,
        created_at=job.created_at.isoformat(),
        finished_at=job.finished_at.isoformat() if job.finished_at else None,
    )


async def _expire_stale(session: AsyncSession, project_context_id: str | None = None) -> None:
    """Job RUNNING sem atualização há `STALE_AFTER` = processo morreu: libera a obra."""
    now = utcnow()
    statement = (
        update(MondayApplyJob)
        .where(MondayApplyJob.status == "RUNNING", MondayApplyJob.updated_at < now - STALE_AFTER)
        .values(
            status="FAILED",
            error_code="INTERRUPTED",
            error="A importação foi interrompida (o servidor reiniciou). Gere o plano e tente novamente.",
            finished_at=now,
            updated_at=now,
        )
    )
    if project_context_id is not None:
        statement = statement.where(MondayApplyJob.project_context_id == project_context_id)
    await session.execute(statement)


async def start_apply(
    session: AsyncSession,
    actor: CurrentUser,
    batch_ids: list[str],
    mapping: MappingFileSchema,
    plan_sha256: str,
) -> tuple[MondayApplyJob, asyncio.Task[None]]:
    """Valida rápido, grava o job (commitado) e dispara a task. 409 se já há apply na obra."""
    project_context_id, unique_ids = await services.validate_apply_request(session, actor, batch_ids, mapping)
    await _expire_stale(session, project_context_id)
    job = MondayApplyJob(
        project_context_id=project_context_id,
        actor_id=actor.id,
        status="RUNNING",
        stage="QUEUED",
        batch_ids=sorted(unique_ids),
        plan_sha256=plan_sha256,
    )
    session.add(job)
    try:
        await session.commit()
    except IntegrityError as exc:  # índice único parcial: já existe RUNNING nesta obra
        await session.rollback()
        raise ConflictError(
            "APPLY_IN_PROGRESS: já existe uma importação em andamento para esta obra."
        ) from exc
    task = asyncio.create_task(
        run_apply_job(job.id, actor, unique_ids, mapping, plan_sha256), name=f"monday-apply-{job.id}"
    )
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    return job, task


async def get_job(session: AsyncSession, actor: CurrentUser, job_id: str) -> MondayApplyJob:
    await _expire_stale(session)
    await session.commit()
    job = await session.get(MondayApplyJob, job_id)
    if job is None:
        raise NotFoundError("Importação não encontrada.")
    # Mesmo escopo por unidade do apply (404 fora do escopo, sem vazar existência).
    await assert_context_allowed(session, actor, job.project_context_id)
    return job


async def _update_job(job_id: str, **values: Any) -> None:
    """Atualização curta em sessão própria (a do apply tem a transação grande aberta)."""
    async with SessionLocal() as session:
        await session.execute(
            update(MondayApplyJob).where(MondayApplyJob.id == job_id).values(updated_at=utcnow(), **values)
        )
        await session.commit()


def _failure(exc: Exception) -> tuple[str, str]:
    """(código, mensagem) segura para o usuário."""
    if isinstance(exc, ConflictError) and exc.message.startswith("PLAN_STALE"):
        return "PLAN_STALE", exc.message
    if isinstance(exc, DomainError | ConflictError | NotFoundError):
        return "INVALID", str(exc.message)[:_ERROR_LIMIT]
    return "APPLY_FAILED", "Falha inesperada ao aplicar a importação. Nada foi gravado; tente novamente."


async def run_apply_job(
    job_id: str,
    actor: CurrentUser,
    batch_ids: list[str],
    mapping: MappingFileSchema,
    plan_sha256: str,
) -> None:
    """Corpo da task. Nunca propaga exceção (a task é fire-and-forget)."""

    async def on_stage(stage: str) -> None:
        await _update_job(job_id, stage=stage)

    try:
        async with SessionLocal() as session:
            out = await services.apply_batches(
                session, actor, batch_ids, mapping, plan_sha256, on_stage=on_stage
            )
        await _update_job(
            job_id,
            status="COMPLETED",
            stage="DONE",
            migration_run_id=out.migration_run_id,
            result=out.model_dump(mode="json", by_alias=True),
            finished_at=utcnow(),
        )
    except Exception as exc:
        code, message = _failure(exc)
        if code == "APPLY_FAILED":
            logger.exception("monday apply job failed job=%s", job_id)
        else:
            logger.info("monday apply job rejected job=%s code=%s", job_id, code)
        try:
            await _update_job(job_id, status="FAILED", error_code=code, error=message, finished_at=utcnow())
        except Exception:
            logger.exception("monday apply job: could not record failure job=%s", job_id)
