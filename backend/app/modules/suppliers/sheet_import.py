"""Importação (upsert) de fornecedores a partir de uma planilha .xlsx.

Colunas localizadas pelo nome do cabeçalho (nunca por posição):
CODIGO_FORNECEDOR, NOME_FORNECEDOR, DOCUMENTO, ATIVO. Nunca apaga nem
desativa fornecedores ausentes da planilha. Linhas com erro são ignoradas e
reportadas; as válidas são aplicadas numa única transação.

O casamento é feito em memória (`plan_import`) sobre um snapshot enxuto dos
fornecedores; a gravação (`apply_plan`) usa INSERT multi-VALUES e UPDATE
executemany em lotes, sem flush por linha — poucas dezenas de round-trips
mesmo para milhares de linhas num banco remoto.
"""

from __future__ import annotations

import asyncio
import re
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import bindparam, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.errors import ConflictError, DomainError
from app.models.common import utcnow
from app.models.supplier import Supplier
from app.modules.monday_import.normalization import (
    canonical_header,
    canonical_text,
    clean_text,
    normalize_external_id,
)
from app.modules.monday_import.xlsx import XlsxReadError, read_first_sheet
from app.shared.audit import build_audit_row, bulk_insert_audit, chunk_size_for
from app.shared.schema import CamelModel

REQUIRED_HEADERS = {
    "corporate_code": "CODIGO_FORNECEDOR",
    "legal_name": "NOME_FORNECEDOR",
    "tax_id": "DOCUMENTO",
    "active": "ATIVO",
}
_TRUE = {"s", "sim", "1", "true", "ativo", "x", "yes", "y", "verdadeiro"}
_FALSE = {"n", "nao", "0", "false", "inativo", "no", "falso"}
_MAX_CODE, _MAX_NAME, _MAX_TAX_ID = 20, 200, 32


class SupplierImportErrorOut(CamelModel):
    row: int
    message: str


class SupplierImportOut(CamelModel):
    total: int
    created: int
    updated: int
    unchanged: int
    errors: list[SupplierImportErrorOut]


@dataclass(slots=True)
class ParsedRow:
    row: int
    corporate_code: str | None
    legal_name: str | None
    tax_id: str | None
    active: bool | None  # None = célula vazia
    error: str | None = None


class RowError(ValueError):
    pass


def normalize_code(value: Any) -> str | None:
    """Código como texto; 123.0 numérico do Excel vira "123"."""
    if isinstance(value, bool):
        return clean_text(value)
    return normalize_external_id(value)


def normalize_tax_id(value: Any) -> str | None:
    """Somente dígitos (padrão da carga de fornecedores); texto com letras é mantido."""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = clean_text(value)
    if text is None:
        return None
    if re.search(r"[A-Za-z]", text):
        return text
    digits = re.sub(r"\D", "", text)
    return digits or None


