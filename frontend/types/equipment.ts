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

/**
 * Prazos e agregações derivados dos componentes (FUN-001). Somente leitura
 * — nunca enviados em create/update, sempre recalculados pelo backend a
 * partir dos campos-base. `null` quando faltar dado-base obrigatório ou
 * não houver componente com o dado preenchido.
 */
/** GAP-014 (Etapa 6C) — enum estável da API; nunca os rótulos/emoji do
 * Monday. `NOT_APPLICABLE` fica pronto para quando o Hub modelar um campo
 * equivalente ao A.Status (CANCELADO/Em Saneamento/Não se Aplica) — nenhum
 * equipamento do C2 usa esse valor hoje. */
export type NegotiationStatus =
  | "NOT_APPLICABLE"
  | "COMPLETED"
  | "OVERDUE"
  | "DUE_TODAY"
  | "CRITICAL"
  | "URGENT"
  | "UPCOMING"
  | "ON_TRACK";

/** Etapa 6C.1 — enum estável da API para "Status Necessidade da Obra";
 * nunca os rótulos/emoji do Monday (ex.: "2. < 30 DIAS 🔥"). */
export type WorkNeedStatus =
  | "CHECK_DELIVERY_FUP"
  | "NEEDED_TODAY"
  | "LT_30_DAYS"
  | "LT_60_DAYS"
  | "LT_90_DAYS"
  | "SAFE";

export interface EquipmentCalculated {
  maxLeadTimeDays: number | null;
  maxPreStartDays: number | null;
  maxFreightDays: number | null;
  deliveryDeadline: string | null;
  contractOrderDeadline: string | null;
  negotiationDeadline: string | null;
  /** Dinâmico (hoje UTC no momento da consulta) — nunca persistido. */
  negotiationDaysRemaining: number | null;
  /** `null` quando não há `negotiationDeadline` nem `negotiatedAt`. */
  negotiationStatus: NegotiationStatus | null;
  /** Dinâmico, mesma data-base de `deliveryDeadline` — nunca persistido. */
  workNeedDaysRemaining: number | null;
  /** `null` quando não há `deliveryDeadline`. */
  workNeedStatus: WorkNeedStatus | null;
}

/** Prazos derivados do componente (FUN-001). Depende só do startup PRÓPRIO
 * do componente — nunca herda `equipment.startupAt`. */
export interface ComponentCalculated {
  deliveryDeadline: string | null;
  availableForCollection: string | null;
  contractOrderDeadline: string | null;
  negotiationDeadline: string | null;
  negotiationDaysRemaining: number | null;
  deliveryMarginDays: number | null;
}

/** Etapa 7A: separação entre FASE do processo (`currentStage`, 0-8) e
 * ESTADO OPERACIONAL — um equipamento pode estar ativo, em Standby,
 * cancelado ou em Saneamento independentemente da fase em que parou. */
export type OperationalStatus = "ACTIVE" | "STANDBY" | "CANCELLED" | "IN_SANITATION";

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
  /** Etapa 7A: um equipamento tem no máximo um fornecedor vinculado. */
  supplier: NamedRef | null;
  operationalStatus: OperationalStatus;
  /** Informado manualmente — nunca somado automaticamente a partir das OCs. */
  projectTotalValue: string | number | null;
  /** Janela de entrega contratual (De/Até) — o fornecedor pode entregar em
   * lotes até a data final. */
  contractualDeliveryStart: string | null;
  contractualDeliveryEnd: string | null;
  /**
   * @deprecated Espelho do FK legado singular (0..1). Não é mais escrito por
   * create/update — use `workPackages` (0..N, fonte oficial). Só existe
   * porque a migração do Monday ainda o preenche quando a origem trazia
   * exatamente 1 Work Package.
   */
  workPackage: NamedRef | null;
  /** Fonte oficial de leitura (0..N), ordenada por `code`. */
  workPackages: NamedRef[];
  responsibleUser: UserRef | null;
  componentsCount: number;
  calculated: EquipmentCalculated;
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

/** Etapa 6C.1 — card "Situação de prazos": distribuição do recorte atual
 * pelo Status Necessidade da Obra oficial (mesma fonte do detalhe do
 * equipamento). `available=false` fica reservado a um cenário técnico. */
export interface DeadlinesSummary {
  available: boolean;
  reason: string | null;
  total: number;
  withDeadline: number;
  withoutDeadline: number;
  checkDeliveryFup: number;
  neededToday: number;
  lt30Days: number;
  lt60Days: number;
  lt90Days: number;
  safe: number;
}

/** Widget do Monday "Status dos prazos de negociação" (GAP-014) — mesmo
 * `NegotiationStatus` calculado no detalhe do equipamento
 * (`calculated.negotiationStatus`), agregado pelo backend nas 5 categorias
 * do widget original: Atrasado/Urgente/Próximo/No prazo/Concluído.
 * `notCalculable` (sem `negotiationDeadline` e sem `negotiatedAt`) nunca é
 * uma 6ª fatia do donut — mesmo padrão de `DeadlinesSummary.withoutDeadline`. */
