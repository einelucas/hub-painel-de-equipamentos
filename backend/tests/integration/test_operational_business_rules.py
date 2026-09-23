"""Etapa 7 (7B–7E): estados especiais, exceções de fluxo, reabertura com
aprovação, cardinalidade 1:N e comentários — via HTTP, mesmo padrão de
`test_workflow_routes.py`.
"""

from __future__ import annotations

from tests.integration.test_workflow_routes import _advance, _make_completable, _new_equipment


async def test_standby_keeps_stage_blocks_advance_and_lift_restores(client, auth_header) -> None:
    equipment_id = await _new_equipment(client, auth_header, "Standby")
    await _advance(client, auth_header, equipment_id, 1)

    missing_justification = await client.post(
        f"/api/v1/equipments/{equipment_id}/standby", json={}, headers=auth_header("ANALYST")
    )
    assert missing_justification.status_code == 422

    entered = await client.post(
        f"/api/v1/equipments/{equipment_id}/standby",
        json={"justification": "Aguardando definição de escopo"},
        headers=auth_header("ANALYST"),
    )
    assert entered.status_code == 200, entered.text
    assert entered.json()["operationalStatus"] == "STANDBY"

    blocked = await client.post(
        f"/api/v1/equipments/{equipment_id}/transitions",
        json={"targetStage": 2},
        headers=auth_header("ANALYST"),
    )
    assert blocked.status_code == 422

    lifted = await client.post(
        f"/api/v1/equipments/{equipment_id}/standby/lift", json={}, headers=auth_header("ANALYST")
    )
    assert lifted.status_code == 200
    assert lifted.json()["operationalStatus"] == "ACTIVE"

    detail = await client.get(f"/api/v1/equipments/{equipment_id}", headers=auth_header("VIEWER"))
    assert detail.json()["equipment"]["currentStage"] == 1


