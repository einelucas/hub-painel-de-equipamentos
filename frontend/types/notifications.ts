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
