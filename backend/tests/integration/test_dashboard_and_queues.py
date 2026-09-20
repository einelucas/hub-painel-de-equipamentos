"""Agregações do dashboard e recortes das filas operacionais."""

from __future__ import annotations

from datetime import date, timedelta

from app.modules.queues.service import QUEUE_STAGES
from tests.helpers import grant_unit

# Dados fictícios de teste: nenhum número/contrato real do processo.
_ADVANCE_PAYLOAD: dict[int, tuple[str, dict[str, object]]] = {
    2: ("negotiation", {"equalized": True}),
    3: ("negotiation", {"negotiatedAt": "2026-02-10"}),
    4: ("legal", {"openedAt": "2026-02-12", "ticketNumber": "TICKET-0001"}),
    5: ("legal", {"draftPrepared": True, "draftApproved": True}),
    6: ("contract", {"contractNumber": "CT-0001", "executedAt": "2026-03-01"}),
    7: (
        "purchase-request",
        {"kind": "SC", "requestNumber": "SC-0001", "requestedAt": "2026-03-05"},
    ),
    8: ("purchase-order", {"orderNumber": "OC-0001", "orderedAt": "2026-03-10"}),
}


async def _unit_with_context(client, auth_header, suffix: str) -> dict[str, str]:
    headers = auth_header("ADMIN")
    unit = (
        await client.post(
            "/api/v1/units",
            json={"code": f"U-{suffix}", "name": f"Unidade {suffix}"},
            headers=headers,
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


async def _create(client, auth_header, context_id: str, name: str, **extra: object) -> str:
    response = await client.post(
        "/api/v1/equipments",
        json={"projectContextId": context_id, "name": name, **extra},
        headers=auth_header("ANALYST"),
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def _advance_to(client, auth_header, equipment_id: str, target: int) -> None:
    for stage in range(1, target + 1):
        payload = _ADVANCE_PAYLOAD.get(stage)
        if payload is not None:
            resource, body = payload
            patched = await client.patch(
                f"/api/v1/equipments/{equipment_id}/{resource}",
                json=body,
                headers=auth_header("ANALYST"),
            )
            assert patched.status_code == 200, patched.text
        if stage == 8:
            await client.patch(
                f"/api/v1/equipments/{equipment_id}/contract",
                json={"deliveryAt": "2026-08-01"},
                headers=auth_header("ANALYST"),
            )
        moved = await client.post(
            f"/api/v1/equipments/{equipment_id}/transitions",
            json={"targetStage": stage},
            headers=auth_header("ANALYST"),
        )
        assert moved.status_code == 200, moved.text


async def test_summary_totals_and_workflow_distribution(client, auth_header) -> None:
    ids = await _unit_with_context(client, auth_header, "DASH")
    first = await _create(client, auth_header, ids["context"], "Bomba dash", capexEstimated=1000)
    await _create(client, auth_header, ids["context"], "Ventilador dash", capexEstimated=500)
    await client.post(
        f"/api/v1/equipments/{first}/components",
        json={"name": "Motor"},
        headers=auth_header("ANALYST"),
    )
    await _advance_to(client, auth_header, first, 2)

    response = await client.get(
        f"/api/v1/dashboard/summary?unit_id={ids['unit']}", headers=auth_header("VIEWER")
    )
    assert response.status_code == 200
    body = response.json()

    assert body["context"] == {"unitId": ids["unit"], "equipmentId": None}
    assert body["totals"]["equipments"] == 2
    assert body["totals"]["components"] == 1
    assert body["totals"]["inProgress"] == 2
    assert body["totals"]["completed"] == 0
    assert float(body["totals"]["capexEstimated"]) == 1500.0

    distribution = {item["stage"]: item["count"] for item in body["workflow"]}
    assert len(body["workflow"]) == 9
    assert distribution[0] == 1
    assert distribution[2] == 1
    assert [item["stage"] for item in body["workflow"]] == list(range(9))


async def test_summary_respects_unit_and_equipment_filters(client, auth_header) -> None:
    first = await _unit_with_context(client, auth_header, "F1")
    second = await _unit_with_context(client, auth_header, "F2")
    target = await _create(client, auth_header, first["context"], "Alvo filtro")
    await _create(client, auth_header, first["context"], "Outro da unidade")
    await _create(client, auth_header, second["context"], "De outra unidade")

    by_unit = (
        await client.get(
            f"/api/v1/dashboard/summary?unit_id={first['unit']}", headers=auth_header("VIEWER")
        )
    ).json()
    by_equipment = (
        await client.get(
            f"/api/v1/dashboard/summary?unit_id={first['unit']}&equipment_id={target}",
            headers=auth_header("VIEWER"),
        )
    ).json()

    assert by_unit["totals"]["equipments"] == 2
    assert by_equipment["totals"]["equipments"] == 1
    assert by_equipment["context"]["equipmentId"] == target


async def test_summary_purchase_order_and_negotiation_metrics(client, auth_header) -> None:
    ids = await _unit_with_context(client, auth_header, "OC")
    equipment_id = await _create(client, auth_header, ids["context"], "Com OC")
    await _advance_to(client, auth_header, equipment_id, 7)
    await client.patch(
        f"/api/v1/equipments/{equipment_id}/purchase-order",
        json={"orderNumber": "OC-9001", "orderedAt": "2026-04-01", "amount": 2500.50},
        headers=auth_header("ANALYST"),
    )

    body = (
        await client.get(
            f"/api/v1/dashboard/summary?unit_id={ids['unit']}", headers=auth_header("VIEWER")
        )
    ).json()

    assert body["totals"]["purchaseOrders"] == 1
    assert float(body["totals"]["purchaseOrderAmount"]) == 2500.50
    # negotiatedAt foi preenchido no caminho até a etapa 7.
    assert body["negotiation"]["completed"] == 1
    assert body["negotiation"]["open"] == 0


async def test_summary_deadlines_are_not_calculated(client, auth_header) -> None:
    ids = await _unit_with_context(client, auth_header, "PRZ")
    await _create(client, auth_header, ids["context"], "Sem prazo")
    body = (
        await client.get(
            f"/api/v1/dashboard/summary?unit_id={ids['unit']}", headers=auth_header("VIEWER")
        )
    ).json()
    assert body["deadlines"]["available"] is False
    assert body["deadlines"]["reason"]


async def test_summary_next_startup_ignores_past_dates(client, auth_header) -> None:
    ids = await _unit_with_context(client, auth_header, "STU")
    today = date.today()
    await _create(
        client,
        auth_header,
        ids["context"],
        "Startup passada",
        startupAt=str(today - timedelta(days=30)),
    )
    future = await _create(
        client,
        auth_header,
        ids["context"],
        "Startup futura",
        startupAt=str(today + timedelta(days=10)),
    )
    await _create(
        client,
        auth_header,
        ids["context"],
        "Startup distante",
        startupAt=str(today + timedelta(days=90)),
    )

    startup = (
        await client.get(
            f"/api/v1/dashboard/summary?unit_id={ids['unit']}", headers=auth_header("VIEWER")
        )
    ).json()["startup"]

    assert startup["equipmentId"] == future
    assert startup["daysRemaining"] == 10


async def test_summary_requires_read_permission(client, auth_header) -> None:
    response = await client.get("/api/v1/dashboard/summary")
    assert response.status_code == 401


async def test_queues_split_equipments_by_documented_stage_ranges(client, auth_header) -> None:
    ids = await _unit_with_context(client, auth_header, "FILA")
    engineering = await _create(client, auth_header, ids["context"], "Fica em engenharia")
    legal = await _create(client, auth_header, ids["context"], "Vai para juridico")
    procurement = await _create(client, auth_header, ids["context"], "Vai para suprimentos")
    await _advance_to(client, auth_header, legal, QUEUE_STAGES["legal"][0])
    await _advance_to(client, auth_header, procurement, QUEUE_STAGES["procurement"][0])

    async def ids_in(queue: str) -> list[str]:
        response = await client.get(
            f"/api/v1/queues/{queue}?unit_id={ids['unit']}", headers=auth_header("VIEWER")
        )
        assert response.status_code == 200
        return [item["equipmentId"] for item in response.json()["items"]]

    assert await ids_in("engineering") == [engineering]
    assert await ids_in("legal") == [legal]
    assert await ids_in("procurement") == [procurement]


async def test_engineering_queue_exposes_pending_requirement(client, auth_header) -> None:
    ids = await _unit_with_context(client, auth_header, "PEND")
    equipment_id = await _create(client, auth_header, ids["context"], "Com pendencia")
    await _advance_to(client, auth_header, equipment_id, 1)

    row = (
        await client.get(
            f"/api/v1/queues/engineering?unit_id={ids['unit']}", headers=auth_header("VIEWER")
        )
    ).json()["items"][0]

    assert row["currentStage"] == 1
    assert row["nextStage"] == 2
    assert row["nextStageName"] == "Equalização"
    assert [item["code"] for item in row["pending"]] == ["negotiation_equalized_required"]


async def test_legal_queue_returns_process_data(client, auth_header) -> None:
    ids = await _unit_with_context(client, auth_header, "JUR")
    equipment_id = await _create(client, auth_header, ids["context"], "No juridico")
    # O chamado jurídico é requisito de 3 -> 4, então só está preenchido na etapa 4.
    await _advance_to(client, auth_header, equipment_id, 4)

    row = (
        await client.get(
            f"/api/v1/queues/legal?unit_id={ids['unit']}", headers=auth_header("VIEWER")
        )
    ).json()["items"][0]

    assert row["ticketNumber"] == "TICKET-0001"
    assert row["openedAt"] == "2026-02-12"
    assert row["draftApproved"] is False


async def test_procurement_queue_returns_order_data(client, auth_header) -> None:
    ids = await _unit_with_context(client, auth_header, "SUP")
    equipment_id = await _create(client, auth_header, ids["context"], "Em suprimentos")
    await _advance_to(client, auth_header, equipment_id, 7)
    await client.patch(
        f"/api/v1/equipments/{equipment_id}/purchase-order",
        json={"orderNumber": "OC-7001", "amount": 100},
        headers=auth_header("ANALYST"),
    )

    row = (
        await client.get(
            f"/api/v1/queues/procurement?unit_id={ids['unit']}", headers=auth_header("VIEWER")
        )
    ).json()["items"][0]

    assert row["kind"] == "SC"
    assert row["requestNumber"] == "SC-0001"
    assert row["orderNumber"] == "OC-7001"
    assert float(row["amount"]) == 100.0


async def test_queues_filter_by_unit_and_paginate(client, auth_header) -> None:
    first = await _unit_with_context(client, auth_header, "Q1")
    second = await _unit_with_context(client, auth_header, "Q2")
    await _create(client, auth_header, first["context"], "Primeiro da fila")
    await _create(client, auth_header, first["context"], "Segundo da fila")
    await _create(client, auth_header, second["context"], "De outra unidade")

    page = (
        await client.get(
            f"/api/v1/queues/engineering?unit_id={first['unit']}&pageSize=1",
            headers=auth_header("VIEWER"),
        )
    ).json()

    assert page["pagination"] == {"page": 1, "pageSize": 1, "total": 2, "totalPages": 2}
    assert len(page["items"]) == 1


async def test_queues_require_authentication(client) -> None:
    for queue in ("engineering", "legal", "procurement"):
        assert (await client.get(f"/api/v1/queues/{queue}")).status_code == 401


async def test_equipments_list_filters_by_discipline(client, auth_header) -> None:
    ids = await _unit_with_context(client, auth_header, "DISC")
    discipline = (
        await client.post(
            "/api/v1/disciplines",
            json={"code": "D-DISC", "name": "Elétrica"},
            headers=auth_header("ADMIN"),
        )
    ).json()
    with_discipline = await _create(
        client, auth_header, ids["context"], "Com disciplina", disciplineId=discipline["id"]
    )
    await _create(client, auth_header, ids["context"], "Sem disciplina")

    filtered = (
        await client.get(
            f"/api/v1/equipments?unit_id={ids['unit']}&discipline_id={discipline['id']}",
            headers=auth_header("VIEWER"),
        )
    ).json()

    assert [item["id"] for item in filtered["items"]] == [with_discipline]