async def test_cancel_is_definitive_and_blocks_advance(client, auth_header) -> None:
    equipment_id = await _new_equipment(client, auth_header, "Cancelamento")

    cancelled = await client.post(
        f"/api/v1/equipments/{equipment_id}/cancel",
        json={"justification": "Projeto descontinuado"},
        headers=auth_header("ANALYST"),
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["operationalStatus"] == "CANCELLED"

    blocked = await client.post(
        f"/api/v1/equipments/{equipment_id}/transitions",
        json={"targetStage": 1},
        headers=auth_header("ANALYST"),
    )
    assert blocked.status_code == 422

    recancel = await client.post(
        f"/api/v1/equipments/{equipment_id}/cancel",
        json={"justification": "de novo"},
        headers=auth_header("ANALYST"),
    )
    assert recancel.status_code == 422


async def test_sanitation_resets_to_stage_zero_and_ending_keeps_it(client, auth_header) -> None:
    equipment_id = await _new_equipment(client, auth_header, "Saneamento")
    await _advance(client, auth_header, equipment_id, 1)
    await _advance(client, auth_header, equipment_id, 2)

    entered = await client.post(
        f"/api/v1/equipments/{equipment_id}/sanitation",
        json={"justification": "Necessário revisar levantamento técnico"},
        headers=auth_header("ANALYST"),
    )
    assert entered.status_code == 200
    assert entered.json()["operationalStatus"] == "IN_SANITATION"

    detail = await client.get(f"/api/v1/equipments/{equipment_id}", headers=auth_header("VIEWER"))
    assert detail.json()["equipment"]["currentStage"] == 0
    assert detail.json()["equipment"]["operationalStatus"] == "IN_SANITATION"

    ended = await client.post(
        f"/api/v1/equipments/{equipment_id}/sanitation/end", json={}, headers=auth_header("ANALYST")
    )
    assert ended.status_code == 200
    assert ended.json()["operationalStatus"] == "ACTIVE"

    detail_after = await client.get(f"/api/v1/equipments/{equipment_id}", headers=auth_header("VIEWER"))
    assert detail_after.json()["equipment"]["currentStage"] == 0
    assert detail_after.json()["equipment"]["operationalStatus"] == "ACTIVE"


async def test_fixed_supplier_exception_dispenses_negotiation_and_reaches_stage_five(
    client, auth_header
) -> None:
    equipment_id = await _new_equipment(client, auth_header, "ExcecaoFornecedor")

    created = await client.post(
        f"/api/v1/equipments/{equipment_id}/workflow-exceptions",
        json={"type": "FIXED_SUPPLIER", "justification": "Fornecedor único homologado"},
        headers=auth_header("ANALYST"),
    )
    assert created.status_code == 201, created.text
    assert created.json()["intendedTargetStage"] == 5

    second = await client.post(
        f"/api/v1/equipments/{equipment_id}/workflow-exceptions",
        json={"type": "IMPORTATION", "justification": "outra"},
        headers=auth_header("ANALYST"),
    )
    assert second.status_code == 409

    # No negotiation data filled — dispensed by the exception.
    step1 = await client.post(
        f"/api/v1/equipments/{equipment_id}/transitions",
        json={"targetStage": 1},
        headers=auth_header("ANALYST"),
    )
    assert step1.status_code == 200, step1.text
    step2 = await client.post(
        f"/api/v1/equipments/{equipment_id}/transitions",
        json={"targetStage": 2},
        headers=auth_header("ANALYST"),
    )
    assert step2.status_code == 200, step2.text

    transitions = await client.get(
        f"/api/v1/equipments/{equipment_id}/available-transitions", headers=auth_header("VIEWER")
    )
    missing_codes = {item["code"] for item in transitions.json()["transitions"][0]["missingRequirements"]}
    assert "negotiation_date_required" not in missing_codes


async def test_importation_exception_reaches_stage_seven_without_contract_or_purchase_request(
    client, auth_header
) -> None:
    equipment_id = await _new_equipment(client, auth_header, "ExcecaoImportacao")

    created = await client.post(
        f"/api/v1/equipments/{equipment_id}/workflow-exceptions",
        json={"type": "IMPORTATION", "justification": "Equipamento importado, sem SC/OCI local"},
        headers=auth_header("ANALYST"),
    )
    assert created.status_code == 201
    assert created.json()["intendedTargetStage"] == 7

    # Stages 1-4 (negotiation/legal) are NOT dispensed by IMPORTATION — only
    # contract/SC-OCI are — so they still need real data via `_advance`.
    for target in (1, 2, 3, 4):
        response = await _advance(client, auth_header, equipment_id, target)
        assert response.status_code == 200, (target, response.text)

    # Stages 5 and 6 gate on contract/SC-OCI data — dispensed by the
    # exception, so a bare transition (no pre-filled data) must succeed.
    for target in (5, 6, 7):
        response = await client.post(
            f"/api/v1/equipments/{equipment_id}/transitions",
            json={"targetStage": target},
            headers=auth_header("ANALYST"),
        )
        assert response.status_code == 200, (target, response.text)

    detail = await client.get(f"/api/v1/equipments/{equipment_id}", headers=auth_header("VIEWER"))
    assert detail.json()["equipment"]["currentStage"] == 7

    # Contract/SC-OCI remain empty — never auto-filled.
    processes = await client.get(
        f"/api/v1/equipments/{equipment_id}/processes", headers=auth_header("VIEWER")
    )
    assert processes.json()["contracts"] == []
    assert processes.json()["purchaseRequests"] == []

    # Contract/SC-OCI stay optionally fillable even under the exception.
    optional_contract = await client.post(
        f"/api/v1/equipments/{equipment_id}/contracts",
        json={"contractNumber": "CT-IMPORT-1"},
        headers=auth_header("ANALYST"),
    )
    assert optional_contract.status_code == 201


async def test_reopen_request_then_approve_changes_stage_reject_does_not(client, auth_header) -> None:
    equipment_id = await _new_equipment(client, auth_header, "ReaberturaFluxo")
    await _advance(client, auth_header, equipment_id, 1)
    await _advance(client, auth_header, equipment_id, 2)

    request = await client.post(
        f"/api/v1/equipments/{equipment_id}/reopen-requests",
        json={"targetStage": 1, "justification": "Revisar negociação"},
        headers=auth_header("ANALYST"),
    )
    assert request.status_code == 201
    request_id = request.json()["id"]

    unchanged = await client.get(f"/api/v1/equipments/{equipment_id}", headers=auth_header("VIEWER"))
    assert unchanged.json()["equipment"]["currentStage"] == 2

    unauthorized = await client.post(
        f"/api/v1/equipments/{equipment_id}/reopen-requests/{request_id}/approve",
        json={},
        headers=auth_header("ANALYST"),
    )
    assert unauthorized.status_code == 403

    approved = await client.post(
        f"/api/v1/equipments/{equipment_id}/reopen-requests/{request_id}/approve",
        json={},
        headers=auth_header("ADMIN"),
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"

    changed = await client.get(f"/api/v1/equipments/{equipment_id}", headers=auth_header("VIEWER"))
    assert changed.json()["equipment"]["currentStage"] == 1

    # Rejection path.
    await _advance(client, auth_header, equipment_id, 2)
    request2 = await client.post(
        f"/api/v1/equipments/{equipment_id}/reopen-requests",
        json={"targetStage": 1, "justification": "outra tentativa"},
        headers=auth_header("ANALYST"),
    )
    assert request2.status_code == 201
    rejected = await client.post(
        f"/api/v1/equipments/{equipment_id}/reopen-requests/{request2.json()['id']}/reject",
        json={"note": "Não procede"},
        headers=auth_header("ADMIN"),
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"
    still = await client.get(f"/api/v1/equipments/{equipment_id}", headers=auth_header("VIEWER"))
    assert still.json()["equipment"]["currentStage"] == 2


async def test_supplier_is_limited_to_one_and_replaceable(client, auth_header) -> None:
    equipment_id = await _new_equipment(client, auth_header, "FornecedorUnico")
    first = await client.post(
        "/api/v1/suppliers", json={"legalName": "Fornecedor A"}, headers=auth_header("ANALYST")
    )
    second = await client.post(
        "/api/v1/suppliers", json={"legalName": "Fornecedor B"}, headers=auth_header("ANALYST")
    )
    link1 = await client.post(
        f"/api/v1/equipments/{equipment_id}/suppliers",
        json={"supplierId": first.json()["id"]},
        headers=auth_header("ANALYST"),
    )
    assert link1.status_code == 201

    link2 = await client.post(
        f"/api/v1/equipments/{equipment_id}/suppliers",
        json={"supplierId": second.json()["id"]},
        headers=auth_header("ANALYST"),
    )
    assert link2.status_code == 409

    replaced = await client.put(
        f"/api/v1/equipments/{equipment_id}/suppliers",
        json={"supplierId": second.json()["id"]},
        headers=auth_header("ANALYST"),
    )
    assert replaced.status_code == 200
    assert replaced.json()["supplier"]["id"] == second.json()["id"]

    listed = await client.get(f"/api/v1/equipments/{equipment_id}/suppliers", headers=auth_header("VIEWER"))
    assert len(listed.json()["items"]) == 1


async def test_contracts_purchase_requests_and_orders_are_one_to_many(client, auth_header) -> None:
    equipment_id = await _new_equipment(client, auth_header, "Cardinalidade1N")

    for number in ("CT-A", "CT-B"):
        created = await client.post(
            f"/api/v1/equipments/{equipment_id}/contracts",
            json={"contractNumber": number},
            headers=auth_header("ANALYST"),
        )
        assert created.status_code == 201
    for number in ("SC-A", "SC-B"):
        created = await client.post(
            f"/api/v1/equipments/{equipment_id}/purchase-requests",
            json={"kind": "SC", "requestNumber": number},
            headers=auth_header("ANALYST"),
        )
        assert created.status_code == 201
    for number in ("OC-A", "OC-B"):
        created = await client.post(
            f"/api/v1/equipments/{equipment_id}/purchase-orders",
            json={"orderNumber": number, "amount": "10.00"},
            headers=auth_header("ANALYST"),
        )
        assert created.status_code == 201

    processes = await client.get(
        f"/api/v1/equipments/{equipment_id}/processes", headers=auth_header("VIEWER")
    )
    body = processes.json()
    assert len(body["contracts"]) == 2
    assert len(body["purchaseRequests"]) == 2
    assert len(body["purchaseOrders"]) == 2


async def test_completion_requires_stage_seven_supplier_order_and_total_value(client, auth_header) -> None:
    equipment_id = await _new_equipment(client, auth_header, "Conclusao")
    for target in (1, 2, 3, 4, 5, 6, 7):
        response = await _advance(client, auth_header, equipment_id, target)
        assert response.status_code == 200, (target, response.text)

    blocked = await client.post(
        f"/api/v1/equipments/{equipment_id}/transitions",
        json={"targetStage": 8},
        headers=auth_header("ANALYST"),
    )
    assert blocked.status_code == 422
    missing_codes = {
        item["code"]
        for item in (
            await client.get(
                f"/api/v1/equipments/{equipment_id}/available-transitions", headers=auth_header("VIEWER")
            )
        ).json()["transitions"][0]["missingRequirements"]
    }
    assert missing_codes == {
        "completion_supplier_required",
        "completion_purchase_order_required",
        "completion_project_total_value_required",
    }

    await _make_completable(client, auth_header, equipment_id)
    concluded = await client.post(
        f"/api/v1/equipments/{equipment_id}/transitions",
        json={"targetStage": 8},
        headers=auth_header("ANALYST"),
    )
    assert concluded.status_code == 200, concluded.text
    assert concluded.json()["currentStage"] == 8


async def test_comments_create_list_edit_and_have_no_attachments(client, auth_header) -> None:
    equipment_id = await _new_equipment(client, auth_header, "Comentarios")

    created = await client.post(
        f"/api/v1/equipments/{equipment_id}/comments",
        json={"text": "Primeiro comentário"},
        headers=auth_header("ANALYST"),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert "attachment" not in body
    assert "file" not in body
    assert body["text"] == "Primeiro comentário"
    assert body["author"]["email"]

    listed = await client.get(f"/api/v1/equipments/{equipment_id}/comments", headers=auth_header("VIEWER"))
    assert len(listed.json()["items"]) == 1

    edited = await client.patch(
        f"/api/v1/equipments/{equipment_id}/comments/{body['id']}",
        json={"text": "Editado"},
        headers=auth_header("ANALYST"),
    )
    assert edited.status_code == 200
    assert edited.json()["text"] == "Editado"

    # Jurídico/Suprimentos: consulta funciona, escrita é bloqueada.
    forbidden = await client.post(
        f"/api/v1/equipments/{equipment_id}/comments",
        json={"text": "Tentativa"},
        headers=auth_header("VIEWER"),
    )
    assert forbidden.status_code == 403


async def test_kickoff_and_fup_events_are_generated_once_per_transition(
    client, auth_header, db_session
) -> None:
    from sqlalchemy import select

    from app.models.notification import NotificationEvent

    equipment_id = await _new_equipment(client, auth_header, "Notificacoes")
    for target in (1, 2, 3, 4, 5, 6, 7, 8):
        response = await _advance(client, auth_header, equipment_id, target)
        assert response.status_code == 200, (target, response.text)

    events = (
        (
            await db_session.execute(
                select(NotificationEvent).where(NotificationEvent.equipment_id == equipment_id)
            )
        )
        .scalars()
        .all()
    )
    kickoff = [item for item in events if item.kind == "KICKOFF"]
    fup = [item for item in events if item.kind == "FUP"]
    assert len(kickoff) == 1
    assert len(fup) == 1
    assert kickoff[0].status in ("SENT", "FAILED")
    assert fup[0].status in ("SENT", "FAILED")
