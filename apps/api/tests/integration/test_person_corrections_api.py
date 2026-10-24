# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""人员基础信息「编辑 / 修正」拆分的集成测试。

Requirement: D-095 — 「编辑」覆盖主档并立即生效，审计记录变更前后值；
「修正」不覆盖主档，产出带生效日期的修正记录，档案按 effective_at 返回
「主档登记值 + 最后一条生效修正」的结果。
"""

from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.modules.workforce.models import (
    AuditLog,
    Employment,
    HrEvent,
    Person,
    PersonFieldVersion,
)


pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_person(business_client: AsyncClient, admin_token: str, **overrides) -> dict:
    payload = {
        "legal_name": "合成修正人员",
        "display_name": "合成修正人员",
        "country_code": "CN",
        "reserve_employee_number": True,
        "change_reason": "建立待入职档案",
    }
    payload.update(overrides)
    person = await business_client.post(
        "/api/v1/workforce/persons",
        headers=_auth(admin_token),
        json=payload,
    )
    assert person.status_code == 201, person.text
    return person.json()


async def _add_employment(
    db_session: AsyncSession,
    person_id: str,
    start_date: date,
) -> None:
    """直接落一条劳动关系，充当「最早雇佣生效日」锚点。"""
    db_session.add(
        Employment(
            person_id=person_id,
            employee_type_code="REGULAR",
            status="active",
            planned_start_date=start_date,
            actual_start_date=start_date,
            version=1,
        )
    )
    await db_session.flush()


async def test_edit_overwrites_master_and_audit_records_before_after_values(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    person = await _create_person(business_client, admin_token)
    person_id = person["id"]

    updated = await business_client.patch(
        f"/api/v1/workforce/persons/{person_id}",
        headers=_auth(admin_token),
        json={"gender_code": "F", "change_reason": "补录性别代码"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["gender_code"] == "F"
    assert updated.json()["legal_name"] == "合成修正人员"

    audit = await db_session.scalar(
        select(AuditLog)
        .where(AuditLog.object_type == "person", AuditLog.action == "update")
        .order_by(AuditLog.occurred_at.desc())
    )
    assert audit is not None
    assert audit.before_payload["changed_fields"] == ["gender_code"]
    assert audit.before_payload["values"] == {"gender_code": None}
    assert audit.after_payload["values"] == {"gender_code": "F"}

    master = await db_session.get(Person, person_id)
    assert master is not None
    assert master.gender_code == "F"


async def test_edit_audit_masks_person_name_values(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    person = await _create_person(business_client, admin_token)
    person_id = person["id"]

    updated = await business_client.patch(
        f"/api/v1/workforce/persons/{person_id}",
        headers=_auth(admin_token),
        json={
            "legal_name": "张三丰",
            "birth_date": "1991-02-03",
            "change_reason": "更正法定姓名",
        },
    )
    assert updated.status_code == 200, updated.text

    audit = await db_session.scalar(
        select(AuditLog)
        .where(AuditLog.object_type == "person", AuditLog.action == "update")
        .order_by(AuditLog.occurred_at.desc())
    )
    assert audit is not None
    # 审计记录变更前后值，但姓名与出生日期只留脱敏值，不落个人数据明文。
    assert audit.after_payload["values"] == {
        "legal_name": "张*丰",
        "birth_date": "1991-**-**",
    }
    assert "张三丰" not in str(audit.after_payload)
    assert "1991-02-03" not in str(audit.after_payload)


async def test_correction_creates_version_without_touching_master(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    person = await _create_person(business_client, admin_token)
    person_id = person["id"]
    await _add_employment(db_session, person_id, date(2026, 1, 1))

    correction = await business_client.post(
        f"/api/v1/workforce/persons/{person_id}/corrections",
        headers=_auth(admin_token),
        json={
            "field_code": "gender_code",
            "new_value": "F",
            "effective_from": "2026-03-01",
            "change_reason": "补录历史性别代码",
        },
    )
    assert correction.status_code == 201, correction.text
    body = correction.json()
    assert body["field_code"] == "gender_code"
    assert body["version"] == 1
    assert body["effective_from"] == "2026-03-01"
    assert body["effective_to"] is None
    assert body["change_reason"] == "补录历史性别代码"
    assert body["created_by_name"]

    # 主档不被修正覆盖。
    master = await db_session.get(Person, person_id)
    assert master is not None
    assert master.gender_code is None

    # 档案：当前生效结果 = 主档 + 最后一条生效修正；登记值保持主档原样。
    archive = await business_client.get(
        f"/api/v1/workforce/persons/{person_id}",
        headers=_auth(admin_token),
    )
    assert archive.status_code == 200, archive.text
    assert archive.json()["person"]["gender_code"] == "F"
    assert archive.json()["registered_person"]["gender_code"] is None
    assert archive.json()["effective_at"]
    assert len(archive.json()["corrections"]) == 1
    assert archive.json()["corrections"][0]["new_value"] == "F"

    # 修正记录清单是只读接口。
    listed = await business_client.get(
        f"/api/v1/workforce/persons/{person_id}/corrections",
        headers=_auth(admin_token),
    )
    assert listed.status_code == 200, listed.text
    assert len(listed.json()) == 1


async def test_correction_registers_hr_event_and_audit_without_value(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    person = await _create_person(business_client, admin_token)
    person_id = person["id"]
    await _add_employment(db_session, person_id, date(2026, 1, 1))

    correction = await business_client.post(
        f"/api/v1/workforce/persons/{person_id}/corrections",
        headers=_auth(admin_token),
        json={
            "field_code": "gender_code",
            "new_value": "F",
            "effective_from": "2026-03-01",
            "change_reason": "补录历史性别代码",
        },
    )
    assert correction.status_code == 201, correction.text

    event = await db_session.scalar(
        select(HrEvent).where(HrEvent.event_type == "PERSON_CORRECTION")
    )
    assert event is not None
    assert event.object_type == "person"
    assert str(event.object_id) == person_id
    assert event.effective_date == date(2026, 3, 1)
    # 事件与审计只承载字段名与版本，不复制修正后的取值明文。
    assert event.actual_payload["field_code"] == "gender_code"
    assert "F" not in str(event.actual_payload)

    audit = await db_session.scalar(
        select(AuditLog).where(AuditLog.action == "person.corrected")
    )
    assert audit is not None
    assert audit.object_type == "person"
    assert audit.after_payload["field_code"] == "gender_code"
    assert audit.after_payload["version"] == 1
    assert "F" not in str(audit.after_payload)


async def test_correction_requires_effective_date(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    person = await _create_person(business_client, admin_token)

    missing = await business_client.post(
        f"/api/v1/workforce/persons/{person['id']}/corrections",
        headers=_auth(admin_token),
        json={"field_code": "gender_code", "new_value": "F"},
    )
    assert missing.status_code == 422, missing.text
    assert missing.json()["code"] == "REQUEST_VALIDATION_FAILED"


async def test_correction_rejects_unknown_field(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    person = await _create_person(business_client, admin_token)

    rejected = await business_client.post(
        f"/api/v1/workforce/persons/{person['id']}/corrections",
        headers=_auth(admin_token),
        json={
            "field_code": "employee_number",
            "new_value": "990001",
            "effective_from": "2026-03-01",
        },
    )
    assert rejected.status_code == 422, rejected.text
    assert rejected.json()["code"] == "PERSON_FIELD_NOT_CORRECTABLE"


async def test_edit_rejects_clearing_required_name_field(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    person = await _create_person(business_client, admin_token)

    rejected = await business_client.patch(
        f"/api/v1/workforce/persons/{person['id']}",
        headers=_auth(admin_token),
        json={"display_name": None, "change_reason": "清空显示姓名"},
    )
    assert rejected.status_code == 422, rejected.text
    assert rejected.json()["code"] == "PERSON_FIELD_REQUIRED"


async def test_correction_accepts_birth_date_and_rejects_clearing_required_field(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    person = await _create_person(business_client, admin_token)
    person_id = person["id"]
    await _add_employment(db_session, person_id, date(2026, 1, 1))

    birth_date = await business_client.post(
        f"/api/v1/workforce/persons/{person_id}/corrections",
        headers=_auth(admin_token),
        json={
            "field_code": "birth_date",
            "new_value": "1991-02-03",
            "effective_from": "2026-03-01",
        },
    )
    assert birth_date.status_code == 201, birth_date.text
    assert birth_date.json()["new_value"] == "1991-02-03"

    archive = await business_client.get(
        f"/api/v1/workforce/persons/{person_id}",
        headers=_auth(admin_token),
    )
    assert archive.status_code == 200, archive.text
    assert archive.json()["person"]["birth_date"] == "1991-02-03"

    invalid_date = await business_client.post(
        f"/api/v1/workforce/persons/{person_id}/corrections",
        headers=_auth(admin_token),
        json={
            "field_code": "birth_date",
            "new_value": "1991/02/03",
            "effective_from": "2026-04-01",
        },
    )
    assert invalid_date.status_code == 422, invalid_date.text
    assert invalid_date.json()["code"] == "PERSON_FIELD_VALUE_INVALID"

    # 法定姓名在主档上不允许为空，修正也不能把它清空。
    cleared = await business_client.post(
        f"/api/v1/workforce/persons/{person_id}/corrections",
        headers=_auth(admin_token),
        json={
            "field_code": "legal_name",
            "new_value": "",
            "effective_from": "2026-04-01",
        },
    )
    assert cleared.status_code == 422, cleared.text
    assert cleared.json()["code"] == "PERSON_FIELD_VALUE_INVALID"


async def test_correction_rejects_duplicate_effective_date_for_same_field(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    person = await _create_person(business_client, admin_token)
    person_id = person["id"]
    await _add_employment(db_session, person_id, date(2026, 1, 1))

    first = await business_client.post(
        f"/api/v1/workforce/persons/{person_id}/corrections",
        headers=_auth(admin_token),
        json={
            "field_code": "gender_code",
            "new_value": "F",
            "effective_from": "2026-03-01",
        },
    )
    assert first.status_code == 201, first.text

    duplicate = await business_client.post(
        f"/api/v1/workforce/persons/{person_id}/corrections",
        headers=_auth(admin_token),
        json={
            "field_code": "gender_code",
            "new_value": "M",
            "effective_from": "2026-03-01",
        },
    )
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["code"] == "PERSON_CORRECTION_EFFECTIVE_DATE_CONFLICT"


async def test_correction_rejects_date_before_employment_anchor(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    person = await _create_person(business_client, admin_token)
    person_id = person["id"]
    await _add_employment(db_session, person_id, date(2026, 1, 1))

    too_early = await business_client.post(
        f"/api/v1/workforce/persons/{person_id}/corrections",
        headers=_auth(admin_token),
        json={
            "field_code": "gender_code",
            "new_value": "F",
            "effective_from": "2025-12-31",
        },
    )
    assert too_early.status_code == 422, too_early.text
    assert too_early.json()["code"] == "PERSON_CORRECTION_EFFECTIVE_DATE_TOO_EARLY"


async def test_correction_slices_effective_period_and_supports_backfill(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    person = await _create_person(business_client, admin_token)
    person_id = person["id"]
    await _add_employment(db_session, person_id, date(2026, 1, 1))

    later = await business_client.post(
        f"/api/v1/workforce/persons/{person_id}/corrections",
        headers=_auth(admin_token),
        json={
            "field_code": "gender_code",
            "new_value": "M",
            "effective_from": "2026-05-01",
        },
    )
    assert later.status_code == 201, later.text

    # 往过去补录：插入更早的生效日期，上一版从补录日的前一天起失效。
    backfill = await business_client.post(
        f"/api/v1/workforce/persons/{person_id}/corrections",
        headers=_auth(admin_token),
        json={
            "field_code": "gender_code",
            "new_value": "F",
            "effective_from": "2026-03-01",
        },
    )
    assert backfill.status_code == 201, backfill.text
    assert backfill.json()["version"] == 2
    assert backfill.json()["effective_to"] == "2026-04-30"

    versions = list(
        (
            await db_session.scalars(
                select(PersonFieldVersion)
                .where(PersonFieldVersion.person_id == person_id)
                .order_by(PersonFieldVersion.effective_from)
            )
        ).all()
    )
    assert len(versions) == 2
    # 补录版从 3 月 1 日生效、到 4 月 30 日失效；5 月版接续其后且仍长期有效。
    assert versions[0].effective_from == date(2026, 3, 1)
    assert versions[0].effective_to == date(2026, 4, 30)
    assert versions[1].effective_from == date(2026, 5, 1)
    assert versions[1].effective_to is None

    # 时点查询：3 月用补录值，5 月起用后一条修正。
    at_march = await business_client.get(
        f"/api/v1/workforce/persons/{person_id}?effective_at=2026-03-15",
        headers=_auth(admin_token),
    )
    assert at_march.status_code == 200, at_march.text
    assert at_march.json()["person"]["gender_code"] == "F"
    assert at_march.json()["effective_at"] == "2026-03-15"

    at_may = await business_client.get(
        f"/api/v1/workforce/persons/{person_id}?effective_at=2026-05-15",
        headers=_auth(admin_token),
    )
    assert at_may.status_code == 200, at_may.text
    assert at_may.json()["person"]["gender_code"] == "M"

    # 早于任何修正时点，主档登记值仍然生效。
    at_february = await business_client.get(
        f"/api/v1/workforce/persons/{person_id}?effective_at=2026-02-15",
        headers=_auth(admin_token),
    )
    assert at_february.status_code == 200, at_february.text
    assert at_february.json()["person"]["gender_code"] is None

    # 修正记录清单支持按生效日期过滤。
    filtered = await business_client.get(
        f"/api/v1/workforce/persons/{person_id}/corrections?effective_at=2026-03-15",
        headers=_auth(admin_token),
    )
    assert filtered.status_code == 200, filtered.text
    assert len(filtered.json()) == 1
    assert filtered.json()[0]["new_value"] == "F"


async def test_correction_without_employment_falls_back_to_master_registration_date(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    person = await _create_person(business_client, admin_token)
    person_id = person["id"]

    # 没有雇佣记录时，退回到主档登记日作为生效日期下界。
    too_early = await business_client.post(
        f"/api/v1/workforce/persons/{person_id}/corrections",
        headers=_auth(admin_token),
        json={
            "field_code": "gender_code",
            "new_value": "F",
            "effective_from": (date.today() - timedelta(days=365)).isoformat(),
        },
    )
    assert too_early.status_code == 422, too_early.text
    assert too_early.json()["code"] == "PERSON_CORRECTION_EFFECTIVE_DATE_TOO_EARLY"


async def test_correction_requires_person_edit_permission(
    business_client: AsyncClient,
    admin_token: str,
    restricted_token: str,
) -> None:
    person = await _create_person(business_client, admin_token)

    forbidden = await business_client.post(
        f"/api/v1/workforce/persons/{person['id']}/corrections",
        headers=_auth(restricted_token),
        json={
            "field_code": "gender_code",
            "new_value": "F",
            "effective_from": "2026-03-01",
        },
    )
    assert forbidden.status_code == 403, forbidden.text
    assert forbidden.json()["code"] == "PERMISSION_DENIED"