export interface NegotiationDeadlineStatusSummary {
  total: number;
  overdue: number;
  urgent: number;
  upcoming: number;
  onTrack: number;
  completed: number;
  notCalculable: number;
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
  negotiationDeadlineStatus: NegotiationDeadlineStatusSummary;
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
  calculated: ComponentCalculated;
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

/** Etapa 7A: Contrato deixou de ser 1:1 — um equipamento pode ter vários.
 * Cada contrato tem seu próprio arquivo (opcional até o upload). */
export interface ContractFile {
  fileName: string;
  fileContentType: string | null;
  fileSizeBytes: number | null;
  fileUploadedBy: UserRef | null;
  fileUploadedAt: string | null;
}

export interface Contract {
  id: string;
  equipmentId: string;
  contractNumber: string | null;
  executedAt: string | null;
  file: ContractFile | null;
  createdAt: string;
  updatedAt: string;
}

export type PurchaseRequestKind = "SC" | "OCI";

/** Etapa 7A: SC/OCI deixou de ser 1:1 — um equipamento pode ter várias. */
export interface PurchaseRequest {
  id: string;
  equipmentId: string;
  kind: PurchaseRequestKind | null;
  requestNumber: string | null;
  requestedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

/** Etapa 7A: Ordem de compra deixou de ser 1:1 — um equipamento pode ter
 * várias. O Valor Total do Projeto NÃO é a soma automática das OCs. */
export interface PurchaseOrder {
  id: string;
  equipmentId: string;
  orderNumber: string | null;
  orderedAt: string | null;
  amount: string | number | null;
  createdAt: string;
  updatedAt: string;
}

export interface EquipmentProcesses {
  negotiation: Negotiation;
  legal: LegalProcess;
  contracts: Contract[];
  purchaseRequests: PurchaseRequest[];
  purchaseOrders: PurchaseOrder[];
}

/** Etapa 7B: eventos de mudança de estado operacional — sempre com
 * justificativa, usuário, data/hora e a fase em que ocorreram. */
export type OperationalStatusEventKind =
  | "STANDBY_ENTERED"
  | "STANDBY_LIFTED"
  | "CANCELLED"
  | "SANITATION_ENTERED"
  | "SANITATION_ENDED";

export interface OperationalStatusEvent {
  id: string;
  kind: OperationalStatusEventKind;
  resultingStatus: OperationalStatus;
  stageAtEvent: number;
  justification: string;
  actor: UserRef | null;
  occurredAt: string;
}

export interface EquipmentOperationalStatus {
  operationalStatus: OperationalStatus;
  events: OperationalStatusEvent[];
}

/** Etapa 7.1: dispensa de requisitos por GRUPO — substitui as exceções de
 * fluxo rígidas da Etapa 7B (FIXED_SUPPLIER/IMPORTATION). O motivo é só
 * classificação/auditoria; quais grupos existem e são dispensáveis é
 * decidido pelo backend, nunca reconstruído no frontend. */
export type RequirementWaiverReasonCode =
  | "IMPORTATION"
  | "FIXED_SUPPLIER"
  | "EXCEPTIONAL_PROCESS"
  | "OTHER";
export type RequirementWaiverStatus = "ACTIVE" | "REVOKED";

export interface RequirementWaiver {
  id: string;
  equipmentId: string;
  stage: number;
  requirementGroupCode: string;
  requirementGroupLabel: string;
  reasonCode: RequirementWaiverReasonCode;
  justification: string;
  status: RequirementWaiverStatus;
  createdBy: UserRef | null;
  createdAt: string;
  revokedBy: UserRef | null;
  revokedAt: string | null;
  revokeReason: string | null;
}

/** Etapa 7C: reabertura com aprovação — a fase só muda quando `APPROVED`. */
export type ReopenRequestStatus = "PENDING" | "APPROVED" | "REJECTED";

export interface ReopenRequest {
  id: string;
  equipmentId: string;
  sourceStage: number;
  sourceStageLabel: string;
  targetStage: number;
  targetStageLabel: string;
  justification: string;
  status: ReopenRequestStatus;
  requestedBy: UserRef | null;
  requestedAt: string;
  decidedBy: UserRef | null;
  decidedAt: string | null;
  decisionNote: string | null;
}

/** Etapa 7E: comentário do equipamento — sem anexos, texto puro. */
export interface EquipmentComment {
  id: string;
  equipmentId: string;
  text: string;
  author: UserRef | null;
  createdAt: string;
  updatedAt: string;
}

/** Etapa 7.1: status por GRUPO de requisitos — a UI só reflete o que o
 * backend calculou, nunca reconstrói a regra localmente. */
export type RequirementGroupStatus = "SATISFIED" | "WAIVED" | "MISSING";

export interface RequirementGroup {
  code: string;
  label: string;
  status: RequirementGroupStatus;
  waivable: boolean;
  fields: string[];
  message: string;
  waiver: RequirementWaiver | null;
}

export interface TransitionOption {
  targetStage: number;
  targetStageLabel: string;
  /** Etapa 7C: "reopen" não é mais produzido aqui — reabertura passou a ser
   * `ReopenRequest` (solicitação + aprovação). */
  kind: "advance";
  canExecute: boolean;
  requiresReason: boolean;
  blockedReason: string | null;
  requirementGroups: RequirementGroup[];
}

export interface AvailableTransitions {
  currentStage: number;
  currentStageLabel: string;
  transitions: TransitionOption[];
}

export interface HistoryEntry {
  id: string;
  kind: "transition" | "change" | "operational_status";
  action: string;
  title: string;
  fromStage: number | null;
  fromStageLabel: string | null;
  toStage: number | null;
  toStageLabel: string | null;
  reason: string | null;
  /** Etapa 7B: justificativa de Standby/Cancelado/Saneamento. */
  justification: string | null;
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
  workPackages: NamedRef[];
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
