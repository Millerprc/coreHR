from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.modules.platform.import_models import ImportBatchRow
from hris.modules.platform.governance_models import OutboxEvent
from hris.modules.platform.models import (
    DataDictionary,
    DataDictionaryItem,
    ExternalRecordLink,
)
from hris.modules.workforce.models import (
    AuditLog,
    JobCatalog,
    LegalEntity,
    Organization,
    OrganizationType,
    OrganizationVersion,
)
from hris.modules.workforce.organization_models import OrganizationEvent


pytestmark = pytest.mark.asyncio


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _dictionary_item_batch(idempotency_key: str) -> dict[str, object]:
    return {
        "entity_type": "dictionary_item",
        "source_system": "synthetic_ehr",
        "source_table": "synthetic_dictionary_items",
        "file_name": "synthetic-mapping.csv",
        "idempotency_key": idempotency_key,
        "rows": [
            {
                "source_record_id": "employee-type-regular",
                "data": {
                    "dictionary_code": "EMPLOYEE_TYPE",
                    "code": "REGULAR",
                    "name": "合成正式员工",
                    "sort_order": 10,
                },
            }
        ],
    }


async def _create_dictionary(client: AsyncClient, token: str) -> None:
    response = await client.post(
        "/api/v1/configuration/dictionaries",
        headers=_headers(token),
        json={
            "code": "EMPLOYEE_TYPE",
            "name": "合成员工类型",
            "description": "仅用于自动化测试",
        },
    )
    assert response.status_code == 201, response.text


async def _create_organization_type(client: AsyncClient, token: str) -> None:
    response = await client.post(
        "/api/v1/organization-types",
        headers=_headers(token),
        json={"code": "BU", "name": "合成业务单元", "sort_order": 30},
    )
    assert response.status_code == 201, response.text


async def test_import_batch_validates_executes_and_is_idempotent(
    business_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    await _create_dictionary(business_client, admin_token)
    key = str(uuid4())
    payload = _dictionary_item_batch(key)

    validated = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json=payload,
    )
    assert validated.status_code == 201, validated.text
    body = validated.json()
    assert body["status"] == "validated"
    assert body["total_rows"] == 1
    assert body["valid_rows"] == 1
    assert body["rejected_rows"] == 0
    assert body["rows"][0]["status"] == "valid"
    batch_id = body["id"]

    repeated_validation = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json=payload,
    )
    assert repeated_validation.status_code == 201, repeated_validation.text
    assert repeated_validation.json()["id"] == batch_id

    executed = await business_client.post(
        f"/api/v1/governance/import-batches/{batch_id}/execute",
        headers=_headers(admin_token),
        json={"reason": "执行合成主数据初始化"},
    )
    assert executed.status_code == 200, executed.text
    result = executed.json()
    assert result["status"] == "completed"
    assert result["imported_rows"] == 1
    assert result["skipped_rows"] == 0
    assert result["rows"][0]["status"] == "imported"
    assert result["rows"][0]["target_id"] is not None

    executed_again = await business_client.post(
        f"/api/v1/governance/import-batches/{batch_id}/execute",
        headers=_headers(admin_token),
        json={"reason": "验证重复执行"},
    )
    assert executed_again.status_code == 200, executed_again.text
    assert executed_again.json()["id"] == batch_id

    item_count = await db_session.scalar(
        select(func.count()).select_from(DataDictionaryItem).where(
            DataDictionaryItem.code == "REGULAR"
        )
    )
    link_count = await db_session.scalar(
        select(func.count()).select_from(ExternalRecordLink).where(
            ExternalRecordLink.source_system == "synthetic_ehr",
            ExternalRecordLink.source_record_id == "employee-type-regular",
        )
    )
    audit_count = await db_session.scalar(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "governance.import_batch.execute",
            AuditLog.object_id == UUID(batch_id),
        )
    )
    assert item_count == 1
    assert link_count == 1
    assert audit_count == 1


