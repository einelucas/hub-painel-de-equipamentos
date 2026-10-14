"""Apply em segundo plano: ciclo de vida do job, sem banco (sessão e motor simulados)."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.auth import CurrentUser
from app.core.errors import ConflictError, DomainError
from app.core.permissions import Role
from app.models.monday_import import MondayApplyJob
from app.modules.imports import apply_jobs
from app.modules.imports.schemas import ImportApplyOut
from app.modules.monday_import.mapping_file import MappingFileSchema

ACTOR = CurrentUser(id="U1", email="a@example.com", name="A", role=Role.ADMIN, active=True)


class _Session:
    def __init__(self, updates: list[dict[str, Any]], *, fail_commit: bool = False) -> None:
        self.updates = updates
        self.added: list[Any] = []
        self.fail_commit = fail_commit
        self.rolled_back = False

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    def add(self, obj: Any) -> None:
        obj.id = "job-1"
        self.added.append(obj)

    async def execute(self, statement: Any) -> None:
        params = statement.compile().params
        self.updates.append({k.removesuffix("_1"): v for k, v in params.items()})

    async def commit(self) -> None:
        if self.fail_commit:
            raise IntegrityError("insert", {}, Exception("dup"))

    async def rollback(self) -> None:
        self.rolled_back = True


def _out() -> ImportApplyOut:
    return ImportApplyOut.model_validate(
        {
            "migrationRunId": "run-1",
            "status": "APPLIED",
            "created": 1,
            "updated": 0,
            "unchanged": 0,
            "reconciliation": {
                "equipmentsCompared": 1,
                "componentsCompared": 0,
                "mismatches": 0,
                "pendingMapping": 0,
                "divergences": [],
            },
            "hasDivergences": False,
        }
    )


@pytest.fixture
def updates(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    log: list[dict[str, Any]] = []
    monkeypatch.setattr(apply_jobs, "SessionLocal", lambda: _Session(log))
    return log


async def test_job_completes_with_result_and_stages(
    monkeypatch: pytest.MonkeyPatch, updates: list[dict[str, Any]]
) -> None:
    async def fake_apply(session, actor, batch_ids, mapping, sha, on_stage=None):  # noqa: ANN001, ANN202
        assert on_stage is not None
        await on_stage("APPLYING")
        await on_stage("RECONCILING")
        return _out()

    monkeypatch.setattr(apply_jobs.services, "apply_batches", fake_apply)
    await apply_jobs.run_apply_job("job-1", ACTOR, ["b1"], MappingFileSchema(), "a" * 64)

    stages = [u["stage"] for u in updates if "stage" in u]
    assert stages == ["APPLYING", "RECONCILING", "DONE"]
    final = updates[-1]
    assert final["status"] == "COMPLETED"
    assert final["migration_run_id"] == "run-1"
    assert final["result"]["migrationRunId"] == "run-1"
    assert final["result"]["reconciliation"]["equipmentsCompared"] == 1


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (ConflictError("PLAN_STALE: os dados mudaram"), "PLAN_STALE"),
        (DomainError("O plano tem itens bloqueados"), "INVALID"),
        (RuntimeError("boom com detalhe interno"), "APPLY_FAILED"),
    ],
)
async def test_job_failure_records_code_without_leaking_internals(
    monkeypatch: pytest.MonkeyPatch, updates: list[dict[str, Any]], error: Exception, code: str
) -> None:
    async def fake_apply(*_: object, **__: object) -> ImportApplyOut:
        raise error

    monkeypatch.setattr(apply_jobs.services, "apply_batches", fake_apply)
    await apply_jobs.run_apply_job("job-1", ACTOR, ["b1"], MappingFileSchema(), "a" * 64)

    final = updates[-1]
    assert final["status"] == "FAILED"
    assert final["error_code"] == code
    assert "boom" not in final["error"]


async def test_start_apply_creates_running_job_and_spawns_task(monkeypatch: pytest.MonkeyPatch) -> None:
    log: list[dict[str, Any]] = []
    session = _Session(log)
    ran: list[str] = []

    async def fake_validate(*_: object) -> tuple[str, list[str]]:
        return "ctx-1", ["b1"]

    async def fake_run(job_id: str, *_: object) -> None:
        ran.append(job_id)

    monkeypatch.setattr(apply_jobs.services, "validate_apply_request", fake_validate)
    monkeypatch.setattr(apply_jobs, "run_apply_job", fake_run)

    job, task = await apply_jobs.start_apply(
        session, ACTOR, ["b1"], MappingFileSchema(), "a" * 64  # type: ignore[arg-type]
    )
    await task
    assert (job.status, job.stage, job.project_context_id) == ("RUNNING", "QUEUED", "ctx-1")
    assert ran == ["job-1"]


async def test_start_apply_returns_409_when_obra_already_running(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _Session([], fail_commit=True)

    async def fake_validate(*_: object) -> tuple[str, list[str]]:
        return "ctx-1", ["b1"]

    monkeypatch.setattr(apply_jobs.services, "validate_apply_request", fake_validate)
    with pytest.raises(ConflictError, match="APPLY_IN_PROGRESS"):
        await apply_jobs.start_apply(
            session, ACTOR, ["b1"], MappingFileSchema(), "a" * 64  # type: ignore[arg-type]
        )
    assert session.rolled_back


def test_to_out_maps_progress_and_result() -> None:
    job = MondayApplyJob(
        id="job-1",
        project_context_id="ctx-1",
        status="COMPLETED",
        stage="DONE",
        result=_out().model_dump(mode="json", by_alias=True),
        created_at=datetime(2026, 10, 14, 12, 0, 0),
    )
    out = apply_jobs.to_out(job)
    assert out.progress == 100
    assert out.result is not None and out.result.created == 1
    assert out.finished_at is None
    assert SimpleNamespace(stage="RECONCILING").stage in apply_jobs._PROGRESS
