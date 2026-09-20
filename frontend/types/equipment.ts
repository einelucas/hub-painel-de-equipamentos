export interface Unit {
  id: string;
  code: string;
  name: string;
  active: boolean;
}

export interface CatalogItem {
  id: string;
  name: string;
  code?: string | null;
  unitId?: string;
  projectContextId?: string;
  active: boolean;
}

export interface NamedRef {
  id: string;
  name: string;
  code?: string | null;
}

export interface UserRef {
  id: string;
  name: string;
  email: string;
}

export interface Equipment {
  id: string;
  name: string;
  origin: string | null;
  startupAt: string | null;
  criticality: string | null;
  currentStage: number;
  stageName: string;
  capexEstimated: string | number | null;
  projectContext: NamedRef;
  unit: NamedRef;
  discipline: NamedRef | null;
  area: NamedRef | null;
  workPackage: NamedRef | null;
  /** Lista completa (0..N); `workPackage` acima continua como referência primária. */
  workPackages: NamedRef[];
  responsibleUser: UserRef | null;
  componentsCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface Pagination {
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}

export interface EquipmentList {
  items: Equipment[];
  pagination: Pagination;
}

export interface StageDistribution {
  stage: number;
  name: string;
  count: number;
}

export interface DashboardTotals {
  equipments: number;
  components: number;
  inProgress: number;
  completed: number;
  purchaseOrders: number;
  purchaseOrderAmount: string | number;
  capexEstimated: string | number;
}

export interface NegotiationSummary {
  open: number;
  completed: number;
  inNegotiation: number;
}

export interface DeadlinesSummary {
  available: boolean;
  reason: string | null;
}

export interface StartupSummary {
  nextAt: string | null;
  daysRemaining: number | null;
  equipmentId: string | null;
  equipmentName: string | null;
}

export interface DashboardSummary {
  context: { unitId: string | null; equipmentId: string | null };
  totals: DashboardTotals;
  workflow: StageDistribution[];
  negotiation: NegotiationSummary;
  deadlines: DeadlinesSummary;
  startup: StartupSummary;
}

export interface EquipmentComponent {
  id: string;
  equipmentId: string;
  name: string;
  tag: string | null;
  /** Startup próprio do subitem; nunca herdado de `equipment.startupAt`. */
  startupAt: string | null;
  sector: string | null;
  leadTimeDays: number | null;
  preStartDays: number | null;
  contractDeliveryAt: string | null;
  freightDays: number | null;
  createdAt: string;
  updatedAt: string;
}

export interface WorkflowTransition {
  id: string;
  fromStage: number;
  fromStageName: string;
  toStage: number;
  toStageName: string;
  reason: string | null;
  actor: UserRef | null;
  occurredAt: string;
}

export interface EquipmentDetail {
  equipment: Equipment;
  components: EquipmentComponent[];
  history: WorkflowTransition[];
}

export interface Negotiation {
  id: string | null;
  equipmentId: string;
  equalized: boolean;
  negotiatedAt: string | null;
}

export interface LegalProcess {
  id: string | null;
  equipmentId: string;
  openedAt: string | null;
  ticketNumber: string | null;
  draftPrepared: boolean;
  draftApproved: boolean;
}

export interface Contract {
  id: string | null;
  equipmentId: string;
  contractNumber: string | null;
  executedAt: string | null;
  deliveryAt: string | null;
}

export type PurchaseRequestKind = "SC" | "OCI";

export interface PurchaseRequest {
  id: string | null;
  equipmentId: string;
  kind: PurchaseRequestKind | null;
  requestNumber: string | null;
  requestedAt: string | null;
}

export interface PurchaseOrder {
  id: string | null;
  equipmentId: string;
  orderNumber: string | null;
  orderedAt: string | null;
  amount: string | number | null;
}

export interface EquipmentProcesses {
  negotiation: Negotiation;
  legal: LegalProcess;
  contract: Contract;
  purchaseRequest: PurchaseRequest;
  purchaseOrder: PurchaseOrder;
}

export interface TransitionRequirement {
  code: string;
  field: string;
  message: string;
  satisfied: boolean;
}

export interface TransitionOption {
  targetStage: number;
  targetStageLabel: string;
  kind: "advance" | "reopen";
  canExecute: boolean;
  requiresReason: boolean;
  blockedReason: string | null;
  requirements: TransitionRequirement[];
  satisfiedRequirements: TransitionRequirement[];
  missingRequirements: TransitionRequirement[];
}

export interface AvailableTransitions {
  currentStage: number;
  currentStageLabel: string;
  transitions: TransitionOption[];
}

export interface HistoryEntry {
  id: string;
  kind: "transition" | "change";
  action: string;
  title: string;
  fromStage: number | null;
  fromStageLabel: string | null;
  toStage: number | null;
  toStageLabel: string | null;
  reason: string | null;
  actor: UserRef | null;
  occurredAt: string;
  previousData: Record<string, unknown> | null;
  newData: Record<string, unknown> | null;
}

export interface HistoryList {
  items: HistoryEntry[];
}

export interface CatalogList<T> {
  items: T[];
}

export interface PendingRequirement {
  code: string;
  field: string;
  message: string;
}

export interface QueueRow {
  equipmentId: string;
  equipmentName: string;
  unit: NamedRef;
  projectContext: NamedRef;
  currentStage: number;
  currentStageName: string;
  nextStage: number | null;
  nextStageName: string | null;
  pending: PendingRequirement[];
}

export interface EngineeringRow extends QueueRow {
  discipline: NamedRef | null;
  area: NamedRef | null;
  workPackage: NamedRef | null;
  responsibleUser: UserRef | null;
  startupAt: string | null;
  criticality: string | null;
  componentsCount: number;
}

export interface LegalRow extends QueueRow {
  responsibleUser: UserRef | null;
  openedAt: string | null;
  ticketNumber: string | null;
  draftPrepared: boolean;
  draftApproved: boolean;
  contractNumber: string | null;
  executedAt: string | null;
  deliveryAt: string | null;
}

export interface ProcurementRow extends QueueRow {
  responsibleUser: UserRef | null;
  primarySupplier: SupplierRef | null;
  kind: PurchaseRequestKind | null;
  requestNumber: string | null;
  requestedAt: string | null;
  orderNumber: string | null;
  orderedAt: string | null;
  amount: string | number | null;
}

export interface QueueList<T> {
  items: T[];
  pagination: Pagination;
}

export interface Responsible {
  id: string;
  name: string;
  email: string;
}

export interface Supplier {
  id: string;
  legalName: string;
  tradeName: string | null;
  taxId: string | null;
  active: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface EquipmentSupplier {
  supplier: Supplier;
  role: string | null;
  isPrimary: boolean;
  createdAt: string;
}

export interface SupplierRef {
  id: string;
  legalName: string;
  tradeName: string | null;
}

export interface UnitRef {
  id: string;
  code: string;
  name: string;
}

export interface UserUnits {
  userId: string;
  role: string;
  allUnits: boolean;
  units: UnitRef[];
}
