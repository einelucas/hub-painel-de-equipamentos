"""Verificação rápida e direta (sem HTTP) da Etapa 7B: estados especiais
(Standby/Cancelado/Em Saneamento) e exceções de fluxo (FIXED_SUPPLIER /
IMPORTATION). Roda contra o banco TEST (neondb_test), não toca em DEV/C2.
"""

from __future__ import annotations

import asyncio
import os
import uuid

os.environ["DATABASE_URL"] = (
    "postgresql://neondb_owner:npg_zDEtCQS7s8Yl@"
    "ep-red-field-b48nnf5d-pooler.c-6.us-east-2.aws.neon.tech/neondb_test"
    "?sslmode=require&channel_binding=require"
)
os.environ["APP_ENV"] = "test"

from sqlalchemy import select  # noqa: E402

from app.core.auth import CurrentUser  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.core.errors import ConflictError, DomainError  # noqa: E402
from app.core.permissions import Role  # noqa: E402
from app.models.equipment import Discipline, Equipment, ProjectContext, Unit  # noqa: E402
from app.models.user import User  # noqa: E402
from app.modules.equipments.service import create_equipment  # noqa: E402
from app.modules.workflow import exceptions as exceptions_service  # noqa: E402
from app.modules.workflow import operational_status  # noqa: E402
from app.modules.workflow.service import available_transitions, execute_transition  # noqa: E402


async def expect_error(coro, exc_type) -> None:
    try:
        await coro
    except exc_type:
        return
    raise AssertionError(f"Esperava {exc_type.__name__}, mas não ocorreu erro")


