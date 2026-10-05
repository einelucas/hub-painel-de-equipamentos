/** Contratos da importação de equipamentos do Monday (P1.3). Toda regra fica no backend. */

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

export interface ImportSourceValues {
  responsibles: string[];
  areas: string[];
  disciplines: string[];
  workPackages: string[];
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
  equipments: number;
  components: number;
  warnings: number;
  errors: number;
  unknownFields: string[];
  fragileIdentities: number;
  unknownStatuses: number;
  canProceed: boolean;
  issues: ImportIssue[];
  sourceValues: ImportSourceValues;
}

export type MappingSection = "responsibles" | "areas" | "disciplines" | "workPackages";
export type ImportMapping = Record<MappingSection, Record<string, string>>;

export interface PlanGroup {
  name: string;
  create: number;
  update: number;
  noop: number;
  blocked: number;
}

export interface ImportPlan {
  batchId: string;
  projectContextId: string;
  mappingSha256: string;
  planSha256: string;
  mappingIssues: { code: string; category: string; section: string; message: string; sourceValue: string | null }[];
  groups: PlanGroup[];
  blocked: { group: string; sourceKey: string; label: string; issues: { code: string; message: string }[] }[];
  warnings: { code: string; message: string }[];
  hasBlocked: boolean;
  canApply: boolean;
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
