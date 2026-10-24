# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""Integration coverage for the performance OKR definition endpoints."""

from collections.abc import AsyncIterator
from datetime import date
from uuid import UUID

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.business_main import create_business_app
from hris.core.database import get_db
from hris.modules.performance.api import router as performance_router
from hris.modules.workforce.models import AuditLog


pytestmark = pytest.mark.asyncio

_PERFORMANCE_ROUTE_PATH = "/api/v1/performance"
_CYCLE_START = date(2026, 1, 1)
_CYCLE_END = date(2026, 3, 31)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _ensure_performance_router(app: FastAPI) -> None:
    for route in app.routes:
        if getattr(route, "path", None) == _PERFORMANCE_ROUTE_PATH:
            return
    app.include_router(performance_router)


@pytest_asyncio.fixture
async def performance_client(
    db_session: AsyncSession,
) -> AsyncIterator[AsyncClient]:
    app = create_business_app()
    _ensure_performance_router(app)

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


async def _create_person(client: AsyncClient, token: str, display_name: str) -> str:
    response = await client.post(
        "/api/v1/workforce/persons",
        headers=_auth(token),
        json={
            "legal_name": display_name,
            "display_name": display_name,
            "reserve_employee_number": False,
            "change_reason": "建立合成人员档案",
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def _create_cycle(
    client: AsyncClient,
    token: str,
    *,
    code: str = "2026Q1",
    name: str = "2026年第一季度绩效周期",
    cycle_type: str = "quarterly",
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/performance/cycles",
        headers=_auth(token),
        json={
            "code": code,
            "name": name,
            "cycle_type": cycle_type,
            "start_date": _CYCLE_START.isoformat(),
            "end_date": _CYCLE_END.isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_objective(
    client: AsyncClient,
    token: str,
    cycle_id: str,
    person_id: str,
    *,
    title: str = "提升交付质量",
    weight: str = "100",
) -> dict[str, object]:
    response = await client.post(
        f"/api/v1/performance/cycles/{cycle_id}/objectives",
        headers=_auth(token),
        json={
            "person_id": person_id,
            "title": title,
            "description": "合成目标说明",
            "weight": weight,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_key_result(
    client: AsyncClient,
    token: str,
    objective_id: str,
    *,
    title: str = "关键结果一",
    weight: str = "60",
    target_value: str | None = None,
    unit: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {"title": title, "weight": weight}
    if target_value is not None:
        payload["target_value"] = target_value
    if unit is not None:
        payload["unit"] = unit
    response = await client.post(
        f"/api/v1/performance/objectives/{objective_id}/key-results",
        headers=_auth(token),
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_cycle_objective_key_results_and_scorecard(
    performance_client: AsyncClient,
    admin_token: str,
) -> None:
    person_id = await _create_person(performance_client, admin_token, "合成绩效人员甲")

    cycle = await _create_cycle(performance_client, admin_token)
    assert cycle["code"] == "2026Q1"
    assert cycle["cycle_type"] == "quarterly"
    assert cycle["status"] == "draft"

    objective = await _create_objective(
        performance_client,
        admin_token,
        str(cycle["id"]),
        person_id,
    )
    assert objective["person_id"] == person_id
    assert objective["weight"] == "100.00"
    assert objective["status"] == "draft"
    assert objective["sequence_no"] == 1

    first = await _create_key_result(
        performance_client,
        admin_token,
        str(objective["id"]),
        title="交付准时率提升",
        weight="60",
        target_value="98",
        unit="%",
    )
    second = await _create_key_result(
        performance_client,
        admin_token,
        str(objective["id"]),
        title="线上缺陷数下降",
        weight="40",
        target_value="12",
        unit="个",
    )
    assert first["sequence_no"] == 1
    assert second["sequence_no"] == 2
    assert first["target_value"] == "98.0000"
    assert first["score"] is None

    scorecard = await performance_client.get(
        f"/api/v1/performance/cycles/{cycle['id']}/scorecard",
        headers=_auth(admin_token),
    )
    assert scorecard.status_code == 200, scorecard.text
    payload = scorecard.json()
    assert payload["cycle_id"] == cycle["id"]
    assert payload["total"] == 1
    entry = payload["entries"][0]
    assert entry["person_id"] == person_id
    assert entry["objective_count"] == 1
    assert entry["objective_total_weight"] == "100.00"
    assert entry["key_result_count"] == 2
    assert entry["key_result_total_weight"] == "100.00"
    assert entry["scored_key_result_count"] == 0
    assert len(entry["objectives"]) == 1
    assert entry["objectives"][0]["key_result_count"] == 2


async def test_objective_weight_sum_over_hundred_returns_422(
    performance_client: AsyncClient,
    admin_token: str,
) -> None:
    first_person = await _create_person(performance_client, admin_token, "合成绩效人员乙")
    second_person = await _create_person(performance_client, admin_token, "合成绩效人员丙")
    cycle = await _create_cycle(performance_client, admin_token, code="2026Q2")

    await _create_objective(
        performance_client,
        admin_token,
        str(cycle["id"]),
        first_person,
        title="目标一",
        weight="60",
    )
    exceeded = await performance_client.post(
        f"/api/v1/performance/cycles/{cycle['id']}/objectives",
        headers=_auth(admin_token),
        json={
            "person_id": first_person,
            "title": "目标二",
            "weight": "50",
        },
    )
    assert exceeded.status_code == 422, exceeded.text
    assert exceeded.json()["code"] == "PERFORMANCE_OBJECTIVE_WEIGHT_EXCEEDED"

    # Requirement: HR-PERF-005 — 权重上限按人独立计算，换人不受影响。
    other_person = await _create_objective(
        performance_client,
        admin_token,
        str(cycle["id"]),
        second_person,
        title="他人目标",
        weight="50",
    )
    assert other_person["person_id"] == second_person


async def test_key_result_weight_sum_over_hundred_returns_422(
    performance_client: AsyncClient,
    admin_token: str,
) -> None:
    person_id = await _create_person(performance_client, admin_token, "合成绩效人员丁")
    cycle = await _create_cycle(performance_client, admin_token, code="2026Q3")
    objective = await _create_objective(
        performance_client,
        admin_token,
        str(cycle["id"]),
        person_id,
    )

    await _create_key_result(
        performance_client,
        admin_token,
        str(objective["id"]),
        title="关键结果一",
        weight="60",
    )
    exceeded = await performance_client.post(
        f"/api/v1/performance/objectives/{objective['id']}/key-results",
        headers=_auth(admin_token),
        json={"title": "关键结果二", "weight": "50"},
    )
    assert exceeded.status_code == 422, exceeded.text
    assert exceeded.json()["code"] == "PERFORMANCE_KEY_RESULT_WEIGHT_EXCEEDED"


async def test_key_result_score_out_of_range_returns_422(
    performance_client: AsyncClient,
    admin_token: str,
) -> None:
    person_id = await _create_person(performance_client, admin_token, "合成绩效人员戊")
    cycle = await _create_cycle(performance_client, admin_token, code="2026Q4")
    objective = await _create_objective(
        performance_client,
        admin_token,
        str(cycle["id"]),
        person_id,
    )
    key_result = await _create_key_result(
        performance_client,
        admin_token,
        str(objective["id"]),
    )

    too_high = await performance_client.patch(
        f"/api/v1/performance/key-results/{key_result['id']}",
        headers=_auth(admin_token),
        json={"score": "150"},
    )
    assert too_high.status_code == 422, too_high.text
    assert too_high.json()["code"] == "PERFORMANCE_SCORE_OUT_OF_RANGE"

    too_low = await performance_client.patch(
        f"/api/v1/performance/key-results/{key_result['id']}",
        headers=_auth(admin_token),
        json={"score": "-1"},
    )
    assert too_low.status_code == 422, too_low.text
    assert too_low.json()["code"] == "PERFORMANCE_SCORE_OUT_OF_RANGE"

    accepted = await performance_client.patch(
        f"/api/v1/performance/key-results/{key_result['id']}",
        headers=_auth(admin_token),
        json={"score": "88.5", "actual_value": "95"},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["score"] == "88.50"
    assert accepted.json()["actual_value"] == "95.0000"


async def test_unscored_okr_score_is_null_instead_of_zero(
    performance_client: AsyncClient,
    admin_token: str,
) -> None:
    person_id = await _create_person(performance_client, admin_token, "合成绩效人员己")
    cycle = await _create_cycle(performance_client, admin_token, code="2026Q5")
    objective = await _create_objective(
        performance_client,
        admin_token,
        str(cycle["id"]),
        person_id,
    )
    key_result = await _create_key_result(
        performance_client,
        admin_token,
        str(objective["id"]),
    )

    unscored = await performance_client.get(
        f"/api/v1/performance/cycles/{cycle['id']}/scorecard",
        headers=_auth(admin_token),
    )
    assert unscored.status_code == 200, unscored.text
    entry = unscored.json()["entries"][0]
    # Requirement: HR-PERF-012 — 全部未评分时加权得分必须是 null，不能是 0。
    assert entry["weighted_score"] is None
    assert entry["objectives"][0]["objective_score"] is None
    assert entry["scored_key_result_count"] == 0

    await performance_client.patch(
        f"/api/v1/performance/key-results/{key_result['id']}",
        headers=_auth(admin_token),
        json={"score": "80"},
    )
    scored = await performance_client.get(
        f"/api/v1/performance/cycles/{cycle['id']}/scorecard",
        headers=_auth(admin_token),
    )
    assert scored.status_code == 200, scored.text
    scored_entry = scored.json()["entries"][0]
    assert scored_entry["scored_key_result_count"] == 1
    assert scored_entry["weighted_score"] == "80.00"
    assert scored_entry["objectives"][0]["objective_score"] == "80.00"


async def test_missing_permission_returns_403(
    performance_client: AsyncClient,
    restricted_token: str,
) -> None:
    denied = await performance_client.post(
        "/api/v1/performance/cycles",
        headers=_auth(restricted_token),
        json={
            "code": "2026Q9",
            "name": "无权限周期",
            "cycle_type": "quarterly",
            "start_date": _CYCLE_START.isoformat(),
            "end_date": _CYCLE_END.isoformat(),
        },
    )
    assert denied.status_code == 403, denied.text
    assert denied.json()["code"] == "PERMISSION_DENIED"

    listed = await performance_client.get(
        "/api/v1/performance/cycles",
        headers=_auth(restricted_token),
    )
    assert listed.status_code == 403, listed.text


async def test_objective_weight_change_revalidates_cycle_weight_sum(
    performance_client: AsyncClient,
    admin_token: str,
) -> None:
    person_id = await _create_person(performance_client, admin_token, "合成绩效人员庚")
    cycle = await _create_cycle(performance_client, admin_token, code="2026Q6")
    first = await _create_objective(
        performance_client,
        admin_token,
        str(cycle["id"]),
        person_id,
        title="目标一",
        weight="60",
    )
    await _create_objective(
        performance_client,
        admin_token,
        str(cycle["id"]),
        person_id,
        title="目标二",
        weight="40",
    )

    # Requirement: HR-PERF-013 — 权重上调后必须重新校验周期内同一人权重之和。
    exceeded = await performance_client.patch(
        f"/api/v1/performance/objectives/{first['id']}",
        headers=_auth(admin_token),
        json={"weight": "70"},
    )
    assert exceeded.status_code == 422, exceeded.text
    assert exceeded.json()["code"] == "PERFORMANCE_OBJECTIVE_WEIGHT_EXCEEDED"

    accepted = await performance_client.patch(
        f"/api/v1/performance/objectives/{first['id']}",
        headers=_auth(admin_token),
        json={"weight": "50"},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["weight"] == "50.00"

    grouped = await performance_client.get(
        f"/api/v1/performance/cycles/{cycle['id']}/objectives?group_by_person=true",
        headers=_auth(admin_token),
    )
    assert grouped.status_code == 200, grouped.text
    group = grouped.json()["person_groups"][0]
    assert group["person_id"] == person_id
    assert group["objective_count"] == 2
    assert group["objective_total_weight"] == "90.00"


async def test_okr_writes_are_audited_without_employee_names(
    performance_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    person_id = await _create_person(performance_client, admin_token, "合成审计人员")
    cycle = await _create_cycle(performance_client, admin_token, code="2026Q7")
    objective = await _create_objective(
        performance_client,
        admin_token,
        str(cycle["id"]),
        person_id,
    )
    await _create_key_result(
        performance_client,
        admin_token,
        str(objective["id"]),
    )

    logs = list(
        (
            await db_session.scalars(
                select(AuditLog)
                .where(AuditLog.object_type == "performance_objective")
                .order_by(AuditLog.occurred_at)
            )
        ).all()
    )
    assert logs
    payload = logs[-1].after_payload
    assert payload["person_id"] == person_id
    assert payload["cycle_id"] == str(cycle["id"])
    # Requirement: HR-PERF-011 — 审计与日志不得包含员工姓名等个人信息。
    assert "合成审计人员" not in str(payload)


async def test_delete_key_result_removes_it_from_objective(
    performance_client: AsyncClient,
    admin_token: str,
) -> None:
    person_id = await _create_person(performance_client, admin_token, "合成绩效人员辛")
    cycle = await _create_cycle(performance_client, admin_token, code="2026Q8")
    objective = await _create_objective(
        performance_client,
        admin_token,
        str(cycle["id"]),
        person_id,
    )
    key_result = await _create_key_result(
        performance_client,
        admin_token,
        str(objective["id"]),
    )

    deleted = await performance_client.delete(
        f"/api/v1/performance/key-results/{key_result['id']}",
        headers=_auth(admin_token),
    )
    assert deleted.status_code == 204, deleted.text
    assert deleted.content == b""

    listed = await performance_client.get(
        f"/api/v1/performance/cycles/{cycle['id']}/objectives",
        headers=_auth(admin_token),
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["items"][0]["key_results"] == []

    missing = await performance_client.delete(
        f"/api/v1/performance/key-results/{key_result['id']}",
        headers=_auth(admin_token),
    )
    assert missing.status_code == 404, missing.text
    assert missing.json()["code"] == "PERFORMANCE_KEY_RESULT_NOT_FOUND"
