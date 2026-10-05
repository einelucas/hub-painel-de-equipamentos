"""Contratos HTTP da importação Monday pelo Hub (P1.3)."""

from __future__ import annotations

from pydantic import Field

from app.modules.monday_import.mapping_file import MappingFileSchema
from app.shared.schema import CamelModel


class ImportProfileOut(CamelModel):
    """Só metadados: nunca caminho de arquivo nem o conteúdo do profile."""

    profile_id: str
    version: int
    source_system: str
    description: str


class ImportProfileListOut(CamelModel):
    items: list[ImportProfileOut]


class ImportProfileRef(CamelModel):
    profile_id: str
    version: int
    sha256: str


class ImportIssueOut(CamelModel):
    severity: str
    code: str
    message: str
    row_number: int | None = None
    field: str | None = None


class SourceValuesOut(CamelModel):
    """Valores observados na origem que dependem do MappingFile (catálogos do Hub)."""

    responsibles: list[str]
    areas: list[str]
    disciplines: list[str]
    work_packages: list[str]


class ImportBatchOut(CamelModel):
    batch_id: str
    already_staged: bool
    status: str
    project_context_id: str
    file_name: str
    file_sha256: str
    board_title: str | None
    sheet_name: str
    profile: ImportProfileRef | None
    equipments: int
    components: int
    warnings: int
    errors: int
    unknown_fields: list[str]
    fragile_identities: int
    unknown_statuses: int
    # Erros do staging impedem avançar para o mapping/plan.
    can_proceed: bool
    issues: list[ImportIssueOut]
    source_values: SourceValuesOut


# --- Checkpoint B: mapping + plan ------------------------------------------------------


class ImportPlanIn(CamelModel):
    """Mapping interativo: valores da origem -> IDs existentes no Hub.

    Mesmo contrato do MappingFile do motor (responsibles, areas, disciplines,
    workPackages). Nunca cria User/Area/Discipline/WorkPackage.
    """

    mapping: MappingFileSchema = Field(default_factory=MappingFileSchema)


class MappingIssueOut(CamelModel):
    code: str
    category: str
    section: str
    message: str
    source_value: str | None = None


class PlanGroupOut(CamelModel):
    name: str
    create: int
    update: int
    noop: int
    blocked: int


class PlanIssueOut(CamelModel):
    code: str
    message: str


class PlanBlockedOut(CamelModel):
    group: str
    source_key: str
    label: str
    issues: list[PlanIssueOut]


class ImportPlanOut(CamelModel):
    batch_id: str
    project_context_id: str
    mapping_sha256: str
    plan_sha256: str
    mapping_issues: list[MappingIssueOut]
    groups: list[PlanGroupOut]
    blocked: list[PlanBlockedOut]
    warnings: list[PlanIssueOut]
    has_blocked: bool
    # Só aplica sem mapping inválido e sem nenhum item BLOCKED.
    can_apply: bool


# --- Checkpoint D: apply + reconciliation ----------------------------------------------


class ImportApplyIn(CamelModel):
    """O backend reconstrói o plano com este mapping e só aplica se o hash bater."""

    mapping: MappingFileSchema = Field(default_factory=MappingFileSchema)
    plan_sha256: str = Field(min_length=64, max_length=64)


class ImportDivergenceOut(CamelModel):
    equipment: str
    field: str
    hub_value: str | None
    source_value: str | None


class ImportReconciliationOut(CamelModel):
    equipments_compared: int
    components_compared: int
    mismatches: int
    pending_mapping: int
    divergences: list[ImportDivergenceOut]


class ImportApplyOut(CamelModel):
    migration_run_id: str
    status: str
    created: int
    updated: int
    unchanged: int
    reconciliation: ImportReconciliationOut
    # Divergência nunca é reportada como sucesso simples.
    has_divergences: bool
