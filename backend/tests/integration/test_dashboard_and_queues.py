"""Agregações do dashboard e recortes das filas operacionais."""

from __future__ import annotations

from datetime import date, timedelta

from app.modules.queues.service import QUEUE_STAGES
from tests.helpers import grant_unit

# Dados fictícios de teste: nenhum número/contrato real do processo.
# Etapa 7A: Contract/PurchaseRequest/PurchaseOrder são 1:N — ver
# `test_workflow_routes.py` para a mesma adaptação.
_ADVANCE_PAYLOAD: dict[int, tuple[str, dict[str, object]]] = {
    2: ("negotiation", {"equalized": True}),
    3: ("negotiation", {"negotiatedAt": "2026-02-10"}),
    4: ("legal", {"openedAt": "2026-02-12", "ticketNumber": "TICKET-0001"}),
    5: ("legal", {"draftPrepared": True, "draftApproved": True}),
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
        if stage == 6:
            created = await client.post(
                f"/api/v1/equipments/{equipment_id}/contracts",
                json={"contractNumber": "CT-0001", "executedAt": "2026-03-01"},
                headers=auth_header("ANALYST"),
            )
            assert created.status_code == 201, created.text
        if stage == 7:
            created = await client.post(
                f"/api/v1/equipments/{equipment_id}/purchase-requests",
                json={"kind": "SC", "requestNumber": "SC-0001", "requestedAt": "2026-03-05"},
                headers=auth_header("ANALYST"),
            )
            assert created.status_code == 201, created.text
        if stage == 8:
            await _make_completable(client, auth_header, equipment_id)
        moved = await client.post(
            f"/api/v1/equipments/{equipment_id}/transitions",
            json={"targetStage": stage},
            headers=auth_header("ANALYST"),
        )
        assert moved.status_code == 200, moved.text


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
    created = await client.post(
        f"/api/v1/equipments/{equipment_id}/purchase-orders",
        json={"orderNumber": "OC-9001", "orderedAt": "2026-04-01", "amount": 2500.50},
        headers=auth_header("ANALYST"),
    )
    assert created.status_code == 201, created.text

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


# --- Etapa 6C.1: card "Situação de prazos" (Status Necessidade da Obra) ---


async def test_summary_deadlines_card_is_active_with_real_distribution(client, auth_header) -> None:
    """Substitui o antigo placeholder `available=False`: a partir da Etapa
    6C.1 o card fica sempre ativo, com a distribuição real do recorte."""
    ids = await _unit_with_context(client, auth_header, "PRZ")
    equipment_id = await _create(client, auth_header, ids["context"], "Sem componente ainda")

    body = (
        await client.get(
            f"/api/v1/dashboard/summary?unit_id={ids['unit']}", headers=auth_header("VIEWER")
        )
    ).json()
    deadlines = body["deadlines"]
    assert deadlines["available"] is True
    assert deadlines["reason"] is None
    assert deadlines["total"] == 1
    assert deadlines["withoutDeadline"] == 1
    assert deadlines["withDeadline"] == 0
    assert deadlines["safe"] == 0

    today = date.today()
    # Startup bem distante -> componente cai em SAFE (>=90 dias).
    await client.post(
        f"/api/v1/equipments/{equipment_id}/components",
        json={
            "name": "C",
            "startupAt": (today + timedelta(days=200)).isoformat(),
            "preStartDays": 0,
            "freightDays": 0,
            "leadTimeDays": 0,
        },
        headers=auth_header("ANALYST"),
    )
    after = (
        await client.get(
            f"/api/v1/dashboard/summary?unit_id={ids['unit']}", headers=auth_header("VIEWER")
        )
    ).json()["deadlines"]
    assert after["withoutDeadline"] == 0
    assert after["withDeadline"] == 1
    assert after["safe"] == 1


async def test_summary_deadlines_categories_sum_to_with_deadline_and_total(client, auth_header) -> None:
    ids = await _unit_with_context(client, auth_header, "PRZSUM")
    today = date.today()
    # Um equipamento por faixa: CHECK_DELIVERY_FUP, LT_30_DAYS, SAFE, e um sem componente.
    offsets = {"Atrasado": -5, "Menos30": 10, "Seguro": 200}
    for name, offset in offsets.items():
        equipment_id = await _create(client, auth_header, ids["context"], name)
        await client.post(
            f"/api/v1/equipments/{equipment_id}/components",
            json={
                "name": "C",
                "startupAt": (today + timedelta(days=offset)).isoformat(),
                "preStartDays": 0,
                "freightDays": 0,
                "leadTimeDays": 0,
            },
            headers=auth_header("ANALYST"),
        )
    await _create(client, auth_header, ids["context"], "Sem componente")

    deadlines = (
        await client.get(
            f"/api/v1/dashboard/summary?unit_id={ids['unit']}", headers=auth_header("VIEWER")
        )
    ).json()["deadlines"]

    assert deadlines["total"] == 4
    assert deadlines["withDeadline"] + deadlines["withoutDeadline"] == deadlines["total"]
    category_sum = (
        deadlines["checkDeliveryFup"]
        + deadlines["neededToday"]
        + deadlines["lt30Days"]
        + deadlines["lt60Days"]
        + deadlines["lt90Days"]
        + deadlines["safe"]
    )
    assert category_sum == deadlines["withDeadline"]
    assert deadlines["checkDeliveryFup"] == 1
    assert deadlines["lt30Days"] == 1
    assert deadlines["safe"] == 1
    assert deadlines["withoutDeadline"] == 1


async def test_summary_deadlines_without_deadline_is_never_classified_as_safe(client, auth_header) -> None:
    ids = await _unit_with_context(client, auth_header, "PRZNULL")
    await _create(client, auth_header, ids["context"], "Sem startup no componente")
    equipment_id = await _create(client, auth_header, ids["context"], "Com componente sem startup")
    await client.post(
        f"/api/v1/equipments/{equipment_id}/components",
        json={"name": "C", "preStartDays": 10, "freightDays": 0, "leadTimeDays": 0},
        headers=auth_header("ANALYST"),
    )
    deadlines = (
        await client.get(
            f"/api/v1/dashboard/summary?unit_id={ids['unit']}", headers=auth_header("VIEWER")
        )
    ).json()["deadlines"]
    assert deadlines["total"] == 2
    assert deadlines["withoutDeadline"] == 2
    assert deadlines["safe"] == 0
    assert deadlines["withDeadline"] == 0


async def test_summary_deadlines_respects_equipment_filter(client, auth_header) -> None:
    ids = await _unit_with_context(client, auth_header, "PRZEQ")
    today = date.today()
    target = await _create(client, auth_header, ids["context"], "Alvo do filtro")
    await client.post(
        f"/api/v1/equipments/{target}/components",
        json={
            "name": "C",
            "startupAt": (today + timedelta(days=200)).isoformat(),
            "preStartDays": 0,
            "freightDays": 0,
            "leadTimeDays": 0,
        },
        headers=auth_header("ANALYST"),
    )
    other = await _create(client, auth_header, ids["context"], "Outro equipamento")
    await client.post(
        f"/api/v1/equipments/{other}/components",
        json={
            "name": "C",
            "startupAt": (today - timedelta(days=5)).isoformat(),
            "preStartDays": 0,
            "freightDays": 0,
            "leadTimeDays": 0,
        },
        headers=auth_header("ANALYST"),
    )

    deadlines = (
        await client.get(
            f"/api/v1/dashboard/summary?unit_id={ids['unit']}&equipment_id={target}",
            headers=auth_header("VIEWER"),
        )
    ).json()["deadlines"]
    assert deadlines["total"] == 1
    assert deadlines["safe"] == 1
    assert deadlines["checkDeliveryFup"] == 0


async def test_summary_deadlines_respects_unit_scoping_and_permissions(client, auth_header) -> None:
    """Mesmo recorte já usado pelo restante do dashboard: só unidades
    autorizadas para o ator entram na distribuição. `first` é liberado ao
    VIEWER via `_unit_with_context` (que chama `grant_unit`); `second` é
    criada sem conceder acesso, para provar que fica de fora."""
    first = await _unit_with_context(client, auth_header, "PRZU1")
    admin = auth_header("ADMIN")
    second_unit = (
        await client.post(
            "/api/v1/units",
            json={"code": "U-PRZU2", "name": "Unidade PRZU2"},
            headers=admin,
        )
    ).json()
    second_context = (
        await client.post(
            f"/api/v1/units/{second_unit['id']}/project-contexts",
            json={"code": "CTX-PRZU2", "name": "Contexto PRZU2"},
            headers=admin,
        )
    ).json()

    today = date.today()
    # ANALYST/VIEWER só têm acesso à unidade `first` (concedido por
    # `_unit_with_context`); o equipamento de `second` precisa ser criado
    # como ADMIN (acesso global por perfil, sem depender de vínculo).
    for context_id, name, headers in [
        (first["context"], "Da unidade 1", auth_header("ANALYST")),
        (second_context["id"], "Da unidade 2", admin),
    ]:
        equipment = await client.post(
            "/api/v1/equipments",
            json={"projectContextId": context_id, "name": name},
            headers=headers,
        )
        assert equipment.status_code == 201, equipment.text
        equipment_id = equipment.json()["id"]
        await client.post(
            f"/api/v1/equipments/{equipment_id}/components",
            json={
                "name": "C",
                "startupAt": (today + timedelta(days=200)).isoformat(),
                "preStartDays": 0,
                "freightDays": 0,
                "leadTimeDays": 0,
            },
            headers=headers,
        )

    scoped = (
        await client.get(
            f"/api/v1/dashboard/summary?unit_id={first['unit']}", headers=auth_header("VIEWER")
        )
    ).json()["deadlines"]
    assert scoped["total"] == 1

    forbidden = await client.get(
        f"/api/v1/dashboard/summary?unit_id={second_unit['id']}", headers=auth_header("VIEWER")
    )
    assert forbidden.status_code == 404

    unscoped = (
        await client.get("/api/v1/dashboard/summary", headers=auth_header("VIEWER"))
    ).json()["deadlines"]
    assert unscoped["safe"] >= scoped["safe"]


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
    created = await client.post(
        f"/api/v1/equipments/{equipment_id}/purchase-orders",
        json={"orderNumber": "OC-7001", "amount": 100},
        headers=auth_header("ANALYST"),
    )
    assert created.status_code == 201, created.text

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


async def _responsible_id(client, auth_header, unit_id: str, name: str, email: str) -> str:
    admin = auth_header("ADMIN")
    created = (
        await client.post(
            "/api/v1/usuarios",
            json={"name": name, "email": email, "role": "ANALYST"},
            headers=admin,
        )
    ).json()
    user_id = created["user"]["id"]
    updated = await client.put(
        f"/api/v1/usuarios/{user_id}/units", json={"unitIds": [unit_id]}, headers=admin
    )
    assert updated.status_code == 200, updated.text
    return str(user_id)


# --- GAP-011: Engenharia por Disciplina + Responsável -------------------


async def test_engineering_queue_filters_by_discipline_id(client, auth_header) -> None:
    ids = await _unit_with_context(client, auth_header, "ENGDISC")
    metal_mec = (
        await client.post(
            "/api/v1/disciplines",
            json={"code": "MM-ENG", "name": "Metal Mec."},
            headers=auth_header("ADMIN"),
        )
    ).json()
    other = (
        await client.post(
            "/api/v1/disciplines",
            json={"code": "EI-ENG", "name": "E&I"},
            headers=auth_header("ADMIN"),
        )
    ).json()
    metal_equipment = await _create(
        client, auth_header, ids["context"], "Equipamento Metal Mec.", disciplineId=metal_mec["id"]
    )
    await _create(client, auth_header, ids["context"], "Equipamento E&I", disciplineId=other["id"])

    filtered = (
        await client.get(
            f"/api/v1/queues/engineering?unit_id={ids['unit']}&discipline_id={metal_mec['id']}",
            headers=auth_header("VIEWER"),
        )
    ).json()
    assert [item["equipmentId"] for item in filtered["items"]] == [metal_equipment]


async def test_engineering_queue_filters_by_responsible_user_id(client, auth_header) -> None:
    ids = await _unit_with_context(client, auth_header, "ENGRESP")
    responsible_id = await _responsible_id(
        client, auth_header, ids["unit"], "Ana Teste", "ana.teste@example.com"
    )
    with_responsible = await _create(
        client, auth_header, ids["context"], "Com responsável", responsibleUserId=responsible_id
    )
    await _create(client, auth_header, ids["context"], "Sem responsável")

    filtered = (
        await client.get(
            f"/api/v1/queues/engineering?unit_id={ids['unit']}&responsible_user_id={responsible_id}",
            headers=auth_header("VIEWER"),
        )
    ).json()
    assert [item["equipmentId"] for item in filtered["items"]] == [with_responsible]


async def test_engineering_queue_combines_discipline_and_responsible_filters(client, auth_header) -> None:
    ids = await _unit_with_context(client, auth_header, "ENGCOMBO")
    metal_mec = (
        await client.post(
            "/api/v1/disciplines",
            json={"code": "MM-COMBO", "name": "Metal Mec. combo"},
            headers=auth_header("ADMIN"),
        )
    ).json()
    ana = await _responsible_id(client, auth_header, ids["unit"], "Ana Combo", "ana.combo@example.com")
    uilson = await _responsible_id(
        client, auth_header, ids["unit"], "Uilson Combo", "uilson.combo@example.com"
    )
    match = await _create(
        client,
        auth_header,
        ids["context"],
        "Metal Mec. da Ana",
        disciplineId=metal_mec["id"],
        responsibleUserId=ana,
    )
    await _create(
        client,
        auth_header,
        ids["context"],
        "Metal Mec. do Uilson",
        disciplineId=metal_mec["id"],
        responsibleUserId=uilson,
    )
    await _create(client, auth_header, ids["context"], "Outra disciplina da Ana", responsibleUserId=ana)

    filtered = (
        await client.get(
            "/api/v1/queues/engineering"
            f"?unit_id={ids['unit']}&discipline_id={metal_mec['id']}&responsible_user_id={ana}",
            headers=auth_header("VIEWER"),
        )
    ).json()
    assert [item["equipmentId"] for item in filtered["items"]] == [match]


async def test_legal_and_procurement_queues_do_not_accept_discipline_filter(client, auth_header) -> None:
    """GAP-011 é só da Engenharia: `discipline_id` não é um param reconhecido
    em Jurídico/Suprimentos — mandá-lo não deve quebrar nem filtrar nada."""
    ids = await _unit_with_context(client, auth_header, "NODISC")
    legal_equipment = await _create(client, auth_header, ids["context"], "Jurídico sem filtro disciplina")
    await _advance_to(client, auth_header, legal_equipment, QUEUE_STAGES["legal"][0])

    fake_discipline_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(
        f"/api/v1/queues/legal?unit_id={ids['unit']}&discipline_id={fake_discipline_id}",
        headers=auth_header("VIEWER"),
    )
    assert response.status_code == 200
    assert [item["equipmentId"] for item in response.json()["items"]] == [legal_equipment]


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
