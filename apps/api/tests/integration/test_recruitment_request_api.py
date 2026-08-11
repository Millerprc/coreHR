from datetime import UTC, date, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from hris.modules.workforce.models import JobCatalog, Organization


pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_recruitment_request_is_visible_but_not_blocked_by_headcount_freeze(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    period_month = date.today().replace(day=1)
    organization = Organization(code="733001")
    job = JobCatalog(
        code="JOB-REQ-SYNTHETIC",
        name="合成招聘职务",
        status="active",
        effective_from=period_month,
        attributes={},
    )
    db_session.add_all([organization, job])
    await db_session.flush()

    future_job = JobCatalog(
        code="JOB-REQ-FUTURE",
        name="未来生效职务",
        status="active",
        effective_from=period_month + timedelta(days=40),
        attributes={},
    )
    db_session.add(future_job)
    await db_session.flush()

    rejected = await business_client.post(
        "/api/v1/lifecycle/recruitment-requests",
        headers=_auth(admin_token),
        json={
            "organization_id": str(organization.id),
            "job_id": str(future_job.id),
            "requested_count": 1,
            "target_month": period_month.isoformat(),
            "reason": "验证招聘月份必须使用已生效职务",
        },
    )
    assert rejected.status_code == 422, rejected.text
    assert rejected.json()["code"] == "JOB_NOT_EFFECTIVE"

    freeze = await business_client.post(
        "/api/v1/workforce/headcount-freezes",
        headers=_auth(admin_token),
        json={
            "freeze_type": "business",
            "period_month": period_month.isoformat(),
            "organization_id": str(organization.id),
            "job_id": str(job.id),
            "starts_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
            "reason": "合成业务冻结",
        },
    )
    assert freeze.status_code == 201, freeze.text

    created = await business_client.post(
        "/api/v1/lifecycle/recruitment-requests",
        headers=_auth(admin_token),
        json={
            "organization_id": str(organization.id),
            "job_id": str(job.id),
            "requested_count": 3,
            "target_month": period_month.isoformat(),
            "reason": "冻结期间仍可提出招聘需求",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "draft"
    assert created.json()["request_number"].startswith("R")

    job.effective_to = period_month + timedelta(days=40)
    await db_session.flush()
    invalid_target = await business_client.patch(
        f"/api/v1/lifecycle/recruitment-requests/{created.json()['id']}",
        headers=_auth(admin_token),
        json={
            "target_month": (period_month + timedelta(days=90)).replace(day=1).isoformat(),
            "change_reason": "验证变更目标月份时重新检查职务有效期",
        },
    )
    assert invalid_target.status_code == 422, invalid_target.text
    assert invalid_target.json()["code"] == "JOB_NOT_EFFECTIVE"
    job.effective_to = None
    await db_session.flush()

    listed = await business_client.get(
        "/api/v1/lifecycle/recruitment-requests",
        headers=_auth(admin_token),
        params={"organization_id": str(organization.id)},
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == created.json()["id"]

    submitted = await business_client.patch(
        f"/api/v1/lifecycle/recruitment-requests/{created.json()['id']}",
        headers=_auth(admin_token),
        json={"status": "submitted", "change_reason": "提交招聘需求"},
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "submitted"

    invalid_return = await business_client.patch(
        f"/api/v1/lifecycle/recruitment-requests/{created.json()['id']}",
        headers=_auth(admin_token),
        json={"status": "draft", "change_reason": "错误退回"},
    )
    assert invalid_return.status_code == 409
    assert invalid_return.json()["code"] == "RECRUITMENT_STATUS_TRANSITION_INVALID"

    closed = await business_client.patch(
        f"/api/v1/lifecycle/recruitment-requests/{created.json()['id']}",
        headers=_auth(admin_token),
        json={"status": "closed", "change_reason": "结束招聘"},
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
