"""Microsoft Graph client-credentials; log é simulação, nunca envio confirmado."""

from __future__ import annotations

from urllib.parse import quote

import httpx

from app.core.config import Settings, get_settings


class DeliveryError(Exception):
    """Mensagem segura: não inclui token, credenciais ou corpo da resposta."""


def graph_ready(settings: Settings) -> bool:
    return all((
        settings.notification_graph_tenant_id,
        settings.notification_graph_client_id,
        settings.notification_graph_client_secret,
        settings.notification_graph_sender,
    ))


async def send_mail(
    recipients: list[str],
    subject: str,
    body: str,
    settings: Settings | None = None,
) -> str:
    """Retorna SIMULATED ou ACCEPTED (HTTP 202 não garante entrega na caixa postal)."""
    config = settings or get_settings()
    mode = config.notification_mode
    if mode == "log":
        return "SIMULATED"
    if not graph_ready(config):
        raise DeliveryError("Microsoft Graph não configurado.")
    if mode == "sandbox":
        if not config.notification_test_inbox:
            raise DeliveryError("NOTIFICATION_TEST_INBOX não configurado.")
        recipients = [config.notification_test_inbox]
        subject = "[TESTE HUB] " + subject
    if not recipients:
        raise DeliveryError("Nenhum destinatário válido para o envio.")

    tenant = quote(config.notification_graph_tenant_id or "", safe="")
    sender = quote(config.notification_graph_sender or "", safe="@")
    token_url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    send_url = f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            token_response = await client.post(
                token_url,
                data={
                    "client_id": config.notification_graph_client_id,
                    "client_secret": config.notification_graph_client_secret,
                    "scope": "https://graph.microsoft.com/.default",
                    "grant_type": "client_credentials",
                },
            )
            if token_response.status_code != 200:
                raise DeliveryError(f"Graph: autenticação rejeitada (HTTP {token_response.status_code}).")
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
        raise DeliveryError("Graph: indisponível ou tempo limite excedido; revise antes de reenviar.") from exc
    return "ACCEPTED"