async def test_import_batch_rejects_invalid_rows_and_executes_valid_rows(
    business_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    await _create_dictionary(business_client, admin_token)
    payload = _dictionary_item_batch(str(uuid4()))
    payload["rows"] = [
        payload["rows"][0],
        {
            "source_record_id": "employee-type-invalid",
            "data": {
                "dictionary_code": "EMPLOYEE_TYPE",
                "code": "invalid lower case",
                "name": "合成非法值",
            },
        },
        {
            "source_record_id": "employee-type-unknown-dictionary",
            "data": {
                "dictionary_code": "UNKNOWN_DICTIONARY",
                "code": "CONTRACTOR",
                "name": "合成未知字典",
            },
        },
    ]

    validated = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json=payload,
    )
    assert validated.status_code == 201, validated.text
    body = validated.json()
    assert body["status"] == "validated_with_errors"
    assert body["valid_rows"] == 1
    assert body["rejected_rows"] == 2
    rejected = [row for row in body["rows"] if row["status"] == "rejected"]
    assert {error["code"] for row in rejected for error in row["errors"]} == {
        "ROW_SCHEMA_INVALID",
        "DICTIONARY_NOT_FOUND",
    }

    executed = await business_client.post(
        f"/api/v1/governance/import-batches/{body['id']}/execute",
        headers=_headers(admin_token),
        json={"reason": "只执行通过校验的合成行"},
    )
    assert executed.status_code == 200, executed.text
    assert executed.json()["status"] == "completed_with_errors"
    assert executed.json()["imported_rows"] == 1
    assert executed.json()["rejected_rows"] == 2

    row_count = await db_session.scalar(
        select(func.count()).select_from(ImportBatchRow).where(
            ImportBatchRow.batch_id == body["id"]
        )
    )
    assert row_count == 3


async def test_import_batch_rejects_changed_idempotency_payload(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    await _create_dictionary(business_client, admin_token)
    key = str(uuid4())
    payload = _dictionary_item_batch(key)
    first = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json=payload,
    )
    assert first.status_code == 201, first.text

    changed = _dictionary_item_batch(key)
    changed["rows"][0]["data"]["name"] = "不同的合成名称"
    conflict = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json=changed,
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["code"] == "IMPORT_IDEMPOTENCY_CONFLICT"


async def test_import_batch_requires_governance_permission(
    business_client: AsyncClient,
    restricted_token: str,
) -> None:
    response = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(restricted_token),
        json=_dictionary_item_batch(str(uuid4())),
    )
    assert response.status_code == 403, response.text


async def test_import_batch_lists_and_returns_details(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    await _create_dictionary(business_client, admin_token)
    created = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json=_dictionary_item_batch(str(uuid4())),
    )
    assert created.status_code == 201, created.text
    batch_id = created.json()["id"]

    listed = await business_client.get(
        "/api/v1/governance/import-batches",
        headers=_headers(admin_token),
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] >= 1
    assert any(item["id"] == batch_id for item in listed.json()["items"])

    detail = await business_client.get(
        f"/api/v1/governance/import-batches/{batch_id}",
        headers=_headers(admin_token),
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["rows"][0]["source_record_id"] == "employee-type-regular"


@pytest.mark.parametrize(
    ("entity_type", "source_record_id", "data", "model_type", "code"),
    [
        (
            "dictionary",
            "agreement-type-dictionary",
            {
                "code": "AGREEMENT_TYPE",
                "name": "合成协议类型",
                "description": "仅用于自动化测试",
            },
            DataDictionary,
            "AGREEMENT_TYPE",
        ),
        (
            "organization_type",
            "organization-type-group",
            {"code": "SYNTHETIC_GROUP", "name": "合成集团", "sort_order": 10},
            OrganizationType,
            "SYNTHETIC_GROUP",
        ),
        (
            "legal_entity",
            "legal-entity-cn",
            {
                "code": "SYNTHETIC_LE_CN",
                "name": "合成法人",
                "registered_name": "合成法人注册名称",
                "country_code": "CN",
                "registration_number": "SYNTHETIC-REGISTRATION",
                "effective_from": "2026-01-01",
            },
            LegalEntity,
            "SYNTHETIC_LE_CN",
        ),
        (
            "job",
            "job-engineer",
            {
                "code": "SYNTHETIC_ENGINEER",
                "name": "合成工程师",
                "level_code": "L1",
                "grade_code": "G1",
                "class_code": "TECH",
                "sequence_code": "ENGINEERING",
                "effective_from": "2026-01-01",
            },
            JobCatalog,
            "SYNTHETIC_ENGINEER",
        ),
    ],
)
async def test_import_batch_supports_each_master_data_executor(
    business_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
    entity_type: str,
    source_record_id: str,
    data: dict[str, object],
    model_type: type[object],
    code: str,
) -> None:
    validated = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json={
            "entity_type": entity_type,
            "source_system": "synthetic_ehr",
            "source_table": f"synthetic_{entity_type}",
            "idempotency_key": str(uuid4()),
            "rows": [{"source_record_id": source_record_id, "data": data}],
        },
    )
    assert validated.status_code == 201, validated.text
    assert validated.json()["status"] == "validated"

    executed = await business_client.post(
        f"/api/v1/governance/import-batches/{validated.json()['id']}/execute",
        headers=_headers(admin_token),
        json={"reason": "验证合成主数据执行器"},
    )
    assert executed.status_code == 200, executed.text
    assert executed.json()["status"] == "completed"
    assert executed.json()["imported_rows"] == 1
    assert await db_session.scalar(
        select(func.count()).select_from(model_type).where(model_type.code == code)
    ) == 1


