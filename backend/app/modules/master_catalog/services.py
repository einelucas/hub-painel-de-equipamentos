"""Serviços do Catálogo Mestre — somente modelos, sem metadados operacionais."""
# ruff: noqa: I001  # Imports de classes de domínio agrupados

from __future__ import annotations

import json
import unicodedata

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import CurrentUser
from app.core.errors import ConflictError, DomainError, NotFoundError
from app.core.scope import assert_unit_allowed
from app.models.equipment import Equipment, EquipmentComponent, ProjectContext, Unit
from app.models.master_catalog import (
    MasterArea,
    MasterComponentOption,
    MasterEquipment,
    MasterEquipmentArea,
    MasterProjectCreation,
)
from app.modules.master_catalog.schemas import (
    MasterAreaOut,
    MasterCatalogOut,
    MasterCatalogSeedIn,
    MasterCatalogSeedOut,
    MasterComponentOut,
    MasterEquipmentOut,
    MasterProjectCreateIn,
    MasterProjectCreatedOut,
)
from app.shared.audit import record_audit


def key_for(value: str) -> str:
    raw = unicodedata.normalize("NFKD", value.strip())
    return " ".join("".join(c for c in raw if not unicodedata.combining(c)).casefold().split())


def _equipment_query():
    return select(MasterEquipment).options(
        selectinload(MasterEquipment.links),
        selectinload(MasterEquipment.components),
    ).order_by(MasterEquipment.name)


async def catalog(session: AsyncSession, *, include_inactive: bool = False) -> MasterCatalogOut:
    areas = list((await session.scalars(select(MasterArea).order_by(MasterArea.name))).all())
    equipment = list((await session.scalars(_equipment_query())).all())
    return MasterCatalogOut(
        areas=[
            MasterAreaOut.model_validate(area)
            for area in areas if include_inactive or area.active
        ],
        equipments=[
            MasterEquipmentOut(
                id=item.id, name=item.name,
                area_ids=[link.area_id for link in item.links],
                review_flags=json.loads(item.review_flags or "[]"),
                active=item.active,
                components=[
                    MasterComponentOut.model_validate(component)
                    for component in sorted(item.components, key=lambda x: x.name)
                    if include_inactive or component.active
                ],
            )
            for item in equipment if include_inactive or item.active
        ],
    )


def _check_seed(seed: MasterCatalogSeedIn) -> None:
    if seed.schema_version != "2.1":
        raise DomainError("Seed deve estar na versão 2.1")
    area_ids = [x.get("id") for x in seed.areas]
    eq_ids = [x.get("id") for x in seed.equipments]
    component_ids = [x.get("id") for x in seed.component_options]
    for ids in (area_ids, eq_ids, component_ids):
        if any(not isinstance(x, str) or not x for x in ids) or len(set(ids)) != len(ids):
            raise DomainError("IDs inválidos ou repetidos no seed")
    if len({key_for(x.get("name", "")) for x in seed.areas}) != len(seed.areas):
        raise DomainError("Áreas duplicadas no seed")
    if len({key_for(x.get("name", "")) for x in seed.equipments}) != len(seed.equipments):
        raise DomainError("Equipamentos duplicados no seed")
    area_set, eq_set, cmp_set = set(area_ids), set(eq_ids), set(component_ids)
    by_equipment: set[tuple[str, str]] = set()
    for item in seed.equipments:
        if not set(item.get("area_ids", [])) <= area_set:
            raise DomainError("Equipamento referencia área inexistente")
        if not set(item.get("component_option_ids", [])) <= cmp_set:
            raise DomainError("Equipamento referencia componente inexistente")
        if any(k in item for k in ("tag", "source", "source_project", "project_context_id")):
            raise DomainError("Seed mestre contém vínculo operacional proibido")
    for item in seed.component_options:
        parent = item.get("equipment_id")
        if parent not in eq_set:
            raise DomainError("Componente referencia equipamento inexistente")
        if any(k in item for k in ("tag", "source", "source_project", "project_context_id")):
            raise DomainError("Componente mestre contém vínculo operacional proibido")
        identity = (parent, key_for(item.get("name", "")))
        if identity in by_equipment:
            raise DomainError("Componente duplicado em equipamento mestre")
        by_equipment.add(identity)
    for item in seed.equipments:
        actual = {x["id"] for x in seed.component_options if x["equipment_id"] == item["id"]}
        if actual != set(item.get("component_option_ids", [])):
            raise DomainError("Relações equipamento-componente inconsistentes")


