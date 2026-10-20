"""Envio através de Microsoft Graph ou Resend; proteção de sandbox comum.

O provedor é escolhido explicitamente, sem fallback automático: uma falha no
Graph nunca deve fazer e-mails corporativos serem encaminhados a terceiros.
"""

from __future__ import annotations

from typing import Literal
from urllib.parse import quote

import httpx

from app.core.config import Settings, get_settings

MailProvider = Literal["graph", "resend"]


class DeliveryError(Exception):
    """Mensagem segura: nunca incluir token, credenciais ou corpo da resposta."""


def graph_ready(settings: Settings) -> bool:
    return all((
        settings.notification_graph_tenant_id,
        settings.notification_graph_client_id,
        settings.notification_graph_client_secret,
        settings.notification_graph_sender,
    ))


def resend_ready(settings: Settings) -> bool:
    return bool(settings.notification_resend_api_key and settings.notification_resend_from_email)


def provider_ready(settings: Settings, provider: MailProvider) -> bool:
    if provider == "graph":
        return graph_ready(settings)
    return resend_ready(settings)


def provider_sender(settings: Settings, provider: MailProvider) -> str | None:
    if provider == "graph":
        return settings.notification_graph_sender
    return settings.notification_resend_from_email


async def _send_graph(
    recipients: list[str], subject: str, body: str, settings: Settings
) -> str:
    tenant = quote(settings.notification_graph_tenant_id or "", safe="")
    sender = quote(settings.notification_graph_sender or "", safe="@")
    token_url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    send_url = f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            token_response = await client.post(
                token_url,
                data={
                    "client_id": settings.notification_graph_client_id,
                    "client_secret": settings.notification_graph_client_secret,
                    "scope": "https://graph.microsoft.com/.default",
                    "grant_type": "client_credentials",
                },
            )
            if token_response.status_code != 200:
                raise DeliveryError(
                    f"Graph: autenticação rejeitada (HTTP {token_response.status_code})."
                )
            token = token_response.json().get("access_token")
            if not isinstance(token, str) or not token:
                raise DeliveryError("Graph: token de aplicação indisponível.")
            response = await client.post(
                send_url,
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "message": {
                        "subject": subject,
                        "body": {"contentType": "Text", "content": body},
                        "toRecipients": [
                            {"emailAddress": {"address": email}} for email in recipients
                        ],
                    },
                    "saveToSentItems": True,
                },
            )
            if response.status_code != 202:
                raise DeliveryError(f"Graph: envio recusado (HTTP {response.status_code}).")
    except httpx.HTTPError as exc:
        raise DeliveryError(
            "Graph: indisponível ou tempo limite excedido; revise antes de reenviar."
        ) from exc
    return "ACCEPTED"


async def _send_resend(
    recipients: list[str], subject: str, body: str, settings: Settings,
    idempotency_key: str | None,
) -> str:
    headers = {"Authorization": f"Bearer {settings.notification_resend_api_key}"}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers=headers,
                json={
                    "from": settings.notification_resend_from_email,
                    "to": recipients,
                    "subject": subject,
                    "text": body,
                },
            )
    except httpx.HTTPError as exc:
        raise DeliveryError(
            "Resend: indisponível ou tempo limite excedido; revise antes de reenviar."
        ) from exc
    if response.status_code not in (200, 201):
        # Nunca incluir body da resposta: pode conter detalhes sensíveis.
        raise DeliveryError(f"Resend: envio recusado (HTTP {response.status_code}).")
    try:
        message_id = response.json().get("id")
    except ValueError as exc:
        raise DeliveryError("Resend: resposta inválida; confirme o envio antes de reenviar.") from exc
    if not isinstance(message_id, str) or not message_id:
        raise DeliveryError("Resend: aceite sem ID de mensagem; confirme antes de reenviar.")
    return "ACCEPTED"


async def send_mail(
    recipients: list[str],
    subject: str,
    body: str,
    settings: Settings | None = None,
    *,
    provider: MailProvider | None = None,
    force_sandbox: bool = False,
    idempotency_key: str | None = None,
) -> str:
    """Retorna SIMULATED ou ACCEPTED; aceite na API não confirma entrega.

    force_sandbox é usado pelo botão de teste até em NOTIFICATION_MODE=live.
    Seleção de provedor é independente do modo, mas NUNCA envia aos dois.
    """
    config = settings or get_settings()
    selected = provider or config.notification_provider
    if config.notification_mode == "log":
        return "SIMULATED"
    if config.notification_mode == "sandbox" or force_sandbox:
        if not config.notification_test_inbox:
            raise DeliveryError("NOTIFICATION_TEST_INBOX não configurado.")
        recipients = [config.notification_test_inbox]
        if not subject.startswith("[TESTE HUB]"):
            subject = "[TESTE HUB] " + subject
    if not recipients:
        raise DeliveryError("Nenhum destinatário válido para o envio.")
    # Dados operacionais corporativos só saem pelo Graph. Resend serve
    # para testes (sandbox ou botão de teste protegido mesmo em live).
    if selected == "resend" and config.notification_mode == "live" and not force_sandbox:
        raise DeliveryError("Resend reservado para testes; use Microsoft Graph em produção.")
    if not provider_ready(config, selected):
        label = "Microsoft Graph" if selected == "graph" else "Resend"
        raise DeliveryError(f"{label} não configurado.")
    if selected == "graph":
        return await _send_graph(recipients, subject, body, config)
    return await _send_resend(recipients, subject, body, config, idempotency_key)
