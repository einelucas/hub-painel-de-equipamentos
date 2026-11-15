/** Contratos da API de cenários (camelCase) e rascunhos editáveis. */
export interface StartupItemInput {
  equipmentId: string | null;
  name: string;
  origin: string | null;
  discipline: string | null;
  supplier: string | null;
  area: string | null;
  responsible: string | null;
  startupAt: string | null;
  suppliesDays: number | null;
  legalDays: number | null;
  manufactureDays: number | null;
  preStartDays: number | null;
}

export interface StartupItem extends StartupItemInput {
  id: string;
  deliveryDeadline: string | null;
  contractDeadline: string | null;
  negotiationDeadline: string | null;
}

export interface StartupMonth {
  month: string;
  negotiations: number;
  contracts: number;
  deliveries: number;
}

export interface StartupSummary {
  equipments: number;
  negotiationsCalculated: number;
  contractsCalculated: number;
  deliveriesCalculated: number;
  firstNegotiation: string | null;
  lastNegotiation: string | null;
  firstDelivery: string | null;
  lastDelivery: string | null;
  averageManufactureDays: number | null;
  averagePreStartDays: number | null;
  monthly: StartupMonth[];
}

export interface StartupScenario {
  id: string;
  projectContextId: string;
  name: string;
  startupAt: string;
  source: string;
  createdAt: string;
  updatedAt: string;
  items: StartupItem[];
  summary: StartupSummary;
}

export interface StartupScenarioList {
  items: StartupScenario[];
}

export type StartupMetric = "negotiations" | "contracts" | "deliveries";