async def test_dictionary_item_import_orders_parent_before_child(
    business_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    await _create_dictionary(business_client, admin_token)
    validated = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json={
            "entity_type": "dictionary_item",
            "source_system": "synthetic_ehr",
            "source_table": "synthetic_dictionary_tree",
            "idempotency_key": str(uuid4()),
            "rows": [
                {
                    "source_record_id": "child",
                    "data": {
                        "dictionary_code": "EMPLOYEE_TYPE",
                        "code": "CHILD",
                        "name": "合成子项",
                        "parent_item_code": "PARENT",
                    },
                },
                {
                    "source_record_id": "parent",
                    "data": {
                        "dictionary_code": "EMPLOYEE_TYPE",
                        "code": "PARENT",
                        "name": "合成父项",
                    },
                },
            ],
        },
    )
    assert validated.status_code == 201, validated.text
    assert validated.json()["valid_rows"] == 2

    executed = await business_client.post(
        f"/api/v1/governance/import-batches/{validated.json()['id']}/execute",
        headers=_headers(admin_token),
        json={"reason": "验证父子导入顺序"},
    )
    assert executed.status_code == 200, executed.text
    assert executed.json()["imported_rows"] == 2
    parent = await db_session.scalar(
        select(DataDictionaryItem).where(DataDictionaryItem.code == "PARENT")
    )
    child = await db_session.scalar(
        select(DataDictionaryItem).where(DataDictionaryItem.code == "CHILD")
    )
    assert parent is not None and parent.level == 0
    assert child is not None and child.parent_item_id == parent.id and child.level == 1


async def test_dictionary_item_import_rejects_parent_cycle(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    await _create_dictionary(business_client, admin_token)
    validated = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json={
            "entity_type": "dictionary_item",
            "source_system": "synthetic_ehr",
            "source_table": "synthetic_dictionary_cycle",
            "idempotency_key": str(uuid4()),
            "rows": [
                {
                    "source_record_id": "cycle-a",
                    "data": {
                        "dictionary_code": "EMPLOYEE_TYPE",
                        "code": "CYCLE_A",
                        "name": "合成循环A",
                        "parent_item_code": "CYCLE_B",
                    },
                },
                {
                    "source_record_id": "cycle-b",
                    "data": {
                        "dictionary_code": "EMPLOYEE_TYPE",
                        "code": "CYCLE_B",
                        "name": "合成循环B",
                        "parent_item_code": "CYCLE_A",
                    },
                },
            ],
        },
    )
    assert validated.status_code == 201, validated.text
    body = validated.json()
    assert body["status"] == "validated_with_errors"
    assert body["rejected_rows"] == 2
    assert all(
        "DICTIONARY_PARENT_CYCLE" in {error["code"] for error in row["errors"]}
        for row in body["rows"]
    )


