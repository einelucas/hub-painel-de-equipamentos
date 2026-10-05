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

/** RESOLVED: EAP única do catálogo; MULTIPLE: várias (nenhuma escolhida); NONE: sem código; NOT_FOUND: fora do catálogo. */
export type EapLocationStatus = "RESOLVED" | "MULTIPLE" | "NONE" | "NOT_FOUND";

export interface ImportLocationValue {
  value: string;
  status: EapLocationStatus;
  candidates: string[];
  eapNodeId: string | null;
  eapCode: string | null;
  eapName: string | null;
  equipments: number;
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
export type ImportMapping = Record<MappingSection, Record<string, string>>;

export interface PlanGroup {
  name: string;
  create: number;
  update: number;
  noop: number;
  blocked: number;
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
  eap: { resolved: number; multiple: number; none: number; notFound: number };
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

/** Falha de análise de um arquivo do conjunto (os demais seguem analisados). */
export interface ImportFileFailure {
  fileName: string;
  message: string;
}
