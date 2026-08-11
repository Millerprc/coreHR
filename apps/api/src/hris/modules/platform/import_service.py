import hashlib
import json
from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.config import get_settings
from hris.core.errors import ApiError
from hris.modules.platform.configuration_schemas import DictionaryCreate
from hris.modules.platform.governance_models import OutboxEvent
from hris.modules.platform.import_models import ImportBatch, ImportBatchRow
from hris.modules.platform.import_schemas import (
    DictionaryItemImport,
    ImportBatchValidate,
    ImportEntityType,
    JobDimensionImport,
    JobImport,
    OrganizationImport,
)
from hris.modules.platform.models import (
    DataDictionary,
    DataDictionaryItem,
    ExternalRecordLink,
)
from hris.modules.workforce.extended_schemas import LegalEntityCreate
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
)
from hris.modules.workforce.organization_models import OrganizationEvent
from hris.modules.workforce.organization_schemas import OrganizationTypeCreate


_TARGET_TYPES: dict[str, str] = {
    "dictionary": "data_dictionary",
    "dictionary_item": "data_dictionary_item",
    "organization_type": "organization_type",
    "legal_entity": "legal_entity",
    "job_dimension": "job_dimension",
    "job": "job",
    "organization": "organization",
}

_TEMPLATES: dict[str, tuple[list[str], list[str]]] = {
    "dictionary": (
        ["code", "name", "english_name", "description"],
        ["code", "name"],
    ),
    "dictionary_item": (
        [
            "dictionary_code",
            "code",
            "name",
            "english_name",
            "parent_item_code",
            "sort_order",
            "description",
        ],
        ["dictionary_code", "code", "name"],
    ),
    "organization_type": (
        ["code", "name", "sort_order"],
        ["code", "name"],
    ),
    "legal_entity": (
        [
            "code",
            "name",
            "registered_name",
            "country_code",
            "registration_number",
            "effective_from",
            "effective_to",
        ],
        ["code", "name", "country_code", "effective_from"],
    ),
    "job": (
        [
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
        [
            "job_code",
            "job_name",
            "level_code",
            "grade_code",
            "class_code",
            "sequence_code",
            "effective_from",
            "status",
        ],
    ),
    "job_dimension": (
        [
            "dimension_type",
            "dimension_code",
            "dimension_name",
            "parent_dimension_type",
            "parent_dimension_code",
            "sort_order",
            "effective_from",
            "effective_to",
            "status",
            "notes",
        ],
        [
            "dimension_type",
            "dimension_code",
            "dimension_name",
            "sort_order",
            "effective_from",
            "status",
        ],
    ),
    "organization": (
        [
            "code",
            "name",
            "organization_type_code",
            "parent_code",
            "country_code",
            "effective_from",
            "effective_to",
        ],
        ["code", "name", "organization_type_code", "effective_from"],
    ),
}


class ImportService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        actor_id: UUID,
        trace_id: str,
    ) -> None:
        self._session = session
        self._actor_id = actor_id
        self._trace_id = trace_id

    @staticmethod
    def template(entity_type: ImportEntityType) -> tuple[list[str], list[str]]:
        return _TEMPLATES[entity_type]

    async def validate_batch(
        self,
        payload: ImportBatchValidate,
    ) -> tuple[ImportBatch, list[ImportBatchRow]]:
        request_checksum = self._checksum(payload.model_dump(mode="json"))
        existing = await self._session.scalar(
            select(ImportBatch).where(
                ImportBatch.idempotency_key == payload.idempotency_key
            )
        )
        if existing is not None:
            if existing.request_checksum != request_checksum:
                raise ApiError(
                    status_code=409,
                    code="IMPORT_IDEMPOTENCY_CONFLICT",
                    message="相同幂等键已用于不同导入内容",
                )
            return existing, await self._rows(existing.id)

        batch = ImportBatch(
            entity_type=payload.entity_type,
            source_system=payload.source_system,
            source_table=payload.source_table,
            file_name=payload.file_name,
            idempotency_key=payload.idempotency_key,
            request_checksum=request_checksum,
            status="validating",
            total_rows=len(payload.rows),
            valid_rows=0,
            rejected_rows=0,
            imported_rows=0,
            skipped_rows=0,
            created_by=self._actor_id,
        )
        self._session.add(batch)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise ApiError(
                status_code=409,
                code="IMPORT_IDEMPOTENCY_CONFLICT",
                message="导入幂等键已经存在",
            ) from exc

        parsed, errors = self._parse_rows(payload)
        target_keys = self._target_keys(payload.entity_type, parsed)
        self._mark_duplicate_targets(target_keys, errors)
        existing_targets = await self._existing_targets(payload.entity_type, parsed)
        if payload.entity_type == "dictionary_item":
            await self._validate_dictionary_item_relations(parsed, existing_targets, errors)
        elif payload.entity_type == "job_dimension":
            await self._validate_job_dimension_relations(parsed, existing_targets, errors)
        elif payload.entity_type == "job":
            await self._validate_job_relations(parsed, errors)
        elif payload.entity_type == "organization":
            await self._validate_organization_relations(parsed, existing_targets, errors)

        links = await self._existing_links(payload)
        rows: list[ImportBatchRow] = []
        target_type = _TARGET_TYPES[payload.entity_type]
        for index, source_row in enumerate(payload.rows, start=1):
            parsed_row = parsed.get(index)
            normalized = (
                parsed_row.model_dump(mode="json", exclude_none=True)
                if parsed_row is not None
                else {}
            )
            checksum = self._checksum(
                normalized if parsed_row is not None else source_row.data
            )
            row_errors = errors[index]
            target_key = self._target_key(payload.entity_type, parsed.get(index))
            target = existing_targets.get(target_key) if target_key else None
            link = links.get(source_row.source_record_id)
            status = "valid"
            target_id: UUID | None = None
            if not row_errors and link is not None:
                if link.source_checksum != checksum:
                    row_errors.append(
                        self._error(
                            "SOURCE_RECORD_CHANGED",
                            None,
                            "来源记录内容已变化，必须先确认更新策略",
                        )
                    )
                elif target is None or target.id != link.target_id:
                    row_errors.append(
                        self._error(
                            "EXTERNAL_LINK_TARGET_INVALID",
                            None,
                            "来源追踪记录指向的目标已不存在或代码不一致",
                        )
                    )
                else:
                    status = "skipped"
                    target_id = link.target_id
            if not row_errors and link is None and target is not None:
                row_errors.append(
                    self._error(
                        "TARGET_CODE_CONFLICT",
                        "code",
                        "目标稳定代码已存在，但没有对应来源追踪记录",
                    )
                )
            if row_errors:
                status = "rejected"
            row = ImportBatchRow(
                batch_id=batch.id,
                row_number=index,
                source_record_id=source_row.source_record_id,
                source_checksum=checksum,
                payload=normalized,
                status=status,
                errors=row_errors,
                target_type=target_type if target_id else None,
                target_id=target_id,
            )
            self._session.add(row)
            rows.append(row)

        await self._session.flush()
        self._refresh_counts(batch, rows)
        batch.status = (
            "validated_with_errors" if batch.rejected_rows else "validated"
        )
        await self._audit_batch(
            batch,
            action="governance.import_batch.validate",
            reason=None,
        )
        return batch, rows

    async def execute_batch(
        self,
        batch_id: UUID,
        *,
        reason: str,
    ) -> tuple[ImportBatch, list[ImportBatchRow]]:
        batch = await self._session.get(ImportBatch, batch_id, with_for_update=True)
        if batch is None:
            raise ApiError(
                status_code=404,
                code="IMPORT_BATCH_NOT_FOUND",
                message="导入批次不存在",
            )
        rows = await self._rows(batch.id)
        if batch.status in {"completed", "completed_with_errors"}:
            return batch, rows
        if batch.status not in {"validated", "validated_with_errors"}:
            raise ApiError(
                status_code=409,
                code="IMPORT_BATCH_NOT_EXECUTABLE",
                message="导入批次尚未完成校验或当前状态不可执行",
            )

        batch.status = "executing"
        valid_rows = [row for row in rows if row.status == "valid"]
        if batch.entity_type == "dictionary_item":
            valid_rows = await self._order_dictionary_item_rows(valid_rows)
        elif batch.entity_type == "job_dimension":
            valid_rows = await self._order_job_dimension_rows(valid_rows)
        elif batch.entity_type == "organization":
            valid_rows = await self._order_organization_rows(valid_rows)

        for row in valid_rows:
            try:
                async with self._session.begin_nested():
                    target = await self._create_target(batch, row)
                    await self._session.flush()
                    self._session.add(
                        ExternalRecordLink(
                            source_system=batch.source_system,
                            source_table=batch.source_table,
                            source_record_id=row.source_record_id,
                            target_type=_TARGET_TYPES[batch.entity_type],
                            target_id=target.id,
                            source_updated_at=None,
                            source_checksum=row.source_checksum,
                        )
                    )
                    await self._session.flush()
            except IntegrityError:
                row.status = "rejected"
                row.errors = [
                    self._error(
                        "IMPORT_TARGET_CONFLICT",
                        "code",
                        "执行时目标代码或来源追踪记录发生冲突",
                    )
                ]
                row.target_type = None
                row.target_id = None
                continue

            row.status = "imported"
            row.target_type = _TARGET_TYPES[batch.entity_type]
            row.target_id = target.id
            await self._audit_target(batch, row, target)

        await self._session.flush()
        self._refresh_counts(batch, rows)
        batch.status = (
            "completed_with_errors" if batch.rejected_rows else "completed"
        )
        batch.executed_at = datetime.now(UTC)
        await self._audit_batch(
            batch,
            action="governance.import_batch.execute",
            reason=reason,
        )
        await self._session.flush()
        await self._session.refresh(batch)
        return batch, rows

    async def get_batch(
        self,
        batch_id: UUID,
    ) -> tuple[ImportBatch, list[ImportBatchRow]]:
        batch = await self._session.get(ImportBatch, batch_id)
        if batch is None:
            raise ApiError(
                status_code=404,
                code="IMPORT_BATCH_NOT_FOUND",
                message="导入批次不存在",
            )
        return batch, await self._rows(batch.id)

    async def list_batches(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[ImportBatch], int]:
        total = await self._session.scalar(
            select(func.count()).select_from(ImportBatch)
        )
        items = list(
            (
                await self._session.scalars(
                    select(ImportBatch)
                    .order_by(ImportBatch.created_at.desc(), ImportBatch.id.desc())
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        return items, total or 0

    async def _existing_links(
        self,
        payload: ImportBatchValidate,
    ) -> dict[str, ExternalRecordLink]:
        source_ids = [row.source_record_id for row in payload.rows]
        result = await self._session.scalars(
            select(ExternalRecordLink).where(
                ExternalRecordLink.source_system == payload.source_system,
                ExternalRecordLink.source_table == payload.source_table,
                ExternalRecordLink.source_record_id.in_(source_ids),
                ExternalRecordLink.target_type == _TARGET_TYPES[payload.entity_type],
            )
        )
        return {link.source_record_id: link for link in result.all()}

    def _parse_rows(
        self,
        payload: ImportBatchValidate,
    ) -> tuple[dict[int, BaseModel], defaultdict[int, list[dict[str, Any]]]]:
        schema_type: type[BaseModel] = {
            "dictionary": DictionaryCreate,
            "dictionary_item": DictionaryItemImport,
            "organization_type": OrganizationTypeCreate,
            "legal_entity": LegalEntityCreate,
            "job_dimension": JobDimensionImport,
            "job": JobImport,
            "organization": OrganizationImport,
        }[payload.entity_type]
        parsed: dict[int, BaseModel] = {}
        errors: defaultdict[int, list[dict[str, Any]]] = defaultdict(list)
        allowed_fields = set(_TEMPLATES[payload.entity_type][0])
        for index, row in enumerate(payload.rows, start=1):
            unexpected_fields = sorted(set(row.data) - allowed_fields)
            if unexpected_fields:
                for field in unexpected_fields:
                    errors[index].append(
                        self._error(
                            "ROW_FIELD_NOT_ALLOWED",
                            field,
                            "字段不在当前主数据导入模板中",
                        )
                    )
                continue
            try:
                parsed[index] = schema_type.model_validate(row.data)
            except ValidationError as exc:
                for error in exc.errors():
                    errors[index].append(
                        self._error(
                            "ROW_SCHEMA_INVALID",
                            ".".join(str(part) for part in error["loc"]),
                            error["msg"],
                        )
                    )
        return parsed, errors

    def _target_keys(
        self,
        entity_type: str,
        parsed: dict[int, BaseModel],
    ) -> defaultdict[str, list[int]]:
        result: defaultdict[str, list[int]] = defaultdict(list)
        for index, model in parsed.items():
            key = self._target_key(entity_type, model)
            if key is not None:
                result[key].append(index)
        return result

    def _mark_duplicate_targets(
        self,
        target_keys: dict[str, list[int]],
        errors: defaultdict[int, list[dict[str, Any]]],
    ) -> None:
        for indexes in target_keys.values():
            if len(indexes) < 2:
                continue
            for index in indexes:
                errors[index].append(
                    self._error(
                        "TARGET_CODE_DUPLICATE",
                        "code",
                        "同一批次不能重复使用目标稳定代码",
                    )
                )

    async def _existing_targets(
        self,
        entity_type: str,
        parsed: dict[int, BaseModel],
    ) -> dict[str, Any]:
        if not parsed:
            return {}
        if entity_type == "dictionary_item":
            dictionary_codes = {
                model.dictionary_code
                for model in parsed.values()
                if isinstance(model, DictionaryItemImport)
            }
            dictionaries = list(
                (
                    await self._session.scalars(
                        select(DataDictionary).where(
                            DataDictionary.code.in_(dictionary_codes),
                            DataDictionary.is_active.is_(True),
                        )
                    )
                ).all()
            )
            dictionary_by_id = {item.id: item.code for item in dictionaries}
            item_codes = {
                code
                for model in parsed.values()
                if isinstance(model, DictionaryItemImport)
                for code in (model.code, model.parent_item_code)
                if code is not None
            }
            items = []
            if dictionary_by_id and item_codes:
                items = list(
                    (
                        await self._session.scalars(
                            select(DataDictionaryItem).where(
                                DataDictionaryItem.dictionary_id.in_(dictionary_by_id),
                                DataDictionaryItem.code.in_(item_codes),
                                DataDictionaryItem.is_active.is_(True),
                            )
                        )
                    ).all()
                )
            result: dict[str, Any] = {
                f"dictionary:{item.code}": item for item in dictionaries
            }
            result.update(
                {
                    f"{dictionary_by_id[item.dictionary_id]}:{item.code}": item
                    for item in items
                }
            )
            return result

        if entity_type == "organization":
            organization_codes = {
                code
                for model in parsed.values()
                if isinstance(model, OrganizationImport)
                for code in (model.code, model.parent_code)
                if code is not None
            }
            type_codes = {
                model.organization_type_code
                for model in parsed.values()
                if isinstance(model, OrganizationImport)
            }
            organizations = list(
                (
                    await self._session.scalars(
                        select(Organization).where(Organization.code.in_(organization_codes))
                    )
                ).all()
            )
            organization_types = list(
                (
                    await self._session.scalars(
                        select(OrganizationType).where(
                            OrganizationType.code.in_(type_codes),
                            OrganizationType.is_active.is_(True),
                        )
                    )
                ).all()
            )
            result = {item.code: item for item in organizations}
            result.update(
                {f"organization_type:{item.code}": item for item in organization_types}
            )
            return result

        if entity_type == "job_dimension":
            dimension_keys = {
                (dimension_type, code)
                for model in parsed.values()
                if isinstance(model, JobDimensionImport)
                for dimension_type, code in (
                    (model.dimension_type, model.dimension_code),
                    (model.parent_dimension_type, model.parent_dimension_code),
                )
                if dimension_type is not None and code is not None
            }
            dimensions = list(
                (
                    await self._session.scalars(
                        select(JobDimension).where(
                            JobDimension.dimension_type.in_({key[0] for key in dimension_keys}),
                            JobDimension.code.in_({key[1] for key in dimension_keys}),
                        )
                    )
                ).all()
            ) if dimension_keys else []
            return {
                f"{item.dimension_type}:{item.code}": item
                for item in dimensions
                if (item.dimension_type, item.code) in dimension_keys
            }

        if entity_type == "job":
            codes = {
                model.job_code
                for model in parsed.values()
                if isinstance(model, JobImport)
            }
            items = list(
                (
                    await self._session.scalars(
                        select(JobCatalog).where(JobCatalog.code.in_(codes))
                    )
                ).all()
            ) if codes else []
            return {item.code: item for item in items}

        model_type: type[Any] = {
            "dictionary": DataDictionary,
            "organization_type": OrganizationType,
            "legal_entity": LegalEntity,
        }[entity_type]
        codes = {str(getattr(model, "code")) for model in parsed.values()}
        items = list(
            (
                await self._session.scalars(
                    select(model_type).where(model_type.code.in_(codes))
                )
            ).all()
        )
        return {item.code: item for item in items}

    async def _validate_dictionary_item_relations(
        self,
        parsed: dict[int, BaseModel],
        existing: dict[str, Any],
        errors: defaultdict[int, list[dict[str, Any]]],
    ) -> None:
        incoming: dict[str, DictionaryItemImport] = {}
        index_by_key: dict[str, int] = {}
        for index, model in parsed.items():
            if not isinstance(model, DictionaryItemImport):
                continue
            dictionary_key = f"dictionary:{model.dictionary_code}"
            if dictionary_key not in existing:
                errors[index].append(
                    self._error(
                        "DICTIONARY_NOT_FOUND",
                        "dictionary_code",
                        "目标数据字典不存在，请先导入字典定义",
                    )
                )
                continue
            key = f"{model.dictionary_code}:{model.code}"
            incoming[key] = model
            index_by_key[key] = index
            if model.parent_item_code is not None:
                parent_key = f"{model.dictionary_code}:{model.parent_item_code}"
                if parent_key not in existing and parent_key not in {
                    f"{candidate.dictionary_code}:{candidate.code}"
                    for candidate in parsed.values()
                    if isinstance(candidate, DictionaryItemImport)
                }:
                    errors[index].append(
                        self._error(
                            "DICTIONARY_PARENT_NOT_FOUND",
                            "parent_item_code",
                            "父字典项不存在且不在当前批次",
                        )
                    )

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(key: str, path: list[str]) -> None:
            if key in visited:
                return
            if key in visiting:
                cycle = path[path.index(key) :]
                for cycle_key in cycle:
                    errors[index_by_key[cycle_key]].append(
                        self._error(
                            "DICTIONARY_PARENT_CYCLE",
                            "parent_item_code",
                            "字典项父子关系不能形成循环",
                        )
                    )
                return
            model = incoming.get(key)
            if model is None or model.parent_item_code is None:
                visited.add(key)
                return
            parent_key = f"{model.dictionary_code}:{model.parent_item_code}"
            if parent_key not in incoming:
                visited.add(key)
                return
            visiting.add(key)
            visit(parent_key, [*path, parent_key])
            visiting.discard(key)
            visited.add(key)

        for key in incoming:
            visit(key, [key])

        dependency_changed = True
        while dependency_changed:
            dependency_changed = False
            invalid_keys = {
                key for key, index in index_by_key.items() if errors[index]
            }
            for key, model in incoming.items():
                index = index_by_key[key]
                if errors[index] or model.parent_item_code is None:
                    continue
                parent_key = f"{model.dictionary_code}:{model.parent_item_code}"
                if parent_key in invalid_keys:
                    errors[index].append(
                        self._error(
                            "DICTIONARY_PARENT_REJECTED",
                            "parent_item_code",
                            "父字典项未通过当前批次校验",
                        )
                    )
                    dependency_changed = True

    async def _order_dictionary_item_rows(
        self,
        rows: list[ImportBatchRow],
    ) -> list[ImportBatchRow]:
        pending = {row.id: row for row in rows}
        ordered: list[ImportBatchRow] = []
        available = {
            (dictionary.code, item.code)
            for dictionary, item in (
                await self._session.execute(
                    select(DataDictionary, DataDictionaryItem).join(
                        DataDictionaryItem,
                        DataDictionaryItem.dictionary_id == DataDictionary.id,
                    )
                )
            ).all()
        }
        while pending:
            progressed = False
            for row_id, row in list(pending.items()):
                model = DictionaryItemImport.model_validate(row.payload)
                parent = (
                    (model.dictionary_code, model.parent_item_code)
                    if model.parent_item_code
                    else None
                )
                if parent is not None and parent not in available:
                    continue
                ordered.append(row)
                available.add((model.dictionary_code, model.code))
                del pending[row_id]
                progressed = True
            if not progressed:
                raise ApiError(
                    status_code=409,
                    code="IMPORT_DICTIONARY_DEPENDENCY_INVALID",
                    message="字典项依赖顺序无法解析，请重新校验批次",
                )
        return ordered

    async def _job_dimension_version_at(
        self,
        dimension_id: UUID,
        effective_at: date,
    ) -> JobDimensionVersion | None:
        return await self._session.scalar(
            select(JobDimensionVersion)
            .where(
                JobDimensionVersion.dimension_id == dimension_id,
                JobDimensionVersion.status == "active",
                JobDimensionVersion.effective_from <= effective_at,
                (
                    JobDimensionVersion.effective_to.is_(None)
                    | (JobDimensionVersion.effective_to >= effective_at)
                ),
            )
            .order_by(
                JobDimensionVersion.effective_from.desc(),
                JobDimensionVersion.version.desc(),
            )
            .limit(1)
        )

    async def _validate_job_dimension_relations(
        self,
        parsed: dict[int, BaseModel],
        existing: dict[str, Any],
        errors: defaultdict[int, list[dict[str, Any]]],
    ) -> None:
        incoming: dict[str, JobDimensionImport] = {}
        index_by_key: dict[str, int] = {}
        for index, model in parsed.items():
            if not isinstance(model, JobDimensionImport):
                continue
            key = f"{model.dimension_type}:{model.dimension_code}"
            incoming[key] = model
            index_by_key[key] = index
            if model.parent_dimension_type is None or model.parent_dimension_code is None:
                continue
            parent_key = f"{model.parent_dimension_type}:{model.parent_dimension_code}"
            parent_incoming = incoming.get(parent_key) or next(
                (
                    candidate
                    for candidate in parsed.values()
                    if isinstance(candidate, JobDimensionImport)
                    and candidate.dimension_type == model.parent_dimension_type
                    and candidate.dimension_code == model.parent_dimension_code
                ),
                None,
            )
            parent_existing = existing.get(parent_key)
            if parent_incoming is None and parent_existing is None:
                errors[index].append(
                    self._error(
                        "JOB_DIMENSION_PARENT_NOT_FOUND",
                        "parent_dimension_code",
                        "父职务维度不存在且不在当前批次",
                    )
                )
            elif parent_incoming is not None and not (
                parent_incoming.status == "active"
                and parent_incoming.effective_from <= model.effective_from
                and (
                    parent_incoming.effective_to is None
                    or parent_incoming.effective_to >= model.effective_from
                )
            ):
                errors[index].append(
                    self._error(
                        "JOB_DIMENSION_PARENT_NOT_EFFECTIVE",
                        "parent_dimension_code",
                        "当前批次父职务维度在子维度生效日未启用",
                    )
                )
            elif (
                parent_existing is not None
                and await self._job_dimension_version_at(
                    parent_existing.id,
                    model.effective_from,
                )
                is None
            ):
                errors[index].append(
                    self._error(
                        "JOB_DIMENSION_PARENT_NOT_EFFECTIVE",
                        "parent_dimension_code",
                        "父职务维度在子维度生效日未启用",
                    )
                )

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(key: str, path: list[str]) -> None:
            if key in visited:
                return
            if key in visiting:
                for cycle_key in path[path.index(key) :]:
                    errors[index_by_key[cycle_key]].append(
                        self._error(
                            "JOB_DIMENSION_PARENT_CYCLE",
                            "parent_dimension_code",
                            "职务维度父级不能形成循环",
                        )
                    )
                return
            model = incoming.get(key)
            if (
                model is None
                or model.parent_dimension_type is None
                or model.parent_dimension_code is None
            ):
                visited.add(key)
                return
            parent_key = f"{model.parent_dimension_type}:{model.parent_dimension_code}"
            if parent_key not in incoming:
                visited.add(key)
                return
            visiting.add(key)
            visit(parent_key, [*path, parent_key])
            visiting.discard(key)
            visited.add(key)

        for key in incoming:
            visit(key, [key])

        dependency_changed = True
        while dependency_changed:
            dependency_changed = False
            invalid_keys = {key for key, index in index_by_key.items() if errors[index]}
            for key, model in incoming.items():
                index = index_by_key[key]
                if (
                    errors[index]
                    or model.parent_dimension_type is None
                    or model.parent_dimension_code is None
                ):
                    continue
                parent_key = f"{model.parent_dimension_type}:{model.parent_dimension_code}"
                if parent_key in invalid_keys:
                    errors[index].append(
                        self._error(
                            "JOB_DIMENSION_PARENT_REJECTED",
                            "parent_dimension_code",
                            "父职务维度未通过当前批次校验",
                        )
                    )
                    dependency_changed = True

    async def _validate_job_relations(
        self,
        parsed: dict[int, BaseModel],
        errors: defaultdict[int, list[dict[str, Any]]],
    ) -> None:
        dimension_pairs = {
            (dimension_type, code)
            for model in parsed.values()
            if isinstance(model, JobImport)
            for dimension_type, code in (
                ("LEVEL", model.level_code),
                ("GRADE", model.grade_code),
                ("CLASS", model.class_code),
                ("SEQUENCE", model.sequence_code),
            )
        }
        dimensions = list(
            (
                await self._session.scalars(
                    select(JobDimension).where(
                        JobDimension.dimension_type.in_({pair[0] for pair in dimension_pairs}),
                        JobDimension.code.in_({pair[1] for pair in dimension_pairs}),
                    )
                )
            ).all()
        ) if dimension_pairs else []
        dimension_by_key = {
            (item.dimension_type, item.code): item
            for item in dimensions
            if (item.dimension_type, item.code) in dimension_pairs
        }
        effective_cache: dict[tuple[UUID, date], bool] = {}
        for index, model in parsed.items():
            if not isinstance(model, JobImport):
                continue
            for field, dimension_type, code in (
                ("level_code", "LEVEL", model.level_code),
                ("grade_code", "GRADE", model.grade_code),
                ("class_code", "CLASS", model.class_code),
                ("sequence_code", "SEQUENCE", model.sequence_code),
            ):
                dimension = dimension_by_key.get((dimension_type, code))
                if dimension is None:
                    errors[index].append(
                        self._error(
                            "JOB_DIMENSION_NOT_FOUND",
                            field,
                            f"{dimension_type}维度代码不存在，请先导入职务维度",
                        )
                    )
                    continue
                cache_key = (dimension.id, model.effective_from)
                if cache_key not in effective_cache:
                    effective_cache[cache_key] = (
                        await self._job_dimension_version_at(
                            dimension.id,
                            model.effective_from,
                        )
                    ) is not None
                if not effective_cache[cache_key]:
                    errors[index].append(
                        self._error(
                            "JOB_DIMENSION_NOT_EFFECTIVE",
                            field,
                            f"{dimension_type}维度在职务生效日未启用",
                        )
                    )

    async def _order_job_dimension_rows(
        self,
        rows: list[ImportBatchRow],
    ) -> list[ImportBatchRow]:
        pending = {row.id: row for row in rows}
        available = {
            (dimension_type, code)
            for dimension_type, code in (
                await self._session.execute(
                    select(JobDimension.dimension_type, JobDimension.code)
                )
            ).all()
        }
        ordered: list[ImportBatchRow] = []
        while pending:
            progressed = False
            for row_id, row in list(pending.items()):
                model = JobDimensionImport.model_validate(row.payload)
                parent = (
                    (model.parent_dimension_type, model.parent_dimension_code)
                    if model.parent_dimension_type and model.parent_dimension_code
                    else None
                )
                if parent is not None and parent not in available:
                    continue
                ordered.append(row)
                available.add((model.dimension_type, model.dimension_code))
                del pending[row_id]
                progressed = True
            if not progressed:
                raise ApiError(
                    status_code=409,
                    code="IMPORT_JOB_DIMENSION_DEPENDENCY_INVALID",
                    message="职务维度父级依赖顺序无法解析，请重新校验批次",
                )
        return ordered

    async def _validate_organization_relations(
        self,
        parsed: dict[int, BaseModel],
        existing: dict[str, Any],
        errors: defaultdict[int, list[dict[str, Any]]],
    ) -> None:
        incoming: dict[str, OrganizationImport] = {}
        index_by_code: dict[str, int] = {}
        for index, model in parsed.items():
            if not isinstance(model, OrganizationImport):
                continue
            incoming[model.code] = model
            index_by_code[model.code] = index
            if f"organization_type:{model.organization_type_code}" not in existing:
                errors[index].append(
                    self._error(
                        "ORGANIZATION_TYPE_NOT_FOUND",
                        "organization_type_code",
                        "组织类型不存在或未启用，请先导入组织类型",
                    )
                )
            if model.parent_code is None:
                continue
            parent = incoming.get(model.parent_code)
            if parent is None:
                parent = next(
                    (
                        candidate
                        for candidate in parsed.values()
                        if isinstance(candidate, OrganizationImport)
                        and candidate.code == model.parent_code
                    ),
                    None,
                )
            if parent is not None:
                if (
                    parent.effective_from > model.effective_from
                    or (
                        parent.effective_to is not None
                        and parent.effective_to < model.effective_from
                    )
                ):
                    errors[index].append(
                        self._error(
                            "ORGANIZATION_PARENT_NOT_EFFECTIVE",
                            "parent_code",
                            "上级组织在当前组织生效日期无有效版本",
                        )
                    )
            elif model.parent_code not in existing:
                errors[index].append(
                    self._error(
                        "ORGANIZATION_PARENT_NOT_FOUND",
                        "parent_code",
                        "上级组织不存在且不在当前批次",
                    )
                )
            elif not await self._organization_effective_at(
                existing[model.parent_code].id,
                model.effective_from,
            ):
                errors[index].append(
                    self._error(
                        "ORGANIZATION_PARENT_NOT_EFFECTIVE",
                        "parent_code",
                        "上级组织在当前组织生效日期无有效版本",
                    )
                )

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(code: str, path: list[str]) -> None:
            if code in visited:
                return
            if code in visiting:
                cycle = path[path.index(code) :]
                for cycle_code in cycle:
                    errors[index_by_code[cycle_code]].append(
                        self._error(
                            "ORGANIZATION_PARENT_CYCLE",
                            "parent_code",
                            "组织父子关系不能形成循环",
                        )
                    )
                return
            model = incoming.get(code)
            if model is None or model.parent_code not in incoming:
                visited.add(code)
                return
            visiting.add(code)
            visit(model.parent_code, [*path, model.parent_code])
            visiting.discard(code)
            visited.add(code)

        for code in incoming:
            visit(code, [code])

        dependency_changed = True
        while dependency_changed:
            dependency_changed = False
            invalid_codes = {
                code for code, index in index_by_code.items() if errors[index]
            }
            for code, model in incoming.items():
                index = index_by_code[code]
                if errors[index] or model.parent_code is None:
                    continue
                if model.parent_code in invalid_codes:
                    errors[index].append(
                        self._error(
                            "ORGANIZATION_PARENT_REJECTED",
                            "parent_code",
                            "上级组织未通过当前批次校验",
                        )
                    )
                    dependency_changed = True

    async def _organization_effective_at(
        self,
        organization_id: UUID,
        effective_at: date,
    ) -> bool:
        return (
            await self._session.scalar(
                select(OrganizationVersion.id).where(
                    OrganizationVersion.organization_id == organization_id,
                    OrganizationVersion.effective_from <= effective_at,
                    (
                        OrganizationVersion.effective_to.is_(None)
                        | (OrganizationVersion.effective_to >= effective_at)
                    ),
                    OrganizationVersion.status == "active",
                )
            )
        ) is not None

    async def _order_organization_rows(
        self,
        rows: list[ImportBatchRow],
    ) -> list[ImportBatchRow]:
        pending = {row.id: row for row in rows}
        available = set((await self._session.scalars(select(Organization.code))).all())
        ordered: list[ImportBatchRow] = []
        while pending:
            progressed = False
            for row_id, row in list(pending.items()):
                model = OrganizationImport.model_validate(row.payload)
                if model.parent_code is not None and model.parent_code not in available:
                    continue
                ordered.append(row)
                available.add(model.code)
                del pending[row_id]
                progressed = True
            if not progressed:
                raise ApiError(
                    status_code=409,
                    code="IMPORT_ORGANIZATION_DEPENDENCY_INVALID",
                    message="组织父级依赖顺序无法解析，请重新校验批次",
                )
        return ordered

    async def _create_target(self, batch: ImportBatch, row: ImportBatchRow) -> Any:
        if batch.entity_type == "dictionary":
            payload = DictionaryCreate.model_validate(row.payload)
            target = DataDictionary(
                **payload.model_dump(),
                source=batch.source_system,
                is_active=True,
            )
        elif batch.entity_type == "dictionary_item":
            payload = DictionaryItemImport.model_validate(row.payload)
            dictionary = await self._session.scalar(
                select(DataDictionary).where(
                    DataDictionary.code == payload.dictionary_code,
                    DataDictionary.is_active.is_(True),
                )
            )
            if dictionary is None:
                raise ApiError(
                    status_code=409,
                    code="DICTIONARY_NOT_FOUND",
                    message="执行时目标数据字典不存在或已停用",
                )
            parent: DataDictionaryItem | None = None
            if payload.parent_item_code is not None:
                parent = await self._session.scalar(
                    select(DataDictionaryItem).where(
                        DataDictionaryItem.dictionary_id == dictionary.id,
                        DataDictionaryItem.code == payload.parent_item_code,
                        DataDictionaryItem.is_active.is_(True),
                    )
                )
                if parent is None:
                    raise ApiError(
                        status_code=409,
                        code="DICTIONARY_PARENT_NOT_FOUND",
                        message="执行时父字典项不存在或已停用",
                    )
            target = DataDictionaryItem(
                dictionary_id=dictionary.id,
                parent_item_id=parent.id if parent else None,
                code=payload.code,
                name=payload.name,
                english_name=payload.english_name,
                sort_order=payload.sort_order,
                level=(parent.level + 1) if parent else 0,
                description=payload.description,
                is_active=True,
            )
        elif batch.entity_type == "organization_type":
            payload = OrganizationTypeCreate.model_validate(row.payload)
            target = OrganizationType(
                **payload.model_dump(),
                is_active=True,
            )
        elif batch.entity_type == "legal_entity":
            payload = LegalEntityCreate.model_validate(row.payload)
            target = LegalEntity(
                **payload.model_dump(),
                status="active",
            )
        elif batch.entity_type == "job_dimension":
            payload = JobDimensionImport.model_validate(row.payload)
            parent: JobDimension | None = None
            if payload.parent_dimension_type and payload.parent_dimension_code:
                parent = await self._session.scalar(
                    select(JobDimension).where(
                        JobDimension.dimension_type == payload.parent_dimension_type,
                        JobDimension.code == payload.parent_dimension_code,
                    )
                )
                if (
                    parent is None
                    or await self._job_dimension_version_at(
                        parent.id,
                        payload.effective_from,
                    )
                    is None
                ):
                    raise ApiError(
                        status_code=409,
                        code="JOB_DIMENSION_PARENT_NOT_EFFECTIVE",
                        message="执行时父职务维度不存在或未启用",
                    )
            target = JobDimension(
                dimension_type=payload.dimension_type,
                code=payload.dimension_code,
            )
            self._session.add(target)
            await self._session.flush()
            self._session.add(
                JobDimensionVersion(
                    dimension_id=target.id,
                    version=1,
                    name=payload.dimension_name,
                    parent_dimension_id=parent.id if parent else None,
                    sort_order=payload.sort_order,
                    status=payload.status,
                    effective_from=payload.effective_from,
                    effective_to=payload.effective_to,
                    is_current=True,
                    notes=payload.notes,
                    change_reason="主数据初始化导入",
                )
            )
        elif batch.entity_type == "job":
            payload = JobImport.model_validate(row.payload)
            dimensions: dict[str, JobDimension] = {}
            for key, dimension_type, code in (
                ("level", "LEVEL", payload.level_code),
                ("grade", "GRADE", payload.grade_code),
                ("class", "CLASS", payload.class_code),
                ("sequence", "SEQUENCE", payload.sequence_code),
            ):
                dimension = await self._session.scalar(
                    select(JobDimension).where(
                        JobDimension.dimension_type == dimension_type,
                        JobDimension.code == code,
                    )
                )
                if (
                    dimension is None
                    or await self._job_dimension_version_at(
                        dimension.id,
                        payload.effective_from,
                    )
                    is None
                ):
                    raise ApiError(
                        status_code=409,
                        code="JOB_DIMENSION_NOT_EFFECTIVE",
                        message=f"执行时{dimension_type}维度不存在或未启用",
                    )
                dimensions[key] = dimension
            target = JobCatalog(
                code=payload.job_code,
                name=payload.job_name,
                level_code=payload.level_code,
                grade_code=payload.grade_code,
                class_code=payload.class_code,
                sequence_code=payload.sequence_code,
                status=payload.status,
                effective_from=payload.effective_from,
                effective_to=payload.effective_to,
                attributes={},
            )
            self._session.add(target)
            await self._session.flush()
            self._session.add(
                JobCatalogVersion(
                    job_id=target.id,
                    version=1,
                    name=payload.job_name,
                    level_dimension_id=dimensions["level"].id,
                    grade_dimension_id=dimensions["grade"].id,
                    class_dimension_id=dimensions["class"].id,
                    sequence_dimension_id=dimensions["sequence"].id,
                    status=payload.status,
                    effective_from=payload.effective_from,
                    effective_to=payload.effective_to,
                    is_current=True,
                    source_job_id=payload.source_job_id,
                    notes=payload.notes,
                    attributes={},
                    change_reason="主数据初始化导入",
                )
            )
        elif batch.entity_type == "organization":
            payload = OrganizationImport.model_validate(row.payload)
            organization_type = await self._session.scalar(
                select(OrganizationType).where(
                    OrganizationType.code == payload.organization_type_code,
                    OrganizationType.is_active.is_(True),
                )
            )
            if organization_type is None:
                raise ApiError(
                    status_code=409,
                    code="ORGANIZATION_TYPE_NOT_FOUND",
                    message="执行时组织类型不存在或未启用",
                )
            parent: Organization | None = None
            if payload.parent_code is not None:
                parent = await self._session.scalar(
                    select(Organization).where(Organization.code == payload.parent_code)
                )
                if parent is None or not await self._organization_effective_at(
                    parent.id,
                    payload.effective_from,
                ):
                    raise ApiError(
                        status_code=409,
                        code="ORGANIZATION_PARENT_NOT_EFFECTIVE",
                        message="执行时上级组织不存在或在生效日期无有效版本",
                    )
            target = Organization(code=payload.code)
            self._session.add(target)
            await self._session.flush()
            business_date = datetime.now(
                ZoneInfo(get_settings().business_timezone)
            ).date()
            version = OrganizationVersion(
                organization_id=target.id,
                version=1,
                name=payload.name,
                organization_type_id=organization_type.id,
                parent_organization_id=parent.id if parent else None,
                country_code=payload.country_code,
                status="active",
                effective_from=payload.effective_from,
                effective_to=payload.effective_to,
                is_current=(
                    payload.effective_from <= business_date
                    and (
                        payload.effective_to is None
                        or payload.effective_to >= business_date
                    )
                ),
                change_reason="主数据初始化导入",
            )
            self._session.add(version)
            event_idempotency = uuid5(
                NAMESPACE_URL,
                f"corehr:organization-import:{batch.id}:{row.id}",
            )
            self._session.add_all(
                [
                    OrganizationEvent(
                        organization_id=target.id,
                        event_type="CREATE",
                        effective_date=payload.effective_from,
                        status="applied",
                        payload={"organization_id": str(target.id), "version": 1},
                        expected_version=1,
                        idempotency_key=event_idempotency,
                        change_reason="主数据初始化导入",
                        applied_at=datetime.now(UTC),
                    ),
                    OutboxEvent(
                        event_type="organization.created",
                        aggregate_type="organization",
                        aggregate_id=target.id,
                        payload={"organization_id": str(target.id), "version": 1},
                        occurred_at=datetime.now(UTC),
                        attempt_count=0,
                    ),
                ]
            )
        else:
            raise ApiError(
                status_code=422,
                code="IMPORT_ENTITY_UNSUPPORTED",
                message="当前导入实体类型没有执行器",
            )
        self._session.add(target)
        return target

    async def _rows(self, batch_id: UUID) -> list[ImportBatchRow]:
        return list(
            (
                await self._session.scalars(
                    select(ImportBatchRow)
                    .where(ImportBatchRow.batch_id == batch_id)
                    .order_by(ImportBatchRow.row_number)
                )
            ).all()
        )

    @staticmethod
    def _target_key(entity_type: str, model: BaseModel | None) -> str | None:
        if model is None:
            return None
        if entity_type == "dictionary_item" and isinstance(
            model, DictionaryItemImport
        ):
            return f"{model.dictionary_code}:{model.code}"
        if entity_type == "job_dimension" and isinstance(model, JobDimensionImport):
            return f"{model.dimension_type}:{model.dimension_code}"
        if entity_type == "job" and isinstance(model, JobImport):
            return model.job_code
        return str(getattr(model, "code"))

    @staticmethod
    def _refresh_counts(batch: ImportBatch, rows: list[ImportBatchRow]) -> None:
        batch.total_rows = len(rows)
        batch.valid_rows = sum(
            row.status in {"valid", "imported", "skipped"} for row in rows
        )
        batch.rejected_rows = sum(row.status == "rejected" for row in rows)
        batch.imported_rows = sum(row.status == "imported" for row in rows)
        batch.skipped_rows = sum(row.status == "skipped" for row in rows)

    async def _audit_batch(
        self,
        batch: ImportBatch,
        *,
        action: str,
        reason: str | None,
    ) -> None:
        self._session.add(
            AuditLog(
                occurred_at=datetime.now(UTC),
                actor_id=self._actor_id,
                trace_id=self._trace_id,
                action=action,
                object_type="import_batch",
                object_id=batch.id,
                reason=reason,
                before_payload={},
                after_payload={
                    "entity_type": batch.entity_type,
                    "source_system": batch.source_system,
                    "source_table": batch.source_table,
                    "status": batch.status,
                    "total_rows": batch.total_rows,
                    "valid_rows": batch.valid_rows,
                    "rejected_rows": batch.rejected_rows,
                    "imported_rows": batch.imported_rows,
                    "skipped_rows": batch.skipped_rows,
                },
                source="import",
            )
        )

    async def _audit_target(
        self,
        batch: ImportBatch,
        row: ImportBatchRow,
        target: Any,
    ) -> None:
        self._session.add(
            AuditLog(
                occurred_at=datetime.now(UTC),
                actor_id=self._actor_id,
                trace_id=self._trace_id,
                action="governance.import_row.create",
                object_type=_TARGET_TYPES[batch.entity_type],
                object_id=target.id,
                reason="主数据初始化导入",
                before_payload={},
                after_payload={
                    "batch_id": str(batch.id),
                    "source_record_id": row.source_record_id,
                    "code": str(getattr(target, "code", "")),
                },
                source="import",
            )
        )

    @staticmethod
    def _checksum(value: Any) -> str:
        canonical = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    @staticmethod
    def _error(code: str, field: str | None, message: str) -> dict[str, Any]:
        return {"code": code, "field": field, "message": message}
