from datetime import date
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

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
    JobCatalogVersion,
    JobDimension,
    JobDimensionVersion,
    LegalEntity,
    Organization,
    OrganizationType,
    OrganizationVersion,
    Person,
)
from hris.modules.workforce.organization_models import OrganizationEvent


pytestmark = pytest.mark.asyncio


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_person_basic_import_is_non_sensitive_and_keeps_employee_number(
    business_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    template = await business_client.get(
        "/api/v1/governance/import-templates/person_basic",
        headers=_headers(admin_token),
    )
    assert template.status_code == 200, template.text
    assert template.json()["required_columns"] == ["employee_number", "legal_name"]
    assert set(template.json()["columns"]) == {
        "employee_number",
        "legal_name",
        "display_name",
        "former_name",
    }
    assert "birth_date" not in template.json()["columns"]
    assert "document_number" not in template.json()["columns"]

    validated = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json={
            "entity_type": "person_basic",
            "source_system": "synthetic_ehr",
            "source_table": "synthetic_person_basic",
            "file_name": "synthetic-person-basic.csv",
            "idempotency_key": str(uuid4()),
            "rows": [
                {
                    "source_record_id": "synthetic-person-1",
                    "data": {
                        "employee_number": "991001",
                        "legal_name": "Synthetic Imported Person",
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
        json={"reason": "Execute synthetic non-sensitive personnel import"},
    )
    assert executed.status_code == 200, executed.text
    assert executed.json()["status"] == "completed"
    person = await db_session.scalar(
        select(Person).where(Person.employee_number == "991001")
    )
    assert person is not None
    assert person.legal_name == "Synthetic Imported Person"
    assert person.display_name == "Synthetic Imported Person"

    row = await db_session.scalar(
        select(ImportBatchRow).where(
            ImportBatchRow.batch_id == UUID(validated.json()["id"])
        )
    )
    assert row is not None
    assert set(row.payload) == {"employee_number", "legal_name"}

    exported = await business_client.get(
        "/api/v1/governance/exports/person_basic",
        headers=_headers(admin_token),
    )
    assert exported.status_code == 200, exported.text
    header = exported.content.decode("utf-8-sig").splitlines()[0]
    assert header == "source_record_id,employee_number,legal_name,display_name,former_name"
    assert "birth_date" not in exported.text
    assert "document_number" not in exported.text


async def _seed_job_dimensions(db_session: AsyncSession) -> None:
    for dimension_type, code in (
        ("LEVEL", "L1"),
        ("GRADE", "G1"),
        ("CLASS", "TECH"),
        ("SEQUENCE", "ENGINEERING"),
    ):
        dimension = JobDimension(dimension_type=dimension_type, code=code)
        db_session.add(dimension)
        await db_session.flush()
        db_session.add(
            JobDimensionVersion(
                dimension_id=dimension.id,
                version=1,
                name=code,
                sort_order=0,
                status="active",
                effective_from=date(2026, 1, 1),
                is_current=True,
                change_reason="合成导入测试",
            )
        )
    await db_session.flush()


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
                "job_code": "SYNTHETIC_ENGINEER",
                "job_name": "合成工程师",
                "level_code": "L1",
                "grade_code": "G1",
                "class_code": "TECH",
                "sequence_code": "ENGINEERING",
                "effective_from": "2026-01-01",
                "status": "active",
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
    if entity_type == "job":
        await _seed_job_dimensions(db_session)
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


async def test_job_dimension_import_validates_and_orders_parent_dependencies(
    business_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    rows = [
        ("LEVEL", "LEVEL_06", "六级", "GRADE", "GRADE_02"),
        ("GRADE", "GRADE_02", "二等", "CLASS", "CLASS_02"),
        ("CLASS", "CLASS_02", "二级职类", "SEQUENCE", "TECH"),
        ("SEQUENCE", "TECH", "技术", None, None),
    ]
    validated = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json={
            "entity_type": "job_dimension",
            "source_system": "synthetic_ehr",
            "source_table": "synthetic_job_dimensions",
            "idempotency_key": str(uuid4()),
            "rows": [
                {
                    "source_record_id": f"{dimension_type}-{code}",
                    "data": {
                        "dimension_type": dimension_type,
                        "dimension_code": code,
                        "dimension_name": name,
                        "parent_dimension_type": parent_type,
                        "parent_dimension_code": parent_code,
                        "sort_order": index * 10,
                        "effective_from": "2026-01-01",
                        "status": "active",
                    },
                }
                for index, (dimension_type, code, name, parent_type, parent_code) in enumerate(rows, start=1)
            ],
        },
    )
    assert validated.status_code == 201, validated.text
    assert validated.json()["status"] == "validated"

    executed = await business_client.post(
        f"/api/v1/governance/import-batches/{validated.json()['id']}/execute",
        headers=_headers(admin_token),
        json={"reason": "验证职务维度导入顺序"},
    )
    assert executed.status_code == 200, executed.text
    assert executed.json()["imported_rows"] == 4
    assert await db_session.scalar(select(func.count()).select_from(JobDimension)) == 4


async def test_job_history_import_appends_versions_in_effective_date_order(
    business_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    await _seed_job_dimensions(db_session)
    job_response = await business_client.post(
        "/api/v1/workforce/jobs",
        headers=_headers(admin_token),
        json={
            "code": "SYNTHETIC_HISTORY_JOB",
            "name": "合成历史职务",
            "level_code": "L1",
            "grade_code": "G1",
            "class_code": "TECH",
            "sequence_code": "ENGINEERING",
            "effective_from": "2026-01-01",
            "status": "active",
            "change_reason": "建立合成历史职务首版本",
        },
    )
    assert job_response.status_code == 201, job_response.text

    dimension_batch = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json={
            "entity_type": "job_dimension_version",
            "source_system": "synthetic_ehr",
            "source_table": "synthetic_job_dimension_history",
            "idempotency_key": str(uuid4()),
            "rows": [
                {
                    "source_record_id": "level-l1-2028",
                    "data": {
                        "dimension_type": "LEVEL",
                        "dimension_code": "L1",
                        "dimension_name": "合成职级2028",
                        "sort_order": 30,
                        "effective_from": "2028-01-01",
                        "status": "active",
                        "change_reason": "导入2028职级版本",
                    },
                },
                {
                    "source_record_id": "level-l1-2027",
                    "data": {
                        "dimension_type": "LEVEL",
                        "dimension_code": "L1",
                        "dimension_name": "合成职级2027",
                        "sort_order": 20,
                        "effective_from": "2027-01-01",
                        "status": "active",
                        "change_reason": "导入2027职级版本",
                    },
                },
            ],
        },
    )
    assert dimension_batch.status_code == 201, dimension_batch.text
    assert dimension_batch.json()["valid_rows"] == 2
    executed_dimensions = await business_client.post(
        f"/api/v1/governance/import-batches/{dimension_batch.json()['id']}/execute",
        headers=_headers(admin_token),
        json={"reason": "执行合成职级历史版本导入"},
    )
    assert executed_dimensions.status_code == 200, executed_dimensions.text
    assert executed_dimensions.json()["imported_rows"] == 2

    job_batch = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json={
            "entity_type": "job_version",
            "source_system": "synthetic_ehr",
            "source_table": "synthetic_job_history",
            "idempotency_key": str(uuid4()),
            "rows": [
                {
                    "source_record_id": "history-job-2028",
                    "data": {
                        "job_code": "SYNTHETIC_HISTORY_JOB",
                        "job_name": "合成历史职务2028",
                        "level_code": "L1",
                        "grade_code": "G1",
                        "class_code": "TECH",
                        "sequence_code": "ENGINEERING",
                        "effective_from": "2028-01-01",
                        "status": "active",
                        "change_reason": "导入2028职务版本",
                    },
                },
                {
                    "source_record_id": "history-job-2027",
                    "data": {
                        "job_code": "SYNTHETIC_HISTORY_JOB",
                        "job_name": "合成历史职务2027",
                        "level_code": "L1",
                        "grade_code": "G1",
                        "class_code": "TECH",
                        "sequence_code": "ENGINEERING",
                        "effective_from": "2027-01-01",
                        "status": "active",
                        "change_reason": "导入2027职务版本",
                    },
                },
            ],
        },
    )
    assert job_batch.status_code == 201, job_batch.text
    assert job_batch.json()["valid_rows"] == 2
    executed_jobs = await business_client.post(
        f"/api/v1/governance/import-batches/{job_batch.json()['id']}/execute",
        headers=_headers(admin_token),
        json={"reason": "执行合成职务历史版本导入"},
    )
    assert executed_jobs.status_code == 200, executed_jobs.text
    assert executed_jobs.json()["imported_rows"] == 2

    job = await db_session.scalar(
        select(JobCatalog).where(JobCatalog.code == "SYNTHETIC_HISTORY_JOB")
    )
    assert job is not None and job.name == "合成历史职务2028"
    job_versions = list(
        (
            await db_session.scalars(
                select(JobCatalogVersion)
                .where(JobCatalogVersion.job_id == job.id)
                .order_by(JobCatalogVersion.version)
            )
        ).all()
    )
    assert [item.effective_from for item in job_versions] == [
        date(2026, 1, 1),
        date(2027, 1, 1),
        date(2028, 1, 1),
    ]
    assert [item.effective_to for item in job_versions] == [
        date(2026, 12, 31),
        date(2027, 12, 31),
        None,
    ]


async def test_job_history_import_rejects_backward_and_unknown_stable_codes(
    business_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    await _seed_job_dimensions(db_session)
    dimension = await db_session.scalar(
        select(JobDimension).where(
            JobDimension.dimension_type == "LEVEL",
            JobDimension.code == "L1",
        )
    )
    assert dimension is not None
    response = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json={
            "entity_type": "job_dimension_version",
            "source_system": "synthetic_ehr",
            "source_table": "synthetic_invalid_job_history",
            "idempotency_key": str(uuid4()),
            "rows": [
                {
                    "source_record_id": "backward-level",
                    "data": {
                        "dimension_type": "LEVEL",
                        "dimension_code": "L1",
                        "dimension_name": "倒插职级",
                        "sort_order": 10,
                        "effective_from": "2025-01-01",
                        "status": "active",
                        "change_reason": "验证倒插拒绝",
                    },
                },
                {
                    "source_record_id": "unknown-level",
                    "data": {
                        "dimension_type": "LEVEL",
                        "dimension_code": "UNKNOWN_LEVEL",
                        "dimension_name": "未知职级",
                        "sort_order": 10,
                        "effective_from": "2027-01-01",
                        "status": "active",
                        "change_reason": "验证未知代码拒绝",
                    },
                },
            ],
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["rejected_rows"] == 2
    errors_by_source = {
        row["source_record_id"]: {error["code"] for error in row["errors"]}
        for row in response.json()["rows"]
    }
    assert "JOB_DIMENSION_VERSION_DATE_NOT_FORWARD" in errors_by_source[
        "backward-level"
    ]
    assert "JOB_DIMENSION_NOT_FOUND" in errors_by_source["unknown-level"]


async def test_job_dimension_history_import_rejects_parent_cycle(
    business_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    await _seed_job_dimensions(db_session)
    response = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json={
            "entity_type": "job_dimension_version",
            "source_system": "synthetic_ehr",
            "source_table": "synthetic_job_dimension_cycle_history",
            "idempotency_key": str(uuid4()),
            "rows": [
                {
                    "source_record_id": "level-cycle-2027",
                    "data": {
                        "dimension_type": "LEVEL",
                        "dimension_code": "L1",
                        "dimension_name": "循环职级",
                        "parent_dimension_type": "GRADE",
                        "parent_dimension_code": "G1",
                        "sort_order": 10,
                        "effective_from": "2027-01-01",
                        "status": "active",
                        "change_reason": "验证历史维度循环拒绝",
                    },
                },
                {
                    "source_record_id": "grade-cycle-2027",
                    "data": {
                        "dimension_type": "GRADE",
                        "dimension_code": "G1",
                        "dimension_name": "循环职等",
                        "parent_dimension_type": "LEVEL",
                        "parent_dimension_code": "L1",
                        "sort_order": 10,
                        "effective_from": "2027-01-01",
                        "status": "active",
                        "change_reason": "验证历史维度循环拒绝",
                    },
                },
            ],
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["rejected_rows"] == 2
    assert all(
        "JOB_DIMENSION_PARENT_CYCLE"
        in {error["code"] for error in row["errors"]}
        for row in response.json()["rows"]
    )


async def test_job_history_template_is_import_only(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    template = await business_client.get(
        "/api/v1/governance/import-templates/job_version",
        headers=_headers(admin_token),
    )
    assert template.status_code == 200, template.text
    assert "change_reason" in template.json()["required_columns"]

    rejected_export = await business_client.get(
        "/api/v1/governance/exports/job_version",
        headers=_headers(admin_token),
    )
    assert rejected_export.status_code == 422, rejected_export.text


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


async def test_organization_history_import_appends_versions_in_effective_date_order(
    business_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    await _create_organization_type(business_client, admin_token)
    initial_batch = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json={
            "entity_type": "organization",
            "source_system": "synthetic_ehr",
            "source_table": "synthetic_organization_history_base",
            "idempotency_key": str(uuid4()),
            "rows": [
                {
                    "source_record_id": "history-root-base",
                    "data": {
                        "code": "HISTORY-ROOT",
                        "name": "合成历史根组织",
                        "organization_type_code": "BU",
                        "country_code": "CN",
                        "effective_from": "2024-01-01",
                    },
                },
                {
                    "source_record_id": "history-child-base",
                    "data": {
                        "code": "HISTORY-CHILD",
                        "name": "合成历史子组织",
                        "organization_type_code": "BU",
                        "parent_code": "HISTORY-ROOT",
                        "country_code": "CN",
                        "effective_from": "2024-01-01",
                    },
                },
            ],
        },
    )
    assert initial_batch.status_code == 201, initial_batch.text
    initial_execution = await business_client.post(
        f"/api/v1/governance/import-batches/{initial_batch.json()['id']}/execute",
        headers=_headers(admin_token),
        json={"reason": "建立组织历史版本导入测试基线"},
    )
    assert initial_execution.status_code == 200, initial_execution.text
    assert initial_execution.json()["imported_rows"] == 2

    template = await business_client.get(
        "/api/v1/governance/import-templates/organization_version",
        headers=_headers(admin_token),
    )
    assert template.status_code == 200, template.text
    assert "change_reason" in template.json()["required_columns"]
    assert "effective_from" in template.json()["required_columns"]

    version_batch = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json={
            "entity_type": "organization_version",
            "source_system": "synthetic_ehr",
            "source_table": "synthetic_organization_history",
            "idempotency_key": str(uuid4()),
            "rows": [
                {
                    "source_record_id": "history-child-2026",
                    "data": {
                        "organization_code": "HISTORY-CHILD",
                        "name": "合成历史子组织2026",
                        "organization_type_code": "BU",
                        "parent_code": "HISTORY-ROOT",
                        "country_code": "CN",
                        "status": "active",
                        "effective_from": "2026-01-01",
                        "change_reason": "导入2026组织版本",
                    },
                },
                {
                    "source_record_id": "history-child-2025",
                    "data": {
                        "organization_code": "HISTORY-CHILD",
                        "name": "合成历史子组织2025",
                        "organization_type_code": "BU",
                        "parent_code": "HISTORY-ROOT",
                        "country_code": "CN",
                        "status": "active",
                        "effective_from": "2025-01-01",
                        "change_reason": "导入2025组织版本",
                    },
                },
            ],
        },
    )
    assert version_batch.status_code == 201, version_batch.text
    assert version_batch.json()["status"] == "validated"
    assert version_batch.json()["valid_rows"] == 2

    version_execution = await business_client.post(
        f"/api/v1/governance/import-batches/{version_batch.json()['id']}/execute",
        headers=_headers(admin_token),
        json={"reason": "执行合成组织历史版本导入"},
    )
    assert version_execution.status_code == 200, version_execution.text
    assert version_execution.json()["status"] == "completed"
    assert version_execution.json()["imported_rows"] == 2

    organization = await db_session.scalar(
        select(Organization).where(Organization.code == "HISTORY-CHILD")
    )
    assert organization is not None
    versions = list(
        (
            await db_session.scalars(
                select(OrganizationVersion)
                .where(OrganizationVersion.organization_id == organization.id)
                .order_by(OrganizationVersion.version)
            )
        ).all()
    )
    assert [item.name for item in versions] == [
        "合成历史子组织",
        "合成历史子组织2025",
        "合成历史子组织2026",
    ]
    assert [item.effective_from for item in versions] == [
        date(2024, 1, 1),
        date(2025, 1, 1),
        date(2026, 1, 1),
    ]
    assert [item.effective_to for item in versions] == [
        date(2024, 12, 31),
        date(2025, 12, 31),
        None,
    ]
    events = list(
        (
            await db_session.scalars(
                select(OrganizationEvent)
                .where(
                    OrganizationEvent.organization_id == organization.id,
                    OrganizationEvent.event_type == "VERSION_CHANGE",
                )
                .order_by(OrganizationEvent.effective_date)
            )
        ).all()
    )
    assert [event.status for event in events] == ["applied", "applied"]
    assert [event.change_reason for event in events] == [
        "导入2025组织版本",
        "导入2026组织版本",
    ]

    rejected_export = await business_client.get(
        "/api/v1/governance/exports/organization_version",
        headers=_headers(admin_token),
    )
    assert rejected_export.status_code == 422, rejected_export.text


async def test_organization_history_import_rejects_invalid_stable_relations(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    await _create_organization_type(business_client, admin_token)
    initial_batch = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json={
            "entity_type": "organization",
            "source_system": "synthetic_ehr",
            "source_table": "synthetic_organization_invalid_history_base",
            "idempotency_key": str(uuid4()),
            "rows": [
                {
                    "source_record_id": "invalid-history-root-base",
                    "data": {
                        "code": "INVALID-HISTORY-ROOT",
                        "name": "合成组织历史校验根节点",
                        "organization_type_code": "BU",
                        "country_code": "CN",
                        "effective_from": "2024-01-01",
                    },
                }
            ],
        },
    )
    assert initial_batch.status_code == 201, initial_batch.text
    initial_execution = await business_client.post(
        f"/api/v1/governance/import-batches/{initial_batch.json()['id']}/execute",
        headers=_headers(admin_token),
        json={"reason": "建立组织历史拒绝测试基线"},
    )
    assert initial_execution.status_code == 200, initial_execution.text

    response = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json={
            "entity_type": "organization_version",
            "source_system": "synthetic_ehr",
            "source_table": "synthetic_invalid_organization_history",
            "idempotency_key": str(uuid4()),
            "rows": [
                {
                    "source_record_id": "unknown-organization",
                    "data": {
                        "organization_code": "ORGANIZATION-NOT-FOUND",
                        "name": "未知组织版本",
                        "organization_type_code": "BU",
                        "status": "active",
                        "effective_from": "2025-01-01",
                        "change_reason": "验证未知组织拒绝",
                    },
                },
                {
                    "source_record_id": "backward-version",
                    "data": {
                        "organization_code": "INVALID-HISTORY-ROOT",
                        "name": "倒插组织版本",
                        "organization_type_code": "BU",
                        "status": "active",
                        "effective_from": "2023-01-01",
                        "change_reason": "验证倒插拒绝",
                    },
                },
                {
                    "source_record_id": "unknown-type",
                    "data": {
                        "organization_code": "INVALID-HISTORY-ROOT",
                        "name": "未知类型组织版本",
                        "organization_type_code": "UNKNOWN_TYPE",
                        "status": "active",
                        "effective_from": "2025-01-01",
                        "change_reason": "验证未知组织类型拒绝",
                    },
                },
                {
                    "source_record_id": "missing-parent",
                    "data": {
                        "organization_code": "INVALID-HISTORY-ROOT",
                        "name": "缺失父级组织版本",
                        "organization_type_code": "BU",
                        "parent_code": "PARENT-NOT-FOUND",
                        "status": "active",
                        "effective_from": "2026-01-01",
                        "change_reason": "验证缺失父级拒绝",
                    },
                },
            ],
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "validated_with_errors"
    assert response.json()["rejected_rows"] == 4
    errors_by_source = {
        row["source_record_id"]: {error["code"] for error in row["errors"]}
        for row in response.json()["rows"]
    }
    assert "ORGANIZATION_NOT_FOUND" in errors_by_source["unknown-organization"]
    assert "ORGANIZATION_VERSION_DATE_NOT_FORWARD" in errors_by_source[
        "backward-version"
    ]
    assert "ORGANIZATION_TYPE_NOT_FOUND" in errors_by_source["unknown-type"]
    assert "ORGANIZATION_PARENT_NOT_FOUND" in errors_by_source["missing-parent"]


async def test_organization_history_import_keeps_future_event_and_replays_source(
    business_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    await _create_organization_type(business_client, admin_token)
    initial_batch = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json={
            "entity_type": "organization",
            "source_system": "synthetic_ehr",
            "source_table": "synthetic_future_organization_base",
            "idempotency_key": str(uuid4()),
            "rows": [
                {
                    "source_record_id": "future-organization-base",
                    "data": {
                        "code": "FUTURE-HISTORY-ORG",
                        "name": "合成未来组织基线",
                        "organization_type_code": "BU",
                        "country_code": "CN",
                        "effective_from": "2024-01-01",
                    },
                }
            ],
        },
    )
    assert initial_batch.status_code == 201, initial_batch.text
    initial_execution = await business_client.post(
        f"/api/v1/governance/import-batches/{initial_batch.json()['id']}/execute",
        headers=_headers(admin_token),
        json={"reason": "建立未来组织版本导入基线"},
    )
    assert initial_execution.status_code == 200, initial_execution.text

    source_row = {
        "source_record_id": "future-organization-2099",
        "data": {
            "organization_code": "FUTURE-HISTORY-ORG",
            "name": "合成未来组织2099",
            "organization_type_code": "BU",
            "country_code": "CN",
            "status": "active",
            "effective_from": "2099-01-01",
            "change_reason": "导入未来组织版本",
        },
    }
    first_batch = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json={
            "entity_type": "organization_version",
            "source_system": "synthetic_ehr",
            "source_table": "synthetic_future_organization_history",
            "idempotency_key": str(uuid4()),
            "rows": [source_row],
        },
    )
    assert first_batch.status_code == 201, first_batch.text
    first_execution = await business_client.post(
        f"/api/v1/governance/import-batches/{first_batch.json()['id']}/execute",
        headers=_headers(admin_token),
        json={"reason": "执行未来组织版本导入"},
    )
    assert first_execution.status_code == 200, first_execution.text
    assert first_execution.json()["imported_rows"] == 1

    organization = await db_session.scalar(
        select(Organization).where(Organization.code == "FUTURE-HISTORY-ORG")
    )
    assert organization is not None
    event = await db_session.scalar(
        select(OrganizationEvent).where(
            OrganizationEvent.organization_id == organization.id,
            OrganizationEvent.event_type == "VERSION_CHANGE",
            OrganizationEvent.effective_date == date(2099, 1, 1),
        )
    )
    assert event is not None and event.status == "planned"
    assert await db_session.scalar(
        select(func.count())
        .select_from(OrganizationVersion)
        .where(OrganizationVersion.organization_id == organization.id)
    ) == 1

    repeated_batch = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json={
            "entity_type": "organization_version",
            "source_system": "synthetic_ehr",
            "source_table": "synthetic_future_organization_history",
            "idempotency_key": str(uuid4()),
            "rows": [source_row],
        },
    )
    assert repeated_batch.status_code == 201, repeated_batch.text
    assert repeated_batch.json()["status"] == "validated"
    assert repeated_batch.json()["skipped_rows"] == 1
    repeated_execution = await business_client.post(
        f"/api/v1/governance/import-batches/{repeated_batch.json()['id']}/execute",
        headers=_headers(admin_token),
        json={"reason": "验证未来组织版本来源重放"},
    )
    assert repeated_execution.status_code == 200, repeated_execution.text
    assert repeated_execution.json()["skipped_rows"] == 1
    assert repeated_execution.json()["imported_rows"] == 0
    assert await db_session.scalar(
        select(func.count())
        .select_from(OrganizationEvent)
        .where(
            OrganizationEvent.organization_id == organization.id,
            OrganizationEvent.event_type == "VERSION_CHANGE",
            OrganizationEvent.effective_date == date(2099, 1, 1),
        )
    ) == 1


async def test_organization_history_import_replaces_cancelled_date_without_ambiguity(
    business_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    await _create_organization_type(business_client, admin_token)
    base_batch = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json={
            "entity_type": "organization",
            "source_system": "synthetic_ehr",
            "source_table": "synthetic_cancelled_history_base",
            "idempotency_key": str(uuid4()),
            "rows": [
                {
                    "source_record_id": "cancelled-history-base",
                    "data": {
                        "code": "CANCELLED-HISTORY-ORG",
                        "name": "合成取消事件组织",
                        "organization_type_code": "BU",
                        "country_code": "CN",
                        "effective_from": "2024-01-01",
                    },
                }
            ],
        },
    )
    assert base_batch.status_code == 201, base_batch.text
    base_execution = await business_client.post(
        f"/api/v1/governance/import-batches/{base_batch.json()['id']}/execute",
        headers=_headers(admin_token),
        json={"reason": "建立取消事件重建基线"},
    )
    assert base_execution.status_code == 200, base_execution.text

    organization = await db_session.scalar(
        select(Organization).where(Organization.code == "CANCELLED-HISTORY-ORG")
    )
    organization_type = await db_session.scalar(
        select(OrganizationType).where(OrganizationType.code == "BU")
    )
    assert organization is not None and organization_type is not None
    scheduled = await business_client.post(
        f"/api/v1/organizations/{organization.id}/versions",
        headers=_headers(admin_token),
        json={
            "name": "待取消版本",
            "organization_type_id": str(organization_type.id),
            "parent_organization_id": None,
            "country_code": "CN",
            "status": "active",
            "effective_date": "2098-01-01",
            "command": {
                "expected_version": 1,
                "idempotency_key": str(uuid4()),
                "change_reason": "建立待取消版本",
            },
        },
    )
    assert scheduled.status_code == 201, scheduled.text
    cancelled = await business_client.post(
        f"/api/v1/organization-events/{scheduled.json()['id']}/cancel",
        headers=_headers(admin_token),
        json={
            "expected_version": 2,
            "idempotency_key": str(uuid4()),
            "change_reason": "验证取消后同日重建",
        },
    )
    assert cancelled.status_code == 200, cancelled.text

    replacement_row = {
        "source_record_id": "replacement-2098",
        "data": {
            "organization_code": "CANCELLED-HISTORY-ORG",
            "name": "替代版本",
            "organization_type_code": "BU",
            "country_code": "CN",
            "status": "active",
            "effective_from": "2098-01-01",
            "change_reason": "导入同日替代版本",
        },
    }
    replacement_batch = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json={
            "entity_type": "organization_version",
            "source_system": "synthetic_ehr",
            "source_table": "synthetic_cancelled_history_replacement",
            "idempotency_key": str(uuid4()),
            "rows": [replacement_row],
        },
    )
    assert replacement_batch.status_code == 201, replacement_batch.text
    assert replacement_batch.json()["valid_rows"] == 1
    replacement_execution = await business_client.post(
        f"/api/v1/governance/import-batches/{replacement_batch.json()['id']}/execute",
        headers=_headers(admin_token),
        json={"reason": "执行同日替代版本"},
    )
    assert replacement_execution.status_code == 200, replacement_execution.text
    assert replacement_execution.json()["imported_rows"] == 1

    replay_batch = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json={
            "entity_type": "organization_version",
            "source_system": "synthetic_ehr",
            "source_table": "synthetic_cancelled_history_replacement",
            "idempotency_key": str(uuid4()),
            "rows": [replacement_row],
        },
    )
    assert replay_batch.status_code == 201, replay_batch.text
    assert replay_batch.json()["skipped_rows"] == 1
    cancelled_source_row = {
        "source_record_id": "cancelled-source-2099",
        "data": {
            "organization_code": "CANCELLED-HISTORY-ORG",
            "name": "来源事件后续被取消",
            "organization_type_code": "BU",
            "country_code": "CN",
            "status": "active",
            "effective_from": "2099-01-01",
            "change_reason": "导入后取消并重放",
        },
    }
    cancelled_source_batch = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json={
            "entity_type": "organization_version",
            "source_system": "synthetic_ehr",
            "source_table": "synthetic_cancelled_source_replay",
            "idempotency_key": str(uuid4()),
            "rows": [cancelled_source_row],
        },
    )
    assert cancelled_source_batch.status_code == 201, cancelled_source_batch.text
    cancelled_source_execution = await business_client.post(
        f"/api/v1/governance/import-batches/{cancelled_source_batch.json()['id']}/execute",
        headers=_headers(admin_token),
        json={"reason": "导入后取消来源事件"},
    )
    assert cancelled_source_execution.status_code == 200, cancelled_source_execution.text
    cancelled_source_event_id = cancelled_source_execution.json()["rows"][0][
        "target_id"
    ]
    cancelled_source_event = await business_client.post(
        f"/api/v1/organization-events/{cancelled_source_event_id}/cancel",
        headers=_headers(admin_token),
        json={
            "expected_version": 3,
            "idempotency_key": str(uuid4()),
            "change_reason": "验证已取消来源仍保持幂等",
        },
    )
    assert cancelled_source_event.status_code == 200, cancelled_source_event.text
    cancelled_source_replay = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json={
            "entity_type": "organization_version",
            "source_system": "synthetic_ehr",
            "source_table": "synthetic_cancelled_source_replay",
            "idempotency_key": str(uuid4()),
            "rows": [cancelled_source_row],
        },
    )
    assert cancelled_source_replay.status_code == 201, cancelled_source_replay.text
    assert cancelled_source_replay.json()["skipped_rows"] == 1
    events = list(
        (
            await db_session.scalars(
                select(OrganizationEvent)
                .where(
                    OrganizationEvent.organization_id == organization.id,
                    OrganizationEvent.event_type == "VERSION_CHANGE",
                    OrganizationEvent.effective_date == date(2098, 1, 1),
                )
                .order_by(OrganizationEvent.created_at)
            )
        ).all()
    )
    assert [event.status for event in events] == ["cancelled", "planned"]


async def test_organization_history_execution_rechecks_source_and_event_fingerprint(
    business_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    await _create_organization_type(business_client, admin_token)
    base_batch = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json={
            "entity_type": "organization",
            "source_system": "synthetic_ehr",
            "source_table": "synthetic_execution_recheck_base",
            "idempotency_key": str(uuid4()),
            "rows": [
                {
                    "source_record_id": "execution-recheck-base",
                    "data": {
                        "code": "EXECUTION-RECHECK-ORG",
                        "name": "合成执行复核组织",
                        "organization_type_code": "BU",
                        "country_code": "CN",
                        "effective_from": "2024-01-01",
                    },
                }
            ],
        },
    )
    assert base_batch.status_code == 201, base_batch.text
    base_execution = await business_client.post(
        f"/api/v1/governance/import-batches/{base_batch.json()['id']}/execute",
        headers=_headers(admin_token),
        json={"reason": "建立执行复核测试基线"},
    )
    assert base_execution.status_code == 200, base_execution.text

    source_system = "synthetic_ehr"
    source_table = "synthetic_execution_recheck_history"
    repeated_row = {
        "source_record_id": "same-source-2097",
        "data": {
            "organization_code": "EXECUTION-RECHECK-ORG",
            "name": "合成执行复核组织2097",
            "organization_type_code": "BU",
            "country_code": "CN",
            "status": "active",
            "effective_from": "2097-01-01",
            "change_reason": "验证执行前来源复核",
        },
    }

    validated_batches = []
    for _ in range(2):
        validated = await business_client.post(
            "/api/v1/governance/import-batches/validate",
            headers=_headers(admin_token),
            json={
                "entity_type": "organization_version",
                "source_system": source_system,
                "source_table": source_table,
                "idempotency_key": str(uuid4()),
                "rows": [repeated_row],
            },
        )
        assert validated.status_code == 201, validated.text
        assert validated.json()["rows"][0]["status"] == "valid"
        validated_batches.append(validated.json()["id"])

    first_execution = await business_client.post(
        f"/api/v1/governance/import-batches/{validated_batches[0]}/execute",
        headers=_headers(admin_token),
        json={"reason": "执行第一批相同来源"},
    )
    assert first_execution.status_code == 200, first_execution.text
    assert first_execution.json()["imported_rows"] == 1

    second_execution = await business_client.post(
        f"/api/v1/governance/import-batches/{validated_batches[1]}/execute",
        headers=_headers(admin_token),
        json={"reason": "执行第二批相同来源"},
    )
    assert second_execution.status_code == 200, second_execution.text
    assert second_execution.json()["status"] == "completed"
    assert second_execution.json()["imported_rows"] == 0
    assert second_execution.json()["skipped_rows"] == 1
    assert second_execution.json()["rows"][0]["status"] == "skipped"

    organization = await db_session.scalar(
        select(Organization).where(Organization.code == "EXECUTION-RECHECK-ORG")
    )
    organization_type = await db_session.scalar(
        select(OrganizationType).where(OrganizationType.code == "BU")
    )
    assert organization is not None and organization_type is not None

    poisoned_source_id = "poisoned-source-2099"
    poisoned_idempotency = uuid5(
        NAMESPACE_URL,
        (
            "corehr:organization-version-import:"
            f"{source_system}:{source_table}:{poisoned_source_id}"
        ),
    )
    poisoned_event = await business_client.post(
        f"/api/v1/organizations/{organization.id}/versions",
        headers=_headers(admin_token),
        json={
            "name": "预植入的不一致版本",
            "organization_type_id": str(organization_type.id),
            "parent_organization_id": None,
            "country_code": "CN",
            "status": "active",
            "effective_date": "2098-01-01",
            "command": {
                "expected_version": 2,
                "idempotency_key": str(poisoned_idempotency),
                "change_reason": "预植入不一致事件",
            },
        },
    )
    assert poisoned_event.status_code == 201, poisoned_event.text

    poisoned_batch = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json={
            "entity_type": "organization_version",
            "source_system": source_system,
            "source_table": source_table,
            "idempotency_key": str(uuid4()),
            "rows": [
                {
                    "source_record_id": poisoned_source_id,
                    "data": {
                        "organization_code": "EXECUTION-RECHECK-ORG",
                        "name": "应导入的组织版本2099",
                        "organization_type_code": "BU",
                        "country_code": "CN",
                        "status": "active",
                        "effective_from": "2099-01-01",
                        "change_reason": "验证事件业务指纹",
                    },
                }
            ],
        },
    )
    assert poisoned_batch.status_code == 201, poisoned_batch.text
    assert poisoned_batch.json()["rows"][0]["status"] == "valid"
    poisoned_execution = await business_client.post(
        f"/api/v1/governance/import-batches/{poisoned_batch.json()['id']}/execute",
        headers=_headers(admin_token),
        json={"reason": "验证预植入事件不会被接管"},
    )
    assert poisoned_execution.status_code == 200, poisoned_execution.text
    assert poisoned_execution.json()["status"] == "completed_with_errors"
    assert poisoned_execution.json()["rows"][0]["status"] == "rejected"
    assert poisoned_execution.json()["rows"][0]["errors"][0]["code"] == (
        "IDEMPOTENCY_KEY_CONFLICT"
    )
    assert await db_session.scalar(
        select(func.count())
        .select_from(ExternalRecordLink)
        .where(
            ExternalRecordLink.source_system == source_system,
            ExternalRecordLink.source_table == source_table,
            ExternalRecordLink.source_record_id == poisoned_source_id,
            ExternalRecordLink.target_type == "organization_version",
        )
    ) == 0

    corrupted_source_id = "corrupted-link-2100"
    corrupted_batch = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json={
            "entity_type": "organization_version",
            "source_system": source_system,
            "source_table": source_table,
            "idempotency_key": str(uuid4()),
            "rows": [
                {
                    "source_record_id": corrupted_source_id,
                    "data": {
                        "organization_code": "EXECUTION-RECHECK-ORG",
                        "name": "不应接管错误链接的版本2100",
                        "organization_type_code": "BU",
                        "country_code": "CN",
                        "status": "active",
                        "effective_from": "2100-01-01",
                        "change_reason": "验证错误来源链接拒绝",
                    },
                }
            ],
        },
    )
    assert corrupted_batch.status_code == 201, corrupted_batch.text
    corrupted_batch_id = UUID(corrupted_batch.json()["id"])
    corrupted_row = await db_session.scalar(
        select(ImportBatchRow).where(
            ImportBatchRow.batch_id == corrupted_batch_id,
            ImportBatchRow.source_record_id == corrupted_source_id,
        )
    )
    assert corrupted_row is not None
    db_session.add(
        ExternalRecordLink(
            source_system=source_system,
            source_table=source_table,
            source_record_id=corrupted_source_id,
            target_type="organization_version",
            target_id=uuid4(),
            source_updated_at=None,
            source_checksum=corrupted_row.source_checksum,
        )
    )
    await db_session.flush()

    corrupted_execution = await business_client.post(
        f"/api/v1/governance/import-batches/{corrupted_batch_id}/execute",
        headers=_headers(admin_token),
        json={"reason": "验证执行期错误来源链接拒绝"},
    )
    assert corrupted_execution.status_code == 200, corrupted_execution.text
    assert corrupted_execution.json()["status"] == "completed_with_errors"
    assert corrupted_execution.json()["rows"][0]["status"] == "rejected"
    assert corrupted_execution.json()["rows"][0]["errors"][0]["code"] == (
        "EXTERNAL_LINK_TARGET_INVALID"
    )

    preexisting_link_validation = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json={
            "entity_type": "organization_version",
            "source_system": source_system,
            "source_table": source_table,
            "idempotency_key": str(uuid4()),
            "rows": [
                {
                    "source_record_id": corrupted_source_id,
                    "data": {
                        "organization_code": "EXECUTION-RECHECK-ORG",
                        "name": "不应接管错误链接的版本2100",
                        "organization_type_code": "BU",
                        "country_code": "CN",
                        "status": "active",
                        "effective_from": "2100-01-01",
                        "change_reason": "验证错误来源链接拒绝",
                    },
                }
            ],
        },
    )
    assert preexisting_link_validation.status_code == 201
    assert preexisting_link_validation.json()["status"] == "validated_with_errors"
    assert preexisting_link_validation.json()["rows"][0]["status"] == "rejected"
    assert preexisting_link_validation.json()["rows"][0]["errors"][0]["code"] == (
        "EXTERNAL_LINK_TARGET_INVALID"
    )
