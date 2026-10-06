"""Arquivo explícito de mapeamento de catálogos Monday -> Hub.

Carrega e valida um arquivo JSON que resolve valores textuais da origem para IDs
já existentes no domínio. O importador nunca cria usuário ou fornecedor. EAP,
disciplina e Work Package podem ser criados pelo plan/apply quando há evidência
suficiente (ver `catalog_evidence`); `catalogEvidence` neste arquivo é a
evidência manual, usada só como fallback. A seção legada `suppliers` continua
aceita no schema por compatibilidade, mas não cria nem vincula Supplier.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.scope import user_can_access_unit
from app.domain.eap import EQUIPMENT_EAP_LEVELS
from app.models.equipment import Area, Discipline, EapNode, ProjectContext, WorkPackage
from app.models.supplier import Supplier
from app.models.user import User
from app.modules.monday_import.normalization import canonical_text

IssueCategory = Literal["error", "warning"]


class _EvidenceModel(BaseModel):
    model_config = {"populate_by_name": True, "extra": "forbid"}


class DisciplineEvidenceIn(_EvidenceModel):
    code: str = Field(min_length=1, max_length=40)
    name: str | None = Field(default=None, max_length=160)


class WorkPackageEvidenceIn(_EvidenceModel):
    name: str = Field(min_length=1, max_length=160)


class EapEvidenceIn(_EvidenceModel):
    name: str = Field(min_length=1, max_length=160)


class SupplierEvidenceIn(_EvidenceModel):
    legal_name: str = Field(min_length=1, max_length=200, alias="legalName")
    trade_name: str | None = Field(default=None, max_length=200, alias="tradeName")
    tax_id: str | None = Field(default=None, max_length=32, alias="taxId")


class CatalogEvidenceIn(_EvidenceModel):
    """Evidência manual (FALLBACK) para criar catálogos que Monday/LGE não comprovam.

    disciplines: valor da origem → sigla (e nome opcional)
    workPackages: código do WP na origem → nome
    eapProcesses: código canônico de PROCESS → nome
    suppliers: código corporativo → dados do fornecedor
    """

    disciplines: dict[str, DisciplineEvidenceIn] = Field(default_factory=dict)
    work_packages: dict[str, WorkPackageEvidenceIn] = Field(default_factory=dict, alias="workPackages")
    eap_processes: dict[str, EapEvidenceIn] = Field(default_factory=dict, alias="eapProcesses")
    suppliers: dict[str, SupplierEvidenceIn] = Field(default_factory=dict)

    def is_empty(self) -> bool:
        return not (self.disciplines or self.work_packages or self.eap_processes or self.suppliers)


class SupplierSelectionIn(_EvidenceModel):
    """Decisão humana por equipamento. Ausência significa apenas sugestão."""

    action: Literal["USE", "NONE"]
    supplier_id: str | None = Field(default=None, alias="supplierId")

    @model_validator(mode="after")
    def validate_action(self) -> SupplierSelectionIn:
        if self.action == "USE" and not self.supplier_id:
            raise ValueError("supplierId é obrigatório para USE")
        if self.action == "NONE" and self.supplier_id is not None:
            raise ValueError("supplierId deve ficar vazio para NONE")
        return self


class MappingFileSchema(BaseModel):
    """Schema validado do arquivo JSON de mapeamento."""

    responsibles: dict[str, str] = Field(default_factory=dict)
    # LEGADO: Area deixou de ser destino da localização (P1.3.1). Ainda é aceito e
    # validado para não quebrar arquivos antigos, mas o plan não grava `area_id`.
    areas: dict[str, str] = Field(default_factory=dict)
    disciplines: dict[str, str] = Field(default_factory=dict)
    work_packages: dict[str, str] = Field(default_factory=dict, alias="workPackages")
    # valor de localização da origem -> EapNode escolhido explicitamente pelo usuário
    eap_nodes: dict[str, str] = Field(default_factory=dict, alias="eapNodes")
    supplier_selections: dict[str, SupplierSelectionIn] = Field(
        default_factory=dict, alias="supplierSelections"
    )
    # Opcional e retrocompatível: ausente/vazio não altera o mappingSha256.
    catalog_evidence: CatalogEvidenceIn = Field(default_factory=CatalogEvidenceIn, alias="catalogEvidence")

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def _no_blank_keys_or_values(self) -> MappingFileSchema:
        for label, mapping in self._sections():
            for source, target in mapping.items():
                if not source.strip():
                    raise ValueError(f"{label}: chave de origem em branco")
                if not target.strip():
                    raise ValueError(f"{label}: valor de destino em branco para '{source}'")
        return self

    def _sections(self) -> list[tuple[str, dict[str, str]]]:
        return [
            ("responsibles", self.responsibles),
            ("areas", self.areas),
            ("disciplines", self.disciplines),
            ("workPackages", self.work_packages),
            ("eapNodes", self.eap_nodes),
        ]


@dataclass(slots=True, frozen=True)
class MappingIssue:
    code: str
    category: IssueCategory
    section: str
    message: str
    source_value: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "code": self.code,
            "category": self.category,
            "section": self.section,
            "message": self.message,
            "sourceValue": self.source_value,
        }


@dataclass(slots=True, frozen=True)
class ValidatedMapping:
    """Mapeamento pronto para uso pelo `plan`: valores de origem já resolvidos
    e validados para IDs existentes, ativos e no escopo correto."""

    project_context_id: str
    sha256: str
    responsibles: dict[str, str] = field(default_factory=dict)
    areas: dict[str, str] = field(default_factory=dict)
    disciplines: dict[str, str] = field(default_factory=dict)
    work_packages: dict[str, str] = field(default_factory=dict)
    eap_nodes: dict[str, str] = field(default_factory=dict)
    supplier_selections: dict[str, SupplierSelectionIn] = field(default_factory=dict)
    issues: list[MappingIssue] = field(default_factory=list)
    # Evidência manual (fallback) para criar catálogos; já validada em formato.
    catalog_evidence: CatalogEvidenceIn = field(default_factory=CatalogEvidenceIn)

    @property
    def has_errors(self) -> bool:
        return any(issue.category == "error" for issue in self.issues)

    def resolve_responsible(self, source_value: str | None) -> str | None:
        return None if source_value is None else self.responsibles.get(canonical_text(source_value))

    def resolve_area(self, source_value: str | None) -> str | None:
        return None if source_value is None else self.areas.get(canonical_text(source_value))

    def resolve_discipline(self, source_value: str | None) -> str | None:
        return None if source_value is None else self.disciplines.get(canonical_text(source_value))

    def resolve_work_package(self, source_value: str | None) -> str | None:
        return None if source_value is None else self.work_packages.get(canonical_text(source_value))

    def to_summary(self) -> dict[str, object]:
        return {
            "mappingSha256": self.sha256,
            "counts": {
                "responsibles": len(self.responsibles),
                "areas": len(self.areas),
                "disciplines": len(self.disciplines),
                "workPackages": len(self.work_packages),
                "eapNodes": len(self.eap_nodes),
                "supplierSelections": len(self.supplier_selections),
                "catalogEvidence": {
                    "disciplines": len(self.catalog_evidence.disciplines),
                    "workPackages": len(self.catalog_evidence.work_packages),
                    "eapProcesses": len(self.catalog_evidence.eap_processes),
                    "suppliers": len(self.catalog_evidence.suppliers),
                },
            },
            "issues": [issue.to_dict() for issue in self.issues],
        }


def load_mapping_file(path: str | Path) -> MappingFileSchema:
    text = Path(path).read_text(encoding="utf-8")
    return MappingFileSchema.model_validate(json.loads(text))


def mapping_file_sha256(schema: MappingFileSchema) -> str:
    dumped = schema.model_dump(by_alias=True)
    if not schema.supplier_selections:
        # Compatibilidade com mappings anteriores à revisão explícita.
        dumped.pop("supplierSelections", None)
    if schema.catalog_evidence.is_empty():
        # Mantém o hash de mappings anteriores à evidência manual.
        dumped.pop("catalogEvidence", None)
    canonical = json.dumps(dumped, sort_keys=True, ensure_ascii=False)
    return sha256(canonical.encode("utf-8")).hexdigest()


def _find_duplicate_canonical_keys(label: str, mapping: dict[str, str]) -> list[MappingIssue]:
    """Duas chaves de origem diferentes que colidem depois de canonicalizadas
    são ambíguas: o `plan` faz o lookup pela forma canônica."""
    seen: dict[str, str] = {}
    issues: list[MappingIssue] = []
    for source in mapping:
        key = canonical_text(source)
        if key in seen and seen[key] != source:
            issues.append(
                MappingIssue(
                    code="duplicate_source_value",
                    category="error",
                    section=label,
                    message=f"'{source}' colide com '{seen[key]}' após normalização",
                    source_value=source,
                )
            )
        else:
            seen[key] = source
    return issues


async def validate_mapping(
    session: AsyncSession, schema: MappingFileSchema, *, project_context_id: str
) -> ValidatedMapping:
    """Resolve cada valor de origem para um ID existente, ativo e no escopo
    correto. Nada é criado; entradas inválidas viram issue de erro e ficam de
    fora do mapeamento resolvido (o `plan` trata a ausência como BLOCKED)."""
    context = await session.get(ProjectContext, project_context_id)
    if context is None:
        raise ValueError("project_context não encontrado")

    issues: list[MappingIssue] = []
    for label, mapping in schema._sections():
        issues.extend(_find_duplicate_canonical_keys(label, mapping))

    resolved_responsibles: dict[str, str] = {}
    for source, user_id in schema.responsibles.items():
        user = await session.get(User, user_id)
        if user is None:
            issues.append(
                MappingIssue("unknown_user", "error", "responsibles", f"usuário {user_id} não existe", source)
            )
        elif not user.active:
            issues.append(
                MappingIssue(
                    "inactive_user", "error", "responsibles", f"usuário {user_id} está inativo", source
                )
            )
        elif not await user_can_access_unit(session, user_id, context.unit_id):
            issues.append(
                MappingIssue(
                    "user_without_unit_access",
                    "error",
                    "responsibles",
                    f"usuário {user_id} não tem acesso à unidade do contexto",
                    source,
                )
            )
        else:
            resolved_responsibles[canonical_text(source)] = user_id

    resolved_areas: dict[str, str] = {}
    for source, area_id in schema.areas.items():
        area = await session.get(Area, area_id)
        if area is None or not area.active:
            issues.append(
                MappingIssue("unknown_area", "error", "areas", f"área {area_id} inválida ou inativa", source)
            )
        elif area.unit_id != context.unit_id:
            issues.append(
                MappingIssue(
                    "area_wrong_unit", "error", "areas", f"área {area_id} pertence a outra unidade", source
                )
            )
        else:
            resolved_areas[canonical_text(source)] = area_id
    if schema.areas:
        issues.append(
            MappingIssue(
                "legacy_area_mapping_ignored",
                "warning",
                "areas",
                "Área é legado: a localização dos equipamentos agora é a EAP (eapNodes).",
            )
        )

    resolved_eap_nodes: dict[str, str] = {}
    eligible_levels = {level.value for level in EQUIPMENT_EAP_LEVELS}
    for source, eap_node_id in schema.eap_nodes.items():
        node = await session.get(EapNode, eap_node_id)
        if node is None or not node.active or node.level not in eligible_levels:
            issues.append(
                MappingIssue(
                    "unknown_eap_node",
                    "error",
                    "eapNodes",
                    f"EAP {eap_node_id} inválida, inativa ou de nível não permitido",
                    source,
                )
            )
        else:
            resolved_eap_nodes[canonical_text(source)] = eap_node_id

    resolved_disciplines: dict[str, str] = {}
    for source, discipline_id in schema.disciplines.items():
        discipline = await session.get(Discipline, discipline_id)
        if discipline is None or not discipline.active:
            issues.append(
                MappingIssue(
                    "unknown_discipline",
                    "error",
                    "disciplines",
                    f"disciplina {discipline_id} inválida ou inativa",
                    source,
                )
            )
        else:
            resolved_disciplines[canonical_text(source)] = discipline_id

    resolved_work_packages: dict[str, str] = {}
    for source, work_package_id in schema.work_packages.items():
        work_package = await session.get(WorkPackage, work_package_id)
        if work_package is None or not work_package.active:
            issues.append(
                MappingIssue(
                    "unknown_work_package",
                    "error",
                    "workPackages",
                    f"work package {work_package_id} inválido ou inativo",
                    source,
                )
            )
        elif work_package.project_context_id != project_context_id:
            issues.append(
                MappingIssue(
                    "work_package_wrong_context",
                    "error",
                    "workPackages",
                    f"work package {work_package_id} pertence a outro contexto",
                    source,
                )
            )
        else:
            resolved_work_packages[canonical_text(source)] = work_package_id

    resolved_supplier_selections: dict[str, SupplierSelectionIn] = {}
    for source_key, selection in schema.supplier_selections.items():
        if not source_key.strip():
            issues.append(
                MappingIssue(
                    "blank_supplier_source_key",
                    "error",
                    "supplierSelections",
                    "Identidade do equipamento não pode ficar vazia",
                )
            )
            continue
        if selection.action == "USE":
            supplier = await session.get(Supplier, selection.supplier_id)
            if supplier is None or not supplier.active:
                issues.append(
                    MappingIssue(
                        "unknown_supplier",
                        "error",
                        "supplierSelections",
                        f"fornecedor {selection.supplier_id} inválido ou inativo",
                        source_key,
                    )
                )
                continue
        resolved_supplier_selections[source_key] = selection

    return ValidatedMapping(
        project_context_id=project_context_id,
        sha256=mapping_file_sha256(schema),
        responsibles=resolved_responsibles,
        areas=resolved_areas,
        disciplines=resolved_disciplines,
        work_packages=resolved_work_packages,
        eap_nodes=resolved_eap_nodes,
        supplier_selections=resolved_supplier_selections,
        issues=issues,
        catalog_evidence=schema.catalog_evidence,
    )


EMPTY_MAPPING_SCHEMA = MappingFileSchema()