async def test_dictionary_item_import_rejects_child_of_rejected_parent(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    await _create_dictionary(business_client, admin_token)
    response = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json={
            "entity_type": "dictionary_item",
            "source_system": "synthetic_ehr",
            "source_table": "synthetic_rejected_dictionary_parent",
            "idempotency_key": str(uuid4()),
            "rows": [
                {
                    "source_record_id": "duplicate-parent-1",
                    "data": {
                        "dictionary_code": "EMPLOYEE_TYPE",
                        "code": "DUPLICATE_PARENT",
                        "name": "合成重复父项一",
                    },
                },
                {
                    "source_record_id": "duplicate-parent-2",
                    "data": {
                        "dictionary_code": "EMPLOYEE_TYPE",
                        "code": "DUPLICATE_PARENT",
                        "name": "合成重复父项二",
                    },
                },
                {
                    "source_record_id": "dependent-child",
                    "data": {
                        "dictionary_code": "EMPLOYEE_TYPE",
                        "code": "DEPENDENT_CHILD",
                        "name": "合成依赖子项",
                        "parent_item_code": "DUPLICATE_PARENT",
                    },
                },
            ],
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["rejected_rows"] == 3
    child = next(
        row for row in body["rows"] if row["source_record_id"] == "dependent-child"
    )
    assert "DICTIONARY_PARENT_REJECTED" in {
        error["code"] for error in child["errors"]
    }


async def test_new_batch_skips_same_source_and_rejects_changed_source(
    business_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    await _create_dictionary(business_client, admin_token)
    first_payload = _dictionary_item_batch(str(uuid4()))
    first = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json=first_payload,
    )
    await business_client.post(
        f"/api/v1/governance/import-batches/{first.json()['id']}/execute",
        headers=_headers(admin_token),
        json={"reason": "首次合成导入"},
    )

    same_payload = _dictionary_item_batch(str(uuid4()))
    same = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json=same_payload,
    )
    assert same.status_code == 201, same.text
    assert same.json()["rows"][0]["status"] == "skipped"
    assert same.json()["skipped_rows"] == 1
    same_execution = await business_client.post(
        f"/api/v1/governance/import-batches/{same.json()['id']}/execute",
        headers=_headers(admin_token),
        json={"reason": "重复来源应跳过"},
    )
    assert same_execution.status_code == 200, same_execution.text
    assert same_execution.json()["status"] == "completed"
    assert await db_session.scalar(
        select(func.count()).select_from(DataDictionaryItem).where(
            DataDictionaryItem.code == "REGULAR"
        )
    ) == 1

    changed_payload = _dictionary_item_batch(str(uuid4()))
    changed_payload["rows"][0]["data"]["name"] = "变化后的合成名称"
    changed = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json=changed_payload,
    )
    assert changed.status_code == 201, changed.text
    assert changed.json()["rows"][0]["status"] == "rejected"
    assert changed.json()["rows"][0]["errors"][0]["code"] == "SOURCE_RECORD_CHANGED"


async def test_invalid_sensitive_column_is_rejected_without_storing_raw_payload(
    business_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    payload = {
        "entity_type": "legal_entity",
        "source_system": "synthetic_ehr",
        "source_table": "synthetic_legal_entities",
        "idempotency_key": str(uuid4()),
        "rows": [
            {
                "source_record_id": "legal-entity-sensitive-field",
                "data": {
                    "code": "SYNTHETIC_LE_SENSITIVE",
                    "name": "合成法人",
                    "country_code": "CN",
                    "effective_from": "2026-01-01",
                    "personal_phone": "synthetic-not-a-real-number",
                },
            }
        ],
    }

    response = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json=payload,
    )
    assert response.status_code == 201, response.text
    assert response.json()["rows"][0]["status"] == "rejected"
    assert response.json()["rows"][0]["errors"][0]["code"] == "ROW_FIELD_NOT_ALLOWED"
    stored = await db_session.scalar(
        select(ImportBatchRow).where(
            ImportBatchRow.batch_id == UUID(response.json()["id"])
        )
    )
    assert stored is not None
    assert stored.payload == {}


