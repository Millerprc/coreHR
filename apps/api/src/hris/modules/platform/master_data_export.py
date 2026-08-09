import csv
from datetime import UTC, date, datetime
from io import StringIO
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from hris.core.config import get_settings
from hris.core.errors import ApiError
from hris.modules.platform.import_schemas import ImportEntityType
from hris.modules.platform.import_service import ImportService
from hris.modules.platform.models import DataDictionary, DataDictionaryItem
from hris.modules.workforce.models import (
    AuditLog,
    JobCatalog,
    LegalEntity,
    Organization,
    OrganizationType,
    OrganizationVersion,
)


_MAX_EXPORT_ROWS = 50_000
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")


class MasterDataExportService:
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
        self._timezone = ZoneInfo(get_settings().business_timezone)

    async def export(self, entity_type: ImportEntityType) -> tuple[bytes, str, int]:
        as_of = datetime.now(self._timezone).date()
        rows = await self._rows(entity_type, as_of)
        if len(rows) > _MAX_EXPORT_ROWS:
            raise ApiError(
                status_code=409,
                code="MASTER_DATA_EXPORT_TOO_LARGE",
                message="当前主数据超过单次导出上限，请联系系统管理员分批处理",
                details=[{"max_rows": _MAX_EXPORT_ROWS}],
            )

        columns, _required = ImportService.template(entity_type)
        fieldnames = ["source_record_id", *columns]
        buffer = StringIO(newline="")
        writer = csv.DictWriter(
            buffer,
            fieldnames=fieldnames,
            extrasaction="ignore",
            lineterminator="\r\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {column: self._safe_cell(row.get(column)) for column in fieldnames}
            )

        self._session.add(
            AuditLog(
                occurred_at=datetime.now(UTC),
                actor_id=self._actor_id,
                trace_id=self._trace_id,
                action="governance.master_data.export",
                object_type="master_data_export",
                object_id=None,
                reason="导出当前有效非敏感主数据",
                before_payload={},
                after_payload={
                    "entity_type": entity_type,
                    "as_of": as_of.isoformat(),
                    "row_count": len(rows),
                },
                source="export",
            )
        )
        await self._session.flush()
        content = ("\ufeff" + buffer.getvalue()).encode("utf-8")
        return content, f"{entity_type}-current.csv", len(rows)

    async def _rows(
        self,
        entity_type: ImportEntityType,
        as_of: date,
    ) -> list[dict[str, Any]]:
        if entity_type == "dictionary":
            return await self._dictionary_rows()
        if entity_type == "dictionary_item":
            return await self._dictionary_item_rows()
        if entity_type == "organization_type":
            return await self._organization_type_rows()
        if entity_type == "legal_entity":
            return await self._legal_entity_rows(as_of)
        if entity_type == "job":
            return await self._job_rows(as_of)
        return await self._organization_rows(as_of)

    async def _dictionary_rows(self) -> list[dict[str, Any]]:
        items = (
            await self._session.scalars(
                select(DataDictionary)
                .where(DataDictionary.is_active.is_(True))
                .order_by(DataDictionary.code)
                .limit(_MAX_EXPORT_ROWS + 1)
            )
        ).all()
        return [
            {
                "source_record_id": f"dictionary:{item.code}",
                "code": item.code,
                "name": item.name,
                "english_name": item.english_name,
                "description": item.description,
            }
            for item in items
        ]

    async def _dictionary_item_rows(self) -> list[dict[str, Any]]:
        parent = aliased(DataDictionaryItem)
        result = (
            await self._session.execute(
                select(DataDictionaryItem, DataDictionary, parent.code)
                .join(
                    DataDictionary,
                    DataDictionary.id == DataDictionaryItem.dictionary_id,
                )
                .outerjoin(parent, parent.id == DataDictionaryItem.parent_item_id)
                .where(
                    DataDictionary.is_active.is_(True),
                    DataDictionaryItem.is_active.is_(True),
                )
                .order_by(
                    DataDictionary.code,
                    DataDictionaryItem.sort_order,
                    DataDictionaryItem.code,
                )
                .limit(_MAX_EXPORT_ROWS + 1)
            )
        ).all()
        return [
            {
                "source_record_id": (
                    f"dictionary_item:{dictionary.code}:{item.code}"
                ),
                "dictionary_code": dictionary.code,
                "code": item.code,
                "name": item.name,
                "english_name": item.english_name,
                "parent_item_code": parent_code,
                "sort_order": item.sort_order,
                "description": item.description,
            }
            for item, dictionary, parent_code in result
        ]

    async def _organization_type_rows(self) -> list[dict[str, Any]]:
        items = (
            await self._session.scalars(
                select(OrganizationType)
                .where(OrganizationType.is_active.is_(True))
                .order_by(OrganizationType.sort_order, OrganizationType.code)
                .limit(_MAX_EXPORT_ROWS + 1)
            )
        ).all()
        return [
            {
                "source_record_id": f"organization_type:{item.code}",
                "code": item.code,
                "name": item.name,
                "sort_order": item.sort_order,
            }
            for item in items
        ]

    async def _legal_entity_rows(self, as_of: date) -> list[dict[str, Any]]:
        items = (
            await self._session.scalars(
                select(LegalEntity)
                .where(
                    LegalEntity.status == "active",
                    LegalEntity.effective_from <= as_of,
                    or_(
                        LegalEntity.effective_to.is_(None),
                        LegalEntity.effective_to >= as_of,
                    ),
                )
                .order_by(LegalEntity.code)
                .limit(_MAX_EXPORT_ROWS + 1)
            )
        ).all()
        return [
            {
                "source_record_id": f"legal_entity:{item.code}",
                "code": item.code,
                "name": item.name,
                "registered_name": item.registered_name,
                "country_code": item.country_code,
                "registration_number": item.registration_number,
                "effective_from": item.effective_from,
                "effective_to": item.effective_to,
            }
            for item in items
        ]

    async def _job_rows(self, as_of: date) -> list[dict[str, Any]]:
        items = (
            await self._session.scalars(
                select(JobCatalog)
                .where(
                    JobCatalog.status == "active",
                    JobCatalog.effective_from <= as_of,
                    or_(
                        JobCatalog.effective_to.is_(None),
                        JobCatalog.effective_to >= as_of,
                    ),
                )
                .order_by(JobCatalog.code)
                .limit(_MAX_EXPORT_ROWS + 1)
            )
        ).all()
        return [
            {
                "source_record_id": f"job:{item.code}",
                "code": item.code,
                "name": item.name,
                "level_code": item.level_code,
                "grade_code": item.grade_code,
                "class_code": item.class_code,
                "sequence_code": item.sequence_code,
                "effective_from": item.effective_from,
                "effective_to": item.effective_to,
            }
            for item in items
        ]

    async def _organization_rows(self, as_of: date) -> list[dict[str, Any]]:
        ranked_versions = (
            select(
                OrganizationVersion.id.label("version_id"),
                func.row_number()
                .over(
                    partition_by=OrganizationVersion.organization_id,
                    order_by=(
                        OrganizationVersion.effective_from.desc(),
                        OrganizationVersion.version.desc(),
                    ),
                )
                .label("row_number"),
            )
            .where(
                OrganizationVersion.status == "active",
                OrganizationVersion.effective_from <= as_of,
                or_(
                    OrganizationVersion.effective_to.is_(None),
                    OrganizationVersion.effective_to >= as_of,
                ),
            )
            .subquery()
        )
        parent = aliased(Organization)
        result = (
            await self._session.execute(
                select(
                    Organization,
                    OrganizationVersion,
                    OrganizationType,
                    parent.code,
                )
                .join(
                    ranked_versions,
                    ranked_versions.c.version_id == OrganizationVersion.id,
                )
                .join(
                    Organization,
                    Organization.id == OrganizationVersion.organization_id,
                )
                .join(
                    OrganizationType,
                    OrganizationType.id == OrganizationVersion.organization_type_id,
                )
                .outerjoin(
                    parent,
                    parent.id == OrganizationVersion.parent_organization_id,
                )
                .where(ranked_versions.c.row_number == 1)
                .order_by(Organization.code)
                .limit(_MAX_EXPORT_ROWS + 1)
            )
        ).all()
        return [
            {
                "source_record_id": f"organization:{organization.code}",
                "code": organization.code,
                "name": version.name,
                "organization_type_code": organization_type.code,
                "parent_code": parent_code,
                "country_code": version.country_code,
                "effective_from": version.effective_from,
                "effective_to": version.effective_to,
            }
            for organization, version, organization_type, parent_code in result
        ]

    @staticmethod
    def _safe_cell(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, date):
            return value.isoformat()
        text = str(value).replace("\x00", "")
        candidate = text.lstrip(" ")
        if candidate.startswith(_FORMULA_PREFIXES):
            return "'" + text
        return text
