"""Resolução de catálogos por equipamento durante o `plan` da migração.

Carrega uma vez os catálogos do Hub (EAP, disciplinas, Work Packages do contexto,
fornecedores, usuários) e, para cada equipamento, decide EXISTING/CREATE/CONFLICT/
UNRESOLVED com base nas evidências agregadas (`catalog_evidence`).

O resultado de cada equipamento traz:
- IDs já existentes (vínculo direto);
- referências (`catalog_refs`) a catálogos que o apply vai CRIAR, para que o
  equipamento receba o ID novo na mesma transação;
- issues (bloqueantes só em conflito real).

Nunca cria User. Nunca usa fuzzy. Nenhuma regra por obra.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.scope import user_can_access_unit
from app.models.equipment import Discipline, ProjectContext, ProjectEap, WorkPackage
from app.models.supplier import Supplier, SupplierAlias
from app.models.user import User
from app.modules.monday_import.catalog_evidence import CatalogEvidence
from app.modules.monday_import.catalog_taxonomy import (
    CatalogAction,
    DisciplineEntry,
    SupplierEntry,
    SupplierIndex,
    WorkPackageEntry,
    decide_discipline,
    decide_project_eap,
    decide_supplier,
    decide_work_package,
    discipline_target_name,
)
from app.modules.monday_import.eap_resolution import EapResolver
from app.modules.monday_import.mapping_file import ValidatedMapping
from app.modules.monday_import.normalization import canonical_text

CatalogKind = Literal["eap_node", "project_eap", "discipline", "work_package", "supplier"]


@dataclass(slots=True, frozen=True)
class CatalogPlanItem:
    """Decisão de catálogo visível no plan. `key` identifica o registro na origem
    (código ou nome). Itens repetidos entre equipamentos aparecem uma vez."""

    kind: CatalogKind
    key: str
    action: CatalogAction
    target_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    evidence_source: str | None = None
    issue_code: str | None = None
    message: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "key": self.key,
            "action": self.action.value,
            "targetId": self.target_id,
            "payload": dict(self.payload),
            "evidenceSource": self.evidence_source,
            "issueCode": self.issue_code,
            "message": self.message,
            "detail": dict(self.detail),
        }


@dataclass(slots=True)
class EquipmentCatalogs:
    eap_node_id: str | None = None
    discipline_id: str | None = None
    responsible_user_id: str | None = None
    supplier_id: str | None = None
    work_package_ids: list[str] = field(default_factory=list)
    # Todos os códigos de WP da origem foram resolvidos (EXISTING/CREATE)? Se não,
    # o plan não propõe remover vínculos existentes (sem perda acidental).
    work_packages_complete: bool = True
    has_work_package_source: bool = False
    refs: dict[str, Any] = field(default_factory=dict)
    issues: list[tuple[str, str, dict[str, Any] | None]] = field(default_factory=list)


class CatalogPlanner:
    def __init__(
        self,
        *,
        project_context_id: str,
        unit_id: str,
        mapping: ValidatedMapping,
        evidence: CatalogEvidence,
        eap_resolver: EapResolver,
        disciplines: tuple[dict[str, DisciplineEntry], dict[str, DisciplineEntry]],
        work_packages: dict[str, WorkPackageEntry],
        suppliers: SupplierIndex,
        users_by_name: dict[str, list[str]],
        linked_eap_node_ids: set[str],
    ) -> None:
        self.project_context_id = project_context_id
        self.unit_id = unit_id
        self.mapping = mapping
        self.evidence = evidence
        self.eap_resolver = eap_resolver
        self.discipline_by_name, self.discipline_by_code = disciplines
        self.work_package_by_code = work_packages
        self.suppliers = suppliers
        self.users_by_name = users_by_name
        self.linked_eap_node_ids = linked_eap_node_ids
        self._items: dict[tuple[str, str], CatalogPlanItem] = {}
        self._user_access: dict[str, bool] = {}
        self.eap_summary: dict[str, int] = {}
        self.responsible_summary: dict[str, int] = {"resolved": 0, "unresolved": 0}

    @classmethod
    async def load(
        cls,
        session: AsyncSession,
        *,
        project_context_id: str,
        mapping: ValidatedMapping,
        evidence: CatalogEvidence,
    ) -> CatalogPlanner:
        context = await session.get(ProjectContext, project_context_id)
        if context is None:
            raise ValueError("project_context não encontrado")
        linked = set(
            (
                await session.scalars(
                    select(ProjectEap.eap_node_id).where(ProjectEap.project_context_id == project_context_id)
                )
            ).all()
        )
        return cls(
            project_context_id=project_context_id,
            unit_id=context.unit_id,
            mapping=mapping,
            evidence=evidence,
            eap_resolver=await EapResolver.load(session, mapping.eap_nodes, evidence),
            disciplines=await _discipline_index(session),
            work_packages=await _work_package_index(session, project_context_id),
            suppliers=await _supplier_index(session),
            users_by_name=await _users_by_name(session),
            linked_eap_node_ids=linked,
        )

    @property
    def items(self) -> list[CatalogPlanItem]:
        return list(self._items.values())

    def _record(self, item: CatalogPlanItem) -> None:
        self._items.setdefault((item.kind, item.key), item)

    async def resolve(self, session: AsyncSession, normalized: dict[str, Any]) -> EquipmentCatalogs:
        result = EquipmentCatalogs()
        self._resolve_eap(normalized, result)
        self._resolve_discipline(normalized, result)
        await self._resolve_responsible(session, normalized, result)
        self._resolve_work_packages(normalized, result)
        self._resolve_supplier(normalized, result)
        return result

    # -- EAP + ProjectEap ----------------------------------------------------------

    def _resolve_eap(self, normalized: dict[str, Any], result: EquipmentCatalogs) -> None:
        eap = self.eap_resolver.resolve(normalized.get("area_name"))
        self.eap_summary[eap.status] = self.eap_summary.get(eap.status, 0) + 1
        decision = eap.decision
        if eap.issue_code is not None:
            detail: dict[str, Any] = {"sourceValue": eap.raw, "candidates": list(eap.codes)}
            if decision is not None and decision.detail:
                detail.update(decision.detail)
            result.issues.append((eap.issue_code, eap.issue_message or "", detail))
        if decision is None:
            return
        code = decision.code or f"raw:{canonical_text(eap.raw)}"
        for spec in eap.creates:
            self._record(
                CatalogPlanItem(
                    kind="eap_node",
                    key=spec.code,
                    action=CatalogAction.CREATE,
                    payload={
                        "code": spec.code,
                        "name": spec.name,
                        "level": spec.level.value,
                        "parentCode": spec.parent_code,
                    },
                    evidence_source=spec.evidence_source,
                )
            )
        if eap.from_mapping:
            # Correção explícita do usuário para ESTE valor de origem (nunca regra global
            # por código); o valor bruto fica registrado ao lado do código escolhido.
            self._record(
                CatalogPlanItem(
                    kind="eap_node",
                    key=f"{code} ← {eap.raw}",
                    action=decision.action,
                    target_id=decision.node_id,
                    evidence_source="MANUAL_MAPPING",
                    detail={"sourceValue": eap.raw, "mappedCode": code},
                )
            )
        elif decision.action is not CatalogAction.CREATE:
            self._record(
                CatalogPlanItem(
                    kind="eap_node",
                    key=code,
                    action=decision.action,
                    target_id=decision.node_id,
                    issue_code=decision.issue_code,
                    message=decision.message,
                    detail=dict(decision.detail),
                )
            )
        if decision.action is CatalogAction.EXISTING and eap.eap_node_id is not None:
            result.eap_node_id = eap.eap_node_id
            self._record(
                CatalogPlanItem(
                    kind="project_eap",
                    key=code,
                    action=decide_project_eap(eap.eap_node_id, self.linked_eap_node_ids),
                    target_id=eap.eap_node_id,
                )
            )
        elif decision.action is CatalogAction.CREATE:
            result.refs["eapCode"] = code
            self._record(CatalogPlanItem(kind="project_eap", key=code, action=CatalogAction.CREATE))

    # -- Discipline ----------------------------------------------------------------

    def _resolve_discipline(self, normalized: dict[str, Any], result: EquipmentCatalogs) -> None:
        name = normalized.get("discipline_name")
        mapped = self.mapping.resolve_discipline(name)
        if mapped is not None:
            result.discipline_id = mapped
            self._record(
                CatalogPlanItem(
                    kind="discipline", key=str(name), action=CatalogAction.EXISTING, target_id=mapped
                )
            )
            return
        # Alias explícito aprovado (ex.: "Metal Mec." → "Metal Mecânica."); a chave
        # do item continua sendo o valor bruto da origem, para rastreabilidade.
        target = discipline_target_name(name)
        lookup = self.evidence.discipline_code(target)
        decision = decide_discipline(target, lookup, self.discipline_by_name, self.discipline_by_code)
        if decision is None:
            return
        raw_name = str(name).strip()
        detail = dict(decision.detail)
        if target != raw_name:
            detail["aliasOf"] = raw_name
        self._record(
            CatalogPlanItem(
                kind="discipline",
                key=raw_name,
                action=decision.action,
                target_id=decision.discipline_id,
                payload={"code": decision.code, "name": decision.name} if decision.code else {},
                evidence_source=decision.evidence_source,
                issue_code=decision.issue_code,
                message=decision.message,
                detail=detail,
            )
        )
        if decision.issue_code is not None:
            result.issues.append(
                (decision.issue_code, decision.message or "", {**detail, "sourceValue": raw_name})
            )
        if decision.action is CatalogAction.EXISTING:
            result.discipline_id = decision.discipline_id
        elif decision.action is CatalogAction.CREATE:
            result.refs["discipline"] = raw_name

    # -- Responsible (nunca cria User) ---------------------------------------------

    async def _resolve_responsible(
        self, session: AsyncSession, normalized: dict[str, Any], result: EquipmentCatalogs
    ) -> None:
        name = normalized.get("responsible_name")
        if not name:
            return
        user_id = self.mapping.resolve_responsible(name)
        if user_id is None:
            candidates = self.users_by_name.get(canonical_text(name), [])
            # Nome exato e único entre usuários ativos com acesso à unidade.
            if len(candidates) == 1 and await self._can_access(session, candidates[0]):
                user_id = candidates[0]
        if user_id is None:
            self.responsible_summary["unresolved"] += 1
            result.issues.append(
                (
                    "RESPONSIBLE_UNRESOLVED",
                    "Responsável não resolvido para usuário do Hub; equipamento importado sem responsável.",
                    {"sourceValue": name},
                )
            )
            return
        self.responsible_summary["resolved"] += 1
        result.responsible_user_id = user_id

    async def _can_access(self, session: AsyncSession, user_id: str) -> bool:
        if user_id not in self._user_access:
            self._user_access[user_id] = await user_can_access_unit(session, user_id, self.unit_id)
        return self._user_access[user_id]

    # -- Work Package --------------------------------------------------------------

    def _resolve_work_packages(self, normalized: dict[str, Any], result: EquipmentCatalogs) -> None:
        codes = [str(code) for code in normalized.get("work_package_codes") or [] if str(code).strip()]
        result.has_work_package_source = bool(codes)
        create_codes: list[str] = []
        for code in codes:
            mapped = self.mapping.resolve_work_package(code)
            if mapped is not None:
                result.work_package_ids.append(mapped)
                self._record(
                    CatalogPlanItem(
                        kind="work_package", key=code, action=CatalogAction.EXISTING, target_id=mapped
                    )
                )
                continue
            decision = decide_work_package(
                code, self.evidence.work_package_name(code), self.work_package_by_code
            )
            self._record(
                CatalogPlanItem(
                    kind="work_package",
                    key=decision.code,
                    action=decision.action,
                    target_id=decision.work_package_id,
                    payload={"code": decision.code, "name": decision.name} if decision.name else {},
                    evidence_source=decision.evidence_source,
                    issue_code=decision.issue_code,
                    message=decision.message,
                    detail=dict(decision.detail),
                )
            )
            if decision.issue_code is not None:
                result.issues.append(
                    (decision.issue_code, decision.message or "", {"sourceValue": code, **decision.detail})
                )
            if decision.action is CatalogAction.EXISTING and decision.work_package_id is not None:
                result.work_package_ids.append(decision.work_package_id)
            elif decision.action is CatalogAction.CREATE:
                create_codes.append(decision.code)
            else:
                result.work_packages_complete = False
        if create_codes:
            result.refs["workPackageCodes"] = sorted(create_codes)

    # -- Supplier ------------------------------------------------------------------

    def _resolve_supplier(self, normalized: dict[str, Any], result: EquipmentCatalogs) -> None:
        raw_names = [str(name) for name in normalized.get("suppliers_raw") or [] if name]
        decision = decide_supplier(
            normalized.get("supplier_corporate_code"), raw_names, self.suppliers, self.evidence.supplier
        )
        if decision is None:
            return
        self._record(
            CatalogPlanItem(
                kind="supplier",
                key=decision.key,
                action=decision.action,
                target_id=decision.supplier_id,
                payload=dict(decision.payload),
                evidence_source=decision.evidence_source,
                issue_code=decision.issue_code,
                message=decision.message,
                detail=dict(decision.detail),
            )
        )
        if decision.issue_code is not None:
            result.issues.append((decision.issue_code, decision.message or "", dict(decision.detail) or None))
        if decision.action is CatalogAction.EXISTING:
            result.supplier_id = decision.supplier_id
        elif decision.action is CatalogAction.CREATE:
            result.refs["supplierCode"] = decision.key


async def _discipline_index(
    session: AsyncSession,
) -> tuple[dict[str, DisciplineEntry], dict[str, DisciplineEntry]]:
    rows = (
        await session.execute(select(Discipline.id, Discipline.code, Discipline.name, Discipline.active))
    ).all()
    entries = [DisciplineEntry(row.id, row.code, row.name, row.active) for row in rows]
    return (
        {canonical_text(entry.name): entry for entry in entries},
        {canonical_text(entry.code): entry for entry in entries},
    )


async def _work_package_index(session: AsyncSession, project_context_id: str) -> dict[str, WorkPackageEntry]:
    """WP é escopado ao ProjectContext: WP de outro contexto nunca é reutilizado."""
    rows = (
        await session.execute(
            select(WorkPackage.id, WorkPackage.code, WorkPackage.name, WorkPackage.active).where(
                WorkPackage.project_context_id == project_context_id
            )
        )
    ).all()
    return {
        canonical_text(row.code): WorkPackageEntry(row.id, row.code, row.name, row.active) for row in rows
    }


def _unique(pairs: list[tuple[str, SupplierEntry]]) -> dict[str, SupplierEntry]:
    """Chave que aponta para mais de um fornecedor é ambígua e fica de fora."""
    found: dict[str, SupplierEntry] = {}
    ambiguous: set[str] = set()
    for key, entry in pairs:
        if not key:
            continue
        if key in found and found[key].id != entry.id:
            ambiguous.add(key)
        found.setdefault(key, entry)
    return {key: entry for key, entry in found.items() if key not in ambiguous}


async def _supplier_index(session: AsyncSession) -> SupplierIndex:
    suppliers = (
        await session.execute(
            select(
                Supplier.id,
                Supplier.corporate_code,
                Supplier.legal_name,
                Supplier.trade_name,
                Supplier.active,
            )
        )
    ).all()
    entries = {
        row.id: SupplierEntry(row.id, row.corporate_code, row.legal_name, row.trade_name, row.active)
        for row in suppliers
    }
    aliases = (await session.execute(select(SupplierAlias.alias, SupplierAlias.supplier_id))).all()
    names: list[tuple[str, SupplierEntry]] = []
    for entry in entries.values():
        names.append((canonical_text(entry.legal_name), entry))
        if entry.trade_name:
            names.append((canonical_text(entry.trade_name), entry))
    return SupplierIndex(
        by_code={entry.corporate_code: entry for entry in entries.values() if entry.corporate_code},
        by_alias=_unique(
            [
                (canonical_text(row.alias), entries[row.supplier_id])
                for row in aliases
                if row.supplier_id in entries
            ]
        ),
        by_name=_unique(names),
    )


async def _users_by_name(session: AsyncSession) -> dict[str, list[str]]:
    rows = (await session.execute(select(User.id, User.name).where(User.active.is_(True)))).all()
    index: dict[str, list[str]] = {}
    for row in rows:
        index.setdefault(canonical_text(row.name), []).append(row.id)
    return index
