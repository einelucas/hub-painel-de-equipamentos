"""Reconciliação do plano de fornecedores com o banco e aplicação idempotente.

- Fornecedor: localizado SOMENTE por `corporate_code` (CREATE/UPDATE/NOOP).
- Alias: único por (source, context, alias); já existente = NOOP.
- Vínculo: equipamento localizado pela identidade de origem registrada pelo
  importador Monday (`external_mapping`, chave `normalized-name:<nome>`); um
  equipamento já vinculado ao mesmo fornecedor = NOOP.

Qualquer conflito (documento de outro fornecedor, alias apontando para outro
fornecedor, equipamento com OUTRO fornecedor) bloqueia a aplicação inteira: a
carga nunca substitui dado existente por conta própria. Equipamento não
localizado não bloqueia — o vínculo é reportado e fica para uma próxima
execução (idempotente) depois que o equipamento for importado.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.models.equipment import ProjectContext, Unit
from app.models.monday_import import ExternalMapping
from app.models.supplier import EquipmentSupplier, Supplier, SupplierAlias
from app.modules.monday_import.mappings import SOURCE_SYSTEM
from app.modules.supplier_import.plan import SupplierImportPlan
from app.shared.audit import record_audit

_AUDIT_SOURCE = "supplier_import.lem_f2"


@dataclass(slots=True)
class SupplierAction:
    corporate_code: str
    action: str  # CREATE | UPDATE | NOOP | CONFLICT
    supplier_id: str | None = None
    changes: dict[str, Any] = field(default_factory=dict)
    detail: str | None = None


@dataclass(slots=True)
class AliasAction:
    alias: str
    corporate_code: str
    action: str  # CREATE | NOOP | CONFLICT
    detail: str | None = None


@dataclass(slots=True)
class LinkAction:
    equipment_name: str
    corporate_code: str
    action: str  # CREATE | NOOP | EQUIPMENT_NOT_FOUND | CONFLICT
    equipment_id: str | None = None
    detail: str | None = None


@dataclass(slots=True)
class DatabaseReconciliation:
    project_context_id: str | None
    suppliers: list[SupplierAction] = field(default_factory=list)
    aliases: list[AliasAction] = field(default_factory=list)
    links: list[LinkAction] = field(default_factory=list)

    def count(self, group: str, action: str) -> int:
        items: list[Any] = getattr(self, group)
        return sum(1 for item in items if item.action == action)

    @property
    def conflicts(self) -> list[str]:
        return [
            f"{kind} {name}: {item.detail}"
            for kind, items, attr in (
                ("fornecedor", self.suppliers, "corporate_code"),
                ("alias", self.aliases, "alias"),
                ("vínculo", self.links, "equipment_name"),
            )
            for item in items
            if item.action == "CONFLICT"
            for name in [getattr(item, attr)]
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "projectContextId": self.project_context_id,
            "suppliers": [asdict(item) for item in self.suppliers],
            "aliases": [asdict(item) for item in self.aliases],
            "links": [asdict(item) for item in self.links],
            "conflicts": self.conflicts,
        }


class SupplierImportBlockedError(RuntimeError):
    pass


async def resolve_project_context(session: AsyncSession, *, unit_code: str, context_code: str) -> str | None:
    return await session.scalar(
        select(ProjectContext.id)
        .join(Unit, ProjectContext.unit_id == Unit.id)
        .where(Unit.code == unit_code, ProjectContext.code == context_code)
    )


async def _reconcile_suppliers(session: AsyncSession, plan: SupplierImportPlan) -> list[SupplierAction]:
    codes = list(plan.suppliers)
    tax_ids = [item.tax_id for item in plan.suppliers.values() if item.tax_id]
    by_code = {
        row.corporate_code: row
        for row in (await session.scalars(select(Supplier).where(Supplier.corporate_code.in_(codes)))).all()
    }
    by_tax_id = {
        row.tax_id: row
        for row in (await session.scalars(select(Supplier).where(Supplier.tax_id.in_(tax_ids)))).all()
    }
    actions: list[SupplierAction] = []
    for code, supplier in plan.suppliers.items():
        existing = by_code.get(code)
        holder = by_tax_id.get(supplier.tax_id) if supplier.tax_id else None
        if holder is not None and holder.corporate_code != code:
            detail = (
                f"documento {supplier.tax_id} já pertence ao fornecedor {holder.legal_name!r} "
                f"(código {holder.corporate_code or 'vazio'}); reconciliar manualmente"
            )
            actions.append(SupplierAction(code, "CONFLICT", holder.id, detail=detail))
            continue
        if existing is None:
            actions.append(SupplierAction(code, "CREATE"))
            continue
        official = {"legal_name": supplier.legal_name, "tax_id": supplier.tax_id, "active": supplier.active}
        changes = {name: value for name, value in official.items() if getattr(existing, name) != value}
        actions.append(SupplierAction(code, "UPDATE" if changes else "NOOP", existing.id, changes))
    return actions


async def _reconcile_aliases(
    session: AsyncSession, plan: SupplierImportPlan, supplier_ids: dict[str, str | None]
) -> list[AliasAction]:
    existing = {
        row.alias: row
        for row in (
            await session.scalars(
                select(SupplierAlias).where(
                    SupplierAlias.source.in_({item.source for item in plan.aliases} or {""}),
                    SupplierAlias.context == plan.alias_context,
                    SupplierAlias.alias.in_([item.alias for item in plan.aliases]),
                )
            )
        ).all()
    }
    actions: list[AliasAction] = []
    for alias in plan.aliases:
        registered = existing.get(alias.alias)
        if registered is None:
            action, detail = "CREATE", None
        elif registered.supplier_id == supplier_ids.get(alias.corporate_code):
            action, detail = "NOOP", None
        else:
            action, detail = "CONFLICT", "alias já registrado para outro fornecedor"
        actions.append(AliasAction(alias.alias, alias.corporate_code, action, detail))
    return actions


async def _reconcile_links(
    session: AsyncSession,
    plan: SupplierImportPlan,
    supplier_ids: dict[str, str | None],
    project_context_id: str | None,
) -> list[LinkAction]:
    equipment_ids: dict[str, str] = {}
    if project_context_id is not None and plan.links:
        rows = await session.execute(
            select(ExternalMapping.external_id, ExternalMapping.target_entity_id).where(
                ExternalMapping.project_context_id == project_context_id,
                ExternalMapping.source_system == SOURCE_SYSTEM,
                ExternalMapping.source_entity_type == "equipment",
                ExternalMapping.external_id.in_([item.equipment_source_key for item in plan.links]),
            )
        )
        equipment_ids = {external_id: target for external_id, target in rows.all()}
    linked = {
        row.equipment_id: row.supplier_id
        for row in (
            await session.scalars(
                select(EquipmentSupplier).where(
                    EquipmentSupplier.equipment_id.in_(list(equipment_ids.values()))
                )
            )
        ).all()
    }
    missing_detail = (
        "contexto de projeto não encontrado no banco"
        if project_context_id is None
        else "equipamento ainda não importado neste contexto"
    )
    actions: list[LinkAction] = []
    for link in plan.links:
        equipment_id = equipment_ids.get(link.equipment_source_key)
        if equipment_id is None:
            action, detail = "EQUIPMENT_NOT_FOUND", missing_detail
        elif equipment_id not in linked:
            action, detail = "CREATE", None
        elif linked[equipment_id] == supplier_ids.get(link.corporate_code):
            action, detail = "NOOP", None
        else:
            action = "CONFLICT"
            detail = "equipamento já vinculado a outro fornecedor; a carga não substitui vínculos"
        actions.append(LinkAction(link.equipment_name, link.corporate_code, action, equipment_id, detail))
    return actions


async def reconcile_with_database(
    session: AsyncSession, plan: SupplierImportPlan, *, project_context_id: str | None
) -> DatabaseReconciliation:
    """Somente leitura: descreve o que a aplicação faria."""
    result = DatabaseReconciliation(project_context_id)
    result.suppliers = await _reconcile_suppliers(session, plan)
    supplier_ids = {action.corporate_code: action.supplier_id for action in result.suppliers}
    result.aliases = await _reconcile_aliases(session, plan, supplier_ids)
    result.links = await _reconcile_links(session, plan, supplier_ids, project_context_id)
    return result


async def apply_supplier_import(
    session: AsyncSession,
    plan: SupplierImportPlan,
    *,
    project_context_id: str | None,
    actor: CurrentUser,
) -> DatabaseReconciliation:
    """Aplica numa única transação. Recalcula a reconciliação dentro dela e
    recusa se houver erro de planilha ou qualquer conflito."""
    if plan.errors:
        raise SupplierImportBlockedError(f"plano com {len(plan.errors)} erro(s): {plan.errors[:5]}")
    reconciliation = await reconcile_with_database(session, plan, project_context_id=project_context_id)
    if reconciliation.conflicts:
        raise SupplierImportBlockedError(f"conflitos com o banco: {reconciliation.conflicts[:5]}")
    metadata = {"source": _AUDIT_SOURCE, "file": plan.source_file, "fileSha256": plan.file_sha256}

    supplier_ids: dict[str, str] = {}
    for action in reconciliation.suppliers:
        official = plan.suppliers[action.corporate_code]
        if action.action == "CREATE":
            values = {
                "corporate_code": official.corporate_code,
                "legal_name": official.legal_name,
                "tax_id": official.tax_id,
                "active": official.active,
            }
            created = Supplier(**values)
            session.add(created)
            await session.flush()
            action.supplier_id = created.id
            await record_audit(
                session,
                user_id=actor.id,
                action="supplier.import_create",
                entity="Supplier",
                entity_id=created.id,
                new_data=values,
                metadata=metadata,
            )
        elif action.action == "UPDATE":
            stored = await session.get(Supplier, action.supplier_id)
            assert stored is not None
            previous = {name: getattr(stored, name) for name in action.changes}
            for name, value in action.changes.items():
                setattr(stored, name, value)
            await record_audit(
                session,
                user_id=actor.id,
                action="supplier.import_update",
                entity="Supplier",
                entity_id=stored.id,
                previous_data=previous,
                new_data=action.changes,
                metadata=metadata,
            )
        assert action.supplier_id is not None
        supplier_ids[action.corporate_code] = action.supplier_id

    for alias_action, alias in zip(reconciliation.aliases, plan.aliases, strict=True):
        if alias_action.action == "CREATE":
            session.add(
                SupplierAlias(
                    supplier_id=supplier_ids[alias.corporate_code],
                    alias=alias.alias,
                    source=alias.source,
                    context=alias.context,
                )
            )
    await session.flush()

    for link_action in reconciliation.links:
        if link_action.action != "CREATE":
            continue
        assert link_action.equipment_id is not None
        supplier_id = supplier_ids[link_action.corporate_code]
        link = EquipmentSupplier(
            equipment_id=link_action.equipment_id, supplier_id=supplier_id, is_primary=True
        )
        session.add(link)
        await session.flush()
        await record_audit(
            session,
            user_id=actor.id,
            action="equipment_supplier.import_link",
            entity="EquipmentSupplier",
            entity_id=link.id,
            new_data={"supplier_id": supplier_id, "is_primary": True},
            metadata={**metadata, "equipmentId": link_action.equipment_id},
        )
    await session.commit()
    return reconciliation