async def seed_catalog(
    session: AsyncSession, seed: MasterCatalogSeedIn, actor: CurrentUser,
    *, dry_run: bool = True,
) -> MasterCatalogSeedOut:
    _check_seed(seed)
    area_by_id = {x.id: x for x in (await session.scalars(select(MasterArea))).all()}
    eq_by_id = {x.id: x for x in (await session.scalars(select(MasterEquipment))).all()}
    comp_by_id = {x.id: x for x in (await session.scalars(select(MasterComponentOption))).all()}
    areas_new = sum(x["id"] not in area_by_id for x in seed.areas)
    eq_new = sum(x["id"] not in eq_by_id for x in seed.equipments)
    components_new = sum(x["id"] not in comp_by_id for x in seed.component_options)
    existing = (
        len(seed.areas) - areas_new
        + len(seed.equipments) - eq_new
        + len(seed.component_options) - components_new
    )
    result = MasterCatalogSeedOut(
        areas_new=areas_new, equipments_new=eq_new, components_new=components_new,
        existing=existing, dry_run=dry_run,
    )
    # Evita sobrescrever alterações administrativas após primeira carga.
    for source, known, _model in (
        (seed.areas, area_by_id, MasterArea),
        (seed.equipments, eq_by_id, MasterEquipment),
        (seed.component_options, comp_by_id, MasterComponentOption),
    ):
        for item in source:
            stored = known.get(item["id"])
            if stored is not None and key_for(stored.name) != key_for(item["name"]):
                raise ConflictError("ID de seed já existe com nome diferente: " + item["id"])
    if dry_run:
        return result
    for item in seed.areas:
        if item["id"] not in area_by_id:
            session.add(MasterArea(
                id=item["id"], name=item["name"], normalized_name=key_for(item["name"]),
                is_unassigned=bool(item.get("is_unassigned_category")),
            ))
    for item in seed.equipments:
        if item["id"] not in eq_by_id:
            session.add(MasterEquipment(
                id=item["id"], name=item["name"], normalized_name=key_for(item["name"]),
                review_flags=json.dumps(item.get("review_flags", []), ensure_ascii=False),
            ))
    await session.flush()
    existing_links = set((await session.execute(
        select(MasterEquipmentArea.equipment_id, MasterEquipmentArea.area_id)
    )).all())
    for item in seed.equipments:
        for area_id in item.get("area_ids", []):
            pair = (item["id"], area_id)
            if pair not in existing_links and item["id"] not in eq_by_id:
                session.add(MasterEquipmentArea(equipment_id=item["id"], area_id=area_id))
    for item in seed.component_options:
        if item["id"] not in comp_by_id:
            session.add(MasterComponentOption(
                id=item["id"], equipment_id=item["equipment_id"],
                name=item["name"], normalized_name=key_for(item["name"]),
                requires_quantity_review=bool(item.get("requires_quantity_review")),
                requires_name_review=bool(item.get("requires_name_review")),
            ))
    await record_audit(
        session, user_id=actor.id, action="master_catalog.seed",
        entity="MasterEquipment", new_data=result.model_dump(),
    )
    await session.commit()
    return result


