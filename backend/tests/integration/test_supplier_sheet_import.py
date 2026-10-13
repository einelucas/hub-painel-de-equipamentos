"""POST /suppliers/import: upsert por planilha."""

from __future__ import annotations

from sqlalchemy import func, select

from app.models.audit import AuditLog
from app.models.supplier import Supplier
from tests.unit.monday_xlsx_fixture import build_workbook

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
HEADER = ["CODIGO_FORNECEDOR", "NOME_FORNECEDOR", "DOCUMENTO", "ATIVO"]


async def _upload(client, headers, rows, name="f.xlsx", header=HEADER):
    content = build_workbook({"Fornecedores": [header, *rows]})
    return await client.post(
        "/api/v1/suppliers/import", files={"file": (name, content, XLSX_MIME)}, headers=headers
    )


async def _create(client, headers, name, code, tax_id):
    response = await client.post(
        "/api/v1/suppliers",
        json={"legalName": name, "corporateCode": code, "taxId": tax_id},
        headers=headers,
    )
    assert response.status_code == 201, response.text


async def test_upsert_flow(client, auth_header, db_session) -> None:
    admin = auth_header("ADMIN")
    await _create(client, admin, "Velho Nome", "7001", "11111111000111")
    await _create(client, admin, "Outro", "7002", "22222222000122")
    await _create(client, admin, "Terceiro", "7008", "88888888000188")

    response = await _upload(
        client,
        admin,
        [
            [7001.0, "Novo Nome", "11.111.111/0001-11", "N"],  # 2 update
            [7008, "Terceiro", "88888888000188", None],  # 3 unchanged
            [7003, "Criado", "33.333.333/0001-33", "Sim"],  # 4 novo
            [None, "Por documento", "44444444000144", None],  # 5 novo sem código
            [7001, "Duplicado", None, "S"],  # 6 código repetido
            [7004, None, None, "S"],  # 7 novo sem nome
            [7005, "Conflito", "22222222000122", "S"],  # 8 doc de fornecedor com outro código
            [7002, "Outro", "11111111000111", "S"],  # 9 código de um, doc de outro
            [7006, "Ativo ruim", None, "talvez"],  # 10
            [None, None, None, None],
        ],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["total"], body["created"], body["updated"], body["unchanged"]) == (9, 2, 1, 1)
    assert [e["row"] for e in body["errors"]] == [6, 7, 8, 9, 10]

    db_session.expire_all()
    first = (await db_session.execute(select(Supplier).where(Supplier.corporate_code == "7001"))).scalar_one()
    assert (first.legal_name, first.active) == ("Novo Nome", False)
    stmt = select(Supplier).where(Supplier.corporate_code == "7003")
    created = (await db_session.execute(stmt)).scalar_one()
    assert (created.tax_id, created.active) == ("33333333000133", True)
    total = (await db_session.execute(select(func.count()).select_from(Supplier))).scalar_one()
    audits = (
        await db_session.execute(
            select(AuditLog.action, AuditLog.entityId, AuditLog.metadata_).where(
                AuditLog.metadata_["source"].astext == "supplier_sheet_import"
            )
        )
    ).all()
    assert sorted(a.action for a in audits) == ["supplier.create", "supplier.create", "supplier.update"]
    assert any(a.entityId == created.id and a.metadata_["row"] == 4 for a in audits)
    assert total >= 5

    again = (await _upload(client, admin, [[7001, "Novo Nome", "11111111000111", "N"]])).json()
    assert (again["updated"], again["unchanged"], again["created"]) == (0, 1, 0)


async def test_errors_and_permissions(client, auth_header) -> None:
    admin = auth_header("ADMIN")
    missing = await _upload(client, admin, [], header=["CODIGO_FORNECEDOR", "NOME_FORNECEDOR"])
    assert missing.status_code in (400, 422)
    assert "DOCUMENTO" in missing.text
    wrong_ext = await _upload(client, admin, [], name="f.csv")
    assert wrong_ext.status_code in (400, 422)
    denied = await _upload(client, auth_header("VIEWER"), [])
    assert denied.status_code == 403
