/** Contratos da importação de equipamentos do Monday (P1.3 / P1.3.1). Toda regra fica no backend. */

export interface ImportProfile {
  profileId: string;
  version: number;
  sourceSystem: string;
  description: string;
}

export interface ImportIssue {
  severity: "error" | "warning" | string;
  code: string;
  message: string;
  rowNumber: number | null;
  field: string | null;
}

/**
 * RESOLVED: EAP existente no Hub; CREATE: nova, com nome comprovado (criada no apply);
 * CONFLICT: mesmo código com nome diferente no Hub; MULTIPLE: várias (nenhuma escolhida);
 * NONE: sem código; NOT_FOUND/UNRESOLVED: sem dados suficientes (nada é inventado).
 */
export type EapLocationStatus = "RESOLVED" | "CREATE" | "CONFLICT" | "UNRESOLVED" | "MULTIPLE" | "NONE" | "NOT_FOUND";

export interface ImportLocationValue {
  value: string;
  status: EapLocationStatus;
  candidates: string[];
  eapNodeId: string | null;
  eapCode: string | null;
  eapName: string | null;
  equipments: number;
  plannedEapCode?: string | null;
  plannedEapName?: string | null;
  evidenceSource?: string | null;
  issueCode?: string | null;
  issueMessage?: string | null;
}

export interface ImportSourceValues {
  responsibles: string[];
  disciplines: string[];
  workPackages: string[];
  locations: ImportLocationValue[];
}

export interface ImportBatch {
  batchId: string;
  alreadyStaged: boolean;
  status: string;
  projectContextId: string;
  fileName: string;
  fileSha256: string;
  boardTitle: string | null;
  sheetName: string;
  profile: { profileId: string; version: number; sha256: string } | null;
  /** Grupos (fases) presentes no arquivo; fases vazias não aparecem e não são exigidas. */
  groups: string[];
  equipments: number;
  components: number;
  warnings: number;
  errors: number;
  unknownFields: string[];
  fragileIdentities: number;
  unknownStatuses: number;
  operationalStatuses: Record<string, number>;
  canProceed: boolean;
  issues: ImportIssue[];
  sourceValues: ImportSourceValues;
}

export type MappingSection = "responsibles" | "disciplines" | "workPackages" | "eapNodes";
export interface SupplierSelection {
  action: "USE" | "NONE";
  supplierId?: string | null;
}
export type ImportMapping = Record<MappingSection, Record<string, string>> & {
  supplierSelections: Record<string, SupplierSelection>;
};

export interface PlanGroup {
  name: string;
  create: number;
  update: number;
  noop: number;
  blocked: number;
}

/** Decisão de catálogo do plano. EXISTING/CREATE não bloqueiam; CONFLICT bloqueia; UNRESOLVED é pendência. */
export type CatalogAction = "EXISTING" | "CREATE" | "CONFLICT" | "UNRESOLVED";
export type CatalogKind = "eap_node" | "project_eap" | "discipline" | "work_package" | "supplier";

export interface CatalogItem {
  kind: CatalogKind;
  key: string;
  action: CatalogAction;
  label: string;
  evidenceSource: string | null;
  issueCode: string | null;
  message: string | null;
  detail: Record<string, unknown>;
}

export interface ImportPlan {
  batchIds: string[];
  projectContextId: string;
  mappingSha256: string;
  planSha256: string;
  mappingIssues: { code: string; category: string; section: string; message: string; sourceValue: string | null }[];
  groups: PlanGroup[];
  blocked: { group: string; sourceKey: string; label: string; issues: { code: string; message: string }[] }[];
  warnings: { code: string; message: string }[];
  equipmentWarnings?: { group: string; sourceKey: string; label: string; issues: { code: string; message: string }[] }[];
  catalogCounts?: Record<string, Record<string, number>>;
  catalogs?: CatalogItem[];
  responsibles?: { resolved: number; unresolved: number };
  supplierSuggestions?: SupplierSuggestion[];
  eap: { resolved: number; multiple: number; none: number; notFound: number; create?: number; conflict?: number; unresolved?: number };
  hasBlocked: boolean;
  canApply: boolean;
}

export interface SupplierSuggestion {
  sourceKey: string;
  equipmentName: string;
  sourceValue: string | null;
  supplierId: string | null;
  supplierName: string | null;
  corporateCode: string | null;
  confidence: "HIGH" | "MEDIUM" | "LOW" | "NONE";
  evidence: string[];
  requiresRegistration: boolean;
  sourceMatched: boolean;
  selectedAction: "USE" | "NONE" | null;
  selectedSupplierId: string | null;
}

export interface ImportDivergence {
  equipment: string;
  field: string;
  hubValue: string | null;
  sourceValue: string | null;
}

export interface ImportApplyResult {
  migrationRunId: string;
  status: string;
  created: number;
  updated: number;
  unchanged: number;
  reconciliation: {
    equipmentsCompared: number;
    componentsCompared: number;
    mismatches: number;
    pendingMapping: number;
    divergences: ImportDivergence[];
  };
  hasDivergences: boolean;
}

export interface ImportOption {
  id: string;
  label: string;
}

/** Falha de análise de um arquivo do conjunto (os demais seguem analisados). */
export interface ImportFileFailure {
  fileName: string;
  message: string;
}
