"""Seed idempotente das evidências da `relacao_fornecedores_hub.xlsx`.

A carga não cria Supplier nem EquipmentSupplier. Ela preserva recomendações,
referências e pendências numa tabela auxiliar usada apenas pelo mecanismo de
sugestão. Divergências permanecem marcadas para revisão humana.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.models.supplier import SupplierRecommendationEvidence
from app.modules.monday_import.normalization import canonical_header, canonical_text, clean_text
from app.modules.monday_import.xlsx import XlsxReadError, XlsxSheet, read_sheet
from app.shared.audit import record_audit

SOURCE_FILE = "relacao_fornecedores_hub.xlsx"
SEED_VERSION = 1
SEED_SOURCES = frozenset({"MAPA_TIPOS", "RECOMENDACOES_OC", "LGE", "MONDAY_CODES", "PENDENCIAS"})


class SupplierEvidenceSeedError(ValueError):
    pass


@dataclass(slots=True, frozen=True)
class EvidenceSeedRow:
    equipment_key: str
    equipment_label: str
    supplier_reference: str | None
    corporate_code: str | None
    evidence_type: str
    confidence: str
    occurrences: int | None
    total_occurrences: int | None
    share: Decimal | None
    source: str
    source_key: str
    review_required: bool
    details: dict[str, object] = field(default_factory=dict)

    def values(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True, frozen=True)
class EvidenceSeedAction:
    source: str
    source_key: str
    action: str
    changes: dict[str, object] = field(default_factory=dict)


def _audit_safe(value: Any) -> Any:
    """Converte valores do modelo para o JSON da trilha de auditoria."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _audit_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_audit_safe(item) for item in value]
    return value


def _sheet(source: bytes, name: str, required: dict[str, str]) -> list[tuple[int, dict[str, Any]]]:
    try:
        sheet = read_sheet(source, name)
    except XlsxReadError as exc:
        raise SupplierEvidenceSeedError(str(exc)) from exc
    return _rows(sheet, required)


def _rows(sheet: XlsxSheet, required: dict[str, str]) -> list[tuple[int, dict[str, Any]]]:
    if not sheet.rows:
        raise SupplierEvidenceSeedError(f"aba {sheet.name!r} vazia")
    header = sheet.rows[0]
    positions = {canonical_header(header.value(column)): column for column in header.cells}
    missing = [title for title in required.values() if canonical_header(title) not in positions]
    if missing:
        raise SupplierEvidenceSeedError(f"aba {sheet.name!r} sem coluna(s): {missing}")
    result: list[tuple[int, dict[str, Any]]] = []
    for row in sheet.rows[1:]:
        values = {
            key: row.value(positions[canonical_header(title)]) for key, title in required.items()
        }
        if any(clean_text(value) is not None for value in values.values()):
            result.append((row.number, values))
    return result