async def main() -> None:
    async with SessionLocal() as session:
        admin = (
            (await session.execute(select(User).where(User.role == Role.ADMIN, User.active.is_(True))))
            .scalars()
            .first()
        )
        actor = CurrentUser(id=admin.id, email=admin.email, name=admin.name, role=Role.ADMIN, active=True)

        suffix = uuid.uuid4().hex[:6].upper()
        unit = Unit(code=f"ETP7B{suffix}", name="Unidade verificação 7B", active=True)
        session.add(unit)
        await session.flush()
        context = ProjectContext(
            unit_id=unit.id, code=f"ETP7B{suffix}", name="Contexto verificação 7B", active=True
        )
        session.add(context)
        await session.flush()
        discipline = Discipline(code=f"MM-ETP7B{suffix}", name="Metal Mec. 7B", active=True)
        session.add(discipline)
        await session.flush()
        await session.commit()

        equipment = await create_equipment(
            session,
            values={
                "project_context_id": context.id,
                "name": "Equipamento verificação 7B",
                "origin": None,
                "startup_at": None,
                "discipline_id": discipline.id,
                "area_id": None,
                "work_package_ids": [],
                "responsible_user_id": None,
                "criticality": None,
                "capex_estimated": None,
            },
            actor=actor,
        )
        equipment_id = equipment.id
        print(f"Equipamento de teste criado: {equipment_id}")

        # --- Standby ---
        status = await operational_status.enter_standby(
            session, equipment_id, "Aguardando definição de escopo", actor
        )
        assert status.operational_status == "STANDBY", status
        assert len(status.events) == 1 and status.events[0].kind == "STANDBY_ENTERED"
        row = (await session.execute(select(Equipment).where(Equipment.id == equipment_id))).scalar_one()
        assert row.current_stage == 0, "Standby não deve alterar a fase"
        print("OK: Standby ativado mantendo fase", row.current_stage)

        # Advance blocked while STANDBY.
        await expect_error(
            execute_transition(session, equipment_id=equipment_id, target_stage=1, reason=None, actor=actor),
            DomainError,
        )
        print("OK: avanço bloqueado durante Standby")

        # Lift standby -> back to ACTIVE, same stage.
        status = await operational_status.lift_standby(session, equipment_id, None, actor)
        assert status.operational_status == "ACTIVE", status
        row = (await session.execute(select(Equipment).where(Equipment.id == equipment_id))).scalar_one()
        assert row.current_stage == 0
        print("OK: Standby removido, volta a ACTIVE na mesma fase")

        # --- Em Saneamento ---
        # Advance the equipment to stage 1 first (negotiation.equalized).
        from app.modules.processes.service import ensure_process, update_process  # noqa: E402
        from app.models.process import Negotiation  # noqa: E402

        await ensure_process(session, Negotiation, equipment_id)
        await update_process(
            session,
            model=Negotiation,
            entity_name="Negotiation",
            equipment_id=equipment_id,
            changes={"equalized": True},
            actor=actor,
        )
        await execute_transition(session, equipment_id=equipment_id, target_stage=1, reason=None, actor=actor)
        row = (await session.execute(select(Equipment).where(Equipment.id == equipment_id))).scalar_one()
        assert row.current_stage == 1
        print("OK: avançou manualmente para a fase 1")

        status = await operational_status.enter_sanitation(
            session, equipment_id, "Necessário refazer levantamento técnico", actor
        )
        assert status.operational_status == "IN_SANITATION"
        row = (await session.execute(select(Equipment).where(Equipment.id == equipment_id))).scalar_one()
        assert row.current_stage == 0, "Saneamento deve resetar para fase 0 (Nova Demanda)"
        origin_event = [e for e in status.events if e.kind == "SANITATION_ENTERED"][0]
        assert origin_event.stage_at_event == 1, "Deve registrar a fase de origem (1), não a nova (0)"
        print("OK: Em Saneamento -> fase 0, origem registrada =", origin_event.stage_at_event)

        status = await operational_status.end_sanitation(session, equipment_id, None, actor)
        assert status.operational_status == "ACTIVE"
        row = (await session.execute(select(Equipment).where(Equipment.id == equipment_id))).scalar_one()
        assert row.current_stage == 0, "Fim do saneamento mantém fase 0"
        print("OK: Saneamento encerrado, permanece na fase 0, ACTIVE")

        # --- Cancelamento (definitivo) ---
        status = await operational_status.cancel_equipment(
            session, equipment_id, "Projeto descontinuado", actor
        )
        assert status.operational_status == "CANCELLED"
        await expect_error(
            execute_transition(session, equipment_id=equipment_id, target_stage=1, reason=None, actor=actor),
            DomainError,
        )
        await expect_error(
            operational_status.cancel_equipment(session, equipment_id, "de novo", actor),
            DomainError,
        )
        print("OK: Cancelamento é definitivo (bloqueia avanço e recancelamento)")

        # --- Exceções: FIXED_SUPPLIER ---
        equipment2 = await create_equipment(
            session,
            values={
                "project_context_id": context.id,
                "name": "Equipamento verificação 7B (exceção)",
                "origin": None,
                "startup_at": None,
                "discipline_id": discipline.id,
                "area_id": None,
                "work_package_ids": [],
                "responsible_user_id": None,
                "criticality": None,
                "capex_estimated": None,
            },
            actor=actor,
        )
        eq2_id = equipment2.id
        exc = await exceptions_service.create_exception(
            session,
            eq2_id,
            exception_type="FIXED_SUPPLIER",
            justification="Fornecedor único homologado",
            actor=actor,
        )
        assert exc.status == "ACTIVE" and exc.intended_target_stage == 5
        print("OK: exceção FIXED_SUPPLIER criada, alvo =", exc.intended_target_stage)

        # Second active exception must be rejected.
        await expect_error(
            exceptions_service.create_exception(
                session, eq2_id, exception_type="IMPORTATION", justification="outra", actor=actor
            ),
            ConflictError,
        )
        print("OK: segunda exceção ativa simultânea é rejeitada")

        # Stage 1 -> 2 should be dispensed by FIXED_SUPPLIER (no negotiation data needed).
        await execute_transition(session, equipment_id=eq2_id, target_stage=1, reason=None, actor=actor)
        await execute_transition(session, equipment_id=eq2_id, target_stage=2, reason=None, actor=actor)
        row2 = (await session.execute(select(Equipment).where(Equipment.id == eq2_id))).scalar_one()
        assert row2.current_stage == 2
        print("OK: exceção FIXED_SUPPLIER dispensou negociação, avançou manualmente até a fase 2")

        transitions = await available_transitions(session, eq2_id, actor)
        missing = transitions.transitions[0].missing_requirements
        assert not any(
            item.code in ("negotiation_equalized_required", "negotiation_date_required") for item in missing
        )
        print("OK: requisitos dispensados não aparecem como pendentes")

        print("\nTodas as verificações da Etapa 7B passaram.")

        # Cleanup: remove test fixtures from neondb_test (não é C2/DEV).
        await session.rollback()


if __name__ == "__main__":
    asyncio.run(main())
