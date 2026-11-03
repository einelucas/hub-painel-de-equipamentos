/** Contratos da Central de Notificações (camelCase, espelham o backend). */

export type NotificationKind =
  | "KICKOFF"
  | "FUP"
  | "STARTUP_REMINDER"
  | "NEGOTIATION_OVERDUE"
  | "DELIVERY_REMINDER"
  | "COMPLETED";

export type MailProviderId = "graph" | "resend";

export interface EmailTemplateDraft {
  subject: string;
  title: string;
  intro: string;
  body: string;
  buttonLabel: string;
  footer: string;
  customHtml: string | null;
  useCustomHtml: boolean;
  showDetails: boolean;
  showAlert: boolean;
  showButton: boolean;
  showFooter: boolean;
}

export interface EmailTemplate extends EmailTemplateDraft {
  kind: NotificationKind;
  updatedAt: string;
}

export interface EmailTemplatePreview {
  subject: string;
  html: string;
  text: string;
  sample: boolean;
}

export interface EmailTemplateTestResult {
  preview: EmailTemplatePreview;
  delivery: {
    id: string;
    status: string;
    provider: MailProviderId;
    recipientSummary: string;
    failureReason: string | null;
  };
}

export interface NotificationEquipmentOption {
  id: string;
  name: string;
  unit?: { name: string } | null;
}

export type EquipmentNotificationEventType =
  | "REOPEN_REQUESTED"
  | "REOPEN_APPROVED"
  | "REOPEN_REJECTED"
  | NotificationKind;

export interface EquipmentUserNotification {
  id: string;
  moduleKey: "EQUIPMENT_PANEL";
  eventType: EquipmentNotificationEventType;
  equipmentId: string | null;
  equipmentName: string | null;
  projectContextName: string | null;
  unitName: string | null;
  reopenRequestId: string | null;
  actor: { id: string; name: string; email: string } | null;
  title: string;
  message: string;
  targetUrl: string | null;
  createdAt: string;
  readAt: string | null;
}

export interface NotificationPagination {
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}

export interface EquipmentNotificationList {
  items: EquipmentUserNotification[];
  pagination: NotificationPagination;
}

export interface PendingReopenApproval {
  id: string;
  equipmentId: string;
  equipmentName: string;
  projectContextName: string;
  unitName: string;
  sourceStage: number;
  sourceStageLabel: string;
  targetStage: number;
  targetStageLabel: string;
  justification: string;
  requestedBy: { id: string; name: string; email: string } | null;
  requestedAt: string;
  targetUrl: string;
}

export interface PendingReopenApprovalList {
  items: PendingReopenApproval[];
  pagination: NotificationPagination;
}
