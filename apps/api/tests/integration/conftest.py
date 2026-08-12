import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from hris.business_main import create_business_app
from hris.core.database import get_db
from hris.modules.platform.models import (
    Permission,
    Role,
    RolePermission,
    UserAccount,
    UserRole,
    UserSession,
)
from hris.modules.platform.security import hash_password, token_digest


@pytest.fixture
def test_database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is not configured")

    database_name = make_url(value).database or ""
    if "test" not in database_name.casefold():
        raise RuntimeError("TEST_DATABASE_URL must point to a dedicated test database")
    return value


@pytest_asyncio.fixture
async def test_engine(test_database_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(test_database_url, pool_pre_ping=True)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with test_engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            if transaction.is_active:
                await transaction.rollback()


@pytest_asyncio.fixture
async def business_client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    app = create_business_app()

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


async def _seed_access_token(
    db_session: AsyncSession,
    *,
    username: str,
    role_code: str,
    permission_code: str,
    raw_token: str,
) -> str:
    now = datetime.now(UTC)
    permission = await db_session.scalar(
        select(Permission).where(Permission.code == permission_code)
    )
    if permission is None:
        permission = Permission(
            code=permission_code,
            name=f"Synthetic {permission_code}",
            module_code="TEST",
        )
        db_session.add(permission)
    role = await db_session.scalar(select(Role).where(Role.code == role_code))
    if role is None:
        role = Role(
            code=role_code,
            name=f"Synthetic {role_code}",
            is_system=False,
            is_active=True,
        )
    user = UserAccount(
        username=username,
        display_name=f"Synthetic {username}",
        password_hash=hash_password("synthetic-test-password"),
        status="active",
        failed_attempts=0,
    )
    db_session.add_all([role, user])
    await db_session.flush()
    role_permission = await db_session.scalar(
        select(RolePermission).where(
            RolePermission.role_id == role.id,
            RolePermission.permission_id == permission.id,
        )
    )
    records = [
        UserRole(user_id=user.id, role_id=role.id),
        UserSession(
            user_id=user.id,
            token_hash=token_digest(raw_token),
            expires_at=now + timedelta(hours=1),
            last_seen_at=now,
        ),
    ]
    if role_permission is None:
        records.append(RolePermission(role_id=role.id, permission_id=permission.id))
    db_session.add_all(records)
    await db_session.flush()
    return raw_token


@pytest_asyncio.fixture
async def admin_token(db_session: AsyncSession) -> str:
    return await _seed_access_token(
        db_session,
        username="synthetic-admin",
        role_code="SYSTEM_ADMIN",
        permission_code="*",
        raw_token="synthetic-admin-token",
    )


@pytest_asyncio.fixture
async def restricted_token(db_session: AsyncSession) -> str:
    return await _seed_access_token(
        db_session,
        username="synthetic-viewer",
        role_code="SYNTHETIC_VIEWER",
        permission_code="ORGANIZATION_VIEW",
        raw_token="synthetic-viewer-token",
    )


@pytest_asyncio.fixture
async def ssc_token(db_session: AsyncSession) -> str:
    return await _seed_access_token(
        db_session,
        username="synthetic-ssc",
        role_code="SSC_ADMIN",
        permission_code="ONBOARDING_INITIATE",
        raw_token="synthetic-ssc-token",
    )


@pytest_asyncio.fixture
async def lifecycle_admin_token(db_session: AsyncSession) -> str:
    return await _seed_access_token(
        db_session,
        username="synthetic-lifecycle-admin",
        role_code="SYNTHETIC_LIFECYCLE_ADMIN",
        permission_code="LIFECYCLE_ADMIN",
        raw_token="synthetic-lifecycle-admin-token",
    )
