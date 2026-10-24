# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""批量异动（方案制）后端接口的集成测试。"""

from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from enterprise_support import requires_enterprise
from hris.business_main import create_business_app
from hris.core.config import get_settings
from hris.core.database import get_db
from hris.modules.workflow.models import WorkflowDefinition, WorkflowInstance
from hris.modules.workforce.batch_change_api import router as batch_change_router
from hris.modules.workforce.batch_change_models import HrEventBatch
from hris.modules.workforce.models import Employment, HrEvent, Person


pytestmark = pytest.mark.asyncio

_BATCH_ROUTE_PATH = "/api/v1/workforce/batch-changes"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _business_date() -> date:
    return datetime.now(ZoneInfo(get_settings().business_timezone)).date()


def _ensure_batch_change_router(app: FastAPI) -> None:
    for route in app.routes:
        if getattr(route, "path", None) == _BATCH_ROUTE_PATH:
            return
    app.include_router(batch_change_router)


@pytest_asyncio.fixture
async def batch_client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    app = create_business_app()
    _ensure_batch_change_router(app)

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


async def _create_employment(
    db_session: AsyncSession,
    employee_number: str,
) -> Employment:
    today = _business_date()
    person = Person(
        employee_number=employee_number,
        legal_name="合成批量异动人员",
        display_name="合成批量异动人员",
        status="active",
    )
    db_session.add(person)
    await db_session.flush()
    employment = Employment(
        person_id=person.id,
        employee_type_code="REGULAR",
        status="active",
        planned_start_date=today - timedelta(days=30),
        actual_start_date=today - timedelta(days=30),
        version=1,
    )
    db_session.add(employment)
    await db_session.flush()
    return employment


def _line_payload(
    employment_id: UUID,
    *,
    event_type: str = "CONFIRMATION",
    idempotency_key: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "event_type": event_type,
        "object_type": "employment",
        "object_id": str(employment_id),
        "effective_date": _business_date().isoformat(),
        "reason": "合成批量异动",
        "before_payload": {},
        "planned_payload": {},
    }
    if idempotency_key is not None:
        payload["idempotency_key"] = idempotency_key
    return payload


