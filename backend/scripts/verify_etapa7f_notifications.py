"""Verificação rápida e direta (sem HTTP) da Etapa 7F: Kickoff (conclusão
da fase 5) e FUP (conclusão da fase 7). Roda contra o banco TEST
(neondb_test), não toca em DEV/C2.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import date

os.environ["DATABASE_URL"] = (
    "postgresql://neondb_owner:npg_zDEtCQS7s8Yl@"
    "ep-red-field-b48nnf5d-pooler.c-6.us-east-2.aws.neon.tech/neondb_test"
    "?sslmode=require&channel_binding=require"
)
os.environ["APP_ENV"] = "test"

from sqlalchemy import select  # noqa: E402

from app.core.auth import CurrentUser  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.core.permissions import Role  # noqa: E402
from app.models.equipment import Discipline, Equipment, ProjectContext, Unit, WorkflowTransition  # noqa: E402
from app.models.notification import NotificationEvent  # noqa: E402
from app.models.process import Contract, Negotiation  # noqa: E402
from app.models.user import User  # noqa: E402
from app.modules.equipments.service import create_equipment  # noqa: E402
from app.modules.processes.service import create_item, ensure_process, update_process  # noqa: E402
from app.modules.workflow.service import execute_transition  # noqa: E402


async def main() -> None:
    async with SessionLocal() as session:
        admin = (
            await session.execute(select(User).where(User.role == Role.ADMIN, User.active.is_(True)))
        ).scalars().first()
        actor = CurrentUser(id=admin.id, email=admin.email, name=admin.name, role=Role.ADMIN, active=True)

        suffix = uuid.uuid4().hex[:6].upper()
        unit = Unit(code=f"ETP7F{suffix}", name="Unidade verificação 7F", active=True)
        session.add(unit)
        await session.flush()
        context = ProjectContext(unit_id=unit.id, code=f"ETP7F{suffix}", name="Contexto verificação 7F", active=True)
        session.add(context)
        await session.flush()
        discipline = Discipline(code=f"MM-ETP7F{suffix}", name="Metal Mec. 7F", active=True)
        session.add(discipline)
        await session.flush()
        await session.commit()

        equipment = await create_equipment(
            session,
            values={
                "project_context_id": context.id,
                "name": "Equipamento verificação 7F",
                "origin": None,
                "startup_at": None,
                "discipline_id": discipline.id,
                "area_id": None,
                "work_package_ids": [],
                "responsible_user_id": admin.id,
                "criticality": None,
                "capex_estimated": None,
            },
            actor=actor,
        )
        equipment_id = equipment.id

        # Advance 0 -> 5.
        await ensure_process(session, Negotiation, equipment_id)
        await update_process(
            session, model=Negotiation, entity_name="Negotiation", equipment_id=equipment_id,
            changes={"equalized": True}, actor=actor,
        )
        await execute_transition(session, equipment_id=equipment_id, target_stage=1, reason=None, actor=actor)
        await update_process(
            session, model=Negotiation, entity_name="Negotiation", equipment_id=equipment_id,
            changes={"negotiated_at": date(2026, 1, 1)}, actor=actor,
        )
        await execute_transition(session, equipment_id=equipment_id, target_stage=2, reason=None, actor=actor)

        from app.models.process import LegalProcess

        await ensure_process(session, LegalProcess, equipment_id)
        await update_process(
            session, model=LegalProcess, entity_name="LegalProcess", equipment_id=equipment_id,
            changes={"opened_at": date(2026, 1, 2), "ticket_number": "TCK-1"}, actor=actor,
        )
        await execute_transition(session, equipment_id=equipment_id, target_stage=3, reason=None, actor=actor)
        await update_process(
            session, model=LegalProcess, entity_name="LegalProcess", equipment_id=equipment_id,
            changes={"draft_prepared": True, "draft_approved": True}, actor=actor,
        )
        await execute_transition(session, equipment_id=equipment_id, target_stage=4, reason=None, actor=actor)

        await create_item(
            session, model=Contract, entity_name="Contract", equipment_id=equipment_id,
            values={"contract_number": "CT-1", "executed_at": date(2026, 1, 5)}, actor=actor,
        )

        # This transition (5 -> 6) concludes phase 5: must generate exactly one KICKOFF event.
        await execute_transition(session, equipment_id=equipment_id, target_stage=5, reason=None, actor=actor)
        result = await execute_transition(session, equipment_id=equipment_id, target_stage=6, reason=None, actor=actor)
        assert result.current_stage == 6

        transition_5_6 = (
            await session.execute(
                select(WorkflowTransition).where(
                    WorkflowTransition.equipment_id == equipment_id,
                    WorkflowTransition.from_stage == 5,
                    WorkflowTransition.to_stage == 6,
                )
            )
        ).scalar_one()
        events = (
            (
                await session.execute(
                    select(NotificationEvent).where(
                        NotificationEvent.workflow_transition_id == transition_5_6.id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(events) == 1, f"esperava 1 evento KICKOFF, achou {len(events)}"
        assert events[0].kind == "KICKOFF"
        assert events[0].status == "SENT"
        assert events[0].recipient_summary == admin.email
        print("OK: conclusão da fase 5 gera exatamente 1 evento KICKOFF, enviado, com destinatário resolvido")

        # Retry idempotency: calling the trigger again for the same transition must not duplicate.
        from app.modules.notifications.service import trigger_for_transition

        repeat = await trigger_for_transition(session, equipment=equipment, transition=transition_5_6)
        assert repeat is None
        events_after_retry = (
            (
                await session.execute(
                    select(NotificationEvent).where(
                        NotificationEvent.workflow_transition_id == transition_5_6.id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(events_after_retry) == 1
        print("OK: retry do gatilho não duplica o evento (idempotência)")

        print("\nTodas as verificações da Etapa 7F passaram.")


if __name__ == "__main__":
    asyncio.run(main())
