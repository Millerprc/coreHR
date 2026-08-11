from datetime import date
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.modules.workforce.models import JobCatalogVersion, JobDimensionVersion


pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_dimension(
    client: AsyncClient,
    token: str,
    *,
    dimension_type: str,
    code: str,
    name: str,
    parent_type: str | None = None,
    parent_code: str | None = None,
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/workforce/job-dimensions",
        headers=_auth(token),
        json={
            "dimension_type": dimension_type,
            "code": code,
            "name": name,
            "parent_dimension_type": parent_type,
            "parent_dimension_code": parent_code,
            "sort_order": 10,
            "effective_from": "2026-01-01",
            "status": "active",
            "change_reason": "建立合成职务体系",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_job_dimensions_and_jobs_keep_effective_dated_versions(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    sequence = await _create_dimension(
        business_client,
        admin_token,
        dimension_type="SEQUENCE",
        code="TECH",
        name="技术",
    )
    await _create_dimension(
        business_client,
        admin_token,
        dimension_type="CLASS",
        code="CLASS_02",
        name="二级职类",
        parent_type="SEQUENCE",
        parent_code="TECH",
    )
    await _create_dimension(
        business_client,
        admin_token,
        dimension_type="GRADE",
        code="GRADE_02",
        name="二等",
        parent_type="CLASS",
        parent_code="CLASS_02",
    )
    await _create_dimension(
        business_client,
        admin_token,
        dimension_type="LEVEL",
        code="LEVEL_06",
        name="六级",
        parent_type="GRADE",
        parent_code="GRADE_02",
    )

    job = await business_client.post(
        "/api/v1/workforce/jobs",
        headers=_auth(admin_token),
        json={
            "code": "JOB_LABOR_PRODUCT_GM",
            "name": "劳动者产品部总经理",
            "level_code": "LEVEL_06",
            "grade_code": "GRADE_02",
            "class_code": "CLASS_02",
            "sequence_code": "TECH",
            "effective_from": "2026-01-01",
            "status": "active",
            "change_reason": "建立合成职务",
        },
    )
    assert job.status_code == 201, job.text
    assert job.json()["version"] == 1

    version = await business_client.post(
        f"/api/v1/workforce/jobs/{job.json()['id']}/versions",
        headers=_auth(admin_token),
        json={
            "name": "劳动者产品部总经理（新版）",
            "level_code": "LEVEL_06",
            "grade_code": "GRADE_02",
            "class_code": "CLASS_02",
            "sequence_code": "TECH",
            "effective_from": "2027-01-01",
            "status": "active",
            "change_reason": "年度职务版本调整",
        },
    )
    assert version.status_code == 201, version.text
    assert version.json()["version"] == 2

    old_view = await business_client.get(
        "/api/v1/workforce/jobs?effective_at=2026-06-30&limit=200&offset=0",
        headers=_auth(admin_token),
    )
    new_view = await business_client.get(
        "/api/v1/workforce/jobs?effective_at=2027-01-01&limit=200&offset=0",
        headers=_auth(admin_token),
    )
    assert old_view.status_code == 200, old_view.text
    assert new_view.status_code == 200, new_view.text
    assert old_view.json()["items"][0]["name"] == "劳动者产品部总经理"
    assert new_view.json()["items"][0]["name"] == "劳动者产品部总经理（新版）"

    versions = list(
        (
            await db_session.scalars(
                select(JobCatalogVersion)
                .where(JobCatalogVersion.job_id == UUID(job.json()["id"]))
                .order_by(JobCatalogVersion.version)
            )
        ).all()
    )
    assert versions[0].effective_to == date(2026, 12, 31)
    assert not versions[0].is_current
    assert versions[1].is_current

    dimension_version = await business_client.post(
        f"/api/v1/workforce/job-dimensions/{sequence['id']}/versions",
        headers=_auth(admin_token),
        json={
            "name": "技术序列",
            "sort_order": 20,
            "effective_from": "2027-01-01",
            "status": "active",
            "change_reason": "规范序列名称",
        },
    )
    assert dimension_version.status_code == 201, dimension_version.text
    stored_dimension_versions = list(
        (
            await db_session.scalars(
                select(JobDimensionVersion)
                .where(JobDimensionVersion.dimension_id == UUID(str(sequence["id"])))
                .order_by(JobDimensionVersion.version)
            )
        ).all()
    )
    assert stored_dimension_versions[0].effective_to == date(2026, 12, 31)


async def test_job_creation_rejects_unknown_or_inactive_dimensions(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    rejected = await business_client.post(
        "/api/v1/workforce/jobs",
        headers=_auth(admin_token),
        json={
            "code": "JOB_INVALID_DIMENSIONS",
            "name": "无效维度职务",
            "level_code": "UNKNOWN_LEVEL",
            "grade_code": "UNKNOWN_GRADE",
            "class_code": "UNKNOWN_CLASS",
            "sequence_code": "UNKNOWN_SEQUENCE",
            "effective_from": "2026-01-01",
            "status": "active",
            "change_reason": "验证无效维度拒绝",
        },
    )
    assert rejected.status_code == 422, rejected.text
    assert rejected.json()["code"] == "JOB_DIMENSION_NOT_EFFECTIVE"
