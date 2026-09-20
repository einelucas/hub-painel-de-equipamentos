"""Arquivo explícito de mapeamento de catálogos Monday -> Hub.

O importador nunca cria usuário, área, disciplina ou Work Package
automaticamente. Este módulo carrega e valida um arquivo JSON que resolve os
valores textuais observados na origem para IDs já existentes no domínio.
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
from app.models.equipment import Area, Discipline, ProjectContext, WorkPackage
from app.models.user import User
from app.modules.monday_import.normalization import canonical_text

IssueCategory = Literal["error", "warning"]


class MappingFileSchema(BaseModel):
    """Schema validado do arquivo JSON de mapeamento."""

    responsibles: dict[str, str] = Field(default_factory=dict)
    areas: dict[str, str] = Field(default_factory=dict)
    disciplines: dict[str, str] = Field(default_factory=dict)
    work_packages: dict[str, str] = Field(default_factory=dict, alias="workPackages")

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
    issues: list[MappingIssue] = field(default_factory=list)

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
            },
            "issues": [issue.to_dict() for issue in self.issues],
        }


def load_mapping_file(path: str | Path) -> MappingFileSchema:
    text = Path(path).read_text(encoding="utf-8")
    return MappingFileSchema.model_validate(json.loads(text))


def mapping_file_sha256(schema: MappingFileSchema) -> str:
    canonical = json.dumps(
        schema.model_dump(by_alias=True), sort_keys=True, ensure_ascii=False
    )
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

    return ValidatedMapping(
        project_context_id=project_context_id,
        sha256=mapping_file_sha256(schema),
        responsibles=resolved_responsibles,
        areas=resolved_areas,
        disciplines=resolved_disciplines,
        work_packages=resolved_work_packages,
        issues=issues,
    )


EMPTY_MAPPING_SCHEMA = MappingFileSchema()
