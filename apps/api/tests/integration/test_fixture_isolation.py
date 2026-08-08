from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.modules.workforce.models import OrganizationType


async def test_database_fixture_rolls_back(db_session: AsyncSession) -> None:
    existing = await db_session.scalar(
        select(OrganizationType).where(OrganizationType.code == "TEST_ONLY")
    )
    assert existing is None

    marker = OrganizationType(code="TEST_ONLY", name="测试", sort_order=0)
    db_session.add(marker)
    await db_session.flush()

    assert marker.id is not None
    await db_session.commit()


async def test_business_client_uses_seeded_administrator(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    response = await business_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    assert response.json()["permissions"] == ["*"]
