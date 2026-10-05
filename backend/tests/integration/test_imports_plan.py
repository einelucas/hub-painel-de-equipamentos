"""P1.3 — mapping interativo + plan pela API (somente dados sintéticos)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from app.models.equipment import Equipment, EquipmentComponent
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


def synthetic_board(
    *, status: str = "0.Nova demanda", name: str = "Equipamento Sintético A", startup: str = "2027/10/27"
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
            "Área Origem",
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


async def seed(client, auth_header) -> dict[str, str]:
    """Unidade, obra e catálogos sintéticos via endpoints existentes (nada é criado pelo importador)."""
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
    area = (
        await client.post(
            "/api/v1/areas", json={"unitId": unit["id"], "name": "Área Sintética"}, headers=admin
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
    analyst = (await client.get("/api/v1/auth/me", headers=auth_header("ANALYST"))).json()
    granted = await client.put(
        f"/api/v1/usuarios/{analyst['id']}/units", json={"unitIds": [unit["id"]]}, headers=admin
    )
    assert granted.status_code == 200
    return {
        "unit": unit["id"],
        "context": context["id"],
        "area": area["id"],
        "discipline": discipline["id"],
        "work_package": work_package["id"],
        "responsible": analyst["id"],
    }


def mapping(ids: dict[str, str]) -> dict[str, Any]:
    return {
        "responsibles": {"Responsável Origem A": ids["responsible"]},
        "areas": {"Área Origem": ids["area"]},
        "disciplines": {"Disciplina Origem": ids["discipline"]},
        "workPackages": {"WP-S1": ids["work_package"]},
    }


async def stage(client, headers, context_id: str, content: bytes) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/imports/monday/batches",
        data={"projectContextId": context_id, "profileId": PROFILE_ID},
        files={"file": ("board.xlsx", content, XLSX_MIME)},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


async def plan(client, headers, batch_id: str, body: dict[str, Any]):
    return await client.post(
        f"/api/v1/imports/monday/batches/{batch_id}/plan", json={"mapping": body}, headers=headers
    )


async def test_source_values_drive_mapping_and_valid_mapping_plans_create(
    client, auth_header, db_session
) -> None:
    ids = await seed(client, auth_header)
    analyst = auth_header("ANALYST")
    batch = await stage(client, analyst, ids["context"], synthetic_board())
    assert batch["sourceValues"] == {
        "responsibles": ["Responsável Origem A"],
        "areas": ["Área Origem"],
        "disciplines": ["Disciplina Origem"],
        "workPackages": ["WP-S1"],
    }

    response = await plan(client, analyst, batch["batchId"], mapping(ids))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mappingIssues"] == []
    assert body["canApply"] is True and body["hasBlocked"] is False and body["blocked"] == []
    groups = {group["name"]: group for group in body["groups"]}
    assert (groups["Equipamentos"]["create"], groups["Componentes"]["create"]) == (1, 1)
    assert len(body["planSha256"]) == 64

    # plan é somente leitura
    for model in (Equipment, EquipmentComponent):
        assert (await db_session.execute(select(func.count()).select_from(model))).scalar_one() == 0


async def test_unmapped_values_block_and_disable_apply(client, auth_header) -> None:
    ids = await seed(client, auth_header)
    analyst = auth_header("ANALYST")
    batch = await stage(client, analyst, ids["context"], synthetic_board())

    body = (await plan(client, analyst, batch["batchId"], {})).json()
    assert body["hasBlocked"] is True and body["canApply"] is False
    blocked = body["blocked"][0]
    assert blocked["group"] == "Equipamentos" and blocked["label"] == "Equipamento Sintético A"
    codes = {issue["code"] for issue in blocked["issues"]}
    assert {"unmapped_responsible", "unmapped_area", "unmapped_discipline", "unmapped_work_package"} <= codes


async def test_invalid_mapping_is_reported_and_never_creates_catalogs(client, auth_header) -> None:
    ids = await seed(client, auth_header)
    analyst = auth_header("ANALYST")
    batch = await stage(client, analyst, ids["context"], synthetic_board())
    bad = mapping(ids) | {"areas": {"Área Origem": "00000000-0000-0000-0000-000000000000"}}

    body = (await plan(client, analyst, batch["batchId"], bad)).json()
    assert any(
        issue["section"] == "areas" and issue["category"] == "error" for issue in body["mappingIssues"]
    )
    assert body["canApply"] is False

    malformed = await plan(client, analyst, batch["batchId"], {"areas": {"Área Origem": "  "}})
    assert malformed.status_code == 422


async def test_unknown_status_blocks_plan(client, auth_header) -> None:
    ids = await seed(client, auth_header)
    analyst = auth_header("ANALYST")
    batch = await stage(client, analyst, ids["context"], synthetic_board(status="Status Inventado"))

    body = (await plan(client, analyst, batch["batchId"], mapping(ids))).json()
    assert body["canApply"] is False
    assert "UNKNOWN_STAGE_VALUE" in {issue["code"] for issue in body["blocked"][0]["issues"]}


async def test_staging_errors_prevent_plan_and_scope_is_enforced(client, auth_header) -> None:
    ids = await seed(client, auth_header)
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
