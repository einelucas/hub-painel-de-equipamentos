"""Processo de aquisição: entidades 1:1, state machine 0–8, reabertura e histórico."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.models.audit import AuditLog
from app.models.equipment import EquipmentComponent, WorkflowTransition
from app.models.process import Contract, LegalProcess, Negotiation, PurchaseOrder, PurchaseRequest
from app.shared.audit import record_audit
from tests.helpers import grant_unit

# Requisito de cada transição `target - 1 -> target`.
# Dados fictícios de teste: nenhum número/contrato real do processo.
# Etapa 7A: Contract/PurchaseRequest/PurchaseOrder são 1:N — a etapa 6, 7 e a
# conclusão (8) criam um registro via POST em vez de fazer PATCH num único
# processo. A conclusão (8) usa a regra nova (seção 6): fornecedor + OC +
# Valor Total do Projeto, não mais os requisitos de fases anteriores.
_ADVANCE_PAYLOAD: dict[int, tuple[str, dict[str, object]]] = {
    2: ("negotiation", {"equalized": True}),
    3: ("negotiation", {"negotiatedAt": "2026-02-10"}),
    4: ("legal", {"openedAt": "2026-02-12", "ticketNumber": "TICKET-0001"}),
    5: ("legal", {"draftPrepared": True, "draftApproved": True}),
}


async def _catalogs(client, auth_header, suffix: str = "W") -> dict[str, str]:
    headers = auth_header("ADMIN")
    unit = (
        await client.post(
            "/api/v1/units", json={"code": f"U-{suffix}", "name": f"Unidade {suffix}"}, headers=headers
        )
    ).json()
    context = (
        await client.post(
            f"/api/v1/units/{unit['id']}/project-contexts",
            json={"code": f"CTX-{suffix}", "name": f"Contexto {suffix}"},
            headers=headers,
        )
    ).json()
    await grant_unit(client, auth_header, unit["id"])
    return {"unit": unit["id"], "context": context["id"]}


async def _new_equipment(client, auth_header, name: str = "Compressor de teste") -> str:
    catalogs = await _catalogs(client, auth_header, name[:3].upper())
    created = await client.post(
        "/api/v1/equipments",
        json={"projectContextId": catalogs["context"], "name": name},
        headers=auth_header("ANALYST"),
    )
    assert created.status_code == 201
    return str(created.json()["id"])


async def _advance(client, auth_header, equipment_id: str, target_stage: int):
    """Preenche o requisito da etapa (quando houver) e solicita o avanço."""
    payload = _ADVANCE_PAYLOAD.get(target_stage)
    if payload is not None:
        resource, body = payload
        patched = await client.patch(
            f"/api/v1/equipments/{equipment_id}/{resource}",
            json=body,
            headers=auth_header("ANALYST"),
        )
        assert patched.status_code == 200, patched.text
    if target_stage == 6:
        created = await client.post(
            f"/api/v1/equipments/{equipment_id}/contracts",
            json={"contractNumber": "CT-0001", "executedAt": "2026-03-01"},
            headers=auth_header("ANALYST"),
        )
        assert created.status_code == 201, created.text
    if target_stage == 7:
        created = await client.post(
            f"/api/v1/equipments/{equipment_id}/purchase-requests",
            json={"kind": "SC", "requestNumber": "SC-0001", "requestedAt": "2026-03-05"},
            headers=auth_header("ANALYST"),
        )
        assert created.status_code == 201, created.text
    if target_stage == 8:
        await _make_completable(client, auth_header, equipment_id)
    return await client.post(
        f"/api/v1/equipments/{equipment_id}/transitions",
        json={"targetStage": target_stage},
        headers=auth_header("ANALYST"),
    )


async def _make_completable(client, auth_header, equipment_id: str) -> None:
    """Satisfaz a regra de conclusão (Etapa 7, seção 6): fornecedor + pelo
    menos uma OC + Valor Total do Projeto preenchido."""
    order = await client.post(
        f"/api/v1/equipments/{equipment_id}/purchase-orders",
        json={"orderNumber": "OC-0001", "orderedAt": "2026-03-10", "amount": "1000.00"},
        headers=auth_header("ANALYST"),
    )
    assert order.status_code == 201, order.text
    supplier = await client.post(
        "/api/v1/suppliers",
        json={"legalName": f"Fornecedor {equipment_id[:8]}"},
        headers=auth_header("ANALYST"),
    )
    assert supplier.status_code == 201, supplier.text
    linked = await client.post(
        f"/api/v1/equipments/{equipment_id}/suppliers",
        json={"supplierId": supplier.json()["id"]},
        headers=auth_header("ANALYST"),
    )
    assert linked.status_code == 201, linked.text
    valued = await client.patch(
        f"/api/v1/equipments/{equipment_id}",
        json={"projectTotalValue": "150000.00"},
        headers=auth_header("ANALYST"),
    )
    assert valued.status_code == 200, valued.text


async def test_process_entities_are_created_once_per_equipment(
    client, auth_header, db_session
) -> None:
    equipment_id = await _new_equipment(client, auth_header, "Bomba processo")

    empty = await client.get(
        f"/api/v1/equipments/{equipment_id}/negotiation", headers=auth_header("VIEWER")
    )
    assert empty.status_code == 200
    assert empty.json()["id"] is None
    assert empty.json()["equalized"] is False

    for _ in range(3):
        patched = await client.patch(
            f"/api/v1/equipments/{equipment_id}/negotiation",
            json={"equalized": True},
            headers=auth_header("ANALYST"),
        )
        assert patched.status_code == 200
    assert patched.json()["equalized"] is True

    count = (
        await db_session.execute(
            select(func.count(Negotiation.id)).where(Negotiation.equipment_id == equipment_id)
        )
    ).scalar_one()
    assert count == 1

    processes = await client.get(
        f"/api/v1/equipments/{equipment_id}/processes", headers=auth_header("VIEWER")
    )
    assert processes.status_code == 200
    assert set(processes.json()) == {
        "negotiation",
        "legal",
        "contract",
        "purchaseRequest",
        "purchaseOrder",
    }


async def test_full_workflow_zero_to_eight(client, auth_header, db_session) -> None:
    equipment_id = await _new_equipment(client, auth_header, "Fluxo completo")

    for target in range(1, 9):
        response = await _advance(client, auth_header, equipment_id, target)
        assert response.status_code == 200, response.text
        assert response.json()["currentStage"] == target

    detail = await client.get(f"/api/v1/equipments/{equipment_id}", headers=auth_header("VIEWER"))
    assert detail.json()["equipment"]["currentStage"] == 8

    transitions = (
        (
            await db_session.execute(
                select(WorkflowTransition).where(WorkflowTransition.equipment_id == equipment_id)
            )
        )
        .scalars()
        .all()
    )
    assert [(item.from_stage, item.to_stage) for item in sorted(transitions, key=lambda i: i.to_stage)] == [
        (index, index + 1) for index in range(8)
    ]

    concluded = await client.get(
        f"/api/v1/equipments/{equipment_id}/available-transitions", headers=auth_header("VIEWER")
    )
    # Etapa 7C: reabertura não aparece mais aqui — é feita via
    # /reopen-requests (solicitação + aprovação), e a fase 8 já é final.
    assert concluded.json()["transitions"] == []


async def test_advance_blocked_without_requirements(client, auth_header, db_session) -> None:
    equipment_id = await _new_equipment(client, auth_header, "Sem requisito")
    started = await _advance(client, auth_header, equipment_id, 1)
    assert started.status_code == 200

    available = await client.get(
        f"/api/v1/equipments/{equipment_id}/available-transitions", headers=auth_header("VIEWER")
    )
    advance = available.json()["transitions"][0]
    assert advance["targetStage"] == 2
    assert advance["canExecute"] is False
    assert [item["code"] for item in advance["missingRequirements"]] == [
        "negotiation_equalized_required"
    ]

    blocked = await client.post(
        f"/api/v1/equipments/{equipment_id}/transitions",
        json={"targetStage": 2},
        headers=auth_header("ANALYST"),
    )
    assert blocked.status_code == 422
    assert "equaliza" in blocked.json()["error"].lower()

    assert (
        await db_session.execute(
            select(func.count(WorkflowTransition.id)).where(
                WorkflowTransition.equipment_id == equipment_id
            )
        )
    ).scalar_one() == 1


async def test_cannot_skip_stages_or_replay_transition(client, auth_header) -> None:
    equipment_id = await _new_equipment(client, auth_header, "Sem pulo")
    skipped = await client.post(
        f"/api/v1/equipments/{equipment_id}/transitions",
        json={"targetStage": 3},
        headers=auth_header("ANALYST"),
    )
    assert skipped.status_code == 422
    assert "pular etapas" in skipped.json()["error"]

    await _advance(client, auth_header, equipment_id, 1)
    replay = await client.post(
        f"/api/v1/equipments/{equipment_id}/transitions",
        json={"targetStage": 1},
        headers=auth_header("ANALYST"),
    )
    assert replay.status_code == 409


async def test_current_stage_cannot_be_changed_by_patch(client, auth_header) -> None:
    equipment_id = await _new_equipment(client, auth_header, "Patch bloqueado")
    response = await client.patch(
        f"/api/v1/equipments/{equipment_id}",
        json={"name": "Renomeado", "currentStage": 5},
        headers=auth_header("ANALYST"),
    )
    assert response.status_code == 422

    detail = await client.get(f"/api/v1/equipments/{equipment_id}", headers=auth_header("VIEWER"))
    assert detail.json()["equipment"]["currentStage"] == 0
    assert detail.json()["equipment"]["name"] == "Patch bloqueado"


async def test_reopen_request_requires_permission_and_justification(client, auth_header) -> None:
    # Etapa 7C: reabertura não é mais imediata via /transitions — é uma
    # solicitação (`ReopenRequest`) que só muda a fase depois de aprovada.
    equipment_id = await _new_equipment(client, auth_header, "Reabertura solicitação")
    await _advance(client, auth_header, equipment_id, 1)
    await _advance(client, auth_header, equipment_id, 2)

    missing_justification = await client.post(
        f"/api/v1/equipments/{equipment_id}/reopen-requests",
        json={"targetStage": 1},
        headers=auth_header("ANALYST"),
    )
    assert missing_justification.status_code == 422

    blocked = await client.post(
        f"/api/v1/equipments/{equipment_id}/reopen-requests",
        json={"targetStage": 1, "justification": "Fornecedor revisou a proposta"},
        headers=auth_header("VIEWER"),
    )
    assert blocked.status_code == 403

    response = await client.post(
        f"/api/v1/equipments/{equipment_id}/reopen-requests",
        json={"targetStage": 1, "justification": "Fornecedor revisou a proposta"},
        headers=auth_header("ANALYST"),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "PENDING"
    assert body["targetStage"] == 1

    # A fase não muda enquanto a solicitação está pendente.
    unchanged = await client.get(
        f"/api/v1/equipments/{equipment_id}/available-transitions", headers=auth_header("VIEWER")
    )
    assert unchanged.json()["currentStage"] == 2


@pytest.mark.parametrize(
    ("role", "expected"),
    [("VIEWER", 403), ("ANALYST", 403), ("ADMIN", 200)],
)
async def test_reopen_approval_requires_permission(client, auth_header, role, expected) -> None:
    equipment_id = await _new_equipment(client, auth_header, f"Aprovação reabertura {role}")
    await _advance(client, auth_header, equipment_id, 1)
    await _advance(client, auth_header, equipment_id, 2)

    request = await client.post(
        f"/api/v1/equipments/{equipment_id}/reopen-requests",
        json={"targetStage": 1, "justification": "Fornecedor revisou a proposta"},
        headers=auth_header("ANALYST"),
    )
    assert request.status_code == 201
    request_id = request.json()["id"]

    decision = await client.post(
        f"/api/v1/equipments/{equipment_id}/reopen-requests/{request_id}/approve",
        json={},
        headers=auth_header(role),
    )
    assert decision.status_code == expected
    if expected == 200:
        assert decision.json()["status"] == "APPROVED"
        after = await client.get(
            f"/api/v1/equipments/{equipment_id}/available-transitions", headers=auth_header("VIEWER")
        )
        assert after.json()["currentStage"] == 1


async def test_reopen_target_must_be_prior_stage(client, auth_header) -> None:
    equipment_id = await _new_equipment(client, auth_header, "Reabertura alvo inválido")
    await _advance(client, auth_header, equipment_id, 1)
    await _advance(client, auth_header, equipment_id, 2)

    future_or_equal = await client.post(
        f"/api/v1/equipments/{equipment_id}/reopen-requests",
        json={"targetStage": 2, "justification": "Fase igual à atual"},
        headers=auth_header("ANALYST"),
    )
    assert future_or_equal.status_code == 422

    prior = await client.post(
        f"/api/v1/equipments/{equipment_id}/reopen-requests",
        json={"targetStage": 1, "justification": "Fase anterior válida"},
        headers=auth_header("ANALYST"),
    )
    assert prior.status_code == 201


async def test_reopen_requester_cannot_approve_own_request(client, auth_header) -> None:
    equipment_id = await _new_equipment(client, auth_header, "Reabertura auto-aprovação")
    await _advance(client, auth_header, equipment_id, 1)
    await _advance(client, auth_header, equipment_id, 2)

    request = await client.post(
        f"/api/v1/equipments/{equipment_id}/reopen-requests",
        json={"targetStage": 1, "justification": "Necessário revisar"},
        headers=auth_header("ANALYST"),
    )
    assert request.status_code == 201
    request_id = request.json()["id"]

    reject = await client.post(
        f"/api/v1/equipments/{equipment_id}/reopen-requests/{request_id}/reject",
        json={"note": "Fora do escopo"},
        headers=auth_header("ADMIN"),
    )
    assert reject.status_code == 200
    assert reject.json()["status"] == "REJECTED"

    still_pending_actions = await client.post(
        f"/api/v1/equipments/{equipment_id}/reopen-requests/{request_id}/approve",
        json={},
        headers=auth_header("ADMIN"),
    )
    assert still_pending_actions.status_code == 422


async def test_history_consolidates_transitions_and_data_changes(client, auth_header) -> None:
    equipment_id = await _new_equipment(client, auth_header, "Histórico")
    await _advance(client, auth_header, equipment_id, 1)
    await _advance(client, auth_header, equipment_id, 2)
    await client.patch(
        f"/api/v1/equipments/{equipment_id}/negotiation",
        json={"equalized": True},
        headers=auth_header("ANALYST"),
    )
    await client.post(
        f"/api/v1/equipments/{equipment_id}/transitions",
        json={"targetStage": 1, "reason": "Renegociar escopo"},
        headers=auth_header("ADMIN"),
    )

    history = await client.get(
        f"/api/v1/equipments/{equipment_id}/history", headers=auth_header("VIEWER")
    )
    assert history.status_code == 200
    items = history.json()["items"]
    kinds = {item["kind"] for item in items}
    assert kinds == {"transition", "change"}
    assert any(item["reason"] == "Renegociar escopo" for item in items)
    assert any(item["action"] == "negotiation.update" for item in items)
    assert any(item["action"] == "equipment.create" for item in items)
    timestamps = [item["occurredAt"] for item in items]
    assert timestamps == sorted(timestamps, reverse=True)


async def test_history_surfaces_migration_style_subentity_audits(
    client, auth_header, db_session
) -> None:
    """GAP-002 (Etapa 6D): AuditLogs de sub-entidade no formato exato da
    migração (`entityId` da própria sub-entidade, sem `metadata.equipmentId`
    — ver `monday_import/apply.py`) devem aparecer no histórico do
    equipamento, resolvidos por relacionamento. Nenhum dado histórico é
    reescrito e nenhuma WorkflowTransition é fabricada."""
    equipment_id = await _new_equipment(client, auth_header, "Migração legada")

    component = EquipmentComponent(equipment_id=equipment_id, name="Motor legado")
    negotiation = Negotiation(equipment_id=equipment_id)
    legal = LegalProcess(equipment_id=equipment_id)
    contract = Contract(equipment_id=equipment_id)
    purchase_request = PurchaseRequest(equipment_id=equipment_id)
    purchase_order = PurchaseOrder(equipment_id=equipment_id)
    db_session.add_all([component, negotiation, legal, contract, purchase_request, purchase_order])
    await db_session.flush()

    for model_name, entity_id in [
        ("EquipmentComponent", component.id),
        ("Negotiation", negotiation.id),
        ("LegalProcess", legal.id),
        ("Contract", contract.id),
        ("PurchaseRequest", purchase_request.id),
        ("PurchaseOrder", purchase_order.id),
    ]:
        await record_audit(
            db_session,
            action="migration.import",
            entity=model_name,
            entity_id=entity_id,
            new_data={"migrated": True},
            # Sem `equipmentId` no metadata — exatamente como a migração real grava.
            metadata={"sourceSystem": "monday"},
        )
    await db_session.commit()

    response = await client.get(
        f"/api/v1/equipments/{equipment_id}/history", headers=auth_header("VIEWER")
    )
    assert response.status_code == 200
    items = response.json()["items"]

    migration_entries = [item for item in items if item["action"] == "migration.import"]
    # component + Negotiation + LegalProcess + Contract + PurchaseRequest + PurchaseOrder.
    assert len(migration_entries) == 6
    assert all(item["title"] == "Importado do Monday" for item in migration_entries)
    assert all(item["kind"] == "change" for item in migration_entries)

    transition_count = (
        await db_session.execute(
            select(func.count(WorkflowTransition.id)).where(
                WorkflowTransition.equipment_id == equipment_id
            )
        )
    ).scalar_one()
    assert transition_count == 0


async def test_reopen_is_audited(client, auth_header, db_session) -> None:
    equipment_id = await _new_equipment(client, auth_header, "Auditoria reabertura")
    await _advance(client, auth_header, equipment_id, 1)
    await _advance(client, auth_header, equipment_id, 2)

    request = await client.post(
        f"/api/v1/equipments/{equipment_id}/reopen-requests",
        json={"targetStage": 1, "justification": "Revalidar proposta"},
        headers=auth_header("ANALYST"),
    )
    assert request.status_code == 201
    request_id = request.json()["id"]

    approved = await client.post(
        f"/api/v1/equipments/{equipment_id}/reopen-requests/{request_id}/approve",
        json={"note": "Confirmado com o solicitante"},
        headers=auth_header("ADMIN"),
    )
    assert approved.status_code == 200

    audits = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.entityId == request_id,
                    AuditLog.action == "reopenrequest.approve",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audits) == 1
    assert audits[0].newData["current_stage"] == 1
    assert audits[0].previousData["current_stage"] == 2

    transitions = (
        (
            await db_session.execute(
                select(WorkflowTransition).where(WorkflowTransition.equipment_id == equipment_id)
            )
        )
        .scalars()
        .all()
    )
    reopen_transition = [item for item in transitions if item.to_stage == 1 and item.from_stage == 2]
    assert len(reopen_transition) == 1
    assert reopen_transition[0].reason == "Revalidar proposta"


async def test_viewer_cannot_transition_or_write_process(client, auth_header) -> None:
    equipment_id = await _new_equipment(client, auth_header, "Viewer bloqueado")
    transition = await client.post(
        f"/api/v1/equipments/{equipment_id}/transitions",
        json={"targetStage": 1},
        headers=auth_header("VIEWER"),
    )
    process = await client.patch(
        f"/api/v1/equipments/{equipment_id}/negotiation",
        json={"equalized": True},
        headers=auth_header("VIEWER"),
    )
    assert transition.status_code == 403
    assert process.status_code == 403


# --- GAP-008: edição de processo independente da etapa atual -----------


async def test_process_editable_after_conclusion_without_changing_stage(
    client, auth_header, db_session
) -> None:
    """Equipamento concluído (stage=8): todo dado de processo continua
    editável via PATCH, e editar nunca muda `current_stage` — só o endpoint
    de transições faz isso."""
    equipment_id = await _new_equipment(client, auth_header, "Concluido editavel")
    for target in range(1, 9):
        response = await _advance(client, auth_header, equipment_id, target)
        assert response.status_code == 200, response.text
    assert response.json()["currentStage"] == 8

    before = (
        await client.get(f"/api/v1/equipments/{equipment_id}/processes", headers=auth_header("VIEWER"))
    ).json()
    contract_id = before["contracts"][0]["id"]
    request_id = before["purchaseRequests"][0]["id"]
    order_id = before["purchaseOrders"][0]["id"]

    edits = [
        ("negotiation", {"equalized": True, "negotiatedAt": "2026-05-01"}),
        ("legal", {"ticketNumber": "TICKET-CORRIGIDO"}),
        (f"contracts/{contract_id}", {"contractNumber": "CT-CORRIGIDO"}),
        (f"purchase-requests/{request_id}", {"kind": "OCI", "requestNumber": "OCI-0002"}),
        (f"purchase-orders/{order_id}", {"orderNumber": "OC-CORRIGIDA", "amount": 1500.5}),
    ]
    for resource, payload in edits:
        patched = await client.patch(
            f"/api/v1/equipments/{equipment_id}/{resource}",
            json=payload,
            headers=auth_header("ANALYST"),
        )
        assert patched.status_code == 200, patched.text

    detail = await client.get(f"/api/v1/equipments/{equipment_id}", headers=auth_header("VIEWER"))
    assert detail.json()["equipment"]["currentStage"] == 8

    processes = (
        await client.get(f"/api/v1/equipments/{equipment_id}/processes", headers=auth_header("VIEWER"))
    ).json()
    assert processes["legal"]["ticketNumber"] == "TICKET-CORRIGIDO"
    assert processes["contracts"][0]["contractNumber"] == "CT-CORRIGIDO"
    assert processes["purchaseRequests"][0]["kind"] == "OCI"
    assert processes["purchaseRequests"][0]["requestNumber"] == "OCI-0002"
    assert processes["purchaseOrders"][0]["orderNumber"] == "OC-CORRIGIDA"


async def test_viewer_cannot_write_process_at_stage_8(client, auth_header) -> None:
    equipment_id = await _new_equipment(client, auth_header, "Viewer concluido")
    for target in range(1, 9):
        await _advance(client, auth_header, equipment_id, target)

    blocked = await client.post(
        f"/api/v1/equipments/{equipment_id}/purchase-requests",
        json={"kind": "SC"},
        headers=auth_header("VIEWER"),
    )
    assert blocked.status_code == 403
