"""Persistência, prévia e teste dos modelos de e-mail (PostgreSQL de teste)."""

from __future__ import annotations

from app.core.config import get_settings
from tests.helpers import grant_unit

_TEMPLATE_PAYLOAD = {
    "subject": "Kickoff: {equipamento}",
    "title": "Contrato escriturado",
    "intro": "Atualização do processo.",
    "body": "Equipamento {equipamento} na obra {obra}.",
    "buttonLabel": "Abrir no Hub",
    "footer": "Gerado automaticamente pelo Hub.",
    "customHtml": None,
    "useCustomHtml": False,
    "showDetails": True,
    "showAlert": True,
    "showButton": True,
    "showFooter": True,
}


async def _catalogs(client, auth_header, suffix: str) -> dict[str, str]:
    headers = auth_header("ADMIN")
    unit = (
        await client.post(
            "/api/v1/units",
            json={"code": f"NT-{suffix}", "name": f"Unidade {suffix}"},
            headers=headers,
        )
    ).json()
    context = (
        await client.post(
            f"/api/v1/units/{unit['id']}/project-contexts",
            json={"code": f"CTX-{suffix}", "name": f"Obra {suffix}"},
            headers=headers,
        )
    ).json()
    await grant_unit(client, auth_header, unit["id"])
    area = (
        await client.post(
            "/api/v1/areas",
            json={"unitId": unit["id"], "name": f"Área {suffix}"},
            headers=headers,
        )
    ).json()
    discipline = (
        await client.post(
            "/api/v1/disciplines",
            json={"code": f"ND-{suffix}", "name": f"Disciplina {suffix}"},
            headers=headers,
        )
    ).json()
    work_package = (
        await client.post(
            "/api/v1/work-packages",
            json={
                "projectContextId": context["id"],
                "code": f"NWP-{suffix}",
                "name": f"Pacote {suffix}",
            },
            headers=headers,
        )
    ).json()
    return {
        "unit": unit["id"],
        "context": context["id"],
        "area": area["id"],
        "discipline": discipline["id"],
        "work_package": work_package["id"],
    }


async def _equipment(client, auth_header, catalogs: dict[str, str]) -> dict[str, object]:
    created = await client.post(
        "/api/v1/equipments",
        json={
            "projectContextId": catalogs["context"],
            "name": "Bomba de teste",
            "areaId": catalogs["area"],
            "disciplineId": catalogs["discipline"],
            "workPackageIds": [catalogs["work_package"]],
        },
        headers=auth_header("ANALYST"),
    )
    assert created.status_code == 201, created.text
    equipment = created.json()
    component = await client.post(
        f"/api/v1/equipments/{equipment['id']}/components",
        json={"name": "Componente de teste", "tag": "TAG-TESTE-01"},
        headers=auth_header("ANALYST"),
    )
    assert component.status_code == 201, component.text
    return equipment


async def test_templates_persist_preview_and_reset(client, auth_header) -> None:
    headers = auth_header("ADMIN")
    catalogs = await _catalogs(client, auth_header, "91")
    equipment = await _equipment(client, auth_header, catalogs)

    listed = await client.get("/api/v1/notifications/templates", headers=headers)
    assert listed.status_code == 200, listed.text
    items = listed.json()["items"]
    assert [item["kind"] for item in items] == [
        "KICKOFF", "FUP", "STARTUP_REMINDER", "NEGOTIATION_OVERDUE",
        "DELIVERY_REMINDER", "COMPLETED",
    ]

    updated = await client.put(
        "/api/v1/notifications/templates/KICKOFF",
        json={**_TEMPLATE_PAYLOAD, "subject": "Alerta: {tag}"},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["subject"] == "Alerta: {tag}"

    fetched = await client.get("/api/v1/notifications/templates/KICKOFF", headers=headers)
    assert fetched.json()["subject"] == "Alerta: {tag}"

    real_preview = await client.post(
        "/api/v1/notifications/templates/KICKOFF/preview",
        json={**_TEMPLATE_PAYLOAD, "equipmentId": equipment["id"], "useSample": False},
        headers=headers,
    )
    assert real_preview.status_code == 200, real_preview.text
    preview = real_preview.json()
    assert preview["sample"] is False
    assert "Bomba de teste" in preview["html"]
    assert "TAG-TESTE-01" in preview["html"]
    assert "<script" not in preview["html"].lower()

    sample_preview = await client.post(
        "/api/v1/notifications/templates/KICKOFF/preview",
        json={**_TEMPLATE_PAYLOAD, "useSample": True},
        headers=headers,
    )
    assert sample_preview.status_code == 200, sample_preview.text
    assert sample_preview.json()["sample"] is True
    assert "Bomba de teste" not in sample_preview.json()["html"]
    assert "Exemplo" in sample_preview.json()["html"]

    reset = await client.post(
        "/api/v1/notifications/templates/KICKOFF/reset", headers=headers
    )
    assert reset.status_code == 200, reset.text
    assert reset.json()["subject"] == "Kickoff: {equipamento}"


async def test_template_editor_rejects_non_admin_and_sanitizes_html(client, auth_header) -> None:
    forbidden = await client.put(
        "/api/v1/notifications/templates/KICKOFF",
        json=_TEMPLATE_PAYLOAD,
        headers=auth_header("ANALYST"),
    )
    assert forbidden.status_code == 403

    saved = await client.put(
        "/api/v1/notifications/templates/KICKOFF",
        json={
            **_TEMPLATE_PAYLOAD,
            "useCustomHtml": True,
            "customHtml": (
                '<div><script>alert(1)</script><p onclick="x()">'
                "{equipamento}</p><a href=\"javascript:alert(1)\">x</a></div>"
            ),
        },
        headers=auth_header("ADMIN"),
    )
    assert saved.status_code == 200, saved.text
    custom = saved.json()["customHtml"]
    assert "<script" not in custom.lower()
    assert "onclick" not in custom
    assert "javascript:" not in custom
    assert "{equipamento}" in custom

    unsafe_placeholder = await client.put(
        "/api/v1/notifications/templates/FUP",
        json={**_TEMPLATE_PAYLOAD, "body": "{senha}"},
        headers=auth_header("ADMIN"),
    )
    assert unsafe_placeholder.status_code == 422


async def test_test_send_uses_sample_data_without_network_in_log_mode(
    client, auth_header, monkeypatch
) -> None:
    headers = auth_header("ADMIN")
    catalogs = await _catalogs(client, auth_header, "92")
    equipment = await _equipment(client, auth_header, catalogs)
    monkeypatch.setenv("NOTIFICATION_TEST_INBOX", "qa@example.test")
    monkeypatch.setenv("NOTIFICATION_MODE", "log")
    get_settings.cache_clear()
    try:
        response = await client.post(
            "/api/v1/notifications/templates/KICKOFF/test",
            json={
                **_TEMPLATE_PAYLOAD,
                "equipmentId": equipment["id"],
                "useSample": True,
                "provider": "resend",
            },
            headers=headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["preview"]["sample"] is True
        assert "Bomba de teste" not in body["preview"]["html"]
        assert body["delivery"]["status"] == "SIMULATED"
        assert body["delivery"]["recipientSummary"] == "qa@example.test"
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
