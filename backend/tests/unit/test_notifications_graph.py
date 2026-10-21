"""Guardas do sandbox, templates e semântica real do Microsoft Graph."""

from __future__ import annotations

import httpx
import pytest

from app.core.config import Settings
from app.core.errors import DomainError
from app.modules.notifications.adapter import DeliveryError, send_mail
from app.modules.notifications.mail_service import validate_template
from app.modules.notifications.schemas import MailRuleUpdate


def settings(mode: str, inbox: str | None = "qa@example.test") -> Settings:
    return Settings(
        DATABASE_URL="postgresql://localhost/test",
        NOTIFICATION_MODE=mode,
        NOTIFICATION_TEST_INBOX=inbox,
        GRAPH_TENANT_ID="tenant",
        GRAPH_CLIENT_ID="client",
        GRAPH_CLIENT_SECRET="not-real",
        GRAPH_SENDER="sender@example.test",
        _env_file=None,
    )


def test_templates_only_allow_explicit_simple_fields() -> None:
    validate_template("{equipamento} — {obra} — {data}")
    with pytest.raises(DomainError):
        validate_template("{equipamento.__class__}")
    with pytest.raises(DomainError):
        validate_template("{equipamento:>20}")
    with pytest.raises(DomainError):
        validate_template("Mensagem {")
    with pytest.raises(DomainError):
        validate_template("{unknown}")


def test_recipient_validation_blocks_invalid_and_duplicate() -> None:
    payload = {
        "enabled": False, "includeResponsible": True, "daysBefore": 0,
        "recipientEmails": ["qa@example.com"], "subjectTemplate": "A", "bodyTemplate": "B",
    }
    assert MailRuleUpdate.model_validate(payload).recipient_emails == ["qa@example.com"]
    with pytest.raises(ValueError):
        MailRuleUpdate.model_validate({**payload, "recipientEmails": ["wrong"]})
    with pytest.raises(ValueError):
        MailRuleUpdate.model_validate({**payload, "recipientEmails": ["qa@example.com", "QA@example.com"]})


@pytest.mark.asyncio
async def test_log_mode_never_uses_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("network must not be used")

    monkeypatch.setattr(httpx, "AsyncClient", no_network)
    assert await send_mail(["real@example.com"], "Hello", "Body", settings("log")) == "SIMULATED"


@pytest.mark.asyncio
async def test_sandbox_redirects_all_recipients_to_inbox(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if "login.microsoftonline.com" in str(request.url):
            return httpx.Response(200, json={"access_token": "temporary-token"})
        return httpx.Response(202)

    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(respond)
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: real_client(transport=transport, **kwargs)
    )
    result = await send_mail(
        ["private.person@example.com", "team@example.com"], "Subject", "Message",
        settings("sandbox"),
    )
    assert result == "ACCEPTED"
    assert len(requests) == 2
    message = __import__("json").loads(requests[1].content)["message"]
    assert message["toRecipients"] == [{"emailAddress": {"address": "qa@example.test"}}]
    assert message["subject"].startswith("[TESTE HUB]")


@pytest.mark.asyncio
async def test_sandbox_refuses_missing_test_inbox() -> None:
    with pytest.raises(DeliveryError, match="TEST_INBOX"):
        await send_mail(["real@example.com"], "Subject", "Body", settings("sandbox", None))


@pytest.mark.asyncio
async def test_graph_sends_html_content_type_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if "login.microsoftonline.com" in str(request.url):
            return httpx.Response(200, json={"access_token": "temporary-token"})
        return httpx.Response(202)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    assert await send_mail(
        ["real@example.com"], "Subject", "Plain", settings("live"), html="<b>HTML</b>",
    ) == "ACCEPTED"
    body = __import__("json").loads(requests[1].content)["message"]["body"]
    assert body == {"contentType": "HTML", "content": "<b>HTML</b>"}


@pytest.mark.asyncio
async def test_graph_does_not_report_mailbox_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if "login.microsoftonline.com" in str(request.url):
            return httpx.Response(200, json={"access_token": "temporary-token"})
        return httpx.Response(202)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    assert await send_mail(["real@example.com"], "Subject", "Message", settings("live")) == "ACCEPTED"
