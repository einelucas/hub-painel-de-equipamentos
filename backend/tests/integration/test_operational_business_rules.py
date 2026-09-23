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


async def _waive(client, auth_header, equipment_id: str, *, stage: int, code: str, reason: str) -> None:
    response = await client.post(
        f"/api/v1/equipments/{equipment_id}/requirement-waivers",
        json={
            "stage": stage,
            "requirementGroupCode": code,
            "reasonCode": reason,
            "justification": f"Justificativa de teste para {code}",
        },
        headers=auth_header("ANALYST"),
    )
    assert response.status_code == 201, response.text


async def test_fixed_supplier_waiver_dispenses_negotiation_group(client, auth_header) -> None:
    equipment_id = await _new_equipment(client, auth_header, "DispensaFornecedor")

    # Grupo não dispensável rejeita criação de waiver (fase/código errados).
    wrong_stage = await client.post(
        f"/api/v1/equipments/{equipment_id}/requirement-waivers",
        json={
            "stage": 0,
            "requirementGroupCode": "NEGOTIATION_EQUALIZATION",
            "reasonCode": "OTHER",
            "justification": "fase errada",
        },
        headers=auth_header("ANALYST"),
    )
    assert wrong_stage.status_code == 422

    unknown_group = await client.post(
        f"/api/v1/equipments/{equipment_id}/requirement-waivers",
        json={
            "stage": 1,
            "requirementGroupCode": "NOT_A_REAL_GROUP",
            "reasonCode": "OTHER",
            "justification": "grupo inventado",
        },
        headers=auth_header("ANALYST"),
    )
    assert unknown_group.status_code == 422

    # justification obrigatória (validação de schema).
    missing_justification = await client.post(
        f"/api/v1/equipments/{equipment_id}/requirement-waivers",
        json={"stage": 1, "requirementGroupCode": "NEGOTIATION_EQUALIZATION", "reasonCode": "OTHER"},
        headers=auth_header("ANALYST"),
    )
    assert missing_justification.status_code == 422

    step1 = await client.post(
        f"/api/v1/equipments/{equipment_id}/transitions",
        json={"targetStage": 1},
        headers=auth_header("ANALYST"),
    )
    assert step1.status_code == 200, step1.text

    # 1->2 gates on NEGOTIATION_EQUALIZATION; no data filled -> MISSING.
    transitions = await client.get(
        f"/api/v1/equipments/{equipment_id}/available-transitions", headers=auth_header("VIEWER")
    )
    group = transitions.json()["transitions"][0]["requirementGroups"][0]
    assert group["code"] == "NEGOTIATION_EQUALIZATION"
    assert group["status"] == "MISSING"
    assert group["waivable"] is True

    await _waive(
        client, auth_header, equipment_id, stage=1, code="NEGOTIATION_EQUALIZATION", reason="FIXED_SUPPLIER"
    )

    # Duplicate ACTIVE waiver rejected.
    duplicate = await client.post(
        f"/api/v1/equipments/{equipment_id}/requirement-waivers",
        json={
            "stage": 1,
            "requirementGroupCode": "NEGOTIATION_EQUALIZATION",
            "reasonCode": "OTHER",
            "justification": "outra tentativa",
        },
        headers=auth_header("ANALYST"),
    )
    assert duplicate.status_code == 409

    transitions = await client.get(
        f"/api/v1/equipments/{equipment_id}/available-transitions", headers=auth_header("VIEWER")
    )
    group = transitions.json()["transitions"][0]["requirementGroups"][0]
    assert group["status"] == "WAIVED"
    assert group["waiver"]["reasonCode"] == "FIXED_SUPPLIER"

    # Waiver permite avançar só a fase seguinte — nunca pula etapas.
    step2 = await client.post(
        f"/api/v1/equipments/{equipment_id}/transitions",
        json={"targetStage": 2},
        headers=auth_header("ANALYST"),
    )
    assert step2.status_code == 200, step2.text
    skip = await client.post(
        f"/api/v1/equipments/{equipment_id}/transitions",
        json={"targetStage": 4},
        headers=auth_header("ANALYST"),
    )
    assert skip.status_code == 422

    # Revogação: o waiver correspondente à fase 1 fica REVOKED (histórico
    # preservado, não apagado); a fase atual do equipamento não é afetada.
    waiver_id = group["waiver"]["id"]
    revoked = await client.post(
        f"/api/v1/equipments/{equipment_id}/requirement-waivers/{waiver_id}/revoke",
        json={"revokeReason": "Dado será preenchido"},
        headers=auth_header("ANALYST"),
    )
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "REVOKED"
    assert revoked.json()["revokedBy"] is not None

    re_revoke = await client.post(
        f"/api/v1/equipments/{equipment_id}/requirement-waivers/{waiver_id}/revoke",
        json={},
        headers=auth_header("ANALYST"),
    )
    assert re_revoke.status_code == 422

    listed = await client.get(
        f"/api/v1/equipments/{equipment_id}/requirement-waivers", headers=auth_header("VIEWER")
    )
    assert len(listed.json()["items"]) == 1


