"""Parsing e normalização da planilha de fornecedores (sem banco)."""

from __future__ import annotations

from collections import namedtuple

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.auth import CurrentUser
from app.core.errors import ConflictError, DomainError
from app.core.permissions import Role
from app.modules.suppliers.sheet_import import (
    ParsedRow,
    RowError,
    SupplierState,
    chunked,
    import_suppliers,
    normalize_active,
    normalize_code,
    normalize_tax_id,
    parse_workbook,
    plan_import,
    validate_upload,
)
from app.shared.audit import chunk_size_for
from tests.unit.monday_xlsx_fixture import build_workbook

HEADER = ["CODIGO_FORNECEDOR", "NOME_FORNECEDOR", "DOCUMENTO", "ATIVO"]


def test_code_numeric_from_excel() -> None:
    assert normalize_code(123.0) == "123"
    assert normalize_code(123) == "123"
    assert normalize_code(" 00123 ") == "00123"
    assert normalize_code(None) is None


def test_tax_id_digits_only() -> None:
    assert normalize_tax_id("11.222.333/0001-81") == "11222333000181"
    assert normalize_tax_id(11222333000181) == "11222333000181"
    assert normalize_tax_id("N/A") is None
    assert normalize_tax_id("DE123456") == "DE123456"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("S", True), ("Sim", True), ("1", True), (1, True), ("true", True), ("Ativo", True), ("x", True),
     ("N", False), ("Não", False), ("nao", False), (0, False), ("FALSE", False), ("Inativo", False),
     (None, None), ("", None)],
)
def test_active_values(raw, expected) -> None:
    assert normalize_active(raw) is expected


def test_active_unrecognized() -> None:
    with pytest.raises(RowError):
        normalize_active("talvez")


def test_parse_by_header_name_not_position_and_skips_blank() -> None:
    content = build_workbook(
        {"F": [["ativo", "Documento", "extra", "nome fornecedor", "Codigo-Fornecedor"],
               ["S", "1.2", "z", "Acme", 77.0],
               [None, None, None, None, None]]}
    )
    rows = parse_workbook(content)
    assert len(rows) == 1
    assert (rows[0].row, rows[0].corporate_code, rows[0].legal_name, rows[0].tax_id, rows[0].active) == (
        2, "77", "Acme", "12", True)


def test_missing_header() -> None:
    with pytest.raises(DomainError, match="DOCUMENTO"):
        parse_workbook(build_workbook({"F": [["CODIGO_FORNECEDOR", "NOME_FORNECEDOR", "ATIVO"]]}))


def test_invalid_file() -> None:
    with pytest.raises(DomainError):
        parse_workbook(b"nao e xlsx")
    with pytest.raises(DomainError):
        validate_upload("a.csv", 10, 100)
    with pytest.raises(DomainError):
        validate_upload("a.xlsx", 0, 100)


# --- Casamento em memória e gravação em lote (sem banco) -------------------


def _row(n, code=None, name=None, tax=None, active=None, error=None) -> ParsedRow:
    return ParsedRow(row=n, corporate_code=code, legal_name=name, tax_id=tax, active=active, error=error)


def _state(sid, code, tax, name, active=True) -> SupplierState:
    return SupplierState(id=sid, corporate_code=code, tax_id=tax, legal_name=name, active=active)


