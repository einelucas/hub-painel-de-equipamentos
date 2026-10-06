"""P1.3 / P1.3.1 — mapping interativo + plan pela API (somente dados sintéticos)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from app.models.equipment import EapNode, Equipment, EquipmentComponent
from tests.unit.monday_xlsx_fixture import build_xlsx

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PROFILE_ID = "monday-equipamentos-legacy"
HEADER = [
    "Name",
    "Subelementos",
    "A.Status",
    "0.Startup/Grãos",
    "Work Package",
    "0.Responsável",
    "0.Área",
    "0.Disciplina",
]
LOCATION = "2303 - Sistema Sintético"


def synthetic_board(
    *,
    status: str = "0.Nova demanda",
    name: str = "Equipamento Sintético A",
    startup: str = "2027/10/27",
    location: str | None = LOCATION,
) -> bytes:
    rows: list[list[Any]] = [
        ["Equipamentos - Projeto Sintético"],
        ["Fase 0 - Nova Demanda"],
        HEADER,
        [
            name,
            "Componente Sintético A1",
            status,
            startup,
            "WP-S1",
            "Responsável Origem A",
            location,
            "Disciplina Origem",
        ],
        [
            "Subitems",
            "Name",
            "ID do elemento",
            "0.Startup/Grãos",
            "Frete (Dias)",
            "Lead Time de Fabricação",
            "0.Dias Antes do Startup",
        ],
        [None, "Componente Sintético A1", "800001", "2027/09/01", 5, 30, 10],
    ]
    return build_xlsx(rows)


async def seed(client, auth_header, db_session) -> dict[str, str]:
    """Unidade, obra e catálogos sintéticos (nada é criado pelo importador)."""
    admin = auth_header("ADMIN")
    unit = (
        await client.post("/api/v1/units", json={"code": "TST", "name": "Unidade Teste"}, headers=admin)
    ).json()
    context = (
        await client.post(
            f"/api/v1/units/{unit['id']}/project-contexts",
            json={"code": "PA", "name": "Projeto Sintético A"},
            headers=admin,
        )
    ).json()
    discipline = (
        await client.post(
            "/api/v1/disciplines", json={"code": "DS", "name": "Disciplina Sintética"}, headers=admin
        )
    ).json()
    work_package = (
        await client.post(
            "/api/v1/work-packages",
            json={"projectContextId": context["id"], "code": "WP-S1", "name": "Pacote Sintético"},
            headers=admin,
        )
    ).json()
    # catálogo EAP sintético: o importador só VALIDA contra ele, nunca cria nós
    process = EapNode(code="03", name="Sistema Sintético", level="PROCESS")
    other = EapNode(code="19", name="Outro Sistema Sintético", level="PROCESS")
    db_session.add_all([process, other])
    await db_session.commit()
    analyst = (await client.get("/api/v1/auth/me", headers=auth_header("ANALYST"))).json()
    granted = await client.put(
        f"/api/v1/usuarios/{analyst['id']}/units", json={"unitIds": [unit["id"]]}, headers=admin
    )
    assert granted.status_code == 200
    return {
        "unit": unit["id"],
        "context": context["id"],
        "eap": process.id,
        "eap_other": other.id,
        "discipline": discipline["id"],
        "work_package": work_package["id"],
        "responsible": analyst["id"],
    }


def mapping(ids: dict[str, str]) -> dict[str, Any]:
    return {
        "responsibles": {"Responsável Origem A": ids["responsible"]},
        "disciplines": {"Disciplina Origem": ids["discipline"]},
        "workPackages": {"WP-S1": ids["work_package"]},
    }


async def stage(client, headers, context_id: str, content: bytes, name: str = "board.xlsx") -> dict[str, Any]:
    response = await client.post(
        "/api/v1/imports/monday/batches",
        data={"projectContextId": context_id, "profileId": PROFILE_ID},
        files={"file": (name, content, XLSX_MIME)},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


async def plan(client, headers, batch_ids: str | list[str], body: dict[str, Any]):
    ids = [batch_ids] if isinstance(batch_ids, str) else batch_ids
    return await client.post(
        "/api/v1/imports/monday/plan", json={"batchIds": ids, "mapping": body}, headers=headers
    )


async def test_source_values_drive_mapping_and_valid_mapping_plans_create(
    client, auth_header, db_session
) -> None:
    ids = await seed(client, auth_header, db_session)
    analyst = auth_header("ANALYST")
    batch = await stage(client, analyst, ids["context"], synthetic_board())
    assert batch["groups"] == ["Fase 0 - Nova Demanda"]
    values = batch["sourceValues"]
    assert (values["responsibles"], values["disciplines"], values["workPackages"]) == (
        ["Responsável Origem A"],
        ["Disciplina Origem"],
        ["WP-S1"],
    )
    [location] = values["locations"]
    assert (location["value"], location["status"], location["eapCode"], location["eapNodeId"]) == (
        LOCATION,
        "RESOLVED",
        "03",
        ids["eap"],
    )

    response = await plan(client, analyst, batch["batchId"], mapping(ids))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mappingIssues"] == []
    assert body["canApply"] is True and body["hasBlocked"] is False and body["blocked"] == []
    assert body["batchIds"] == [batch["batchId"]]
    assert body["eap"] == {
        "resolved": 1, "multiple": 0, "none": 0, "notFound": 0, "create": 0, "conflict": 0, "unresolved": 0
    }
    groups = {group["name"]: group for group in body["groups"]}
    assert (groups["Equipamentos"]["create"], groups["Componentes"]["create"]) == (1, 1)
    assert len(body["planSha256"]) == 64

    # plan é somente leitura
    for model in (Equipment, EquipmentComponent):
        assert (await db_session.execute(select(func.count()).select_from(model))).scalar_one() == 0


async def test_unmapped_catalog_values_warn_without_blocking(client, auth_header, db_session) -> None:
    ids = await seed(client, auth_header, db_session)
    analyst = auth_header("ANALYST")
    batch = await stage(client, analyst, ids["context"], synthetic_board())

    body = (await plan(client, analyst, batch["batchId"], {})).json()
    # Responsável/disciplina sem vínculo não bloqueiam o equipamento; o WP já existe
    # no contexto e é reutilizado sem mapping (EXISTING).
    assert body["hasBlocked"] is False and body["blocked"] == [] and body["canApply"] is True
    codes = {issue["code"] for item in body["equipmentWarnings"] for issue in item["issues"]}
    assert {"RESPONSIBLE_UNRESOLVED", "DISCIPLINE_CODE_REQUIRED"} <= codes
    catalogs = {(item["kind"], item["key"]): item["action"] for item in body["catalogs"]}
    assert catalogs[("work_package", "WP-S1")] == "EXISTING"
    assert catalogs[("discipline", "Disciplina Origem")] == "UNRESOLVED"
    assert body["responsibles"] == {"resolved": 0, "unresolved": 1}
    assert "unmapped_area" not in codes  # Area não é mais destino da localização


async def test_invalid_mapping_is_reported_and_never_creates_catalogs(
    client, auth_header, db_session
) -> None:
    ids = await seed(client, auth_header, db_session)
    analyst = auth_header("ANALYST")
    batch = await stage(client, analyst, ids["context"], synthetic_board())
    bad = mapping(ids) | {"eapNodes": {LOCATION: "00000000-0000-0000-0000-000000000000"}}

    body = (await plan(client, analyst, batch["batchId"], bad)).json()
    assert any(
        issue["section"] == "eapNodes" and issue["category"] == "error" for issue in body["mappingIssues"]
    )
    assert body["canApply"] is False

    malformed = await plan(client, analyst, batch["batchId"], {"eapNodes": {LOCATION: "  "}})
    assert malformed.status_code == 422
    assert (await db_session.execute(select(func.count()).select_from(EapNode))).scalar_one() == 2


async def test_unknown_status_blocks_plan(client, auth_header, db_session) -> None:
    ids = await seed(client, auth_header, db_session)
    analyst = auth_header("ANALYST")
    batch = await stage(client, analyst, ids["context"], synthetic_board(status="Status Inventado"))

    body = (await plan(client, analyst, batch["batchId"], mapping(ids))).json()
    assert body["canApply"] is False
    assert "UNKNOWN_STAGE_VALUE" in {issue["code"] for issue in body["blocked"][0]["issues"]}


async def test_staging_errors_prevent_plan_and_scope_is_enforced(client, auth_header, db_session) -> None:
    ids = await seed(client, auth_header, db_session)
    admin = auth_header("ADMIN")
    broken = build_xlsx(
        [
            ["Equipamentos - Projeto Sintético"],
            ["Fase 0 - Nova Demanda"],
            HEADER,
            ["Equipamento Sintético B", None, "0.Nova demanda", "data-invalida", None, None, None, None],
        ]
    )
    batch = await stage(client, admin, ids["context"], broken)
    assert batch["canProceed"] is False
    refused = await plan(client, admin, batch["batchId"], mapping(ids))
    assert refused.status_code == 422

    # VIEWER não usa a API; ANALYST sem a unidade não enxerga o batch
    ok_batch = await stage(client, admin, ids["context"], synthetic_board(name="Equipamento Sintético C"))
    assert (await plan(client, auth_header("VIEWER"), ok_batch["batchId"], mapping(ids))).status_code == 403
    revoke = (await client.get("/api/v1/auth/me", headers=auth_header("ANALYST"))).json()["id"]
    await client.put(f"/api/v1/usuarios/{revoke}/units", json={"unitIds": []}, headers=admin)
    assert (await plan(client, auth_header("ANALYST"), ok_batch["batchId"], mapping(ids))).status_code == 404


async def test_eap_without_code_multiple_or_unknown_never_invents_a_link(
    client, auth_header, db_session
) -> None:
    ids = await seed(client, auth_header, db_session)
    admin = auth_header("ADMIN")
    cases = {
        "Equipamento Sintético Diversos": "Diversos",
        "Equipamento Sintético Multi": "2303 Sistema X / 2319 Sistema Y",
        "Equipamento Sintético Inexistente": "2377 - Sistema Inexistente",
    }
    batch_ids = [
        (await stage(client, admin, ids["context"], synthetic_board(name=name, location=value), f"{n}.xlsx"))[
            "batchId"
        ]
        for n, (name, value) in enumerate(cases.items())
    ]
    body = (await plan(client, admin, batch_ids, mapping(ids))).json()
    # nenhum bloqueia a importação. Sem código e múltiplo ficam pendentes (nunca há
    # escolha automática); código novo com nome na origem vira CREATE (fonte MONDAY).
    assert body["canApply"] is True, body["blocked"]
    assert body["eap"] == {
        "resolved": 0, "multiple": 1, "none": 1, "notFound": 0, "create": 1, "conflict": 0, "unresolved": 0
    }
    [created] = [
        item for item in body["catalogs"] if item["kind"] == "eap_node" and item["action"] == "CREATE"
    ]
    assert (created["key"], created["evidenceSource"]) == ("77", "MONDAY")
    codes = {warning["code"] for warning in body["warnings"]}
    assert codes.isdisjoint({"unmapped_area"})

    # escolha explícita do usuário resolve o caso múltiplo (sem escolha automática)
    chosen = mapping(ids) | {"eapNodes": {cases["Equipamento Sintético Multi"]: ids["eap_other"]}}
    body = (await plan(client, admin, batch_ids, chosen)).json()
    assert body["eap"] == {
        "resolved": 1, "multiple": 0, "none": 1, "notFound": 0, "create": 1, "conflict": 0, "unresolved": 0
    }
