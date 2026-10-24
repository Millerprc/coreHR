# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""搜索关键词的 LIKE 通配符转义测试。

Requirement: D-112 — 搜索关键词按**字面量**匹配。
``%`` 与 ``_`` 在 ``ILIKE`` 里是通配符，用户搜 ``%`` 不应该拿到全表，
搜 ``a_b`` 也不应该命中 ``axb``。
"""

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.search import escape_like, like_pattern
from hris.modules.workforce.models import Employment, Person


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _person(
    db_session: AsyncSession,
    *,
    employee_number: str,
    display_name: str,
) -> Person:
    person = Person(
        employee_number=employee_number,
        legal_name=display_name,
        display_name=display_name,
        status="active",
    )
    db_session.add(person)
    await db_session.flush()
    return person


async def _employment(
    db_session: AsyncSession,
    *,
    person: Person,
    start_date: date,
) -> Employment:
    employment = Employment(
        person_id=person.id,
        employee_type_code="REGULAR",
        status="active",
        planned_start_date=start_date,
        actual_start_date=start_date,
        version=1,
    )
    db_session.add(employment)
    await db_session.flush()
    return employment


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("abc", "abc"),
        ("a%b", "a\\%b"),
        ("a_b", "a\\_b"),
        ("a\\b", "a\\\\b"),
        ("%_%", "\\%\\_\\%"),
    ],
)
def test_escape_like_escapes_wildcards(raw: str, expected: str) -> None:
    """Requirement: D-112 — 通配符与转义符按顺序转义，先反斜杠后百分号下划线。"""

    assert escape_like(raw) == expected


def test_like_pattern_wraps_with_wildcards() -> None:
    """Requirement: D-112 — 模式串是「包含」，用户输入部分已转义。"""

    assert like_pattern("  a%b  ") == "%a\\%b%"


@pytest.mark.asyncio
async def test_roster_search_treats_percent_as_literal(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    """Requirement: D-112 — 搜 ``%`` 只命中名字里真的带 ``%`` 的人，不返回全表。"""

    literal = await _person(
        db_session,
        employee_number="990501",
        display_name="百分%员工",
    )
    await _employment(db_session, person=literal, start_date=date(2026, 1, 1))

    other = await _person(
        db_session,
        employee_number="990502",
        display_name="普通员工",
    )
    await _employment(db_session, person=other, start_date=date(2026, 1, 1))

    response = await business_client.get(
        "/api/v1/workforce/people/roster-history?as_of=2026-05-01&search=%25",
        headers=_auth(admin_token),
    )
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert [item["employee_number"] for item in items] == ["990501"]


@pytest.mark.asyncio
async def test_roster_search_treats_underscore_as_literal(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    """Requirement: D-112 — 搜 ``a_b`` 不会命中 ``axb``。"""

    literal = await _person(
        db_session,
        employee_number="990503",
        display_name="a_b员工",
    )
    await _employment(db_session, person=literal, start_date=date(2026, 1, 1))

    near_miss = await _person(
        db_session,
        employee_number="990504",
        display_name="axb员工",
    )
    await _employment(db_session, person=near_miss, start_date=date(2026, 1, 1))

    response = await business_client.get(
        "/api/v1/workforce/people/roster-history?as_of=2026-05-01&search=a_b",
        headers=_auth(admin_token),
    )
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert [item["employee_number"] for item in items] == ["990503"]