def test_plan_matching_rules_and_errors() -> None:
    existing = [
        _state("a", "7001", "11111111000111", "Velho Nome"),
        _state("b", "7002", "22222222000122", "Outro"),
        _state("c", "7008", "88888888000188", "Terceiro"),
        _state("d", None, "55555555000155", "Sem codigo"),
    ]
    rows = [
        _row(2, "7001", "Novo Nome", "11111111000111", False),  # update
        _row(3, "7008", "Terceiro", "88888888000188", None),  # unchanged
        _row(4, "7003", "Criado", "33333333000133", True),  # create
        _row(5, None, "Por documento", "44444444000144", None),  # create sem código
        _row(6, "7001", "Duplicado", None, True),  # código repetido
        _row(7, "7004", None, None, True),  # novo sem nome
        _row(8, "7005", "Conflito", "22222222000122", True),  # doc com outro código
        _row(9, "7002", "Outro", "11111111000111", True),  # código de um, doc de outro
        _row(10, "7006", "x", None, error="valor inválido em ATIVO"),
        _row(11, "7009", None, "55555555000155", None),  # preenche código vazio
        _row(12, None, None, "44444444000144", False),  # atualiza o recém-criado
        _row(13, "X" * 21, "Longo", None, None),
    ]
    plan = plan_import(rows, existing, actor_id="u1")
    result = plan.result
    assert (result.total, result.created, result.updated, result.unchanged) == (12, 2, 3, 1)
    assert [e.row for e in result.errors] == [6, 7, 8, 9, 10, 13]

    assert {s.corporate_code for s in plan.creates} == {"7003", None}
    by_doc = {s.tax_id: s for s in plan.creates}
    assert by_doc["44444444000144"].active is False  # INSERT já leva o estado final
    assert all(len(s.id) == 36 for s in plan.creates)  # id gerado no cliente

    assert set(plan.updates) == {"a", "d"}
    assert plan.updates["a"][1] == {"legal_name", "active"}
    assert plan.updates["d"][1] == {"corporate_code"}

    actions = [r["action"] for r in plan.audit_rows]
    assert actions.count("supplier.create") == 2 and actions.count("supplier.update") == 3
    first_update = next(r for r in plan.audit_rows if r["entityId"] == "a")
    assert first_update["previousData"] == {"legal_name": "Velho Nome", "active": True}
    assert first_update["newData"] == {"legal_name": "Novo Nome", "active": False}
    assert first_update["metadata"] == {"source": "supplier_sheet_import", "row": 2}
    assert first_update["userId"] == "u1" and first_update["entity"] == "Supplier"


class _FakeResult:
    def __init__(self, rows) -> None:
        self._rows = rows

    def all(self):
        return self._rows


class _FakeSession:
    """Só `execute`/`commit`/`rollback`: qualquer `flush`/`add` quebraria o teste."""

    def __init__(self, snapshot=(), fail_on_write: bool = False) -> None:
        self.snapshot = list(snapshot)
        self.fail_on_write = fail_on_write
        self.executed: list[tuple[object, object]] = []
        self.commits = self.rollbacks = 0

    async def execute(self, stmt, params=None):
        self.executed.append((stmt, params))
        if len(self.executed) == 1:
            return _FakeResult(self.snapshot)
        if self.fail_on_write:
            raise IntegrityError("INSERT", {}, Exception("supplier_tax_id_key"))
        return _FakeResult([])

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def _sheet(rows) -> bytes:
    return build_workbook({"F": [HEADER, *rows]})


_ACTOR = CurrentUser(id="u1", email="a@b.c", name="A", role=Role.ADMIN, active=True)


async def test_create_6k_rows_uses_bounded_statements() -> None:
    n = 6000
    session = _FakeSession()
    content = _sheet([[f"C{i}", f"Fornecedor {i}", f"{i:014d}", "S"] for i in range(n)])
    result = await import_suppliers(session, content=content, actor=_ACTOR)
    assert (result.created, result.updated, result.errors) == (n, 0, [])
    # 1 SELECT + 6 INSERT supplier + 6 INSERT AuditLog; um único commit.
    assert len(session.executed) == 13
    assert session.commits == 1
    inserts = [stmt for stmt, _ in session.executed[1:]]
    assert all(stmt.is_insert for stmt in inserts)


async def test_update_rows_use_executemany_chunks() -> None:
    n = 2500
    Row = namedtuple("Row", "id corporate_code tax_id legal_name active")
    snapshot = [Row(f"id{i}", f"C{i}", None, f"Antigo {i}", True) for i in range(n)]
    session = _FakeSession(snapshot)
    content = _sheet([[f"C{i}", f"Novo {i}", None, None] for i in range(n)])
    result = await import_suppliers(session, content=content, actor=_ACTOR)
    assert (result.created, result.updated) == (0, n)
    updates = [(s, p) for s, p in session.executed if getattr(s, "is_update", False)]
    assert [len(p) for _, p in updates] == [1000, 1000, 500]
    assert set(updates[0][1][0]) == {"b_id", "b_updated_at", "b_legal_name"}
    assert len(session.executed) == 1 + 3 + 3  # SELECT + UPDATE em lote + AuditLog em lote


async def test_integrity_error_becomes_conflict() -> None:
    session = _FakeSession(fail_on_write=True)
    with pytest.raises(ConflictError):
        await import_suppliers(session, content=_sheet([["1", "A", None, None]]), actor=_ACTOR)
    assert (session.commits, session.rollbacks) == (0, 1)


def test_chunking_respects_bind_limit() -> None:
    assert chunk_size_for(7) == 1000
    assert chunk_size_for(100) == 327
    assert 100 * chunk_size_for(100) <= 32767
    assert [len(c) for c in chunked(list(range(2501)), 1000)] == [1000, 1000, 501]