def _integer(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    return int(Decimal(str(value)))


def _decimal(value: Any) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None
    return Decimal(str(value))


def _code(value: Any) -> str | None:
    text = clean_text(value)
    if text is None:
        return None
    normalized = text[:-2] if text.endswith(".0") and text[:-2].isdigit() else text
    return normalized if normalized.isdigit() and len(normalized) <= 20 else None


def _key(source: str, equipment: str, supplier: str | None, kind: str) -> str:
    return "|".join((source, canonical_text(equipment), canonical_text(supplier), kind))[:300]


def _oc_confidence(orders: int | None, share: Decimal | None) -> str:
    if orders and orders >= 2 and share is not None and share >= Decimal("0.70"):
        return "HIGH"
    if (orders and orders >= 2) or (share is not None and share >= Decimal("0.40")):
        return "MEDIUM"
    return "LOW"


def _map_rows(source: bytes) -> list[EvidenceSeedRow]:
    columns = {
        "equipment": "EQUIPAMENTO PADRONIZADO",
        "candidate": "CANDIDATO DE FORNECEDOR",
        "recommendation": "RECOMENDAÇÃO OCs REAIS",
        "orders": "Nº OCs",
        "share": "PARTICIPAÇÃO",
        "references": "REFERENCIAIS LGE",
        "reference_count": "QTD REFERENCIAIS",
        "classification": "CLASSIFICAÇÃO",
        "action": "AÇÃO NO HUB",
    }
    result: list[EvidenceSeedRow] = []
    for _, values in _sheet(source, "Mapa_Tipos_Equipamento", columns):
        equipment = clean_text(values["equipment"])
        if equipment is None:
            continue
        classification = clean_text(values["classification"]) or "SEM_BASE"
        recommendation = clean_text(values["recommendation"])
        candidate = clean_text(values["candidate"])
        orders = _integer(values["orders"])
        share = _decimal(values["share"])
        if classification == "CANDIDATO_OC" and recommendation:
            supplier, kind = recommendation, "PURCHASE_ORDER"
            confidence = _oc_confidence(orders, share)
            review = False
        elif classification == "REFERENCIAL_UNICO" and candidate:
            supplier, kind, confidence, review = candidate, "LGE_REFERENCE", "MEDIUM", False
        else:
            supplier, kind, confidence, review = None, "NO_AUTOMATIC_SUGGESTION", "NONE", True
        result.append(
            EvidenceSeedRow(
                canonical_text(equipment),
                equipment,
                supplier,
                None,
                kind,
                confidence,
                orders,
                None,
                share,
                "MAPA_TIPOS",
                _key("MAPA_TIPOS", equipment, supplier, kind),
                review,
                {
                    "classification": classification,
                    "references": clean_text(values["references"]),
                    "referenceCount": _integer(values["reference_count"]),
                    "action": clean_text(values["action"]),
                },
            )
        )
    return result


def _purchase_order_rows(source: bytes) -> list[EvidenceSeedRow]:
    columns = {
        "equipment": "TIPO PADRONIZADO",
        "supplier": "FORNECEDOR RECOMENDADO",
        "orders": "Nº DE OCs",
        "share": "PARTICIPAÇÃO NO TIPO (%)",
        "competitors": "FORNECEDORES CONCORRENTES",
        "alternatives": "ALTERNATIVAS (TOP 3)",
    }
    result: list[EvidenceSeedRow] = []
    for _, values in _sheet(source, "Recomendacoes_OC", columns):
        equipment, supplier = clean_text(values["equipment"]), clean_text(values["supplier"])
        if not equipment or not supplier:
            continue
        orders, share = _integer(values["orders"]), _decimal(values["share"])
        result.append(
            EvidenceSeedRow(
                canonical_text(equipment), equipment, supplier, None, "PURCHASE_ORDER",
                _oc_confidence(orders, share), orders, None, share, "RECOMENDACOES_OC",
                _key("RECOMENDACOES_OC", equipment, supplier, "PURCHASE_ORDER"), False,
                {
                    "competitors": _integer(values["competitors"]),
                    "alternatives": clean_text(values["alternatives"]),
                },
            )
        )
    return result


def _lge_rows(source: bytes) -> list[EvidenceSeedRow]:
    columns = {
        "supplier": "FORNECEDOR REFERENCIAL",
        "group": "GRUPO / EMPRESA CONSOLIDADA",
        "confidence": "CONFIABILIDADE",
        "status": "STATUS DA CONSOLIDAÇÃO",
        "orders": "Nº DE OCs (ERP LEM F1)",
        "types": "TIPOS FORNECIDOS (ERP)",
    }
    result: list[EvidenceSeedRow] = []
    for _, values in _sheet(source, "Fornecedores_LGE", columns):
        supplier = clean_text(values["group"]) or clean_text(values["supplier"])
        types = clean_text(values["types"])
        if not supplier or not types or canonical_text(types) == "informacao nao fornecida":
            continue
        status = clean_text(values["status"]) or "A VALIDAR"
        canonical_status = canonical_text(status).upper()
        review = "NAO CONSOLIDAR" in canonical_status or "VALIDAR" in canonical_status
        confidence_raw = canonical_text(values["confidence"])
        confidence = {"alta": "HIGH", "media": "MEDIUM", "baixa": "LOW"}.get(
            confidence_raw, "LOW"
        )
        for equipment in (part.strip() for part in types.split(";") if part.strip()):
            result.append(
                EvidenceSeedRow(
                    canonical_text(equipment), equipment, supplier, None, "LGE_HISTORY", confidence,
                    _integer(values["orders"]), None, None, "LGE",
                    _key("LGE", equipment, supplier, "LGE_HISTORY"), review,
                    {"consolidationStatus": status},
                )
            )
    return result


def _monday_rows(source: bytes) -> list[EvidenceSeedRow]:
    columns = {
        "equipment": "EQUIPAMENTO (NOME EXATO NO MONDAY)",
        "rdn": "CÓD. FORN. CS — RDN F1",
        "rvd": "CÓD. FORN. CS — RVD F1",
        "consolidated": "CÓDIGO CONSOLIDADO (SÓ QUANDO SEGURO)",
        "status": "STATUS DA COMPARAÇÃO",
    }
    result: list[EvidenceSeedRow] = []
    for _, values in _sheet(source, "Codigos_Monday_RDN_RVD", columns):
        equipment = clean_text(values["equipment"])
        if not equipment:
            continue
        status = clean_text(values["status"]) or "PENDENTE"
        code = _code(values["consolidated"])
        review = code is None or "DIVERGENTE" in status or "REVISAR" in status or "PENDENTE" in status
        result.append(
            EvidenceSeedRow(
                canonical_text(equipment), equipment, None, None if review else code,
                "MONDAY_CORPORATE_CODE", "NONE" if review else "HIGH", None, None, None,
                "MONDAY_CODES", _key("MONDAY_CODES", equipment, code, "MONDAY_CORPORATE_CODE"), review,
                {
                    "rdnCode": clean_text(values["rdn"]),
                    "rvdCode": clean_text(values["rvd"]),
                    "comparisonStatus": status,
                },
            )
        )
    return result


def _pending_rows(source: bytes) -> list[EvidenceSeedRow]:
    columns = {
        "type": "TIPO",
        "equipment": "ITEM",
        "evidence": "EVIDÊNCIA",
        "reason": "MOTIVO",
        "treatment": "TRATAMENTO",
    }
    result: list[EvidenceSeedRow] = []
    for row_number, values in _sheet(source, "Pendencias_Validacao", columns):
        equipment = clean_text(values["equipment"])
        if not equipment:
            continue
        result.append(
            EvidenceSeedRow(
                canonical_text(equipment), equipment, None, None, "PENDING_REVIEW", "NONE",
                None, None, None, "PENDENCIAS", f"row:{row_number}", True,
                {
                    "type": clean_text(values["type"]),
                    "evidence": clean_text(values["evidence"]),
                    "reason": clean_text(values["reason"]),
                    "treatment": clean_text(values["treatment"]),
                },
            )
        )
    return result


def load_evidence_seed(source: bytes | str | Path) -> list[EvidenceSeedRow]:
    data = source if isinstance(source, bytes) else Path(source).read_bytes()
    rows = (
        _map_rows(data)
        + _purchase_order_rows(data)
        + _lge_rows(data)
        + _monday_rows(data)
        + _pending_rows(data)
    )
    # A planilha contém dois nomes que diferem só por acento/capitalização e
    # apontam para o mesmo código em unidades diferentes. Na chave canônica são
    # a mesma evidência; mantê-la uma vez evita duplicidade sem inventar merge.
    unique: dict[tuple[str, str], EvidenceSeedRow] = {}
    for row in rows:
        unique.setdefault((row.source, row.source_key), row)
    return list(unique.values())


def export_evidence_seed(rows: list[EvidenceSeedRow], destination: str | Path) -> None:
    """Materializa a seed revisável sem carregar o XLSX no deploy."""
    payload = {
        "version": SEED_VERSION,
        "sourceFile": SOURCE_FILE,
        "rows": [_audit_safe(row.values()) for row in rows],
    }
    Path(destination).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_evidence_seed_json(source: str | Path) -> list[EvidenceSeedRow]:
    payload = json.loads(Path(source).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("version") != SEED_VERSION:
        raise SupplierEvidenceSeedError("versão inválida da seed de fornecedores")
    raw_rows = payload.get("rows")
    if not isinstance(raw_rows, list):
        raise SupplierEvidenceSeedError("seed de fornecedores sem lista de evidências")
    rows: list[EvidenceSeedRow] = []
    try:
        for raw in raw_rows:
            values = dict(raw)
            values["share"] = Decimal(values["share"]) if values.get("share") is not None else None
            rows.append(EvidenceSeedRow(**values))
    except (KeyError, TypeError, ValueError) as exc:
        raise SupplierEvidenceSeedError("linha inválida na seed de fornecedores") from exc
    return rows


async def reconcile_evidence_seed(
    session: AsyncSession, rows: list[EvidenceSeedRow]
) -> list[EvidenceSeedAction]:
    existing = {
        (item.source, item.source_key): item
        for item in (
            await session.scalars(
                select(SupplierRecommendationEvidence).where(
                    SupplierRecommendationEvidence.source.in_(SEED_SOURCES)
                )
            )
        ).all()
    }
    actions: list[EvidenceSeedAction] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (row.source, row.source_key)
        seen.add(key)
        stored = existing.get(key)
        values = row.values()
        if stored is None:
            actions.append(EvidenceSeedAction(*key, "CREATE", values))
            continue
        changes = {
            name: value
            for name, value in values.items()
            if getattr(stored, name) != value
        }
        if not stored.active:
            changes["active"] = True
        actions.append(EvidenceSeedAction(*key, "UPDATE" if changes else "NOOP", changes))
    for key, stored in existing.items():
        if key not in seen and stored.active:
            actions.append(EvidenceSeedAction(*key, "DEACTIVATE", {"active": False}))
    return actions


async def apply_evidence_seed(
    session: AsyncSession, rows: list[EvidenceSeedRow], *, actor: CurrentUser
) -> list[EvidenceSeedAction]:
    actions = await reconcile_evidence_seed(session, rows)
    by_key = {(row.source, row.source_key): row for row in rows}
    stored = {
        (item.source, item.source_key): item
        for item in (
            await session.scalars(
                select(SupplierRecommendationEvidence).where(
                    SupplierRecommendationEvidence.source.in_(SEED_SOURCES)
                )
            )
        ).all()
    }
    for action in actions:
        key = (action.source, action.source_key)
        if action.action == "CREATE":
            item = SupplierRecommendationEvidence(**by_key[key].values())
            session.add(item)
            await session.flush()
            await record_audit(
                session, user_id=actor.id, action="supplier_evidence.seed_create",
                entity="SupplierRecommendationEvidence", entity_id=item.id,
                new_data=_audit_safe(action.changes), metadata={"sourceFile": SOURCE_FILE},
            )
        elif action.action in {"UPDATE", "DEACTIVATE"}:
            item = stored[key]
            previous = {name: getattr(item, name) for name in action.changes}
            for name, value in action.changes.items():
                setattr(item, name, value)
            await record_audit(
                session, user_id=actor.id, action="supplier_evidence.seed_update",
                entity="SupplierRecommendationEvidence", entity_id=item.id,
                previous_data=_audit_safe(previous), new_data=_audit_safe(action.changes),
                metadata={"sourceFile": SOURCE_FILE},
            )
    await session.commit()
    return actions
