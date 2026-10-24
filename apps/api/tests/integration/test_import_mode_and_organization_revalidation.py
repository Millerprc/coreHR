# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""审计 B 组 P0 回归用例（Decision D-109）。

覆盖三条已审计确认的缺陷：

1. 初始化导入整批不入库（``mode=initialize``）；
2. 组织版本事件生效时重新校验上级有效性；
3. 组织编码自动避让导入的历史编码。
"""

from datetime import datetime, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.modules.platform.import_models import ImportBatch
from hris.modules.platform.models import ExternalRecordLink
from hris.modules.workforce.models import Organization, OrganizationVersion
from hris.modules.workforce.organization_models import OrganizationEvent


pytestmark = pytest.mark.asyncio


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _command(expected_version: int = 1) -> dict[str, object]:
    return {
        "expected_version": expected_version,
        "idempotency_key": str(uuid4()),
        "change_reason": "合成组织版本测试",
    }


async def _create_organization_type(
    client: AsyncClient,
    token: str,
    code: str,
    name: str,
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/organization-types",
        headers=_headers(token),
        json={"code": code, "name": name},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_organization(
    client: AsyncClient,
    token: str,
    *,
    name: str,
    organization_type_id: str,
    effective_from: str,
    parent_organization_id: str | None = None,
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/organizations",
        headers=_headers(token),
        json={
            "name": name,
            "organization_type_id": organization_type_id,
            "parent_organization_id": parent_organization_id,
            "country_code": "CN",
            "effective_from": effective_from,
            "command": _command(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _organization_import_batch(
    idempotency_key: str,
    *,
    mode: str | None = None,
    source_table: str = "synthetic_initialize_organizations",
) -> dict[str, object]:
    payload: dict[str, object] = {
        "entity_type": "organization",
        "source_system": "synthetic_ehr",
        "source_table": source_table,
        "file_name": "synthetic-organizations.csv",
        "idempotency_key": idempotency_key,
        "rows": [
            {
                "source_record_id": "init-org-valid",
                "data": {
                    "code": "INIT-ORG-001",
                    "name": "合成初始化合法组织",
                    "organization_type_code": "BU",
                    "country_code": "CN",
                    "effective_from": "2026-01-01",
                },
            },
            {
                "source_record_id": "init-org-invalid",
                "data": {
                    "code": "INIT-ORG-002",
                    "name": "合成初始化非法组织",
                    "organization_type_code": "UNKNOWN_TYPE",
                    "country_code": "CN",
                    "effective_from": "2026-01-01",
                },
            },
        ],
    }
    if mode is not None:
        payload["mode"] = mode
    return payload


async def _count_imported_organizations(
    db_session: AsyncSession,
    codes: tuple[str, ...],
) -> int:
    return (
        await db_session.scalar(
            select(func.count())
            .select_from(Organization)
            .where(Organization.code.in_(codes))
        )
    ) or 0


async def test_initialize_import_batch_rejects_execution_and_writes_nothing(
    business_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    await _create_organization_type(business_client, admin_token, "BU", "合成事业部")
    payload = _organization_import_batch(str(uuid4()), mode="initialize")
    payload["source_table"] = "synthetic_initialize_organizations_blocked"

    validated = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json=payload,
    )
    assert validated.status_code == 201, validated.text
    body = validated.json()
    assert body["mode"] == "initialize"
    assert body["status"] == "validated_with_errors"
    assert body["valid_rows"] == 1
    assert body["rejected_rows"] == 1
    batch_id = body["id"]

    before_count = await _count_imported_organizations(
        db_session,
        ("INIT-ORG-001", "INIT-ORG-002"),
    )

    executed = await business_client.post(
        f"/api/v1/governance/import-batches/{batch_id}/execute",
        headers=_headers(admin_token),
        json={"reason": "验证初始化导入整批不入库"},
    )
    assert executed.status_code == 409, executed.text
    assert executed.json()["code"] == "IMPORT_BATCH_HAS_REJECTED_ROWS"
    assert "1" in executed.json()["message"]

    after_count = await _count_imported_organizations(
        db_session,
        ("INIT-ORG-001", "INIT-ORG-002"),
    )
    assert after_count == before_count == 0

    link_count = await db_session.scalar(
        select(func.count())
        .select_from(ExternalRecordLink)
        .where(
            ExternalRecordLink.source_system == "synthetic_ehr",
            ExternalRecordLink.source_record_id.in_(
                ["init-org-valid", "init-org-invalid"]
            ),
        )
    )
    assert link_count == 0

    batch = await db_session.get(ImportBatch, UUID(batch_id))
    assert batch is not None
    assert batch.status == "validated_with_errors"
    assert batch.imported_rows == 0
    assert batch.executed_at is None


async def test_daily_import_batch_keeps_partial_success_semantics(
    business_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    await _create_organization_type(business_client, admin_token, "BU", "合成事业部")
    payload = _organization_import_batch(str(uuid4()))
    payload["source_table"] = "synthetic_daily_organizations"

    validated = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json=payload,
    )
    assert validated.status_code == 201, validated.text
    body = validated.json()
    assert body["mode"] == "daily"
    assert body["status"] == "validated_with_errors"
    assert body["rejected_rows"] == 1

    executed = await business_client.post(
        f"/api/v1/governance/import-batches/{body['id']}/execute",
        headers=_headers(admin_token),
        json={"reason": "验证日常批量维护允许正确行成功"},
    )
    assert executed.status_code == 200, executed.text
    result = executed.json()
    assert result["status"] == "completed_with_errors"
    assert result["imported_rows"] == 1
    assert result["rejected_rows"] == 1
    row_statuses = {row["source_record_id"]: row["status"] for row in result["rows"]}
    assert row_statuses["init-org-valid"] == "imported"
    assert row_statuses["init-org-invalid"] == "rejected"

    assert (
        await _count_imported_organizations(db_session, ("INIT-ORG-001", "INIT-ORG-002"))
        == 1
    )


async def test_import_batch_mode_round_trips_through_read_apis(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    await _create_organization_type(business_client, admin_token, "BU", "合成事业部")
    payload = _organization_import_batch(str(uuid4()), mode="initialize")
    payload["source_table"] = "synthetic_mode_round_trip"

    validated = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json=payload,
    )
    assert validated.status_code == 201, validated.text
    assert validated.json()["mode"] == "initialize"
    batch_id = validated.json()["id"]

    detail = await business_client.get(
        f"/api/v1/governance/import-batches/{batch_id}",
        headers=_headers(admin_token),
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["mode"] == "initialize"

    listed = await business_client.get(
        "/api/v1/governance/import-batches",
        headers=_headers(admin_token),
    )
    assert listed.status_code == 200, listed.text
    item = next(
        entry for entry in listed.json()["items"] if entry["id"] == batch_id
    )
    assert item["mode"] == "initialize"

    default_batch = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json={
            "entity_type": "organization",
            "source_system": "synthetic_ehr",
            "source_table": "synthetic_mode_default",
            "idempotency_key": str(uuid4()),
            "rows": [
                {
                    "source_record_id": "default-mode-org",
                    "data": {
                        "code": "DEFAULT-MODE-ORG",
                        "name": "合成默认模式组织",
                        "organization_type_code": "BU",
                        "country_code": "CN",
                        "effective_from": "2026-01-01",
                    },
                }
            ],
        },
    )
    assert default_batch.status_code == 201, default_batch.text
    assert default_batch.json()["mode"] == "daily"


async def test_organization_event_revalidates_parent_when_it_becomes_inactive(
    business_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    tomorrow = today + timedelta(days=1)
    day_after = today + timedelta(days=2)
    organization_type = await _create_organization_type(
        business_client,
        admin_token,
        "REVALIDATION_TYPE",
        "合成生效复检类型",
    )
    parent = await _create_organization(
        business_client,
        admin_token,
        name="合成待撤销上级",
        organization_type_id=str(organization_type["id"]),
        effective_from=today.isoformat(),
    )
    child = await _create_organization(
        business_client,
        admin_token,
        name="合成待改级下级",
        organization_type_id=str(organization_type["id"]),
        effective_from=today.isoformat(),
    )

    scheduled = await business_client.post(
        f"/api/v1/organizations/{child['id']}/versions",
        headers=_headers(admin_token),
        json={
            "name": child["name"],
            "organization_type_id": child["organization_type_id"],
            "parent_organization_id": parent["id"],
            "country_code": "CN",
            "status": "active",
            "effective_date": day_after.isoformat(),
            "command": _command(expected_version=1),
        },
    )
    assert scheduled.status_code == 201, scheduled.text
    assert scheduled.json()["status"] == "planned"

    deactivate_parent = await business_client.post(
        f"/api/v1/organizations/{parent['id']}/versions",
        headers=_headers(admin_token),
        json={
            "name": parent["name"],
            "organization_type_id": parent["organization_type_id"],
            "country_code": "CN",
            "status": "inactive",
            "effective_date": tomorrow.isoformat(),
            "command": _command(expected_version=1),
        },
    )
    assert deactivate_parent.status_code == 201, deactivate_parent.text

    applied_parent = await business_client.post(
        f"/api/v1/organization-events/apply-due?business_date={tomorrow.isoformat()}",
        headers=_headers(admin_token),
    )
    assert applied_parent.status_code == 200, applied_parent.text
    assert applied_parent.json()["applied_count"] == 1

    rejected = await business_client.post(
        f"/api/v1/organization-events/apply-due?business_date={day_after.isoformat()}",
        headers=_headers(admin_token),
    )
    assert rejected.status_code == 422, rejected.text
    assert rejected.json()["code"] == "ORGANIZATION_PARENT_NOT_ACTIVE"

    versions = list(
        (
            await db_session.scalars(
                select(OrganizationVersion)
                .where(OrganizationVersion.organization_id == UUID(str(child["id"])))
                .order_by(OrganizationVersion.version)
            )
        ).all()
    )
    assert len(versions) == 1
    assert versions[0].version == 1
    assert versions[0].effective_to is None
    assert versions[0].is_current is True

    event = await db_session.scalar(
        select(OrganizationEvent).where(
            OrganizationEvent.id == UUID(scheduled.json()["id"])
        )
    )
    assert event is not None
    assert event.status == "planned"
    assert event.applied_at is None


async def test_organization_import_advances_automatic_code_sequence(
    business_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    await _create_organization_type(business_client, admin_token, "BU", "合成事业部")
    validated = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json={
            "entity_type": "organization",
            "source_system": "synthetic_ehr",
            "source_table": "synthetic_history_code_organizations",
            "idempotency_key": str(uuid4()),
            "rows": [
                {
                    "source_record_id": "history-code-org",
                    "data": {
                        "code": "000001",
                        "name": "合成历史编码组织",
                        "organization_type_code": "BU",
                        "country_code": "CN",
                        "effective_from": "2026-01-01",
                    },
                }
            ],
        },
    )
    assert validated.status_code == 201, validated.text
    assert validated.json()["status"] == "validated"

    executed = await business_client.post(
        f"/api/v1/governance/import-batches/{validated.json()['id']}/execute",
        headers=_headers(admin_token),
        json={"reason": "验证导入历史编码后自动编号避让"},
    )
    assert executed.status_code == 200, executed.text
    assert executed.json()["imported_rows"] == 1

    imported = await db_session.scalar(
        select(Organization).where(Organization.code == "000001")
    )
    assert imported is not None

    automatic_type = await _create_organization_type(
        business_client,
        admin_token,
        "AVOID_TYPE",
        "合成避让类型",
    )
    created = await business_client.post(
        "/api/v1/organizations",
        headers=_headers(admin_token),
        json={
            "name": "合成避让后新建组织",
            "organization_type_id": automatic_type["id"],
            "country_code": "CN",
            "effective_from": datetime.now(ZoneInfo("Asia/Shanghai"))
            .date()
            .isoformat(),
            "command": _command(),
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["code"] != "000001"
    assert created.json()["code"] == "000002"