def normalize_active(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    text = canonical_text(value)
    if text == "":
        return None
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    raise RowError(f"valor inválido em ATIVO: {value!r} (use S/N, Sim/Não, 1/0 ou Ativo/Inativo)")


def validate_upload(file_name: str | None, size: int, max_bytes: int) -> None:
    if not (file_name or "").strip().lower().endswith(".xlsx"):
        raise DomainError("Envie um arquivo .xlsx.")
    if size == 0:
        raise DomainError("Arquivo vazio.")
    if size > max_bytes:
        raise DomainError(f"Arquivo excede o limite de {max_bytes // (1024 * 1024)} MB.")


def parse_workbook(content: bytes) -> list[ParsedRow]:
    try:
        sheet = read_first_sheet(content)
    except XlsxReadError as exc:
        raise DomainError(f"Planilha inválida: {exc}") from exc
    if not sheet.rows:
        raise DomainError("A planilha está vazia.")
    header = sheet.rows[0]
    by_header = {canonical_header(header.value(column)): column for column in header.cells}
    missing = [t for t in REQUIRED_HEADERS.values() if canonical_header(t) not in by_header]
    if missing:
        raise DomainError("Colunas obrigatórias ausentes na planilha: " + ", ".join(missing))
    columns = {key: by_header[canonical_header(title)] for key, title in REQUIRED_HEADERS.items()}
    parsed: list[ParsedRow] = []
    for row in sheet.rows[1:]:
        raw = {key: row.value(column) for key, column in columns.items()}
        if all(clean_text(value) is None for value in raw.values()):
            continue
        error: str | None = None
        active: bool | None = None
        try:
            active = normalize_active(raw["active"])
        except RowError as exc:
            error = str(exc)
        parsed.append(
            ParsedRow(
                row=row.number,
                corporate_code=normalize_code(raw["corporate_code"]),
                legal_name=clean_text(raw["legal_name"]),
                tax_id=normalize_tax_id(raw["tax_id"]),
                active=active,
                error=error,
            )
        )
    return parsed


@dataclass(slots=True)
class SupplierState:
    """Estado em memória de um fornecedor (snapshot do banco ou recém-criado)."""

    id: str
    corporate_code: str | None
    tax_id: str | None
    legal_name: str
    active: bool
    is_new: bool = False


@dataclass(slots=True)
class ImportPlan:
    """Resultado do casamento em memória: o que gravar e o que reportar."""

    result: SupplierImportOut
    creates: list[SupplierState]
    # id -> (estado final, campos alterados) de fornecedores já existentes.
    updates: dict[str, tuple[SupplierState, set[str]]]
    audit_rows: list[dict[str, Any]]


_UPDATABLE = ("legal_name", "tax_id", "corporate_code", "active")
_PRELOAD_COLUMNS = (
    Supplier.id,
    Supplier.corporate_code,
    Supplier.tax_id,
    Supplier.legal_name,
    Supplier.active,
)
_CONFLICT_MESSAGE = (
    "Outro processo cadastrou ou alterou fornecedores com o mesmo código ou documento "
    "durante a importação. Nenhuma alteração foi aplicada; envie a planilha novamente."
)


def plan_import(
    rows: list[ParsedRow], existing: list[SupplierState], *, actor_id: str | None
) -> ImportPlan:
    """Casamento e validação linha a linha, puramente em memória (sem banco)."""
    by_code = {s.corporate_code: s for s in existing if s.corporate_code}
    by_tax = {s.tax_id: s for s in existing if s.tax_id}
    creates: list[SupplierState] = []
    updates: dict[str, tuple[SupplierState, set[str]]] = {}
    audit_rows: list[dict[str, Any]] = []

    created = updated = unchanged = 0
    errors: list[SupplierImportErrorOut] = []
    seen_codes: set[str] = set()

    def fail(row: ParsedRow, message: str) -> None:
        errors.append(SupplierImportErrorOut(row=row.row, message=message))

    for row in rows:
        if row.error:
            fail(row, row.error)
            continue
        if row.corporate_code and row.corporate_code in seen_codes:
            fail(row, f"código {row.corporate_code} repetido na planilha")
            continue
        if row.corporate_code and len(row.corporate_code) > _MAX_CODE:
            fail(row, f"CODIGO_FORNECEDOR excede {_MAX_CODE} caracteres")
            continue
        if row.legal_name and len(row.legal_name) > _MAX_NAME:
            fail(row, f"NOME_FORNECEDOR excede {_MAX_NAME} caracteres")
            continue
        if row.tax_id and len(row.tax_id) > _MAX_TAX_ID:
            fail(row, f"DOCUMENTO excede {_MAX_TAX_ID} caracteres")
            continue
        if row.corporate_code:
            seen_codes.add(row.corporate_code)

        supplier = by_code.get(row.corporate_code) if row.corporate_code else None
        if supplier is None and row.tax_id:
            supplier = by_tax.get(row.tax_id)

        if supplier is None:
            if not row.legal_name:
                fail(row, "NOME_FORNECEDOR é obrigatório para cadastrar um novo fornecedor")
                continue
            holder = by_tax.get(row.tax_id) if row.tax_id else None
            if holder is not None:  # defensivo: já seria casado acima
                fail(row, f"documento já pertence a {holder.legal_name!r}")
                continue
            active = True if row.active is None else row.active
            # id gerado no cliente (mesmo default de `uuid_pk`): dispensa flush.
            supplier = SupplierState(
                id=str(uuid.uuid4()),
                corporate_code=row.corporate_code,
                legal_name=row.legal_name,
                tax_id=row.tax_id,
                active=active,
                is_new=True,
            )
            creates.append(supplier)
            if supplier.corporate_code:
                by_code[supplier.corporate_code] = supplier
            if supplier.tax_id:
                by_tax[supplier.tax_id] = supplier
            audit_rows.append(
                build_audit_row(
                    user_id=actor_id,
                    action="supplier.create",
                    entity="Supplier",
                    entity_id=supplier.id,
                    new_data={
                        "corporate_code": supplier.corporate_code,
                        "legal_name": supplier.legal_name,
                        "tax_id": supplier.tax_id,
                        "active": supplier.active,
                    },
                    metadata={"source": "supplier_sheet_import", "row": row.row},
                )
            )
            created += 1
            continue

        # Fornecedor existente: valida conflitos antes de alterar.
        if row.tax_id:
            holder = by_tax.get(row.tax_id)
            if holder is not None and holder.id != supplier.id:
                fail(
                    row,
                    f"documento {row.tax_id} já pertence a outro fornecedor ({holder.legal_name!r})",
                )
                continue
        if row.corporate_code and supplier.corporate_code not in (None, row.corporate_code):
            fail(
                row,
                f"fornecedor já possui outro código corporativo ({supplier.corporate_code})",
            )
            continue

        changes: dict[str, Any] = {}
        if row.legal_name and row.legal_name != supplier.legal_name:
            changes["legal_name"] = row.legal_name
        if row.tax_id and row.tax_id != supplier.tax_id:
            changes["tax_id"] = row.tax_id
        if row.corporate_code and not supplier.corporate_code:
            changes["corporate_code"] = row.corporate_code
        if row.active is not None and row.active != supplier.active:
            changes["active"] = row.active
        if not changes:
            unchanged += 1
            continue
        previous = {field: getattr(supplier, field) for field in changes}
        for field, value in changes.items():
            setattr(supplier, field, value)
        if "tax_id" in changes:
            by_tax[changes["tax_id"]] = supplier
        if "corporate_code" in changes:
            by_code[changes["corporate_code"]] = supplier
        # Recém-criado: o INSERT (montado no fim) já leva o estado final.
        if not supplier.is_new:
            _, fields = updates.setdefault(supplier.id, (supplier, set()))
            fields.update(changes)
        audit_rows.append(
            build_audit_row(
                user_id=actor_id,
                action="supplier.update",
                entity="Supplier",
                entity_id=supplier.id,
                previous_data=previous,
                new_data=changes,
                metadata={"source": "supplier_sheet_import", "row": row.row},
            )
        )
        updated += 1

    return ImportPlan(
        result=SupplierImportOut(
            total=len(rows), created=created, updated=updated, unchanged=unchanged, errors=errors
        ),
        creates=creates,
        updates=updates,
        audit_rows=audit_rows,
    )


def chunked(items: list[Any], size: int) -> list[list[Any]]:
    return [items[start : start + size] for start in range(0, len(items), size)]


async def apply_plan(session: AsyncSession, plan: ImportPlan) -> int:
    """Grava o plano em lotes, sem flush do ORM. Retorna o nº de statements."""
    table = Supplier.__table__
    now = utcnow()
    statements = 0

    insert_rows = [
        {
            "id": s.id,
            "corporate_code": s.corporate_code,
            "legal_name": s.legal_name,
            "tax_id": s.tax_id,
            "active": s.active,
            "created_at": now,
            "updated_at": now,
        }
        for s in plan.creates
    ]
    for chunk in chunked(insert_rows, chunk_size_for(len(insert_rows[0]) if insert_rows else 1)):
        await session.execute(insert(table).values(chunk))
        statements += 1

    # UPDATE por id via executemany; um statement por conjunto de colunas
    # alteradas para nunca regravar campo que a planilha não mudou.
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for state, fields in plan.updates.values():
        key = tuple(f for f in _UPDATABLE if f in fields)
        params = {"b_id": state.id, "b_updated_at": now}
        params.update({f"b_{f}": getattr(state, f) for f in key})
        groups.setdefault(key, []).append(params)
    for key, params_list in groups.items():
        stmt = (
            update(table)
            .where(table.c.id == bindparam("b_id"))
            .values({f: bindparam(f"b_{f}") for f in (*key, "updated_at")})
        )
        for chunk in chunked(params_list, 1000):
            await session.execute(stmt, chunk)
            statements += 1

    statements += await bulk_insert_audit(session, plan.audit_rows)
    return statements


async def import_suppliers(
    session: AsyncSession, *, content: bytes, actor: CurrentUser
) -> SupplierImportOut:
    # openpyxl é CPU-bound: fora do event loop.
    rows = await asyncio.to_thread(parse_workbook, content)
    snapshot = (await session.execute(select(*_PRELOAD_COLUMNS))).all()
    existing = [
        SupplierState(
            id=r.id,
            corporate_code=r.corporate_code,
            tax_id=r.tax_id,
            legal_name=r.legal_name,
            active=r.active,
        )
        for r in snapshot
    ]
    plan = plan_import(rows, existing, actor_id=actor.id)
    # Snapshot sem lock: um cadastro concorrente pode violar os índices únicos
    # parciais (código/documento). A transação é única: em violação nada é
    # aplicado e o usuário recebe 409 em vez de 500.
    try:
        await apply_plan(session, plan)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(_CONFLICT_MESSAGE) from exc
    return plan.result