async def create_project_from_master(
    session: AsyncSession, body: MasterProjectCreateIn, actor: CurrentUser,
) -> MasterProjectCreatedOut:
    existing = await session.get(MasterProjectCreation, body.request_id)
    if existing is not None:
        if existing.actor_id != actor.id:
            raise ConflictError("Identificador de requisição já utilizado")
        context = await session.get(ProjectContext, existing.project_context_id)
        if context is None:
            raise NotFoundError("Obra anteriormente criada não encontrada")
        await assert_unit_allowed(session, actor, context.unit_id)
        return MasterProjectCreatedOut(
            project_context_id=context.id, equipments_created=0, components_created=0,
            already_created=True,
        )
    await assert_unit_allowed(session, actor, body.unit_id)
    unit = await session.get(Unit, body.unit_id)
    if unit is None or not unit.active:
        raise NotFoundError("Unidade não encontrada ou inativa")
    if body.code and await session.scalar(
        select(ProjectContext.id).where(
            ProjectContext.unit_id == body.unit_id, ProjectContext.code == body.code
        )
    ):
        raise ConflictError("Já existe obra com esse código na unidade")
    ids = [item.equipment_id for item in body.selections]
    masters = (
        list((await session.scalars(_equipment_query().where(MasterEquipment.id.in_(ids)))).all())
        if ids else []
    )
    master_by_id = {item.id: item for item in masters}
    if len(masters) != len(ids):
        raise NotFoundError("Equipamento do catálogo não encontrado")
    for selection in body.selections:
        master = master_by_id[selection.equipment_id]
        if not master.active:
            raise DomainError("Equipamento mestre inativo: " + master.name)
        options = {option.id: option for option in master.components if option.active}
        if any(cid not in options for cid in selection.component_ids):
            raise DomainError("Componente inválido ou inativo em: " + master.name)
    context = ProjectContext(unit_id=body.unit_id, name=body.name.strip(), code=body.code or None)
    session.add(context)
    await session.flush()
    count = 0
    for selection in body.selections:
        master = master_by_id[selection.equipment_id]
        equipment = Equipment(project_context_id=context.id, name=master.name, current_stage=0)
        session.add(equipment)
        await session.flush()
        options = {option.id: option for option in master.components}
        for component_id in selection.component_ids:
            session.add(EquipmentComponent(
                equipment_id=equipment.id, name=options[component_id].name,
                tag=None, startup_at=None, sector=None, lead_time_days=None,
                pre_start_days=None, contract_delivery_at=None, freight_days=None,
            ))
            count += 1
    session.add(MasterProjectCreation(
        request_id=body.request_id, actor_id=actor.id, project_context_id=context.id
    ))
    await record_audit(
        session, user_id=actor.id, action="master_catalog.create_project",
        entity="ProjectContext", entity_id=context.id,
        new_data={"unitId": body.unit_id, "name": context.name,
                  "equipmentsCreated": len(ids), "componentsCreated": count},
    )
    await session.commit()
    return MasterProjectCreatedOut(
        project_context_id=context.id, equipments_created=len(ids), components_created=count,
    )


async def create_area(session: AsyncSession, *, name: str, actor: CurrentUser) -> MasterArea:
    normalized = key_for(name)
    if not normalized:
        raise DomainError("Informe o nome da área")
    if await session.scalar(select(MasterArea.id).where(MasterArea.normalized_name == normalized)):
        raise ConflictError("Área já cadastrada")
    item = MasterArea(name=name.strip(), normalized_name=normalized)
    session.add(item)
    await session.flush()
    await record_audit(session, user_id=actor.id, action="master_catalog.area.create",
                       entity="MasterArea", entity_id=item.id, new_data={"name": item.name})
    await session.commit()
    await session.refresh(item)
    return item


