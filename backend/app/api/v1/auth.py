"""Rotas de autenticação: login local, logout e identidade do usuário."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, extract_bearer_token, require_user
from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.core.local_auth import authenticate, create_session, revoke_session
from app.core.permissions import permissions_for

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


@router.post("/login")
async def login(
    payload: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    user = await authenticate(session, payload.email, payload.password)
    token, record = await create_session(
        session,
        user,
        ttl=timedelta(hours=settings.local_auth_session_hours),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    await session.commit()
    return {"accessToken": token, "expiresAt": record.expiresAt.isoformat() + "Z"}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_model=None, response_class=Response)
async def logout(request: Request, session: AsyncSession = Depends(get_session)) -> None:
    token = extract_bearer_token(request)
    if token:
        await revoke_session(session, token)
        await session.commit()


@router.get("/me")
async def me(current_user: CurrentUser = Depends(require_user)) -> dict:
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "role": current_user.role.value,
        "active": current_user.active,
        "permissions": [p.value for p in permissions_for(current_user.role)],
    }
