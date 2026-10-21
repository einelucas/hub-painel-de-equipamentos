"""Resend e Microsoft Graph no mesmo backend: sandbox, credenciais, isolamento."""

from __future__ import annotations

import json

import httpx
import pytest

from app.core.config import Settings
from app.modules.notifications.adapter import DeliveryError, send_mail
from app.modules.notifications.mail_service import settings_summary
from app.modules.notifications.schemas import MailSettingsOut, MailTestIn


def settings(mode: str = "sandbox", provider: str = "resend", inbox: str | None = "qa@gmail.com",
             api_key: str | None = "re_fake") -> Settings:
    return Settings(
        DATABASE_URL="postgresql://localhost/test",
        NOTIFICATION_MODE=mode,
        NOTIFICATION_PROVIDER=provider,
        NOTIFICATION_TEST_INBOX=inbox,
        RESEND_API_KEY=api_key,
        RESEND_FROM_EMAIL="onboarding@resend.dev",
        GRAPH_TENANT_ID="tenant",
        GRAPH_CLIENT_ID="client",
        GRAPH_CLIENT_SECRET="fake",
        GRAPH_SENDER="corporate@example.com",
        _env_file=None,
    )


@pytest.mark.asyncio
async def test_resend_sandbox_uses_only_the_gmail_inbox(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"id": "message-123"})

    client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient",
        lambda **kwargs: client(transport=httpx.MockTransport(respond), **kwargs),
    )
    result = await send_mail(
        ["real.user@example.com", "staff@example.com"],
        "FUP", "Synthetic test data",
        settings(),
        idempotency_key="hub-mail-123",
    )
    assert result == "ACCEPTED"
    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == "https://api.resend.com/emails"
    body = json.loads(request.content)
    assert body["to"] == ["qa@gmail.com"]
    assert body["from"] == "onboarding@resend.dev"
    assert body["subject"] == "[TESTE HUB] FUP"
    assert body["text"] == "Synthetic test data"
    assert "html" not in body
    assert request.headers["idempotency-key"] == "hub-mail-123"
    assert request.headers["authorization"] == "Bearer re_fake"


@pytest.mark.asyncio
async def test_resend_sends_html_with_text_alternative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["to"] == ["qa@gmail.com"]
        assert body["html"] == "<p>Olá</p>"
        assert body["text"] == "Olá"
        return httpx.Response(200, json={"id": "message-789"})

    client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient",
        lambda **kwargs: client(transport=httpx.MockTransport(respond), **kwargs),
    )
    result = await send_mail(
        ["real.user@example.com"], "Assunto", "Olá", settings(), html="<p>Olá</p>",
    )
    assert result == "ACCEPTED"


@pytest.mark.asyncio
async def test_live_test_through_resend_is_still_redirected_to_inbox(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["to"] == ["qa@gmail.com"]
        assert body["subject"].startswith("[TESTE HUB]")
        return httpx.Response(200, json={"id": "message-456"})

    client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient",
        lambda **kwargs: client(transport=httpx.MockTransport(respond), **kwargs),
    )
    result = await send_mail(
        ["recipient@enterprise.com"], "Confidential", "Synthetic content",
        settings(mode="live", provider="graph"), provider="resend", force_sandbox=True,
    )
    assert result == "ACCEPTED"


@pytest.mark.asyncio
async def test_resend_live_operational_delivery_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("Must not contact external services")

    monkeypatch.setattr(httpx, "AsyncClient", refuse_network)
    with pytest.raises(DeliveryError, match="reservado para testes"):
        await send_mail(
            ["corporate@example.com"], "Operational", "Corporate body",
            settings(mode="live"),
        )


@pytest.mark.asyncio
async def test_missing_inbox_prevents_resend_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("Must not contact external services")

    monkeypatch.setattr(httpx, "AsyncClient", refuse_network)
    with pytest.raises(DeliveryError, match="TEST_INBOX"):
        await send_mail(["recipient@example.com"], "Subject", "Body", settings(inbox=None))


@pytest.mark.asyncio
async def test_missing_resend_api_key_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("Must not contact external services")

    monkeypatch.setattr(httpx, "AsyncClient", refuse_network)
    with pytest.raises(DeliveryError, match="Resend não configurado"):
        await send_mail(["staff@example.com"], "Subject", "Body", settings(api_key=None))


@pytest.mark.asyncio
async def test_http_error_does_not_reveal_provider_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"secret": "should-not-leak", "message": "bad"})

    client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient",
        lambda **kwargs: client(transport=httpx.MockTransport(respond), **kwargs),
    )
    with pytest.raises(DeliveryError, match="HTTP 403") as caught:
        await send_mail(["recipient@example.com"], "Subject", "Body", settings())
    assert "should-not-leak" not in str(caught.value)


@pytest.mark.asyncio
async def test_log_mode_ignores_selected_provider_and_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("Must not contact external services")

    monkeypatch.setattr(httpx, "AsyncClient", refuse_network)
    result = await send_mail(
        ["recipient@example.com"], "Subject", "Body", settings(mode="log"),
        provider="resend",
    )
    assert result == "SIMULATED"


def test_admin_response_shows_both_providers_but_no_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modules.notifications import mail_service

    config = settings(provider="resend")
    monkeypatch.setattr(mail_service, "get_settings", lambda: config)
    summary = settings_summary()
    result = MailSettingsOut.model_validate(summary).model_dump(mode="json", by_alias=True)
    assert result["activeProvider"] == "resend"
    assert [p["id"] for p in result["providers"]] == ["graph", "resend"]
    assert result["configured"] is True
    assert "re_fake" not in str(result)
    assert "client_secret" not in str(result)


def test_admin_test_request_accepts_only_known_provider() -> None:
    assert MailTestIn.model_validate({"provider": "resend"}).provider == "resend"
    with pytest.raises(ValueError):
        MailTestIn.model_validate({"provider": "third-party"})
