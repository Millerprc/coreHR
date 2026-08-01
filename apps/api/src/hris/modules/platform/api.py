from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.database import get_db
from hris.modules.platform.dependencies import CurrentSession
from hris.modules.platform.models import UserAccount
from hris.modules.platform.schemas import (
    BootstrapAdminRequest,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    UserResponse,
)
from hris.modules.platform.service import AuthService


router = APIRouter(prefix="/api/v1/auth", tags=["platform-auth"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.post("/bootstrap", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def bootstrap_admin(payload: BootstrapAdminRequest, db: DbSession) -> UserResponse:
    return await AuthService(db).bootstrap_admin(payload)


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, db: DbSession) -> LoginResponse:
    return await AuthService(db).login(payload)


@router.get("/me", response_model=UserResponse)
async def me(current: CurrentSession, db: DbSession) -> UserResponse:
    user, _ = current
    return await AuthService(db).user_profile(user)


@router.post("/logout", response_model=LogoutResponse)
async def logout(current: CurrentSession) -> LogoutResponse:
    _, session = current
    from datetime import UTC, datetime

    session.revoked_at = datetime.now(UTC)
    return LogoutResponse()
