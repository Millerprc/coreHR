import csv
from datetime import date, datetime, timedelta
from io import StringIO
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.config import get_settings
from hris.modules.platform.models import DataDictionary, DataDictionaryItem
from hris.modules.workforce.models import (
    AuditLog,
    JobCatalog,
    LegalEntity,
    Organization,
    OrganizationType,
    OrganizationVersion,
)


pytestmark = pytest.mark.asyncio


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _csv_rows(response_content: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(StringIO(response_content.decode("utf-8-sig"))))


def _business_date() -> date:
    return datetime.now(ZoneInfo(get_settings().business_timezone)).date()


async def test_dictionary_export_is_safe_current_and_audited(
    business_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    db_session.add_all(
        [
            DataDictionary(
                code="ACTIVE_DICTIONARY",
                name='=HYPERLINK("https://example.invalid")',
                source="synthetic",
                is_active=True,
            ),
            DataDictionary(
                code="INACTIVE_DICTIONARY",
                name="Inactive synthetic dictionary",
                source="synthetic",
                is_active=False,
            ),
        ]
    )
    await db_session.flush()

    response = await business_client.get(
        "/api/v1/governance/exports/dictionary",
        headers=_headers(admin_token),
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert "dictionary-current.csv" in response.headers["content-disposition"]
    assert response.content.startswith(b"\xef\xbb\xbf")
    rows = _csv_rows(response.content)
    assert rows == [
        {
            "source_record_id": "dictionary:ACTIVE_DICTIONARY",
            "code": "ACTIVE_DICTIONARY",
            "name": "'=HYPERLINK(\"https://example.invalid\")",
            "english_name": "",
            "description": "",
        }
    ]

    audit = await db_session.scalar(
        select(AuditLog).where(AuditLog.action == "governance.master_data.export")
    )
    assert audit is not None
    assert audit.before_payload == {}
    assert audit.after_payload == {
        "entity_type": "dictionary",
        "as_of": _business_date().isoformat(),
        "row_count": 1,
    }


async def test_organization_export_uses_effective_business_date_snapshot(
    business_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    today = _business_date()
    organization_type = OrganizationType(
        code="BU",
        name="Synthetic business unit",
        sort_order=20,
        is_active=True,
    )
    parent = Organization(code="ORG_PARENT")
    child = Organization(code="ORG_CHILD")
    expired = Organization(code="ORG_EXPIRED")
    future = Organization(code="ORG_FUTURE")
    inactive = Organization(code="ORG_INACTIVE")
    db_session.add_all(
        [organization_type, parent, child, expired, future, inactive]
    )
    await db_session.flush()
    db_session.add_all(
        [
            OrganizationVersion(
                organization_id=parent.id,
                version=1,
                name="Synthetic parent",
                organization_type_id=organization_type.id,
                status="active",
                effective_from=today - timedelta(days=30),
                is_current=True,
            ),
            OrganizationVersion(
                organization_id=child.id,
                version=1,
                name="Synthetic child",
                organization_type_id=organization_type.id,
                parent_organization_id=parent.id,
                country_code="CN",
                status="active",
                effective_from=today,
                is_current=True,
            ),
            OrganizationVersion(
                organization_id=expired.id,
                version=1,
                name="Expired synthetic organization",
                organization_type_id=organization_type.id,
                status="active",
                effective_from=today - timedelta(days=30),
                effective_to=today - timedelta(days=1),
                is_current=False,
            ),
            OrganizationVersion(
                organization_id=future.id,
                version=1,
                name="Future synthetic organization",
                organization_type_id=organization_type.id,
                status="active",
                effective_from=today + timedelta(days=1),
                is_current=True,
            ),
            OrganizationVersion(
                organization_id=inactive.id,
                version=1,
                name="Inactive synthetic organization",
                organization_type_id=organization_type.id,
                status="inactive",
                effective_from=today - timedelta(days=30),
                is_current=True,
            ),
        ]
    )
    await db_session.flush()

    response = await business_client.get(
        "/api/v1/governance/exports/organization",
        headers=_headers(admin_token),
    )

    assert response.status_code == 200, response.text
    rows = _csv_rows(response.content)
    assert [row["code"] for row in rows] == ["ORG_CHILD", "ORG_PARENT"]
    child_row = next(row for row in rows if row["code"] == "ORG_CHILD")
    assert child_row["organization_type_code"] == "BU"
    assert child_row["parent_code"] == "ORG_PARENT"
    assert child_row["country_code"] == "CN"
    assert child_row["effective_from"] == today.isoformat()


async def test_remaining_master_data_types_export_import_compatible_columns(
    business_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    today = _business_date()
    dictionary = DataDictionary(
        code="EMPLOYEE_TYPE",
        name="Synthetic employee type",
        source="synthetic",
        is_active=True,
    )
    organization_type = OrganizationType(
        code="DEPARTMENT",
        name="Synthetic department",
        sort_order=40,
        is_active=True,
    )
    db_session.add_all([dictionary, organization_type])
    await db_session.flush()
    parent_item = DataDictionaryItem(
        dictionary_id=dictionary.id,
        code="REGULAR",
        name="Synthetic regular employee",
        sort_order=10,
        level=0,
        is_active=True,
    )
    db_session.add(parent_item)
    await db_session.flush()
    db_session.add_all(
        [
            DataDictionaryItem(
                dictionary_id=dictionary.id,
                parent_item_id=parent_item.id,
                code="CAMPUS",
                name="Synthetic campus employee",
                sort_order=20,
                level=1,
                is_active=True,
            ),
            LegalEntity(
                code="LE_CN_001",
                name="Synthetic legal entity",
                registered_name="Synthetic Legal Entity Ltd.",
                country_code="CN",
                status="active",
                effective_from=today,
            ),
            JobCatalog(
                code="JOB_001",
                name="Synthetic job",
                level_code="L1",
                grade_code="G1",
                class_code="C1",
                sequence_code="TECH",
                status="active",
                effective_from=today,
                attributes={},
            ),
        ]
    )
    await db_session.flush()

    expected_headers = {
        "dictionary_item": [
            "source_record_id",
            "dictionary_code",
            "code",
            "name",
            "english_name",
            "parent_item_code",
            "sort_order",
            "description",
        ],
        "organization_type": ["source_record_id", "code", "name", "sort_order"],
        "legal_entity": [
            "source_record_id",
            "code",
            "name",
            "registered_name",
            "country_code",
            "registration_number",
            "effective_from",
            "effective_to",
        ],
        "job": [
            "source_record_id",
            "job_code",
            "job_name",
            "level_code",
            "grade_code",
            "class_code",
            "sequence_code",
            "effective_from",
            "effective_to",
            "status",
            "source_job_id",
            "notes",
        ],
    }
    for entity_type, fieldnames in expected_headers.items():
        response = await business_client.get(
            f"/api/v1/governance/exports/{entity_type}",
            headers=_headers(admin_token),
        )
        assert response.status_code == 200, response.text
        reader = csv.DictReader(StringIO(response.content.decode("utf-8-sig")))
        assert reader.fieldnames == fieldnames
        rows = list(reader)
        assert rows

    dictionary_item_response = await business_client.get(
        "/api/v1/governance/exports/dictionary_item",
        headers=_headers(admin_token),
    )
    dictionary_items = _csv_rows(dictionary_item_response.content)
    campus = next(row for row in dictionary_items if row["code"] == "CAMPUS")
    assert campus["dictionary_code"] == "EMPLOYEE_TYPE"
    assert campus["parent_item_code"] == "REGULAR"


async def test_master_data_export_requires_governance_view_permission(
    business_client: AsyncClient,
    restricted_token: str,
) -> None:
    response = await business_client.get(
        "/api/v1/governance/exports/dictionary",
        headers=_headers(restricted_token),
    )
    assert response.status_code == 403, response.text