async def test_organization_import_orders_parent_before_child_and_preserves_codes(
    business_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    await _create_organization_type(business_client, admin_token)
    validated = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json={
            "entity_type": "organization",
            "source_system": "synthetic_ehr",
            "source_table": "synthetic_organizations",
            "idempotency_key": str(uuid4()),
            "rows": [
                {
                    "source_record_id": "child-org",
                    "data": {
                        "code": "HIST-CHILD-001",
                        "name": "合成子组织",
                        "organization_type_code": "BU",
                        "parent_code": "HIST-PARENT-001",
                        "country_code": "CN",
                        "effective_from": "2026-01-01",
                    },
                },
                {
                    "source_record_id": "parent-org",
                    "data": {
                        "code": "HIST-PARENT-001",
                        "name": "合成父组织",
                        "organization_type_code": "BU",
                        "country_code": "CN",
                        "effective_from": "2025-01-01",
                    },
                },
            ],
        },
    )
    assert validated.status_code == 201, validated.text
    assert validated.json()["status"] == "validated"
    assert validated.json()["valid_rows"] == 2

    executed = await business_client.post(
        f"/api/v1/governance/import-batches/{validated.json()['id']}/execute",
        headers=_headers(admin_token),
        json={"reason": "导入合成历史组织编码"},
    )
    assert executed.status_code == 200, executed.text
    assert executed.json()["status"] == "completed"
    assert executed.json()["imported_rows"] == 2

    parent = await db_session.scalar(
        select(Organization).where(Organization.code == "HIST-PARENT-001")
    )
    child = await db_session.scalar(
        select(Organization).where(Organization.code == "HIST-CHILD-001")
    )
    assert parent is not None and child is not None
    child_version = await db_session.scalar(
        select(OrganizationVersion).where(
            OrganizationVersion.organization_id == child.id
        )
    )
    assert child_version is not None
    assert child_version.parent_organization_id == parent.id
    assert await db_session.scalar(
        select(func.count()).select_from(OrganizationEvent).where(
            OrganizationEvent.organization_id.in_([parent.id, child.id]),
            OrganizationEvent.event_type == "CREATE",
        )
    ) == 2
    assert await db_session.scalar(
        select(func.count()).select_from(OutboxEvent).where(
            OutboxEvent.aggregate_id.in_([parent.id, child.id]),
            OutboxEvent.event_type == "organization.created",
        )
    ) == 2


async def test_organization_import_rejects_unknown_relations_and_cycles(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    await _create_organization_type(business_client, admin_token)
    response = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json={
            "entity_type": "organization",
            "source_system": "synthetic_ehr",
            "source_table": "synthetic_invalid_organizations",
            "idempotency_key": str(uuid4()),
            "rows": [
                {
                    "source_record_id": "unknown-type",
                    "data": {
                        "code": "UNKNOWN-TYPE",
                        "name": "合成未知类型组织",
                        "organization_type_code": "UNKNOWN",
                        "effective_from": "2026-01-01",
                    },
                },
                {
                    "source_record_id": "cycle-a",
                    "data": {
                        "code": "CYCLE-A",
                        "name": "合成循环A",
                        "organization_type_code": "BU",
                        "parent_code": "CYCLE-B",
                        "effective_from": "2026-01-01",
                    },
                },
                {
                    "source_record_id": "cycle-b",
                    "data": {
                        "code": "CYCLE-B",
                        "name": "合成循环B",
                        "organization_type_code": "BU",
                        "parent_code": "CYCLE-A",
                        "effective_from": "2026-01-01",
                    },
                },
                {
                    "source_record_id": "missing-parent",
                    "data": {
                        "code": "MISSING-PARENT",
                        "name": "合成缺失上级组织",
                        "organization_type_code": "BU",
                        "parent_code": "NOT-FOUND",
                        "effective_from": "2026-01-01",
                    },
                },
                {
                    "source_record_id": "child-of-rejected-parent",
                    "data": {
                        "code": "CHILD-OF-REJECTED",
                        "name": "合成被拒父级的子组织",
                        "organization_type_code": "BU",
                        "parent_code": "UNKNOWN-TYPE",
                        "effective_from": "2026-01-01",
                    },
                },
            ],
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "validated_with_errors"
    assert body["rejected_rows"] == 5
    errors_by_source = {
        row["source_record_id"]: {error["code"] for error in row["errors"]}
        for row in body["rows"]
    }
    assert "ORGANIZATION_TYPE_NOT_FOUND" in errors_by_source["unknown-type"]
    assert "ORGANIZATION_PARENT_CYCLE" in errors_by_source["cycle-a"]
    assert "ORGANIZATION_PARENT_CYCLE" in errors_by_source["cycle-b"]
    assert "ORGANIZATION_PARENT_NOT_FOUND" in errors_by_source["missing-parent"]
    assert "ORGANIZATION_PARENT_REJECTED" in errors_by_source[
        "child-of-rejected-parent"
    ]
