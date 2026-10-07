"""Sugestões transparentes de fornecedor, sem reconciliação fuzzy."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.equipment import Equipment
from app.models.supplier import (
    EquipmentSupplier,
    Supplier,
    SupplierAlias,
    SupplierRecommendationEvidence,
)
from app.modules.monday_import.normalization import canonical_text


@dataclass(slots=True, frozen=True)
class SupplierSuggestion:
    supplier_id: str | None
    supplier_name: str
    corporate_code: str | None
    confidence: str
    evidence: list[str] = field(default_factory=list)
    source_value: str | None = None
    requires_registration: bool = False
    source_matched: bool = False


class SupplierSuggestionResolver:
    def __init__(
        self,
        *,
        suppliers: dict[str, Supplier],
        by_code: dict[str, Supplier],
        by_tax_id: dict[str, Supplier],
        by_name: dict[str, Supplier],
        history: dict[str, dict[str, set[str]]],
        evidence: dict[str, list[SupplierRecommendationEvidence]],
    ) -> None:
        self.suppliers = suppliers
        self.by_code = by_code
        self.by_tax_id = by_tax_id
        self.by_name = by_name
        self.history = history
        self.evidence = evidence

    @classmethod
    async def load(cls, session: AsyncSession) -> SupplierSuggestionResolver:
        supplier_rows = list(
            (await session.scalars(select(Supplier).where(Supplier.active.is_(True)))).all()
        )
        suppliers = {item.id: item for item in supplier_rows}
        name_pairs: list[tuple[str, Supplier]] = []
        for item in supplier_rows:
            name_pairs.append((canonical_text(item.legal_name), item))
            if item.trade_name:
                name_pairs.append((canonical_text(item.trade_name), item))
        aliases = (
            await session.execute(select(SupplierAlias.alias, SupplierAlias.supplier_id))
        ).all()
        name_pairs.extend(
            (canonical_text(alias), suppliers[supplier_id])
            for alias, supplier_id in aliases
            if supplier_id in suppliers
        )

        grouped_names: dict[str, list[Supplier]] = defaultdict(list)
        for key, supplier in name_pairs:
            if supplier.id not in {item.id for item in grouped_names[key]}:
                grouped_names[key].append(supplier)
        unique_names = {key: items[0] for key, items in grouped_names.items() if len(items) == 1}

        history: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        history_rows = await session.execute(
            select(Equipment.name, EquipmentSupplier.equipment_id, EquipmentSupplier.supplier_id)
            .join(EquipmentSupplier, EquipmentSupplier.equipment_id == Equipment.id)
            .join(Supplier, Supplier.id == EquipmentSupplier.supplier_id)
            .where(Supplier.active.is_(True))
        )
        for equipment_name, equipment_id, supplier_id in history_rows.all():
            history[canonical_text(equipment_name)][supplier_id].add(equipment_id)

        evidence: dict[str, list[SupplierRecommendationEvidence]] = defaultdict(list)
        evidence_rows = (
            await session.scalars(
                select(SupplierRecommendationEvidence).where(
                    SupplierRecommendationEvidence.active.is_(True)
                )
            )
        ).all()
        for evidence_item in evidence_rows:
            evidence[evidence_item.equipment_key].append(evidence_item)
        return cls(
            suppliers=suppliers,
            by_code={item.corporate_code: item for item in supplier_rows if item.corporate_code},
            by_tax_id={item.tax_id: item for item in supplier_rows if item.tax_id},
            by_name=unique_names,
            history=history,
            evidence=evidence,
        )

    def _source_supplier(
        self, *, code: str | None, tax_id: str | None, name: str | None
    ) -> tuple[Supplier | None, str | None]:
        if code and code in self.by_code:
            return self.by_code[code], "código corporativo exato"
        if tax_id and tax_id in self.by_tax_id:
            return self.by_tax_id[tax_id], "documento corporativo exato"
        if name:
            supplier = self.by_name.get(canonical_text(name))
            if supplier:
                return supplier, "alias ou nome corporativo exato"
        return None, None

    def suggest(
        self,
        equipment_name: str,
        *,
        source_code: str | None = None,
        source_tax_id: str | None = None,
        source_name: str | None = None,
    ) -> SupplierSuggestion | None:
        source_value = source_code or source_tax_id or source_name
        supplier, source_reason = self._source_supplier(
            code=source_code, tax_id=source_tax_id, name=source_name
        )
        if supplier and source_reason:
            return SupplierSuggestion(
                supplier.id,
                supplier.legal_name,
                supplier.corporate_code,
                "HIGH",
                [f"Fornecedor informado na origem reconciliado por {source_reason}."],
                source_value,
                source_matched=True,
            )

        key = canonical_text(equipment_name)
        historical = self.history.get(key, {})
        if historical:
            ranked = sorted(historical.items(), key=lambda item: (-len(item[1]), item[0]))
            best_id, equipment_ids = ranked[0]
            total = len(set().union(*historical.values()))
            tied = len(ranked) > 1 and len(ranked[1][1]) == len(equipment_ids)
            if not tied and best_id in self.suppliers:
                count = len(equipment_ids)
                ratio = count / total if total else 0
                confidence = "HIGH" if count >= 2 and ratio >= 0.8 else "MEDIUM" if ratio >= 0.6 else "LOW"
                best = self.suppliers[best_id]
                return SupplierSuggestion(
                    best.id,
                    best.legal_name,
                    best.corporate_code,
                    confidence,
                    [f"{best.legal_name} foi confirmado em {count} de {total} equipamentos equivalentes."],
                    source_value,
                )

        candidates = [
            item
            for item in self.evidence.get(key, [])
            if not item.review_required and item.confidence != "NONE"
        ]
        priority = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        candidates.sort(
            key=lambda item: (
                priority.get(item.confidence, 9),
                item.evidence_type,
                item.source_key,
            )
        )
        for item in candidates:
            matched = self.by_code.get(item.corporate_code) if item.corporate_code else None
            if matched is None and item.supplier_reference:
                matched = self.by_name.get(canonical_text(item.supplier_reference))
            name = matched.legal_name if matched else item.supplier_reference
            if not name:
                continue
            if item.evidence_type == "PURCHASE_ORDER":
                detail = f"Evidência de {item.occurrences or 0} ordem(ns) de compra"
                if item.share is not None:
                    detail += f", participação de {float(item.share):.1%} no tipo"
                detail += "."
            elif item.evidence_type == "MONDAY_CORPORATE_CODE":
                detail = "Código corporativo consistente no histórico Monday RDN/RVD."
            else:
                detail = "Referência histórica da base corporativa LGE."
            return SupplierSuggestion(
                matched.id if matched else None,
                name,
                matched.corporate_code if matched else item.corporate_code,
                item.confidence,
                [detail],
                source_value,
                requires_registration=matched is None,
            )
        return None
