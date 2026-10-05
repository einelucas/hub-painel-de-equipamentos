"""P1.3 — API de importação Monday: profiles, upload e staging (somente dados sintéticos)."""

from __future__ import annotations

from sqlalchemy import func, select

from app.models.equipment import Equipment, EquipmentComponent
from app.models.monday_import import MondayImportBatch, MondayImportRecord
from app.models.process import Contract, PurchaseOrder, PurchaseRequest
from tests.unit.monday_xlsx_fixture import build_xlsx, representative_xlsx

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PROFILE_ID = "monday-equipamentos-legacy"


async def _context(client, auth_header, *, code: str = "TST", active: bool = True) -> tuple[str, str]:
    admin = auth_header("ADMIN")
    unit = await client.post("/api/v1/units", json={"code": code, "name": f"Unidade {code}"}, headers=admin)
    assert unit.status_code == 201, unit.text
    unit_id = unit.json()["id"]
    context = await client.post(
        f"/api/v1/units/{unit_id}/project-contexts",
        json={"code": "PA", "name": "Projeto Sintético A"},
        headers=admin,
    )
    assert context.status_code == 201, context.text
    context_id = context.json()["id"]
    if not active:
        await client.patch(f"/api/v1/project-contexts/{context_id}", json={"active": False}, headers=admin)
    return unit_id, context_id


async def _grant(client, auth_header, role: str, unit_id: str) -> None:
    me = await client.get("/api/v1/auth/me", headers=auth_header(role))
    response = await client.put(
        f"/api/v1/usuarios/{me.json()['id']}/units", json={"unitIds": [unit_id]}, headers=auth_header("ADMIN")
    )
    assert response.status_code == 200, response.text


async def _upload(
    client, headers, context_id: str, content: bytes, *, name: str = "board.xlsx", profile=PROFILE_ID
):
    return await client.post(
        "/api/v1/imports/monday/batches",
        data={"projectContextId": context_id, "profileId": profile},
        files={"file": (name, content, XLSX_MIME)},
        headers=headers,
    )


async def _count(db_session, model) -> int:
    return (await db_session.execute(select(func.count()).select_from(model))).scalar_one()


async def test_lists_only_runtime_profiles_metadata(client, auth_header) -> None:
    response = await client.get("/api/v1/imports/monday/profiles", headers=auth_header("ANALYST"))
    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["profileId"] for item in items] == [PROFILE_ID]
    assert set(items[0]) == {"profileId", "version", "sourceSystem", "description"}
    # fixtures sintéticas de teste nunca aparecem em runtime
    assert not any(item["profileId"].startswith("synthetic-") for item in items)
    # nenhum caminho de arquivo nem nome de obra exposto
    text = str(items).lower()
    assert ".json" not in text and "profiles" not in text and "\\" not in text
    assert not any(code in str(items) for code in ("C2", "F2", "LEM", "RDN", "NMT", "RVD"))


async def test_upload_stages_without_touching_domain_and_is_idempotent(
    client, auth_header, db_session
) -> None:
    unit_id, context_id = await _context(client, auth_header)
    await _grant(client, auth_header, "ANALYST", unit_id)
    analyst = auth_header("ANALYST")

    content = representative_xlsx()  # mesmos bytes nas duas chamadas (o ZIP embute horário)
    first = await _upload(client, analyst, context_id, content)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["alreadyStaged"] is False
    assert (body["equipments"], body["components"], body["status"]) == (1, 1, "STAGED")
    assert body["boardTitle"] == "Equipamentos - Teste"
    assert body["profile"]["profileId"] == PROFILE_ID
    assert body["unknownFields"] == ["equipment:Coluna futura"]
    assert body["fragileIdentities"] == 1
    assert body["canProceed"] is True
    assert body["sourceValues"]["workPackages"] == ["CAL012", "CIV014"]

    # staging only: nenhum dado de domínio criado
    for model in (Equipment, EquipmentComponent, Contract, PurchaseRequest, PurchaseOrder):
        assert await _count(db_session, model) == 0, model.__name__

    # mesmo arquivo + mesma obra = mesmo batch, sem registros duplicados
    again = await _upload(client, analyst, context_id, content, name="outro-nome.xlsx")
    assert again.status_code == 200
    assert again.json()["batchId"] == body["batchId"] and again.json()["alreadyStaged"] is True
    assert await _count(db_session, MondayImportBatch) == 1
    assert await _count(db_session, MondayImportRecord) == 2

    fetched = await client.get(f"/api/v1/imports/monday/batches/{body['batchId']}", headers=analyst)
    assert fetched.status_code == 200 and fetched.json()["equipments"] == 1


async def test_issues_are_returned_with_severity_row_and_field(client, auth_header) -> None:
    _, context_id = await _context(client, auth_header)
    workbook = build_xlsx(
        [
            ["Equipamentos - Teste"],
            ["Fase 0 - Nova Demanda"],
            ["Name", "Subelementos", "A.Status", "0.Startup/Grãos"],
            ["Equipamento Sintético A", None, "Status Inventado", "data-invalida"],
        ]
    )
    response = await _upload(client, auth_header("ADMIN"), context_id, workbook)
    assert response.status_code == 200, response.text
    body = response.json()
    codes = {issue["code"]: issue for issue in body["issues"]}
    assert codes["unknown_status_value"]["severity"] == "warning"
    assert codes["unknown_status_value"]["rowNumber"] == 4
    assert codes["invalid_date"]["severity"] == "error" and codes["invalid_date"]["field"] == "startup_at"
    assert body["unknownStatuses"] == 1
    assert body["errors"] >= 1 and body["canProceed"] is False


async def test_rejects_wrong_extension_invalid_file_and_unknown_profile(
    client, auth_header, db_session
) -> None:
    _, context_id = await _context(client, auth_header)
    admin = auth_header("ADMIN")

    for name in ("board.xls", "board.csv", "board.exe", "board.zip"):
        response = await _upload(client, admin, context_id, b"conteudo", name=name)
        assert response.status_code == 422, name

    not_xlsx = await _upload(client, admin, context_id, b"isto nao e um zip", name="board.xlsx")
    assert not_xlsx.status_code == 422 and "XLSX" in not_xlsx.json()["error"]

    bad_profile = await _upload(
        client, admin, context_id, representative_xlsx(), profile="synthetic-asset-board-b"
    )
    assert bad_profile.status_code == 422

    assert await _count(db_session, MondayImportBatch) == 0


async def test_context_must_exist_be_active_and_in_scope(client, auth_header) -> None:
    admin = auth_header("ADMIN")
    missing = await _upload(client, admin, "00000000-0000-0000-0000-000000000000", representative_xlsx())
    assert missing.status_code == 404

    _, inactive_id = await _context(client, auth_header, code="TSI", active=False)
    inactive = await _upload(client, admin, inactive_id, representative_xlsx())
    assert inactive.status_code == 422 and "inativo" in inactive.json()["error"]

    # ANALYST sem vínculo com a unidade: o contexto "não existe" para ele
    _, other_id = await _context(client, auth_header, code="TSO")
    out_of_scope = await _upload(client, auth_header("ANALYST"), other_id, representative_xlsx())
    assert out_of_scope.status_code == 404


async def test_viewer_without_equipments_write_is_denied(client, auth_header) -> None:
    unit_id, context_id = await _context(client, auth_header)
    await _grant(client, auth_header, "VIEWER", unit_id)
    viewer = auth_header("VIEWER")
    assert (await client.get("/api/v1/imports/monday/profiles", headers=viewer)).status_code == 403
    assert (await _upload(client, viewer, context_id, representative_xlsx())).status_code == 403