async def create_master_equipment(
    session: AsyncSession, *, name: str, area_ids: list[str], actor: CurrentUser,
) -> MasterEquipment:
    normalized = key_for(name)
    if not normalized:
        raise DomainError("Informe o nome do equipamento")
    if await session.scalar(select(MasterEquipment.id).where(MasterEquipment.normalized_name == normalized)):
        raise ConflictError("Equipamento mestre já cadastrado")
    item = MasterEquipment(name=name.strip(), normalized_name=normalized, review_flags="[]")
    session.add(item)
    await session.flush()
    await assign_areas(session, equipment_id=item.id, area_ids=area_ids, actor=actor, commit=False)
    await record_audit(session, user_id=actor.id, action="master_catalog.equipment.create",
                       entity="MasterEquipment", entity_id=item.id, new_data={"name": item.name})
    await session.commit()
    return item


async def assign_areas(
    session: AsyncSession, *, equipment_id: str, area_ids: list[str],
    actor: CurrentUser, commit: bool = True,
) -> None:
    master = await session.get(MasterEquipment, equipment_id)
    if master is None:
        raise NotFoundError("Equipamento mestre não encontrado")
    if len(area_ids) != len(set(area_ids)):
        raise DomainError("Áreas repetidas")
    areas = (
        list((await session.scalars(select(MasterArea).where(MasterArea.id.in_(area_ids)))).all())
        if area_ids else []
    )
    if len(areas) != len(area_ids) or any(not area.active for area in areas):
        raise DomainError("Área inexistente ou inativa")
    if len(area_ids) > 1 and any(area.is_unassigned for area in areas):
        raise DomainError("Sem área definida não pode ser combinada com áreas reais")
    existing = list((await session.scalars(
        select(MasterEquipmentArea).where(MasterEquipmentArea.equipment_id == equipment_id)
    )).all())
    for link in existing:
        await session.delete(link)
    for area_id in area_ids:
        session.add(MasterEquipmentArea(equipment_id=equipment_id, area_id=area_id))
    await record_audit(
        session, user_id=actor.id, action="master_catalog.areas.assign",
        entity="MasterEquipment", entity_id=equipment_id,
        previous_data={"areaIds": [link.area_id for link in existing]},
        new_data={"areaIds": area_ids},
    )
    if commit:
        await session.commit()


async def create_option(
    session: AsyncSession, *, equipment_id: str, name: str, actor: CurrentUser,
) -> MasterComponentOption:
    if await session.get(MasterEquipment, equipment_id) is None:
        raise NotFoundError("Equipamento mestre não encontrado")
    normalized = key_for(name)
    if not normalized:
        raise DomainError("Informe o nome do componente")
    if await session.scalar(select(MasterComponentOption.id).where(
        MasterComponentOption.equipment_id == equipment_id,
        MasterComponentOption.normalized_name == normalized,
    )):
        raise ConflictError("Componente mestre já cadastrado")
    item = MasterComponentOption(
        equipment_id=equipment_id, name=name.strip(), normalized_name=normalized
    )
    session.add(item)
    await session.flush()
    await record_audit(session, user_id=actor.id, action="master_catalog.component.create",
                       entity="MasterComponentOption", entity_id=item.id, new_data={"name": item.name})
    await session.commit()
    await session.refresh(item)
    return item


async def update_item(
    session: AsyncSession, *, model: type, item_id: str, name: str | None,
    active: bool | None, actor: CurrentUser,
) -> None:
    item = await session.get(model, item_id)
    if item is None:
        raise NotFoundError("Registro do Catálogo Mestre não encontrado")
    before = {"name": item.name, "active": item.active}
    if name is not None:
        normalized = key_for(name)
        if not normalized:
            raise DomainError("Nome obrigatório")
        stmt = select(model.id).where(model.normalized_name == normalized, model.id != item_id)
        if model is MasterComponentOption:
            stmt = stmt.where(model.equipment_id == item.equipment_id)
        if await session.scalar(stmt):
            raise ConflictError("Nome já utilizado")
        item.name, item.normalized_name = name.strip(), normalized
    if active is not None:
        item.active = active
    await record_audit(session, user_id=actor.id, action="master_catalog.update",
                       entity=model.__name__, entity_id=item.id, previous_data=before,
                       new_data={"name": item.name, "active": item.active})
    await session.commit()
