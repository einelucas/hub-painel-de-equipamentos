from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_permission
from app.core.database import get_session
from app.core.permissions import Permission
from app.modules.workflow import operational_status, service
from app.modules.workflow import reopen as reopen_service
from app.modules.workflow import waivers as waivers_service
from app.modules.workflow.schemas import (
    AvailableTransitionsOut,
    EquipmentOperationalStatusOut,
    HistoryOut,
    JustificationIn,
    OptionalJustificationIn,
    ReopenDecisionIn,
    ReopenRequestCreateIn,
    ReopenRequestListOut,
    ReopenRequestOut,
    RequirementWaiverCreateIn,
    RequirementWaiverListOut,
    RequirementWaiverOut,
    RequirementWaiverRevokeIn,
    TransitionRequestIn,
)

router = APIRouter(tags=["workflow"])


@router.get(
    "/equipments/{equipment_id}/available-transitions", response_model=AvailableTransitionsOut
)
async def get_available_transitions(
    equipment_id: str,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.WORKFLOW_READ)),
) -> AvailableTransitionsOut:
    return await service.available_transitions(session, equipment_id, actor)


@router.post("/equipments/{equipment_id}/transitions", response_model=AvailableTransitionsOut)
async def post_transition(
    equipment_id: str,
    body: TransitionRequestIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.WORKFLOW_TRANSITION)),
) -> AvailableTransitionsOut:
    return await service.execute_transition(
        session,
        equipment_id=equipment_id,
        target_stage=body.target_stage,
        reason=body.reason,
        actor=actor,
    )


@router.get("/equipments/{equipment_id}/history", response_model=HistoryOut)
async def get_history(
    equipment_id: str,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.WORKFLOW_READ)),
) -> HistoryOut:
    return await service.history(session, equipment_id, actor)


# --- Etapa 7B: estado operacional (Standby / Cancelado / Em Saneamento) ---


@router.get(
    "/equipments/{equipment_id}/operational-status",
    response_model=EquipmentOperationalStatusOut,
)
async def get_operational_status(
    equipment_id: str,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.WORKFLOW_READ)),
) -> EquipmentOperationalStatusOut:
    return await operational_status.get_operational_status(session, equipment_id, actor)


@router.post(
    "/equipments/{equipment_id}/standby",
    response_model=EquipmentOperationalStatusOut,
)
async def post_standby(
    equipment_id: str,
    body: JustificationIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.WORKFLOW_TRANSITION)),
) -> EquipmentOperationalStatusOut:
    return await operational_status.enter_standby(session, equipment_id, body.justification, actor)


@router.post(
    "/equipments/{equipment_id}/standby/lift",
    response_model=EquipmentOperationalStatusOut,
)
async def post_lift_standby(
    equipment_id: str,
    body: OptionalJustificationIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.WORKFLOW_TRANSITION)),
) -> EquipmentOperationalStatusOut:
    return await operational_status.lift_standby(session, equipment_id, body.justification, actor)


@router.post(
    "/equipments/{equipment_id}/cancel",
    response_model=EquipmentOperationalStatusOut,
)
async def post_cancel(
    equipment_id: str,
    body: JustificationIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.WORKFLOW_TRANSITION)),
) -> EquipmentOperationalStatusOut:
    return await operational_status.cancel_equipment(session, equipment_id, body.justification, actor)


@router.post(
    "/equipments/{equipment_id}/sanitation",
    response_model=EquipmentOperationalStatusOut,
)
async def post_sanitation(
    equipment_id: str,
    body: JustificationIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.WORKFLOW_TRANSITION)),
) -> EquipmentOperationalStatusOut:
    return await operational_status.enter_sanitation(session, equipment_id, body.justification, actor)


@router.post(
    "/equipments/{equipment_id}/sanitation/end",
    response_model=EquipmentOperationalStatusOut,
)
async def post_end_sanitation(
    equipment_id: str,
    body: OptionalJustificationIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.WORKFLOW_TRANSITION)),
) -> EquipmentOperationalStatusOut:
    return await operational_status.end_sanitation(session, equipment_id, body.justification, actor)


# --- Etapa 7.1: dispensa de requisitos por grupo (RequirementWaiver) ---
# Substitui as exceções de workflow rígidas da Etapa 7B (FIXED_SUPPLIER/
# IMPORTATION) — ver docs/validation/etapa-07-1-requirement-waivers.md.


@router.get(
    "/equipments/{equipment_id}/requirement-waivers",
    response_model=RequirementWaiverListOut,
)
async def get_requirement_waivers(
    equipment_id: str,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.WORKFLOW_READ)),
) -> RequirementWaiverListOut:
    return await waivers_service.list_waivers(session, equipment_id, actor)


@router.post(
    "/equipments/{equipment_id}/requirement-waivers",
    response_model=RequirementWaiverOut,
)
async def post_requirement_waiver(
    equipment_id: str,
    body: RequirementWaiverCreateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.WORKFLOW_TRANSITION)),
) -> RequirementWaiverOut:
    return await waivers_service.create_waiver(
        session,
        equipment_id,
        stage=body.stage,
        requirement_group_code=body.requirement_group_code,
        reason_code=body.reason_code,
        justification=body.justification,
        actor=actor,
    )


@router.post(
    "/equipments/{equipment_id}/requirement-waivers/{waiver_id}/revoke",
    response_model=RequirementWaiverOut,
)
async def post_revoke_requirement_waiver(
    equipment_id: str,
    waiver_id: str,
    body: RequirementWaiverRevokeIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.WORKFLOW_TRANSITION)),
) -> RequirementWaiverOut:
    return await waivers_service.revoke_waiver(
        session, equipment_id, waiver_id, revoke_reason=body.revoke_reason, actor=actor
    )


# --- Etapa 7C: reabertura com aprovação ---


@router.get(
    "/equipments/{equipment_id}/reopen-requests",
    response_model=ReopenRequestListOut,
)
async def get_reopen_requests(
    equipment_id: str,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.WORKFLOW_READ)),
) -> ReopenRequestListOut:
    return await reopen_service.list_reopen_requests(session, equipment_id, actor)


@router.post(
    "/equipments/{equipment_id}/reopen-requests",
    response_model=ReopenRequestOut,
)
async def post_reopen_request(
    equipment_id: str,
    body: ReopenRequestCreateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.WORKFLOW_REOPEN_REQUEST)),
) -> ReopenRequestOut:
    return await reopen_service.request_reopen(
        session,
        equipment_id,
        target_stage=body.target_stage,
        justification=body.justification,
        actor=actor,
    )


@router.post(
    "/equipments/{equipment_id}/reopen-requests/{request_id}/approve",
    response_model=ReopenRequestOut,
)
async def post_approve_reopen_request(
    equipment_id: str,
    request_id: str,
    body: ReopenDecisionIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.WORKFLOW_REOPEN_APPROVE)),
) -> ReopenRequestOut:
    return await reopen_service.approve_reopen(
        session, equipment_id, request_id, note=body.note, actor=actor
    )


@router.post(
    "/equipments/{equipment_id}/reopen-requests/{request_id}/reject",
    response_model=ReopenRequestOut,
)
async def post_reject_reopen_request(
    equipment_id: str,
    request_id: str,
    body: ReopenDecisionIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.WORKFLOW_REOPEN_APPROVE)),
) -> ReopenRequestOut:
    return await reopen_service.reject_reopen(
        session, equipment_id, request_id, note=body.note, actor=actor
    )
