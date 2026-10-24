# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from hris.business_main import create_business_app
from hris.core.config import get_settings
from hris.core.database import get_db
from hris.modules.workforce.labels_api import router as labels_router


pytestmark = pytest.mark.asyncio

_LABELS_ROUTE_PATH = "/api/v1/workforce/labels"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _business_date() -> date:
    return datetime.now(ZoneInfo(get_settings().business_timezone)).date()


def _ensure_labels_router(app: FastAPI) -> None:
    for route in app.routes:
        if getattr(route, "path", None) == _LABELS_ROUTE_PATH:
            return
    app.include_router(labels_router)


@pytest_asyncio.fixture
async def labels_client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    app = create_business_app()
    _ensure_labels_router(app)

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


async def _create_person(
    client: AsyncClient,
    token: str,
    legal_name: str,
) -> str:
    response = await client.post(
        "/api/v1/workforce/persons",
        headers=_auth(token),
        json={
            "legal_name": legal_name,
            "display_name": legal_name,
            "reserve_employee_number": False,
            "change_reason": "建立合成人员档案",
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def _create_label(
    client: AsyncClient,
    token: str,
    person_id: str,
    *,
    label_name: str,
    label_type: str,
    effective_from: date,
    effective_to: date | None = None,
    source: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "label_name": label_name,
        "label_type": label_type,
        "effective_from": effective_from.isoformat(),
    }
    if effective_to is not None:
        payload["effective_to"] = effective_to.isoformat()
    if source is not None:
        payload["source"] = source
    response = await client.post(
        f"/api/v1/workforce/persons/{person_id}/labels",
        headers=_auth(token),
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_label_and_query_by_person(
    labels_client: AsyncClient,
    admin_token: str,
) -> None:
    person_id = await _create_person(labels_client, admin_token, "合成标签人员")
    today = _business_date()

    created = await _create_label(
        labels_client,
        admin_token,
        person_id,
        label_name="核心人才",
        label_type="TALENT",
        effective_from=today,
    )
    assert created["person_id"] == person_id
    assert created["label_name"] == "核心人才"
    assert created["label_type"] == "TALENT"
    assert created["source"] == "MANUAL"
    assert created["is_ai_generated"] is False
    assert created["status"] == "active"
    assert created["effective_from"] == today.isoformat()
    assert created["effective_to"] is None

    listed = await labels_client.get(
        f"/api/v1/workforce/persons/{person_id}/labels",
        headers=_auth(admin_token),
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == created["id"]


async def test_label_query_uses_half_open_effective_period(
    labels_client: AsyncClient,
    admin_token: str,
) -> None:
    person_id = await _create_person(labels_client, admin_token, "合成区间人员")
    today = _business_date()
    future = today + timedelta(days=30)

    await _create_label(
        labels_client,
        admin_token,
        person_id,
        label_name="未来标签",
        label_type="PLAN",
        effective_from=future,
    )
    await _create_label(
        labels_client,
        admin_token,
        person_id,
        label_name="当期标签",
        label_type="TALENT",
        effective_from=today,
        effective_to=future,
    )

    current = await labels_client.get(
        f"/api/v1/workforce/persons/{person_id}/labels",
        headers=_auth(admin_token),
    )
    assert current.status_code == 200, current.text
    assert current.json()["total"] == 1
    assert current.json()["items"][0]["label_name"] == "当期标签"

    future_view = await labels_client.get(
        f"/api/v1/workforce/persons/{person_id}/labels?effective_at={future.isoformat()}",
        headers=_auth(admin_token),
    )
    assert future_view.status_code == 200, future_view.text
    assert future_view.json()["total"] == 1
    assert future_view.json()["items"][0]["label_name"] == "未来标签"


async def test_ai_source_derives_is_ai_generated_flag(
    labels_client: AsyncClient,
    admin_token: str,
) -> None:
    person_id = await _create_person(labels_client, admin_token, "合成AI标签人员")
    today = _business_date()

    ai_label = await _create_label(
        labels_client,
        admin_token,
        person_id,
        label_name="高潜人才",
        label_type="TALENT",
        effective_from=today,
        source="AI",
    )
    assert ai_label["source"] == "AI"
    assert ai_label["is_ai_generated"] is True

    manual_label = await _create_label(
        labels_client,
        admin_token,
        person_id,
        label_name="骨干人才",
        label_type="TALENT",
        effective_from=today,
        source="manual",
    )
    assert manual_label["source"] == "MANUAL"
    assert manual_label["is_ai_generated"] is False

    rejected = await labels_client.post(
        f"/api/v1/workforce/persons/{person_id}/labels",
        headers=_auth(admin_token),
        json={
            "label_name": "非法来源",
            "label_type": "TALENT",
            "source": "IMPORT",
            "effective_from": today.isoformat(),
        },
    )
    assert rejected.status_code == 422, rejected.text
    assert rejected.json()["code"] == "REQUEST_VALIDATION_FAILED"


async def test_global_label_query_supports_filters_and_paging(
    labels_client: AsyncClient,
    admin_token: str,
) -> None:
    first_person = await _create_person(labels_client, admin_token, "合成标签人员甲")
    second_person = await _create_person(labels_client, admin_token, "合成标签人员乙")
    today = _business_date()

    await _create_label(
        labels_client,
        admin_token,
        first_person,
        label_name="核心人才",
        label_type="TALENT",
        effective_from=today,
    )
    await _create_label(
        labels_client,
        admin_token,
        first_person,
        label_name="Python",
        label_type="SKILL",
        effective_from=today,
        source="AI",
    )
    await _create_label(
        labels_client,
        admin_token,
        second_person,
        label_name="骨干人才",
        label_type="TALENT",
        effective_from=today,
    )

    everything = await labels_client.get(
        "/api/v1/workforce/labels",
        headers=_auth(admin_token),
    )
    assert everything.status_code == 200, everything.text
    assert everything.json()["total"] == 3
    assert everything.json()["page"] == 1
    assert everything.json()["page_size"] == 20

    by_type = await labels_client.get(
        "/api/v1/workforce/labels?label_type=TALENT",
        headers=_auth(admin_token),
    )
    assert by_type.status_code == 200, by_type.text
    assert by_type.json()["total"] == 2
    assert {item["label_type"] for item in by_type.json()["items"]} == {"TALENT"}

    by_source = await labels_client.get(
        "/api/v1/workforce/labels?source=AI",
        headers=_auth(admin_token),
    )
    assert by_source.status_code == 200, by_source.text
    assert by_source.json()["total"] == 1
    assert by_source.json()["items"][0]["source"] == "AI"

    by_person = await labels_client.get(
        f"/api/v1/workforce/labels?person_id={first_person}",
        headers=_auth(admin_token),
    )
    assert by_person.status_code == 200, by_person.text
    assert by_person.json()["total"] == 2

    combined = await labels_client.get(
        f"/api/v1/workforce/labels?label_type=TALENT&source=MANUAL&person_id={first_person}",
        headers=_auth(admin_token),
    )
    assert combined.status_code == 200, combined.text
    assert combined.json()["total"] == 1
    assert combined.json()["items"][0]["label_name"] == "核心人才"

    first_page = await labels_client.get(
        "/api/v1/workforce/labels?page=1&page_size=2",
        headers=_auth(admin_token),
    )
    assert first_page.status_code == 200, first_page.text
    assert first_page.json()["total"] == 3
    assert first_page.json()["page"] == 1
    assert first_page.json()["page_size"] == 2
    assert len(first_page.json()["items"]) == 2

    second_page = await labels_client.get(
        "/api/v1/workforce/labels?page=2&page_size=2",
        headers=_auth(admin_token),
    )
    assert second_page.status_code == 200, second_page.text
    assert second_page.json()["total"] == 3
    assert second_page.json()["page"] == 2
    assert len(second_page.json()["items"]) == 1


async def test_label_types_are_aggregated_by_current_valid_count(
    labels_client: AsyncClient,
    admin_token: str,
) -> None:
    first_person = await _create_person(labels_client, admin_token, "合成标签人员甲")
    second_person = await _create_person(labels_client, admin_token, "合成标签人员乙")
    today = _business_date()

    await _create_label(
        labels_client,
        admin_token,
        first_person,
        label_name="核心人才",
        label_type="TALENT",
        effective_from=today,
    )
    await _create_label(
        labels_client,
        admin_token,
        second_person,
        label_name="骨干人才",
        label_type="TALENT",
        effective_from=today,
    )
    await _create_label(
        labels_client,
        admin_token,
        first_person,
        label_name="Python",
        label_type="SKILL",
        effective_from=today,
    )

    types = await labels_client.get(
        "/api/v1/workforce/label-types",
        headers=_auth(admin_token),
    )
    assert types.status_code == 200, types.text
    items = types.json()["items"]
    assert [item["code"] for item in items] == ["TALENT", "SKILL"]
    assert items[0]["count"] == 2
    assert items[1]["count"] == 1
    assert items[0]["name"] == "TALENT"


async def test_delete_label_soft_ends_it_and_rejects_repeated_call(
    labels_client: AsyncClient,
    admin_token: str,
) -> None:
    person_id = await _create_person(labels_client, admin_token, "合成结束标签人员")
    today = _business_date()

    created = await _create_label(
        labels_client,
        admin_token,
        person_id,
        label_name="核心人才",
        label_type="TALENT",
        effective_from=today,
    )
    label_id = str(created["id"])

    ended = await labels_client.delete(
        f"/api/v1/workforce/person-labels/{label_id}",
        headers=_auth(admin_token),
    )
    assert ended.status_code == 204, ended.text
    assert ended.content == b""

    listed = await labels_client.get(
        f"/api/v1/workforce/persons/{person_id}/labels",
        headers=_auth(admin_token),
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 0

    current = await labels_client.get(
        "/api/v1/workforce/labels",
        headers=_auth(admin_token),
    )
    assert current.status_code == 200, current.text
    assert current.json()["total"] == 0

    with_expired = await labels_client.get(
        "/api/v1/workforce/labels?include_expired=true",
        headers=_auth(admin_token),
    )
    assert with_expired.status_code == 200, with_expired.text
    assert with_expired.json()["total"] == 1
    assert with_expired.json()["items"][0]["effective_to"] == today.isoformat()
    assert with_expired.json()["items"][0]["status"] == "ended"

    repeated = await labels_client.delete(
        f"/api/v1/workforce/person-labels/{label_id}",
        headers=_auth(admin_token),
    )
    assert repeated.status_code == 409, repeated.text
    assert repeated.json()["code"] == "PERSON_LABEL_ALREADY_ENDED"

    missing = await labels_client.delete(
        "/api/v1/workforce/person-labels/00000000-0000-0000-0000-000000000000",
        headers=_auth(admin_token),
    )
    assert missing.status_code == 404, missing.text
    assert missing.json()["code"] == "PERSON_LABEL_NOT_FOUND"


async def test_duplicate_label_returns_conflict(
    labels_client: AsyncClient,
    admin_token: str,
) -> None:
    person_id = await _create_person(labels_client, admin_token, "合成重复标签人员")
    today = _business_date()

    await _create_label(
        labels_client,
        admin_token,
        person_id,
        label_name="核心人才",
        label_type="TALENT",
        effective_from=today,
    )
    duplicated = await labels_client.post(
        f"/api/v1/workforce/persons/{person_id}/labels",
        headers=_auth(admin_token),
        json={
            "label_name": "核心人才",
            "label_type": "TALENT",
            "effective_from": today.isoformat(),
        },
    )
    assert duplicated.status_code == 409, duplicated.text
    assert duplicated.json()["code"] == "PERSON_LABEL_DUPLICATE"


async def test_label_creation_validates_person_and_effective_period(
    labels_client: AsyncClient,
    admin_token: str,
) -> None:
    person_id = await _create_person(labels_client, admin_token, "合成校验标签人员")
    today = _business_date()

    unknown_person = await labels_client.post(
        "/api/v1/workforce/persons/00000000-0000-0000-0000-000000000000/labels",
        headers=_auth(admin_token),
        json={
            "label_name": "核心人才",
            "label_type": "TALENT",
            "effective_from": today.isoformat(),
        },
    )
    assert unknown_person.status_code == 422, unknown_person.text
    assert unknown_person.json()["code"] == "PERSON_LABEL_PERSON_NOT_FOUND"

    invalid_period = await labels_client.post(
        f"/api/v1/workforce/persons/{person_id}/labels",
        headers=_auth(admin_token),
        json={
            "label_name": "核心人才",
            "label_type": "TALENT",
            "effective_from": today.isoformat(),
            "effective_to": (today - timedelta(days=1)).isoformat(),
        },
    )
    assert invalid_period.status_code == 422, invalid_period.text
    assert invalid_period.json()["code"] == "REQUEST_VALIDATION_FAILED"

    blank_name = await labels_client.post(
        f"/api/v1/workforce/persons/{person_id}/labels",
        headers=_auth(admin_token),
        json={
            "label_name": "   ",
            "label_type": "TALENT",
            "effective_from": today.isoformat(),
        },
    )
    assert blank_name.status_code == 422, blank_name.text
    assert blank_name.json()["code"] == "REQUEST_VALIDATION_FAILED"

    too_long_name = await labels_client.post(
        f"/api/v1/workforce/persons/{person_id}/labels",
        headers=_auth(admin_token),
        json={
            "label_name": "标" * 256,
            "label_type": "TALENT",
            "effective_from": today.isoformat(),
        },
    )
    assert too_long_name.status_code == 422, too_long_name.text
    assert too_long_name.json()["code"] == "REQUEST_VALIDATION_FAILED"

    too_long_type = await labels_client.post(
        f"/api/v1/workforce/persons/{person_id}/labels",
        headers=_auth(admin_token),
        json={
            "label_name": "核心人才",
            "label_type": "类" * 101,
            "effective_from": today.isoformat(),
        },
    )
    assert too_long_type.status_code == 422, too_long_type.text
    assert too_long_type.json()["code"] == "REQUEST_VALIDATION_FAILED"


async def test_label_library_returns_seeded_types_and_items(
    labels_client: AsyncClient,
    admin_token: str,
) -> None:
    response = await labels_client.get(
        "/api/v1/workforce/label-library",
        headers=_auth(admin_token),
    )
    assert response.status_code == 200, response.text
    types = {item["type_code"]: item for item in response.json()["items"]}
    assert "TECH_SKILL" in types
    assert types["TECH_SKILL"]["type_name"] == "技术技能"
    codes = {entry["code"] for entry in types["TECH_SKILL"]["items"]}
    assert "PY_LANG" in codes
    names = {entry["code"]: entry["name"] for entry in types["TECH_SKILL"]["items"]}
    assert names["PY_LANG"] == "Python"


async def test_batch_creates_labels_from_library(
    labels_client: AsyncClient,
    admin_token: str,
) -> None:
    person_id = await _create_person(labels_client, admin_token, "合成批量标签人员")
    today = _business_date()

    response = await labels_client.post(
        f"/api/v1/workforce/persons/{person_id}/labels/batch",
        headers=_auth(admin_token),
        json={
            "effective_from": today.isoformat(),
            "source": "MANUAL",
            "labels": [
                {"label_type_code": "TECH_SKILL", "label_code": "PY_LANG"},
                {"label_type_code": "TECH_SKILL", "label_code": "JAVA_LANG"},
            ],
        },
    )
    assert response.status_code == 201, response.text
    created = response.json()["created"]
    assert len(created) == 2
    assert {item["label_type"] for item in created} == {"TECH_SKILL"}
    assert {item["label_name"] for item in created} == {"Python", "Java"}
    assert {item["source"] for item in created} == {"MANUAL"}
    assert all(item["is_ai_generated"] is False for item in created)

    listed = await labels_client.get(
        f"/api/v1/workforce/persons/{person_id}/labels",
        headers=_auth(admin_token),
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 2


async def test_batch_rejects_unknown_library_item_atomically(
    labels_client: AsyncClient,
    admin_token: str,
) -> None:
    person_id = await _create_person(labels_client, admin_token, "合成越界标签人员")
    today = _business_date()

    response = await labels_client.post(
        f"/api/v1/workforce/persons/{person_id}/labels/batch",
        headers=_auth(admin_token),
        json={
            "effective_from": today.isoformat(),
            "labels": [
                {"label_type_code": "TECH_SKILL", "label_code": "PY_LANG"},
                {"label_type_code": "TECH_SKILL", "label_code": "NOT_IN_LIBRARY"},
            ],
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "PERSON_LABEL_LIBRARY_ITEM_NOT_FOUND"

    listed = await labels_client.get(
        f"/api/v1/workforce/persons/{person_id}/labels",
        headers=_auth(admin_token),
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 0


async def test_batch_rejects_duplicated_library_item_in_request(
    labels_client: AsyncClient,
    admin_token: str,
) -> None:
    person_id = await _create_person(labels_client, admin_token, "合成重复标签人员")
    today = _business_date()

    response = await labels_client.post(
        f"/api/v1/workforce/persons/{person_id}/labels/batch",
        headers=_auth(admin_token),
        json={
            "effective_from": today.isoformat(),
            "labels": [
                {"label_type_code": "TECH_SKILL", "label_code": "PY_LANG"},
                {"label_type_code": "TECH_SKILL", "label_code": "PY_LANG"},
            ],
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "REQUEST_VALIDATION_FAILED"


async def test_batch_rejects_existing_duplicate(
    labels_client: AsyncClient,
    admin_token: str,
) -> None:
    person_id = await _create_person(labels_client, admin_token, "合成重复赋予人员")
    today = _business_date()
    payload = {
        "effective_from": today.isoformat(),
        "labels": [{"label_type_code": "TECH_SKILL", "label_code": "PY_LANG"}],
    }

    first = await labels_client.post(
        f"/api/v1/workforce/persons/{person_id}/labels/batch",
        headers=_auth(admin_token),
        json=payload,
    )
    assert first.status_code == 201, first.text

    second = await labels_client.post(
        f"/api/v1/workforce/persons/{person_id}/labels/batch",
        headers=_auth(admin_token),
        json=payload,
    )
    assert second.status_code == 409, second.text
    assert second.json()["code"] == "PERSON_LABEL_DUPLICATE"


async def test_batch_requires_workforce_admin(
    labels_client: AsyncClient,
    restricted_token: str,
) -> None:
    response = await labels_client.post(
        "/api/v1/workforce/persons/00000000-0000-0000-0000-000000000001/labels/batch",
        headers=_auth(restricted_token),
        json={
            "effective_from": _business_date().isoformat(),
            "labels": [{"label_type_code": "TECH_SKILL", "label_code": "PY_LANG"}],
        },
    )
    assert response.status_code == 403, response.text
