"""Caixa interna e decisões de regressão do Painel de Equipamentos."""

from __future__ import annotations

import asyncio

from sqlalchemy import delete, func, select, update

from app.models.access import UserUnitAccess
from app.models.equipment import Equipment, WorkflowTransition
from app.models.notification import USER_NOTIFICATION_MODULE, UserNotification
from app.models.workflow_extras import ReopenRequest
from tests.integration.test_workflow_routes import _advance, _new_equipment


async def _pending_request(client, auth_header, *, requester: str = "ANALYST") -> tuple[str, str]:
    equipment_id = await _new_equipment(
        client, auth_header, f"Regressão por {requester.lower()}"
    )
    await _advance(client, auth_header, equipment_id, 1)
    await _advance(client, auth_header, equipment_id, 2)
    response = await client.post(
        f"/api/v1/equipments/{equipment_id}/reopen-requests",
        json={"targetStage": 1, "justification": "Revisar equalização técnica"},
        headers=auth_header(requester),
    )
    assert response.status_code == 200, response.text
    return equipment_id, response.json()["id"]


async def test_request_notifies_admin_and_read_state_does_not_decide(
    client, auth_header
) -> None:
    equipment_id, request_id = await _pending_request(client, auth_header)

    inbox = await client.get("/api/v1/notifications/inbox", headers=auth_header("ADMIN"))
    assert inbox.status_code == 200, inbox.text
    items = inbox.json()["items"]
    assert len(items) == 1
    notification = items[0]
    assert notification["moduleKey"] == USER_NOTIFICATION_MODULE
    assert notification["eventType"] == "REOPEN_REQUESTED"
    assert notification["equipmentId"] == equipment_id
    assert notification["reopenRequestId"] == request_id
    assert "Revisar equalização técnica" in notification["message"]

    count = await client.get(
        "/api/v1/notifications/unread-count", headers=auth_header("ADMIN")
    )
    assert count.json() == {"count": 1}

    marked = await client.patch(
        f"/api/v1/notifications/{notification['id']}/read",
        headers=auth_header("ADMIN"),
    )
    assert marked.status_code == 200
    assert marked.json()["readAt"] is not None

    pending = await client.get(
        "/api/v1/notifications/pending-approvals", headers=auth_header("ADMIN")
    )
    assert pending.status_code == 200
    assert pending.json()["pagination"]["total"] == 1
    assert pending.json()["items"][0]["id"] == request_id

async def test_user_cannot_read_another_users_notification(client, auth_header) -> None:
    _, _ = await _pending_request(client, auth_header)
    admin_inbox = await client.get(
        "/api/v1/notifications/inbox", headers=auth_header("ADMIN")
    )
    notification_id = admin_inbox.json()["items"][0]["id"]

    forbidden = await client.patch(
        f"/api/v1/notifications/{notification_id}/read",
        headers=auth_header("ANALYST"),
    )
    assert forbidden.status_code == 404


async def test_notification_inbox_respects_current_unit_scope(
    client, auth_header, db_session
) -> None:
    equipment_id, request_id = await _pending_request(client, auth_header)
    approved = await client.post(
        f"/api/v1/equipments/{equipment_id}/reopen-requests/{request_id}/approve",
        json={},
        headers=auth_header("ADMIN"),
    )
    assert approved.status_code == 200
    visible = await client.get(
        "/api/v1/notifications/inbox", headers=auth_header("ANALYST")
    )
    notification_id = visible.json()["items"][0]["id"]
    analyst_id = (
        await client.get("/api/v1/auth/me", headers=auth_header("ANALYST"))
    ).json()["id"]
    await db_session.execute(
        delete(UserUnitAccess).where(UserUnitAccess.user_id == analyst_id)
    )
    await db_session.commit()

    hidden = await client.get(
        "/api/v1/notifications/inbox", headers=auth_header("ANALYST")
    )
    assert hidden.json()["items"] == []
    count = await client.get(
        "/api/v1/notifications/unread-count", headers=auth_header("ANALYST")
    )
    assert count.json() == {"count": 0}
    cannot_mark = await client.patch(
        f"/api/v1/notifications/{notification_id}/read",
        headers=auth_header("ANALYST"),
    )
    assert cannot_mark.status_code == 404


async def test_admin_can_approve_own_request_without_redundant_result_notification(
    client, auth_header, db_session
) -> None:
    equipment_id, request_id = await _pending_request(
        client, auth_header, requester="ADMIN"
    )
    decision = await client.post(
        f"/api/v1/equipments/{equipment_id}/reopen-requests/{request_id}/approve",
        json={"note": "Aprovado pelo administrador solicitante"},
        headers=auth_header("ADMIN"),
    )
    assert decision.status_code == 200, decision.text
    assert decision.json()["status"] == "APPROVED"
    assert decision.json()["requestedBy"]["id"] == decision.json()["decidedBy"]["id"]

    pending = await client.get(
        "/api/v1/notifications/pending-approvals", headers=auth_header("ADMIN")
    )
    assert pending.json()["pagination"]["total"] == 0
    event_types = (
        await db_session.execute(
            select(UserNotification.event_type).where(
                UserNotification.reopen_request_id == request_id
            )
        )
    ).scalars().all()
    assert event_types == ["REOPEN_REQUESTED"]