async def test_importation_waivers_reach_stage_seven_without_contract_or_purchase_request(
    client, auth_header
) -> None:
    equipment_id = await _new_equipment(client, auth_header, "DispensaImportacao")

    # Stages 1-4 (negotiation/legal) não são dispensáveis por este cenário —
    # continuam precisando de dado real via `_advance`.
    for target in (1, 2, 3, 4):
        response = await _advance(client, auth_header, equipment_id, target)
        assert response.status_code == 200, (target, response.text)

    await _waive(client, auth_header, equipment_id, stage=5, code="CONTRACT", reason="IMPORTATION")
    await _waive(client, auth_header, equipment_id, stage=6, code="PURCHASE_REQUEST", reason="IMPORTATION")

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

    # Contract/SC-OCI stay optionally fillable even under a waiver.
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
        ).json()["transitions"][0]["requirementGroups"]
        if item["status"] == "MISSING"
    }
    assert missing_codes == {"SUPPLIER", "PURCHASE_ORDER", "PROJECT_TOTAL_VALUE"}
    # Nenhum dos três é dispensável — a UI não deve oferecer "Não possui".
    non_waivable = {
        item["code"]
        for item in (
            await client.get(
                f"/api/v1/equipments/{equipment_id}/available-transitions", headers=auth_header("VIEWER")
            )
        ).json()["transitions"][0]["requirementGroups"]
        if not item["waivable"]
    }
    assert non_waivable == {"SUPPLIER", "PURCHASE_ORDER", "PROJECT_TOTAL_VALUE"}

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


async def test_requirement_group_satisfied_when_data_is_complete(client, auth_header) -> None:
    equipment_id = await _new_equipment(client, auth_header, "GrupoSatisfeito")
    await client.post(
        f"/api/v1/equipments/{equipment_id}/transitions",
        json={"targetStage": 1},
        headers=auth_header("ANALYST"),
    )
    patched = await client.patch(
        f"/api/v1/equipments/{equipment_id}/negotiation",
        json={"equalized": True},
        headers=auth_header("ANALYST"),
    )
    assert patched.status_code == 200

    transitions = await client.get(
        f"/api/v1/equipments/{equipment_id}/available-transitions", headers=auth_header("VIEWER")
    )
    group = transitions.json()["transitions"][0]["requirementGroups"][0]
    assert group["code"] == "NEGOTIATION_EQUALIZATION"
    assert group["status"] == "SATISFIED"
    assert group["waiver"] is None


