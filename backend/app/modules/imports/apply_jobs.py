"""Apply da importação Monday em segundo plano, persistente e retomável.

O proxy corta requisições longas, então o POST `/apply` só valida, grava o job (commit) e
devolve 202; a task roda `services.apply_batches` com sessão PRÓPRIA (mesma transação única
do apply de antes) e grava o resultado no job. O front consulta `GET /apply/{job_id}`.

O payload necessário fica no banco. Um lease com heartbeat impede execução concorrente;
após reinício, jobs cujo lease expirou são retomados com segurança.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.database import SessionLocal
from app.core.errors import ConflictError, DomainError, NotFoundError
from app.core.permissions import Role
from app.core.scope import assert_context_allowed
from app.models.common import utcnow
from app.models.monday_import import MondayApplyJob
from app.models.user import User
from app.modules.imports import services
from app.modules.imports.schemas import ImportApplyJobOut, ImportApplyOut
from app.modules.monday_import.mapping_file import MappingFileSchema

logger = logging.getLogger(__name__)

STALE_AFTER = timedelta(minutes=2)
HEARTBEAT_SECONDS = 15
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


async def start_apply(
    session: AsyncSession,
    actor: CurrentUser,
    batch_ids: list[str],
    mapping: MappingFileSchema,
    plan_sha256: str,
) -> tuple[MondayApplyJob, asyncio.Task[None]]:
    """Valida rápido, grava o job (commitado) e dispara a task. 409 se já há apply na obra."""
    project_context_id, unique_ids = await services.validate_apply_request(session, actor, batch_ids, mapping)
    lease_id = str(uuid4())
    now = utcnow()
    job = MondayApplyJob(
        project_context_id=project_context_id,
        actor_id=actor.id,
        status="RUNNING",
        stage="QUEUED",
        batch_ids=sorted(unique_ids),
        mapping_payload=mapping.model_dump(mode="json", by_alias=True),
        plan_sha256=plan_sha256,
        lease_id=lease_id,
        heartbeat_at=now,
        attempt_count=1,
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
        run_apply_job(job.id, actor, unique_ids, mapping, plan_sha256, lease_id),
        name=f"monday-apply-{job.id}",
    )
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    return job, task


async def get_job(session: AsyncSession, actor: CurrentUser, job_id: str) -> MondayApplyJob:
    job = await session.get(MondayApplyJob, job_id)
    if job is None:
        raise NotFoundError("Importação não encontrada.")
    # Mesmo escopo por unidade do apply (404 fora do escopo, sem vazar existência).
    await assert_context_allowed(session, actor, job.project_context_id)
    cutoff = utcnow() - STALE_AFTER
    if job.status == "RUNNING" and (job.heartbeat_at is None or job.heartbeat_at < cutoff):
        await recover_apply_jobs(job_id=job_id)
        await session.refresh(job)
    return job


async def _update_job(job_id: str, *, lease_id: str | None = None, **values: Any) -> None:
    """Atualização curta em sessão própria (a do apply tem a transação grande aberta)."""
    async with SessionLocal() as session:
        statement = update(MondayApplyJob).where(MondayApplyJob.id == job_id)
        if lease_id is not None:
            statement = statement.where(MondayApplyJob.lease_id == lease_id)
        await session.execute(statement.values(updated_at=utcnow(), **values))
        await session.commit()


async def _heartbeat(job_id: str, lease_id: str) -> None:
    while True:
        await asyncio.sleep(HEARTBEAT_SECONDS)
        await _update_job(job_id, lease_id=lease_id, heartbeat_at=utcnow())


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
    lease_id: str | None = None,
) -> None:
    """Corpo da task. Nunca propaga exceção (a task é fire-and-forget)."""

    async def on_stage(stage: str) -> None:
        await _update_job(job_id, lease_id=lease_id, stage=stage, heartbeat_at=utcnow())

    heartbeat = asyncio.create_task(_heartbeat(job_id, lease_id)) if lease_id else None
    try:
        async with SessionLocal() as session:
            out = await services.apply_batches(
                session, actor, batch_ids, mapping, plan_sha256, on_stage=on_stage
            )
        await _update_job(
            job_id,
            lease_id=lease_id,
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
            await _update_job(
                job_id,
                lease_id=lease_id,
                status="FAILED",
                error_code=code,
                error=message,
                finished_at=utcnow(),
            )
        except Exception:
            logger.exception("monday apply job: could not record failure job=%s", job_id)
    finally:
        if heartbeat:
            heartbeat.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat


async def recover_apply_jobs(
    *, project_context_id: str | None = None, job_id: str | None = None
) -> int:
    """Assume jobs sem dono ou com heartbeat vencido e os agenda neste processo."""
    now = utcnow()
    cutoff = now - STALE_AFTER
    recovered: list[tuple[MondayApplyJob, User, str]] = []
    async with SessionLocal() as session:
        query = select(MondayApplyJob).where(
            MondayApplyJob.status == "RUNNING",
            or_(MondayApplyJob.heartbeat_at.is_(None), MondayApplyJob.heartbeat_at < cutoff),
        )
        if project_context_id:
            query = query.where(MondayApplyJob.project_context_id == project_context_id)
        if job_id:
            query = query.where(MondayApplyJob.id == job_id)
        candidates = list((await session.scalars(query)).all())
        for candidate in candidates:
            new_lease = str(uuid4())
            claimed = await session.execute(
                update(MondayApplyJob)
                .where(
                    MondayApplyJob.id == candidate.id,
                    MondayApplyJob.status == "RUNNING",
                    MondayApplyJob.lease_id == candidate.lease_id,
                    or_(MondayApplyJob.heartbeat_at.is_(None), MondayApplyJob.heartbeat_at < cutoff),
                )
                .values(
                    lease_id=new_lease,
                    heartbeat_at=now,
                    updated_at=now,
                    attempt_count=MondayApplyJob.attempt_count + 1,
                )
                .returning(MondayApplyJob.id)
            )
            if claimed.scalar_one_or_none() is None:
                continue
            actor = await session.get(User, candidate.actor_id)
            if actor is not None and actor.active:
                recovered.append((candidate, actor, new_lease))
            else:
                await session.execute(
                    update(MondayApplyJob)
                    .where(MondayApplyJob.id == candidate.id, MondayApplyJob.lease_id == new_lease)
                    .values(
                        status="FAILED",
                        error_code="INVALID",
                        error="O usuário que iniciou a importação não está mais ativo.",
                        finished_at=now,
                        updated_at=now,
                    )
                )
        await session.commit()

    for job, user, lease in recovered:
        current_actor = CurrentUser(
            id=user.id,
            email=user.email,
            name=user.name,
            role=Role(user.role.value),
            active=user.active,
        )
        mapping = MappingFileSchema.model_validate(job.mapping_payload)
        task = asyncio.create_task(
            run_apply_job(job.id, current_actor, job.batch_ids, mapping, job.plan_sha256, lease),
            name=f"monday-apply-recovered-{job.id}",
        )
        _TASKS.add(task)
        task.add_done_callback(_TASKS.discard)
    return len(recovered)
