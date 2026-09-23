"""Verificação rápida e direta (sem HTTP) da Etapa 7.1: dispensa de
requisitos por grupo (RequirementWaiver). Roda contra o banco TEST
(neondb_test), não toca em DEV/C2.
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
from app.models.process import Contract  # noqa: E402
from app.models.user import User  # noqa: E402
from app.modules.equipments.service import create_equipment  # noqa: E402
from app.modules.processes.service import create_item  # noqa: E402
from app.modules.workflow import waivers as waivers_service  # noqa: E402
from app.modules.workflow.service import available_transitions, execute_transition  # noqa: E402


async def expect_error(coro, *exc_types) -> None:
    try:
        await coro
    except exc_types:
        return
    raise AssertionError(f"Esperava um erro de {exc_types}, mas não ocorreu")


async def main() -> None:
    async with SessionLocal() as session:
        admin = (
            await session.execute(select(User).where(User.role == Role.ADMIN, User.active.is_(True)))
        ).scalars().first()
        actor = CurrentUser(id=admin.id, email=admin.email, name=admin.name, role=Role.ADMIN, active=True)

        suffix = uuid.uuid4().hex[:6].upper()
        unit = Unit(code=f"ETP71{suffix}", name="Unidade verificação 7.1", active=True)
        session.add(unit)
        await session.flush()
        context = ProjectContext(unit_id=unit.id, code=f"ETP71{suffix}", name="Contexto verificação 7.1", active=True)
        session.add(context)
        await session.flush()
        discipline = Discipline(code=f"MM-ETP71{suffix}", name="Metal Mec. 7.1", active=True)
        session.add(discipline)
        await session.flush()
        await session.commit()

        equipment = await create_equipment(
            session,
            values={
                "project_context_id": context.id,
                "name": "Equipamento verificação 7.1",
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

        # Stage 0 has no requirement group (gates none) -- advance freely to stage 1.
        transitions = await available_transitions(session, equipment_id, actor)
        assert transitions.transitions[0].requirement_groups == []
        result = await execute_transition(
            session, equipment_id=equipment_id, target_stage=1, reason=None, actor=actor
        )
        assert result.current_stage == 1

        # 1. Grupo incompleto sem waiver -> MISSING, bloqueia avanço (1 -> 2).
        transitions = await available_transitions(session, equipment_id, actor)
        group = transitions.transitions[0].requirement_groups[0]
        assert group.code == "NEGOTIATION_EQUALIZATION"
        assert group.status == "MISSING"
        assert group.waivable is True
        await expect_error(
            execute_transition(session, equipment_id=equipment_id, target_stage=2, reason=None, actor=actor),
            DomainError,
        )
        print("OK: grupo incompleto sem waiver -> MISSING, bloqueia avanço")

        # 2. Grupo não dispensável rejeita criação de waiver (stage errado).
        await expect_error(
            waivers_service.create_waiver(
                session, equipment_id, stage=7, requirement_group_code="SUPPLIER",
                reason_code="OTHER", justification="tentativa inválida", actor=actor,
            ),
            DomainError,
        )
        print("OK: grupo não dispensável (SUPPLIER) rejeita criação de waiver")

        # 3. justification obrigatória (validação de schema cobre isso via Pydantic;
        # aqui testamos a validação de serviço para chamada direta com string vazia).
        await expect_error(
            waivers_service.create_waiver(
                session, equipment_id, stage=1, requirement_group_code="NEGOTIATION_EQUALIZATION",
                reason_code="OTHER", justification="   ", actor=actor,
            ),
            DomainError,
        )
        print("OK: justificativa obrigatória (vazia rejeitada)")

        # 4. Cria waiver válido -> grupo fica WAIVED, avanço permitido (só 1 fase).
        waiver = await waivers_service.create_waiver(
            session, equipment_id, stage=1, requirement_group_code="NEGOTIATION_EQUALIZATION",
            reason_code="EXCEPTIONAL_PROCESS", justification="Negociação não se aplica a este caso", actor=actor,
        )
        assert waiver.status == "ACTIVE"
        transitions = await available_transitions(session, equipment_id, actor)
        group = transitions.transitions[0].requirement_groups[0]
        assert group.status == "WAIVED"
        assert group.waiver is not None and group.waiver.id == waiver.id
        print("OK: waiver criado -> grupo WAIVED")

        # 5. duplicate ACTIVE waiver rejeitado.
        await expect_error(
            waivers_service.create_waiver(
                session, equipment_id, stage=1, requirement_group_code="NEGOTIATION_EQUALIZATION",
                reason_code="OTHER", justification="outra tentativa", actor=actor,
            ),
            ConflictError,
        )
        print("OK: segunda dispensa ativa simultânea é rejeitada")

        # 6. waiver permite avançar UMA fase — nunca pula etapas.
        result = await execute_transition(session, equipment_id=equipment_id, target_stage=2, reason=None, actor=actor)
        assert result.current_stage == 2
        await expect_error(
            execute_transition(session, equipment_id=equipment_id, target_stage=4, reason=None, actor=actor),
            DomainError,
        )
        print("OK: waiver não pula etapas (avançou só 1 fase, bloqueou salto para 4)")

        # 7. Revogação volta requisito para MISSING se dado continuar ausente.
        # (equipamento já avançou da fase 1; revogar o waiver da fase 1 não afeta mais o avanço atual,
        # mas confirmamos que o registro e o estado refletem REVOKED.)
        revoked = await waivers_service.revoke_waiver(
            session, equipment_id, waiver.id, revoke_reason="Dado será preenchido", actor=actor,
        )
        assert revoked.status == "REVOKED"
        assert revoked.revoked_by is not None
        print("OK: revogação registrada (status REVOKED, revoked_by preenchido)")

        # Revoke already-revoked -> error.
        await expect_error(
            waivers_service.revoke_waiver(session, equipment_id, waiver.id, revoke_reason=None, actor=actor),
            DomainError,
        )
        print("OK: revogar uma dispensa já revogada é rejeitado")

        # 8. Contrato 1:N: exige número + data + arquivo no MESMO registro.
        # Cria um contrato com só número (sem data/arquivo) -> CONTRACT continua MISSING.
        await create_item(
            session, model=Contract, entity_name="Contract", equipment_id=equipment_id,
            values={"contract_number": "CT-PARCIAL"}, actor=actor,
        )
        # Avança manualmente até a fase 5 preenchendo negociação/jurídico.
        from datetime import date

        from app.models.process import LegalProcess, Negotiation
        from app.modules.processes.service import ensure_process, update_process

        await ensure_process(session, Negotiation, equipment_id)
        await update_process(
            session, model=Negotiation, entity_name="Negotiation", equipment_id=equipment_id,
            changes={"negotiated_at": date(2026, 1, 1)}, actor=actor,
        )
        # Equipamento já está na fase 2 (avançou no passo 6 usando o waiver).
        await execute_transition(session, equipment_id=equipment_id, target_stage=3, reason=None, actor=actor)
        await ensure_process(session, LegalProcess, equipment_id)
        await update_process(
            session, model=LegalProcess, entity_name="LegalProcess", equipment_id=equipment_id,
            changes={"opened_at": date(2026, 1, 2), "ticket_number": "TCK-1"}, actor=actor,
        )
        await execute_transition(session, equipment_id=equipment_id, target_stage=4, reason=None, actor=actor)
        await update_process(
            session, model=LegalProcess, entity_name="LegalProcess", equipment_id=equipment_id,
            changes={"draft_prepared": True, "draft_approved": True}, actor=actor,
        )
        await execute_transition(session, equipment_id=equipment_id, target_stage=5, reason=None, actor=actor)

        transitions = await available_transitions(session, equipment_id, actor)
        contract_group = next(
            g for g in transitions.transitions[0].requirement_groups if g.code == "CONTRACT"
        )
        assert contract_group.status == "MISSING", "contrato parcial (só número) não deve satisfazer o grupo"
        print("OK: contrato 1:N exige número+data+arquivo no MESMO registro (parcial continua MISSING)")

        # Second contract, now complete (with a fake file key set directly for the check).
        complete_contract = await create_item(
            session, model=Contract, entity_name="Contract", equipment_id=equipment_id,
            values={"contract_number": "CT-COMPLETO", "executed_at": date(2026, 1, 5)}, actor=actor,
        )
        row = (await session.execute(select(Contract).where(Contract.id == complete_contract.id))).scalar_one()
        row.file_storage_key = "contracts/fake/key.pdf"
        await session.commit()

        transitions = await available_transitions(session, equipment_id, actor)
        contract_group = next(
            g for g in transitions.transitions[0].requirement_groups if g.code == "CONTRACT"
        )
        assert contract_group.status == "SATISFIED"
        print("OK: contrato completo (mesmo registro) -> grupo SATISFIED")

        print("\nTodas as verificações da Etapa 7.1 passaram.")


if __name__ == "__main__":
    asyncio.run(main())