async def _create_batch(
    client: AsyncClient,
    token: str,
    title: str = "合成批量异动方案",
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/workforce/batch-changes",
        headers=_auth(token),
        json={"title": title, "reason": "合成批量异动"},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _append_lines(
    client: AsyncClient,
    token: str,
    batch_id: str,
    lines: list[dict[str, object]],
) -> dict[str, object]:
    response = await client.post(
        f"/api/v1/workforce/batch-changes/{batch_id}/lines",
        headers=_auth(token),
        json={"lines": lines},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_workflow(client: AsyncClient, token: str, code: str) -> str:
    definition = await client.post(
        "/api/v1/workflows/definitions",
        headers=_auth(token),
        json={
            "code": code,
            "name": "合成批量异动审批流程",
            "category": "hr_event_batch",
            "nodes": [
                {"code": "START", "name": "Start", "node_type": "start"},
                {
                    "code": "APPROVE",
                    "name": "Approve",
                    "node_type": "approval",
                    "sign_mode": "any",
                    "assignees": [{"assignee_type": "role", "assignee_ref": "HR_ADMIN"}],
                },
                {"code": "END", "name": "End", "node_type": "end"},
            ],
            "edges": [
                {"source": "START", "target": "APPROVE"},
                {"source": "APPROVE", "target": "END"},
            ],
            "change_reason": "合成批量异动审批流程",
        },
    )
    assert definition.status_code == 201, definition.text
    published = await client.post(
        f"/api/v1/lifecycle/workflows/{definition.json()['id']}/publish",
        headers=_auth(token),
    )
    assert published.status_code == 200, published.text
    return str(definition.json()["id"])


async def test_create_batch_append_lines_and_show_detail(
    batch_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    employment = await _create_employment(db_session, "990101")

    created = await _create_batch(batch_client, admin_token, "2026Q3批量调薪")
    assert created["status"] == "draft"
    assert created["line_count"] == 0
    assert created["workflow_instance_id"] is None
    assert str(created["batch_number"]).startswith("B")

    appended = await _append_lines(
        batch_client,
        admin_token,
        str(created["id"]),
        [
            _line_payload(employment.id),
            _line_payload(employment.id, event_type="EMPLOYMENT_CORRECTION"),
        ],
    )
    assert len(appended["created"]) == 2
    assert appended["skipped"] == []
    assert appended["batch"]["line_count"] == 2
    assert all(line["status"] == "draft" for line in appended["created"])

    detail = await batch_client.get(
        f"/api/v1/workforce/batch-changes/{created['id']}",
        headers=_auth(admin_token),
    )
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert payload["line_count"] == 2
    assert len(payload["lines"]) == 2
    assert {line["event_type"] for line in payload["lines"]} == {
        "CONFIRMATION",
        "EMPLOYMENT_CORRECTION",
    }

    listed = await batch_client.get(
        "/api/v1/workforce/batch-changes?status=draft",
        headers=_auth(admin_token),
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == created["id"]


@requires_enterprise
async def test_submit_creates_single_shared_workflow_instance(
    batch_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    employment = await _create_employment(db_session, "990102")
    created = await _create_batch(batch_client, admin_token)
    await _append_lines(
        batch_client,
        admin_token,
        str(created["id"]),
        [_line_payload(employment.id), _line_payload(employment.id)],
    )
    definition_id = await _create_workflow(
        batch_client,
        admin_token,
        "BATCH_CHANGE_TEST_FLOW",
    )

    submitted = await batch_client.post(
        f"/api/v1/workforce/batch-changes/{created['id']}/submit",
        headers=_auth(admin_token),
        json={"workflow_definition_id": definition_id},
    )
    assert submitted.status_code == 200, submitted.text
    body = submitted.json()
    assert body["status"] == "submitted"
    assert body["workflow_instance_id"] is not None
    assert body["submitted_at"] is not None

    instances = list((await db_session.scalars(select(WorkflowInstance))).all())
    assert len(instances) == 1
    assert str(instances[0].id) == body["workflow_instance_id"]
    assert instances[0].business_object_type == "hr_event_batch"
    assert str(instances[0].business_object_id) == str(created["id"])

    detail = await batch_client.get(
        f"/api/v1/workforce/batch-changes/{created['id']}",
        headers=_auth(admin_token),
    )
    assert detail.status_code == 200, detail.text
    lines = detail.json()["lines"]
    assert len(lines) == 2
    assert {line["workflow_instance_id"] for line in lines} == {
        body["workflow_instance_id"],
    }
    assert all(line["status"] == "pending_approval" for line in lines)


async def test_append_beyond_line_limit_returns_422(
    batch_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    employment = await _create_employment(db_session, "990103")
    created = await _create_batch(batch_client, admin_token)
    batch_id = UUID(str(created["id"]))

    # 直接落满 1000 条明细，验证上限判定只认方案总行数。
    batch = await db_session.get(HrEventBatch, batch_id)
    assert batch is not None
    today = _business_date()
    db_session.add_all(
        [
            HrEvent(
                event_number=f"E-SEED-{index:06d}",
                event_type="CONFIRMATION",
                object_type="employment",
                object_id=employment.id,
                effective_date=today,
                status="draft",
                source="api",
                reason="合成批量异动",
                before_payload={},
                planned_payload={},
                actual_payload={},
                attempts=0,
                version=1,
                batch_id=batch.id,
            )
            for index in range(1000)
        ]
    )
    await db_session.flush()
    batch.line_count = 1000
    await db_session.flush()

    rejected = await batch_client.post(
        f"/api/v1/workforce/batch-changes/{created['id']}/lines",
        headers=_auth(admin_token),
        json={"lines": [_line_payload(employment.id)]},
    )
    assert rejected.status_code == 422, rejected.text
    assert rejected.json()["code"] == "BATCH_CHANGE_LINE_LIMIT_EXCEEDED"

    detail = await batch_client.get(
        f"/api/v1/workforce/batch-changes/{created['id']}",
        headers=_auth(admin_token),
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["line_count"] == 1000
    assert len(detail.json()["lines"]) == 1000


@requires_enterprise
async def test_non_draft_batch_rejects_line_changes_and_submit(
    batch_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    employment = await _create_employment(db_session, "990104")
    created = await _create_batch(batch_client, admin_token)
    appended = await _append_lines(
        batch_client,
        admin_token,
        str(created["id"]),
        [_line_payload(employment.id)],
    )
    line_id = str(appended["created"][0]["id"])
    definition_id = await _create_workflow(
        batch_client,
        admin_token,
        "BATCH_CHANGE_TEST_FLOW",
    )
    submitted = await batch_client.post(
        f"/api/v1/workforce/batch-changes/{created['id']}/submit",
        headers=_auth(admin_token),
        json={"workflow_definition_id": definition_id},
    )
    assert submitted.status_code == 200, submitted.text

    appended_again = await batch_client.post(
        f"/api/v1/workforce/batch-changes/{created['id']}/lines",
        headers=_auth(admin_token),
        json={"lines": [_line_payload(employment.id)]},
    )
    assert appended_again.status_code == 409, appended_again.text
    assert appended_again.json()["code"] == "BATCH_CHANGE_NOT_DRAFT"

    removed = await batch_client.delete(
        f"/api/v1/workforce/batch-changes/{created['id']}/lines/{line_id}",
        headers=_auth(admin_token),
    )
    assert removed.status_code == 409, removed.text
    assert removed.json()["code"] == "BATCH_CHANGE_NOT_DRAFT"

    submitted_again = await batch_client.post(
        f"/api/v1/workforce/batch-changes/{created['id']}/submit",
        headers=_auth(admin_token),
        json={"workflow_definition_id": definition_id},
    )
    assert submitted_again.status_code == 409, submitted_again.text
    assert submitted_again.json()["code"] == "BATCH_CHANGE_NOT_DRAFT"


async def test_batch_change_requires_lifecycle_admin_permission(
    batch_client: AsyncClient,
    restricted_token: str,
) -> None:
    created = await batch_client.post(
        "/api/v1/workforce/batch-changes",
        headers=_auth(restricted_token),
        json={"title": "无权限方案", "reason": "合成批量异动"},
    )
    assert created.status_code == 403, created.text
    assert created.json()["code"] == "PERMISSION_DENIED"

    listed = await batch_client.get(
        "/api/v1/workforce/batch-changes",
        headers=_auth(restricted_token),
    )
    assert listed.status_code == 403, listed.text


async def test_idempotency_key_prevents_duplicate_lines(
    batch_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    employment = await _create_employment(db_session, "990105")
    created = await _create_batch(batch_client, admin_token)
    idempotency_key = "3f2b8a1c-5d47-4a90-9c11-0b6d5e7a1234"
    line = _line_payload(employment.id, idempotency_key=idempotency_key)

    first = await _append_lines(
        batch_client,
        admin_token,
        str(created["id"]),
        [line],
    )
    assert len(first["created"]) == 1
    assert first["skipped"] == []
    assert first["batch"]["line_count"] == 1

    second = await _append_lines(
        batch_client,
        admin_token,
        str(created["id"]),
        [line],
    )
    assert len(second["created"]) == 0
    assert len(second["skipped"]) == 1
    assert second["skipped"][0]["id"] == first["created"][0]["id"]
    assert second["batch"]["line_count"] == 1

    detail = await batch_client.get(
        f"/api/v1/workforce/batch-changes/{created['id']}",
        headers=_auth(admin_token),
    )
    assert detail.status_code == 200, detail.text
    assert len(detail.json()["lines"]) == 1

    conflicting = await batch_client.post(
        f"/api/v1/workforce/batch-changes/{created['id']}/lines",
        headers=_auth(admin_token),
        json={
            "lines": [
                _line_payload(
                    employment.id,
                    event_type="EMPLOYMENT_CORRECTION",
                    idempotency_key=idempotency_key,
                )
            ]
        },
    )
    assert conflicting.status_code == 409, conflicting.text
    assert conflicting.json()["code"] == "BATCH_CHANGE_IDEMPOTENCY_CONFLICT"


async def test_remove_line_drops_line_count(
    batch_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    employment = await _create_employment(db_session, "990106")
    created = await _create_batch(batch_client, admin_token)
    appended = await _append_lines(
        batch_client,
        admin_token,
        str(created["id"]),
        [_line_payload(employment.id), _line_payload(employment.id)],
    )
    line_id = str(appended["created"][0]["id"])

    removed = await batch_client.delete(
        f"/api/v1/workforce/batch-changes/{created['id']}/lines/{line_id}",
        headers=_auth(admin_token),
    )
    assert removed.status_code == 204, removed.text
    assert removed.content == b""

    detail = await batch_client.get(
        f"/api/v1/workforce/batch-changes/{created['id']}",
        headers=_auth(admin_token),
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["line_count"] == 1
    assert len(detail.json()["lines"]) == 1

    missing = await batch_client.delete(
        f"/api/v1/workforce/batch-changes/{created['id']}/lines/{line_id}",
        headers=_auth(admin_token),
    )
    assert missing.status_code == 404, missing.text
    assert missing.json()["code"] == "BATCH_CHANGE_LINE_NOT_FOUND"


@requires_enterprise
async def test_submit_without_workflow_definition_uses_default_flow(
    batch_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    employment = await _create_employment(db_session, "990107")
    created = await _create_batch(batch_client, admin_token)
    await _append_lines(
        batch_client,
        admin_token,
        str(created["id"]),
        [_line_payload(employment.id)],
    )
    configured = await db_session.scalar(
        select(WorkflowDefinition).where(
            WorkflowDefinition.code == "BATCH_CHANGE_APPROVAL"
        )
    )

    submitted = await batch_client.post(
        f"/api/v1/workforce/batch-changes/{created['id']}/submit",
        headers=_auth(admin_token),
        json={},
    )
    if configured is None:
        # 未配置默认批量异动审批流程时，明确拒绝而不是落到任意流程上。
        assert submitted.status_code == 422, submitted.text
        assert submitted.json()["code"] == "BATCH_CHANGE_WORKFLOW_NOT_CONFIGURED"
        return

    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "submitted"
    assert submitted.json()["workflow_instance_id"] is not None