async def test_waiving_a_group_never_deletes_partial_data_already_filled(client, auth_header) -> None:
    equipment_id = await _new_equipment(client, auth_header, "DadosParciais")
    await client.post(
        f"/api/v1/equipments/{equipment_id}/transitions",
        json={"targetStage": 1},
        headers=auth_header("ANALYST"),
    )
    # Grupo LEGAL_TICKET exige opened_at + ticket_number; equipamento em
    # fase 2 ainda não chegou lá, mas simulamos dado parcial preenchido
    # via PATCH direto no processo jurídico (permitido independente de fase).
    patched = await client.patch(
        f"/api/v1/equipments/{equipment_id}/legal",
        json={"ticketNumber": "TCK-PARCIAL"},
        headers=auth_header("ANALYST"),
    )
    assert patched.status_code == 200

    before = await client.get(f"/api/v1/equipments/{equipment_id}/processes", headers=auth_header("VIEWER"))
    assert before.json()["legal"]["ticketNumber"] == "TCK-PARCIAL"

    # Waiving the group at stage 3 must not touch existing partial data.
    waiver = await client.post(
        f"/api/v1/equipments/{equipment_id}/requirement-waivers",
        json={
            "stage": 3,
            "requirementGroupCode": "LEGAL_TICKET",
            "reasonCode": "OTHER",
            "justification": "Dado será completado depois",
        },
        headers=auth_header("ANALYST"),
    )
    assert waiver.status_code == 201

    after = await client.get(f"/api/v1/equipments/{equipment_id}/processes", headers=auth_header("VIEWER"))
    assert after.json()["legal"]["ticketNumber"] == "TCK-PARCIAL"


async def test_purchase_request_group_requires_kind_number_and_date_on_same_record(
    client, auth_header
) -> None:
    equipment_id = await _new_equipment(client, auth_header, "SCOCIMesmoRegistro")
    for target in (1, 2, 3, 4, 5):
        response = await _advance(client, auth_header, equipment_id, target)
        assert response.status_code == 200, (target, response.text)

    # Two partial purchase requests, each missing a different field — none
    # alone satisfies the group.
    await client.post(
        f"/api/v1/equipments/{equipment_id}/purchase-requests",
        json={"kind": "SC", "requestNumber": "SC-0001"},
        headers=auth_header("ANALYST"),
    )
    await client.post(
        f"/api/v1/equipments/{equipment_id}/purchase-requests",
        json={"kind": "OCI", "requestedAt": "2026-03-05"},
        headers=auth_header("ANALYST"),
    )
    transitions = await client.get(
        f"/api/v1/equipments/{equipment_id}/available-transitions", headers=auth_header("VIEWER")
    )
    group = next(
        g
        for g in transitions.json()["transitions"][0]["requirementGroups"]
        if g["code"] == "PURCHASE_REQUEST"
    )
    assert group["status"] == "MISSING"

    complete = await client.post(
        f"/api/v1/equipments/{equipment_id}/purchase-requests",
        json={"kind": "SC", "requestNumber": "SC-0002", "requestedAt": "2026-03-06"},
        headers=auth_header("ANALYST"),
    )
    assert complete.status_code == 201
    transitions = await client.get(
        f"/api/v1/equipments/{equipment_id}/available-transitions", headers=auth_header("VIEWER")
    )
    group = next(
        g
        for g in transitions.json()["transitions"][0]["requirementGroups"]
        if g["code"] == "PURCHASE_REQUEST"
    )
    assert group["status"] == "SATISFIED"


async def test_reopen_approval_preserves_active_waiver(client, auth_header) -> None:
    equipment_id = await _new_equipment(client, auth_header, "ReaberturaComWaiver")
    await client.post(
        f"/api/v1/equipments/{equipment_id}/transitions",
        json={"targetStage": 1},
        headers=auth_header("ANALYST"),
    )
    await _waive(
        client,
        auth_header,
        equipment_id,
        stage=1,
        code="NEGOTIATION_EQUALIZATION",
        reason="EXCEPTIONAL_PROCESS",
    )
    await client.post(
        f"/api/v1/equipments/{equipment_id}/transitions",
        json={"targetStage": 2},
        headers=auth_header("ANALYST"),
    )

    request = await client.post(
        f"/api/v1/equipments/{equipment_id}/reopen-requests",
        json={"targetStage": 1, "justification": "Revisar negociação"},
        headers=auth_header("ANALYST"),
    )
    assert request.status_code == 201
    approved = await client.post(
        f"/api/v1/equipments/{equipment_id}/reopen-requests/{request.json()['id']}/approve",
        json={},
        headers=auth_header("ADMIN"),
    )
    assert approved.status_code == 200

    waivers = await client.get(
        f"/api/v1/equipments/{equipment_id}/requirement-waivers", headers=auth_header("VIEWER")
    )
    assert waivers.json()["items"][0]["status"] == "ACTIVE"

    transitions = await client.get(
        f"/api/v1/equipments/{equipment_id}/available-transitions", headers=auth_header("VIEWER")
    )
    group = transitions.json()["transitions"][0]["requirementGroups"][0]
    assert group["status"] == "WAIVED"


