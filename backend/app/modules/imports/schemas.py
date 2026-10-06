"""Contratos HTTP da importação Monday pelo Hub (P1.3 / P1.3.1)."""

from __future__ import annotations

from typing import Any, Literal

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


class LocationValueOut(CamelModel):
    """Valor de localização da origem e a EAP que ele resolve SEM intervenção.

    RESOLVED: um único código, existente no Hub. CREATE: código novo com nome
    comprovado (será criado no apply). CONFLICT: código existente com nome diferente.
    MULTIPLE: vários códigos (nenhum escolhido). NONE: sem código EAP. NOT_FOUND /
    UNRESOLVED: código sem dados suficientes (pai ou nome não comprovado)."""

    value: str
    status: Literal["RESOLVED", "CREATE", "CONFLICT", "UNRESOLVED", "MULTIPLE", "NONE", "NOT_FOUND"]
    candidates: list[str]
    eap_node_id: str | None = None
    eap_code: str | None = None
    eap_name: str | None = None
    equipments: int
    # EAP planejada (CREATE): código/nome e a fonte que comprovou o nome.
    planned_eap_code: str | None = None
    planned_eap_name: str | None = None
    evidence_source: str | None = None
    issue_code: str | None = None
    issue_message: str | None = None


class SourceValuesOut(CamelModel):
    """Valores observados na origem que dependem do mapping (catálogos do Hub)."""

    responsibles: list[str]
    disciplines: list[str]
    work_packages: list[str]
    locations: list[LocationValueOut]


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
    # Grupos (fases) presentes no arquivo; fases vazias simplesmente não aparecem.
    groups: list[str]
    equipments: int
    components: int
    warnings: int
    errors: int
    unknown_fields: list[str]
    fragile_identities: int
    unknown_statuses: int
    # Estados operacionais declarados pela origem (ex.: {"STANDBY": 5}).
    operational_statuses: dict[str, int]
    # Erros do staging impedem avançar para o mapping/plan.
    can_proceed: bool
    issues: list[ImportIssueOut]
    source_values: SourceValuesOut


# --- mapping + plan (um conjunto de batches = uma importação) --------------------------

MAX_BATCHES_PER_IMPORT = 50


class ImportPlanIn(CamelModel):
    """Um ou mais batches da MESMA obra (ex.: um XLSX por fase) e um único mapping.

    Mesmo contrato do MappingFile do motor (responsibles, disciplines,
    workPackages, eapNodes). Nunca cria User/EAP/Discipline/WorkPackage.
    """

    batch_ids: list[str] = Field(min_length=1, max_length=MAX_BATCHES_PER_IMPORT)
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


class EapSummaryOut(CamelModel):
    """Equipamentos do plano por situação da localização."""

    resolved: int
    multiple: int
    none: int
    not_found: int
    create: int = 0
    conflict: int = 0
    unresolved: int = 0


class CatalogItemOut(CamelModel):
    """Decisão de catálogo do plano: EXISTING, CREATE, CONFLICT ou UNRESOLVED."""

    kind: Literal["eap_node", "project_eap", "discipline", "work_package", "supplier"]
    key: str
    action: Literal["EXISTING", "CREATE", "CONFLICT", "UNRESOLVED"]
    label: str
    evidence_source: str | None = None
    issue_code: str | None = None
    message: str | None = None
    detail: dict[str, Any] = {}


class ResponsibleSummaryOut(CamelModel):
    resolved: int = 0
    unresolved: int = 0


class SupplierSuggestionOut(CamelModel):
    source_key: str
    equipment_name: str
    source_value: str | None
    supplier_id: str | None
    supplier_name: str | None
    corporate_code: str | None
    confidence: Literal["HIGH", "MEDIUM", "LOW", "NONE"]
    evidence: list[str]
    requires_registration: bool = False
    selected_action: Literal["USE", "NONE"] | None = None
    selected_supplier_id: str | None = None


class ImportPlanOut(CamelModel):
    batch_ids: list[str]
    project_context_id: str
    mapping_sha256: str
    plan_sha256: str
    mapping_issues: list[MappingIssueOut]
    groups: list[PlanGroupOut]
    blocked: list[PlanBlockedOut]
    warnings: list[PlanIssueOut]
    # Pendências de catálogo por equipamento que não bloqueiam (EXISTING/CREATE/UNRESOLVED).
    equipment_warnings: list[PlanBlockedOut] = []
    # Contagem por tipo de catálogo: {"eap_node": {"existing": n, "create": n, ...}, ...}.
    catalog_counts: dict[str, dict[str, int]] = {}
    # Itens de catálogo do plano, para a UI mostrar EXISTENTE/NOVO/CONFLITO/PENDENTE.
    catalogs: list[CatalogItemOut] = []
    responsibles: ResponsibleSummaryOut = ResponsibleSummaryOut()
    supplier_suggestions: list[SupplierSuggestionOut] = []
    eap: EapSummaryOut
    has_blocked: bool
    # Só aplica sem mapping inválido e sem nenhum item BLOCKED.
    can_apply: bool


# --- apply + reconciliation ----------------------------------------------------------


class ImportApplyIn(CamelModel):
    """O backend reconstrói o plano com estes batches e mapping e só aplica se o hash bater."""

    batch_ids: list[str] = Field(min_length=1, max_length=MAX_BATCHES_PER_IMPORT)
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
