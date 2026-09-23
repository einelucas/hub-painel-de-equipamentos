"""Etapa 7F — adapter de notificação (Kickoff/FUP).

Nenhum provedor real de e-mail está configurado ainda: a hierarquia
corporativa (quem são os "superiores" de um responsável) depende do time de
Automação/Microsoft, ainda não definida. Por isso o único adapter hoje só
registra o envio (log) — nunca finge mandar e-mail de verdade. Trocar por um
adapter real (SMTP/Graph/SES/etc.) no futuro é só implementar o mesmo
`NotificationAdapter` Protocol e trocar a fábrica abaixo.
"""

from __future__ import annotations

import logging
from typing import Protocol

logger = logging.getLogger("app.notifications")


class NotificationAdapter(Protocol):
    async def send(self, *, subject: str, body: str, recipients: list[str]) -> None: ...


class LogNotificationAdapter:
    """DEV/test: registra o envio no log, nunca fala com um provedor real."""

    async def send(self, *, subject: str, body: str, recipients: list[str]) -> None:
        logger.info(
            "notification.send (log adapter, sem provedor real configurado)",
            extra={"subject": subject, "recipients": recipients, "body": body},
        )


def get_notification_adapter() -> NotificationAdapter:
    # Pendência de infraestrutura (documentada em
    # docs/validation/etapa-07-operational-business-rules.md): nenhum
    # provedor real (Microsoft Graph/SMTP corporativo) foi definido. Até lá,
    # todo ambiente — incluindo produção — usa o adapter de log.
    return LogNotificationAdapter()
