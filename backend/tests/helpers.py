"""Helpers compartilhados pelos testes de integração."""

from __future__ import annotations

OPERATIONAL_ROLES = ("VIEWER", "ANALYST")


async def grant_unit(client, auth_header, unit_id: str, roles=OPERATIONAL_ROLES) -> None:
    """Dá acesso à unidade para os perfis operacionais, acumulando os já existentes.

    A partir da Etapa 4 o acesso é explícito: sem vínculo, VIEWER e ANALYST não
    enxergam nada. ADMIN é global por perfil e não precisa de vínculo.
    """
    admin = auth_header("ADMIN")
    for role in roles:
        me = await client.get("/api/v1/auth/me", headers=auth_header(role))
        assert me.status_code == 200, me.text
        user_id = me.json()["id"]

        current = await client.get(f"/api/v1/usuarios/{user_id}/units", headers=admin)
        assert current.status_code == 200, current.text
        unit_ids = sorted({unit["id"] for unit in current.json()["units"]} | {unit_id})

        updated = await client.put(
            f"/api/v1/usuarios/{user_id}/units", json={"unitIds": unit_ids}, headers=admin
        )
        assert updated.status_code == 200, updated.text