async def test_admin_can_reject_own_request(client, auth_header) -> None:
    equipment_id, request_id = await _pending_request(
        client, auth_header, requester="ADMIN"
    )
    decision = await client.post(
        f"/api/v1/equipments/{equipment_id}/reopen-requests/{request_id}/reject",
        json={"note": "Solicitação revista pelo próprio administrador"},
        headers=auth_header("ADMIN"),
    )
    assert decision.status_code == 200, decision.text
    assert decision.json()["status"] == "REJECTED"
    stage = await client.get(
        f"/api/v1/equipments/{equipment_id}/available-transitions",
        headers=auth_header("VIEWER"),
    )
    assert stage.json()["currentStage"] == 2


async def test_analyst_cannot_reject_reopen_request(client, auth_header) -> None:
    equipment_id, request_id = await _pending_request(client, auth_header)
    decision = await client.post(
        f"/api/v1/equipments/{equipment_id}/reopen-requests/{request_id}/reject",
        json={"note": "Tentativa sem privilégio"},
        headers=auth_header("ANALYST"),
    )
    assert decision.status_code == 403


async def test_decision_notifies_requester_and_removes_pending_approval(
    client, auth_header
) -> None:
    equipment_id, request_id = await _pending_request(client, auth_header)
    decision = await client.post(
        f"/api/v1/equipments/{equipment_id}/reopen-requests/{request_id}/reject",
        json={"note": "Manter fase atual por enquanto"},
        headers=auth_header("ADMIN"),
    )
    assert decision.status_code == 200

    requester_inbox = await client.get(
        "/api/v1/notifications/inbox", headers=auth_header("ANALYST")
    )
    items = requester_inbox.json()["items"]
    assert len(items) == 1
    assert items[0]["eventType"] == "REOPEN_REJECTED"
    assert "Manter fase atual por enquanto" in items[0]["message"]

    pending = await client.get(
        "/api/v1/notifications/pending-approvals", headers=auth_header("ADMIN")
    )
    assert pending.json()["pagination"]["total"] == 0


async def test_stale_request_does_not_transition_or_generate_success_notification(
    client, auth_header, db_session
) -> None:
    equipment_id, request_id = await _pending_request(client, auth_header)
    await db_session.execute(
        update(Equipment).where(Equipment.id == equipment_id).values(current_stage=3)
    )
    await db_session.commit()

    decision = await client.post(
        f"/api/v1/equipments/{equipment_id}/reopen-requests/{request_id}/approve",
        json={},
        headers=auth_header("ADMIN"),
    )
    assert decision.status_code == 409
    transitions = await db_session.scalar(
        select(func.count(WorkflowTransition.id)).where(
            WorkflowTransition.equipment_id == equipment_id,
            WorkflowTransition.from_stage == 3,
            WorkflowTransition.to_stage == 1,
        )
    )
    assert transitions == 0
    requester_inbox = await client.get(
        "/api/v1/notifications/inbox", headers=auth_header("ANALYST")
    )
    assert requester_inbox.json()["items"] == []


async def test_duplicate_pending_request_is_blocked_and_notification_is_not_duplicated(
    client, auth_header, db_session
) -> None:
    equipment_id, request_id = await _pending_request(client, auth_header)
    duplicate = await client.post(
        f"/api/v1/equipments/{equipment_id}/reopen-requests",
        json={"targetStage": 0, "justification": "Segunda solicitação"},
        headers=auth_header("ANALYST"),
    )
    assert duplicate.status_code == 409
    request_count = await db_session.scalar(
        select(func.count(ReopenRequest.id)).where(
            ReopenRequest.equipment_id == equipment_id
        )
    )
    notification_count = await db_session.scalar(
        select(func.count(UserNotification.id)).where(
            UserNotification.reopen_request_id == request_id,
            UserNotification.event_type == "REOPEN_REQUESTED",
        )
    )
    assert request_count == 1
    assert notification_count == 1


async def test_concurrent_decisions_create_only_one_transition(
    client, auth_header, db_session
) -> None:
    equipment_id, request_id = await _pending_request(client, auth_header)
    url = f"/api/v1/equipments/{equipment_id}/reopen-requests/{request_id}/approve"
    first, second = await asyncio.gather(
        client.post(url, json={"note": "Decisão A"}, headers=auth_header("ADMIN")),
        client.post(url, json={"note": "Decisão B"}, headers=auth_header("ADMIN")),
    )
    assert sorted((first.status_code, second.status_code)) == [200, 422]
    transition_count = await db_session.scalar(
        select(func.count(WorkflowTransition.id)).where(
            WorkflowTransition.equipment_id == equipment_id,
            WorkflowTransition.from_stage == 2,
            WorkflowTransition.to_stage == 1,
        )
    )
    assert transition_count == 1


async def test_existing_workflow_events_are_mirrored_to_equipment_responsible(
    client, auth_header
) -> None:
    equipment_id = await _new_equipment(client, auth_header, "Eventos internos")
    analyst = await client.get("/api/v1/auth/me", headers=auth_header("ANALYST"))
    assigned = await client.patch(
        f"/api/v1/equipments/{equipment_id}",
        json={"responsibleUserId": analyst.json()["id"]},
        headers=auth_header("ANALYST"),
    )
    assert assigned.status_code == 200, assigned.text
    for target_stage in range(1, 9):
        await _advance(client, auth_header, equipment_id, target_stage)

    response = await client.get(
        "/api/v1/notifications/inbox", headers=auth_header("ANALYST")
    )
    assert response.status_code == 200
    event_types = {item["eventType"] for item in response.json()["items"]}
    assert {"KICKOFF", "FUP", "COMPLETED"}.issubset(event_types)
