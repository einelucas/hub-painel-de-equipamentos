from datetime import timedelta

from sqlalchemy import select, update

from app.core.local_auth import upsert_local_user
from app.models.common import utcnow
from app.models.user import Account, Role, Session

EMAIL = "admin@inpasa.com.br"
PASSWORD = "INP@2026"


async def _seed_admin(db_session) -> None:
    await upsert_local_user(db_session, email=EMAIL, password=PASSWORD, name="Administrador", role=Role.ADMIN)
    await db_session.commit()


async def test_login_issues_session_accepted_by_me(client, db_session) -> None:
    await _seed_admin(db_session)

    response = await client.post(
        "/api/v1/auth/login", json={"email": " Admin@Inpasa.com.br ", "password": PASSWORD}
    )
    assert response.status_code == 200
    token = response.json()["accessToken"]

    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == EMAIL
    assert me.json()["role"] == "ADMIN"

    stored = (await db_session.execute(select(Session.token))).scalar_one()
    assert stored != token
    password_hash = (await db_session.execute(select(Account.password))).scalar_one()
    assert PASSWORD not in password_hash


async def test_login_rejects_wrong_password_and_unknown_email(client, db_session) -> None:
    await _seed_admin(db_session)

    wrong = await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": "errada"})
    unknown = await client.post("/api/v1/auth/login", json={"email": "x@inpasa.com.br", "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


async def test_logout_revokes_session(client, db_session) -> None:
    await _seed_admin(db_session)
    token = (await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})).json()[
        "accessToken"
    ]
    headers = {"Authorization": f"Bearer {token}"}

    assert (await client.post("/api/v1/auth/logout", headers=headers)).status_code == 204
    assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 401


async def test_expired_session_is_rejected(client, db_session) -> None:
    await _seed_admin(db_session)
    token = (await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})).json()[
        "accessToken"
    ]
    await db_session.execute(update(Session).values(expiresAt=utcnow() - timedelta(minutes=1)))
    await db_session.commit()

    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


async def test_upsert_resets_password(client, db_session) -> None:
    await _seed_admin(db_session)
    await upsert_local_user(
        db_session, email=EMAIL, password="NovaSenha123", name="Administrador", role=Role.ADMIN
    )
    await db_session.commit()

    old = await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    new = await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": "NovaSenha123"})
    assert old.status_code == 401
    assert new.status_code == 200