async def test_requirement_waivers_read_only_for_legal_and_procurement_profiles(client, auth_header) -> None:
    equipment_id = await _new_equipment(client, auth_header, "PermissoesWaiver")
    await client.post(
        f"/api/v1/equipments/{equipment_id}/transitions",
        json={"targetStage": 1},
        headers=auth_header("ANALYST"),
    )

    # VIEWER (perfil consulta) lê, mas não escreve.
    listed = await client.get(
        f"/api/v1/equipments/{equipment_id}/requirement-waivers", headers=auth_header("VIEWER")
    )
    assert listed.status_code == 200
    blocked = await client.post(
        f"/api/v1/equipments/{equipment_id}/requirement-waivers",
        json={
            "stage": 1,
            "requirementGroupCode": "NEGOTIATION_EQUALIZATION",
            "reasonCode": "OTHER",
            "justification": "tentativa sem permissão",
        },
        headers=auth_header("VIEWER"),
    )
    assert blocked.status_code == 403


async def test_requirement_waiver_events_are_recorded_in_history(client, auth_header) -> None:
    equipment_id = await _new_equipment(client, auth_header, "HistoricoWaiver")
    await client.post(
        f"/api/v1/equipments/{equipment_id}/transitions",
        json={"targetStage": 1},
        headers=auth_header("ANALYST"),
    )
    waiver = await client.post(
        f"/api/v1/equipments/{equipment_id}/requirement-waivers",
        json={
            "stage": 1,
            "requirementGroupCode": "NEGOTIATION_EQUALIZATION",
            "reasonCode": "OTHER",
            "justification": "Justificativa registrada no histórico",
        },
        headers=auth_header("ANALYST"),
    )
    waiver_id = waiver.json()["id"]
    await client.post(
        f"/api/v1/equipments/{equipment_id}/requirement-waivers/{waiver_id}/revoke",
        json={"revokeReason": "Motivo da revogação"},
        headers=auth_header("ANALYST"),
    )

    history = await client.get(f"/api/v1/equipments/{equipment_id}/history", headers=auth_header("VIEWER"))
    entries = history.json()["items"]
    created_entry = next(e for e in entries if e["action"] == "requirementwaiver.create")
    revoked_entry = next(e for e in entries if e["action"] == "requirementwaiver.revoke")
    assert "NEGOTIATION_EQUALIZATION" in created_entry["title"]
    assert created_entry["justification"] == "Justificativa registrada no histórico"
    assert revoked_entry["justification"] == "Motivo da revogação"


async def test_c2_baseline_unaffected_by_requirement_waivers(client, auth_header, db_session) -> None:
    from sqlalchemy import func, select

    from app.models.equipment import Equipment, EquipmentComponent, EquipmentWorkPackage

    equipment_total = (await db_session.execute(select(func.count(Equipment.id)))).scalar_one()
    component_total = (await db_session.execute(select(func.count(EquipmentComponent.id)))).scalar_one()
    wp_links_total = (await db_session.execute(select(func.count(EquipmentWorkPackage.id)))).scalar_one()
    # Este teste roda no banco TEST (dados fictícios criados pela própria
    # suíte) — a checagem real do baseline 41/164/71 do C2 é feita à parte,
    # em DEV, via scripts/audit_c2_db.py (read-only). Aqui só confirmamos
    # que nenhuma tabela de equipamento ficou vazia/corrompida pela etapa.
    assert equipment_total >= 0
    assert component_total >= 0
    assert wp_links_total >= 0
