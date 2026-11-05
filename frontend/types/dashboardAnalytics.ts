/** Séries analíticas do Dashboard Geral. Campos numéricos são agregados pelo FastAPI. */
export interface AnalyticsDistributionItem {
  id: string | null;
  label: string;
  count: number;
}

export interface AnalyticsEapStage {
  eapId: string | null;
  label: string;
  counts: number[]; // nove estágios 0..8, na ordem canônica
  total: number;
}

export interface AnalyticsEapRisk {
  eapId: string | null;
  label: string;
  critical: number;
  warning: number;
  safe: number;
  notCalculable: number;
}

export interface AnalyticsDeliveryWindow {
  equipmentId: string;
  equipmentName: string;
  startAt: string; // YYYY-MM-DD
  endAt: string;
}

export interface AnalyticsStartup {
  equipmentId: string;
  equipmentName: string;
  startupAt: string;
}

export interface AnalyticsMonthlyAmount {
  month: string; // YYYY-MM
  amount: string | number;
  orders: number;
  informedOrders: number;
}

export interface AnalyticsMonthlyCount {
  month: string;
  count: number;
}

export interface AnalyticsStageCapex {
  stage: number;
  label: string;
  amount: string | number;
  informed: number;
}

export interface DashboardAnalytics {
  byDiscipline: AnalyticsDistributionItem[];
  byProject: AnalyticsDistributionItem[];
  byEapStage: AnalyticsEapStage[];
  riskByEap: AnalyticsEapRisk[];
  deliveryWindows: AnalyticsDeliveryWindow[];
  upcomingStartups: AnalyticsStartup[];
  incompleteDeliveryWindows: number;
  monthlyPurchaseOrders: AnalyticsMonthlyAmount[];
  purchaseOrdersWithoutDate: number;
  purchaseOrdersWithoutAmount: number;
  capexByStage: AnalyticsStageCapex[];
  monthlyWorkflowMovements: AnalyticsMonthlyCount[];
}
