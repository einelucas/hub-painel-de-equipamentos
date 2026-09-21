"""Auditoria somente-leitura do estado real do C2 no banco DEV.

Não escreve nada. Usado pela homologação funcional (Etapa 5).
"""

from __future__ import annotations

import asyncio
import json

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models.access import UserUnitAccess
from app.models.audit import AuditLog
from app.models.equipment import (
    Equipment,
    EquipmentComponent,
    EquipmentWorkPackage,
    WorkflowTransition,
    WorkPackage,
)
from app.models.process import Contract, LegalProcess, Negotiation, PurchaseOrder, PurchaseRequest
from app.models.user import User

PCID = "b264c140-7f10-4430-93d0-d880c2029bd0"


async def main() -> None:
    out: dict = {}
    async with SessionLocal() as s:
        out["equipment_total"] = (
            await s.execute(select(func.count()).select_from(Equipment).where(Equipment.project_context_id == PCID))
        ).scalar_one()
        out["component_total"] = (
            await s.execute(
                select(func.count())
                .select_from(EquipmentComponent)
                .join(Equipment)
                .where(Equipment.project_context_id == PCID)
            )
        ).scalar_one()
        out["wp_links_total"] = (
            await s.execute(
                select(func.count())
                .select_from(EquipmentWorkPackage)
                .join(Equipment, EquipmentWorkPackage.equipment_id == Equipment.id)
                .where(Equipment.project_context_id == PCID)
            )
        ).scalar_one()

        rows = (
            await s.execute(
                select(Equipment.current_stage, func.count(Equipment.id))
                .where(Equipment.project_context_id == PCID)
                .group_by(Equipment.current_stage)
            )
        ).all()
        out["by_stage"] = {str(k): v for k, v in rows}

        for stage in [0, 4, 6, 8]:
            eq = (
                await s.execute(
                    select(Equipment)
                    .where(Equipment.project_context_id == PCID, Equipment.current_stage == stage)
                    .limit(1)
                )
            ).scalars().first()
            if not eq:
                continue
            key = f"stage_{stage}_sample"
            out[key] = {
                "id": eq.id,
                "name": eq.name,
                "origin": eq.origin,
                "startup_at": str(eq.startup_at),
                "criticality": eq.criticality,
                "capex": str(eq.capex_estimated),
                "responsible_user_id": eq.responsible_user_id,
                "area_id": eq.area_id,
                "discipline_id": eq.discipline_id,
                "work_package_id": eq.work_package_id,
            }
            neg = (await s.execute(select(Negotiation).where(Negotiation.equipment_id == eq.id))).scalar_one_or_none()
            legal = (await s.execute(select(LegalProcess).where(LegalProcess.equipment_id == eq.id))).scalar_one_or_none()
            contract = (await s.execute(select(Contract).where(Contract.equipment_id == eq.id))).scalar_one_or_none()
            pr = (await s.execute(select(PurchaseRequest).where(PurchaseRequest.equipment_id == eq.id))).scalar_one_or_none()
            po = (await s.execute(select(PurchaseOrder).where(PurchaseOrder.equipment_id == eq.id))).scalar_one_or_none()
            wp_links = (
                await s.execute(select(EquipmentWorkPackage).where(EquipmentWorkPackage.equipment_id == eq.id))
            ).scalars().all()
            comp_count = (
                await s.execute(
                    select(func.count()).select_from(EquipmentComponent).where(EquipmentComponent.equipment_id == eq.id)
                )
            ).scalar_one()
            out[key]["negotiation_exists"] = neg is not None
            out[key]["negotiation_equalized"] = neg.equalized if neg else None
            out[key]["legal_exists"] = legal is not None
            out[key]["legal_ticket"] = legal.ticket_number if legal else None
            out[key]["contract_exists"] = contract is not None
            out[key]["pr_exists"] = pr is not None
            out[key]["pr_fields"] = list(pr.__table__.columns.keys()) if pr else None
            out[key]["po_exists"] = po is not None
            out[key]["wp_link_count"] = len(wp_links)
            out[key]["component_count"] = comp_count

        wp_counts = (
            await s.execute(
                select(EquipmentWorkPackage.equipment_id, func.count(EquipmentWorkPackage.work_package_id))
                .join(Equipment, EquipmentWorkPackage.equipment_id == Equipment.id)
                .where(Equipment.project_context_id == PCID)
                .group_by(EquipmentWorkPackage.equipment_id)
                .having(func.count(EquipmentWorkPackage.work_package_id) > 1)
            )
        ).all()
        out["multi_wp_equipment_count"] = len(wp_counts)
        if wp_counts:
            sample_id = wp_counts[0][0]
            eq = await s.get(Equipment, sample_id)
            links = (
                await s.execute(select(EquipmentWorkPackage).where(EquipmentWorkPackage.equipment_id == sample_id))
            ).scalars().all()
            codes = []
            for link in links:
                wp = await s.get(WorkPackage, link.work_package_id)
                codes.append(wp.code)
            out["multi_wp_sample"] = {"equipment_id": sample_id, "name": eq.name, "codes": sorted(codes)}

        users = (await s.execute(select(User).where(User.email.like("%inpasa.com.br")))).scalars().all()
        out["responsibles"] = []
        for u in users:
            access = (await s.execute(select(UserUnitAccess).where(UserUnitAccess.user_id == u.id))).scalars().all()
            eq_count = (
                await s.execute(select(func.count()).select_from(Equipment).where(Equipment.responsible_user_id == u.id))
            ).scalar_one()
            out["responsibles"].append(
                {
                    "name": u.name,
                    "email": u.email,
                    "role": str(u.role),
                    "active": u.active,
                    "unit_access_count": len(access),
                    "equipment_count": eq_count,
                }
            )

        try:
            from app.models.supplier import EquipmentSupplier, Supplier

            out["suppliers_catalog_count"] = (
                await s.execute(select(func.count()).select_from(Supplier))
            ).scalar_one()
            out["equipment_supplier_links_c2"] = (
                await s.execute(
                    select(func.count())
                    .select_from(EquipmentSupplier)
                    .join(Equipment, EquipmentSupplier.equipment_id == Equipment.id)
                    .where(Equipment.project_context_id == PCID)
                )
            ).scalar_one()
        except Exception as exc:  # noqa: BLE001
            out["suppliers_error"] = str(exc)

        audit_actions = (
            await s.execute(select(AuditLog.action, func.count(AuditLog.id)).group_by(AuditLog.action))
        ).all()
        out["audit_actions"] = dict(audit_actions)

        out["workflow_transitions_c2"] = (
            await s.execute(
                select(func.count())
                .select_from(WorkflowTransition)
                .join(Equipment, WorkflowTransition.equipment_id == Equipment.id)
                .where(Equipment.project_context_id == PCID)
            )
        ).scalar_one()

        comp = (await s.execute(select(EquipmentComponent).limit(1))).scalars().first()
        if comp:
            out["component_sample"] = {
                "name": comp.name,
                "tag": comp.tag,
                "startup_at": str(comp.startup_at),
                "sector": comp.sector,
                "lead_time_days": comp.lead_time_days,
                "pre_start_days": comp.pre_start_days,
                "contract_delivery_at": str(comp.contract_delivery_at),
                "freight_days": comp.freight_days,
            }

        # componente com startup diferente do equipamento (prova de independência)
        divergent = (
            await s.execute(
                select(EquipmentComponent, Equipment.startup_at)
                .join(Equipment, EquipmentComponent.equipment_id == Equipment.id)
                .where(
                    Equipment.project_context_id == PCID,
                    EquipmentComponent.startup_at.is_not(None),
                    Equipment.startup_at.is_not(None),
                    EquipmentComponent.startup_at != Equipment.startup_at,
                )
                .limit(1)
            )
        ).first()
        out["component_startup_diverges_from_equipment"] = divergent is not None
        if divergent:
            comp2, eq_startup = divergent
            out["component_startup_sample"] = {
                "component_startup": str(comp2.startup_at),
                "equipment_startup": str(eq_startup),
            }

        out["equipment_null_area"] = (
            await s.execute(
                select(func.count()).select_from(Equipment).where(Equipment.project_context_id == PCID, Equipment.area_id.is_(None))
            )
        ).scalar_one()
        out["equipment_null_discipline"] = (
            await s.execute(
                select(func.count())
                .select_from(Equipment)
                .where(Equipment.project_context_id == PCID, Equipment.discipline_id.is_(None))
            )
        ).scalar_one()
        out["equipment_null_responsible"] = (
            await s.execute(
                select(func.count())
                .select_from(Equipment)
                .where(Equipment.project_context_id == PCID, Equipment.responsible_user_id.is_(None))
            )
        ).scalar_one()

        # equipamentos com 0 work packages
        no_wp = (
            await s.execute(
                select(func.count())
                .select_from(Equipment)
                .outerjoin(EquipmentWorkPackage, EquipmentWorkPackage.equipment_id == Equipment.id)
                .where(Equipment.project_context_id == PCID, EquipmentWorkPackage.id.is_(None))
            )
        ).scalar_one()
        out["equipment_zero_work_packages"] = no_wp

    with open("../docs/validation/audit_db_result.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2, default=str)
    print("saved")


if __name__ == "__main__":
    asyncio.run(main())
