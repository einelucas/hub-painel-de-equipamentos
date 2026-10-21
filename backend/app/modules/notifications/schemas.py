"""Contratos HTTP de configurações, testes e outbox (camelCase)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from app.shared.schema import CamelModel

_KIND = Literal[
    "KICKOFF", "FUP", "STARTUP_REMINDER", "NEGOTIATION_OVERDUE",
    "DELIVERY_REMINDER", "COMPLETED",
]
_EMAIL = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$")


class NotificationEventOut(CamelModel):
    id: str
    equipment_id: str
    workflow_transition_id: str
    kind: Literal["KICKOFF", "FUP"]
    status: Literal["PENDING", "SENT", "FAILED"]
    recipient_summary: str | None
    failure_reason: str | None
    created_at: datetime
    sent_at: datetime | None


class NotificationEventListOut(CamelModel):
    items: list[NotificationEventOut]


class MailProviderStatusOut(CamelModel):
    id: Literal["graph", "resend"]
    name: str
    configured: bool
    sender: str | None


class MailSettingsOut(CamelModel):
    mode: Literal["log", "sandbox", "live"]
    provider: str
    active_provider: Literal["graph", "resend"]
    providers: list[MailProviderStatusOut]
    configured: bool
    sender: str | None
    test_inbox: str | None


class MailRuleOut(CamelModel):
    kind: _KIND
    enabled: bool
    include_responsible: bool
    days_before: int
    recipient_emails: list[str]
    subject_template: str
    body_template: str


class MailRuleUpdate(CamelModel):
    enabled: bool
    include_responsible: bool
    days_before: int = Field(ge=0, le=365)
    recipient_emails: list[str] = Field(max_length=50)
    subject_template: str = Field(min_length=1, max_length=200)
    body_template: str = Field(min_length=1, max_length=4000)

    @field_validator("recipient_emails")
    @classmethod
    def valid_emails(cls, emails: list[str]) -> list[str]:
        clean = [email.strip().lower() for email in emails]
        if any(not _EMAIL.fullmatch(email) for email in clean):
            raise ValueError("Informe endereços de e-mail válidos.")
        if len(set(clean)) != len(clean):
            raise ValueError("Há e-mails duplicados.")
        return clean


class MailRuleListOut(CamelModel):
    items: list[MailRuleOut]


class MailDeliveryOut(CamelModel):
    id: str
    kind: str
    equipment_id: str | None
    status: str
    mode: str
    provider: Literal["graph", "resend"]
    recipient_summary: str
    subject: str
    failure_reason: str | None
    attempts: int
    created_at: datetime
    processed_at: datetime | None


class MailDeliveryListOut(CamelModel):
    items: list[MailDeliveryOut]


class MailTestIn(CamelModel):
    provider: Literal["graph", "resend"] | None = None
    subject: str = Field(
        default="Teste de notificações — Painel de Equipamentos", min_length=1, max_length=200
    )
    body: str = Field(default="Mensagem de teste da central de notificações.", min_length=1, max_length=4000)


class EmailTemplateContent(CamelModel):
    """Campos editáveis de um modelo. O HTML avançado é sanitizado no backend."""

    subject: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=160)
    intro: str = Field(default="", max_length=1000)
    body: str = Field(default="", max_length=6000)
    button_label: str = Field(default="", max_length=80)
    footer: str = Field(default="", max_length=1000)
    custom_html: str | None = Field(default=None, max_length=120_000)
    use_custom_html: bool = False
    show_details: bool = True
    show_alert: bool = True
    show_button: bool = True
    show_footer: bool = True


class EmailTemplateOut(EmailTemplateContent):
    kind: _KIND
    updated_at: datetime


class EmailTemplateListOut(CamelModel):
    items: list[EmailTemplateOut]


class EmailTemplatePreviewIn(EmailTemplateContent):
    equipment_id: str | None = None
    use_sample: bool = False


class EmailTemplatePreviewOut(CamelModel):
    subject: str
    html: str
    text: str
    sample: bool


class EmailTemplateTestIn(EmailTemplatePreviewIn):
    provider: Literal["graph", "resend"] | None = None


class EmailTemplateTestOut(CamelModel):
    preview: EmailTemplatePreviewOut
    delivery: MailDeliveryOut



class MailProcessOut(CamelModel):
    scheduled: int
    processed: int
