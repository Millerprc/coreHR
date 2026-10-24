# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""人员级兼岗（concurrent position）服务。

Requirement: D-104 — 兼岗以「人员级组织关系」为唯一权威载体：
写入 organization_person_relations（relation_type='concurrent'），
不再新增 employment 级 EmploymentAssignment 行；既有 employment 级行保留为历史记录。

Requirement: D-026 — 同一时间只能有一个主组织，其他关系（兼岗）可以同时存在多个。

载体与字段说明（重要，避免误读）：
- organization_person_relations 没有 job_id 列，本轮又明确不新建表、不加迁移，
  因此职务引用（job_id / job_name）、变更原因、来源事件 id 统一编码进 note 字段（JSON）。
  note 结构见 NOTE_PAYLOAD_VERSION，读取时对非 JSON 历史值容错降级。
- 有效期区间口径为左闭右开 [effective_from, effective_to)：
  effective_to 为空表示当前有效；effective_to 等于某日表示该日已不再有效。
  该口径与同域的汇报关系（reporting_service）一致。
"""

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from hris.core.config import get_settings
from hris.core.errors import ApiError
from hris.modules.workforce.extended_service import ExtendedWorkforceService
from hris.modules.workforce.models import (
    AuditLog,
    Employment,
    EmploymentAssignment,
    JobCatalog,
    JobCatalogVersion,
    Organization,
    OrganizationPersonRelation,
    OrganizationVersion,
    Person,
)


# Requirement: D-104 — 兼岗在人员级关系表里的关系类型取值。
CONCURRENT_RELATION_TYPE = "concurrent"
# Requirement: D-026 — 主组织关系类型取值；同一时间只能有一条。
PRIMARY_RELATION_TYPE = "primary"
SUPPORTED_RELATION_TYPES = (CONCURRENT_RELATION_TYPE, PRIMARY_RELATION_TYPE)

# note 字段是 String(500)，编码后的 JSON 必须留在长度内。
NOTE_MAX_LENGTH = 500
# 变更原因在 note 中的长度上限（保证 note 不超长）。
CHANGE_REASON_MAX_LENGTH = 100


@dataclass(frozen=True, slots=True)
class ConcurrentPositionRecord:
    """兼岗在接口层对外暴露的只读视图。"""

    id: UUID
    person_id: UUID
    person_name: str | None
    organization_id: UUID
    organization_name: str | None
    job_id: UUID | None
    job_name: str | None
    relation_type: str
    effective_from: date
    effective_to: date | None
    change_reason: str | None


class ConcurrentPositionService:
    """人员级兼岗的读写服务。

    Requirement: D-104 — 唯一权威载体是 organization_person_relations；
    Requirement: D-026 — 唯一性校验在服务层完成，并返回明确中文错误。
    """

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

    def business_date(self) -> date:
        return datetime.now(self._timezone).date()

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------
    async def create_concurrent_position(
        self,
        *,
        person_id: UUID,
        organization_id: UUID,
        job_id: UUID | None,
        effective_from: date,
        effective_to: date | None,
        change_reason: str,
        source_event_id: UUID | None = None,
    ) -> ConcurrentPositionRecord:
        """新建兼岗（人员级组织关系）。

        Requirement: D-104 — 写入 organization_person_relations，relation_type='concurrent'。
        """
        return await self.create_person_organization_relation(
            person_id=person_id,
            organization_id=organization_id,
            relation_type=CONCURRENT_RELATION_TYPE,
            job_id=job_id,
            effective_from=effective_from,
            effective_to=effective_to,
            change_reason=change_reason,
            source_event_id=source_event_id,
        )

    async def create_person_organization_relation(
        self,
        *,
        person_id: UUID,
        organization_id: UUID,
        relation_type: str,
        job_id: UUID | None,
        effective_from: date,
        effective_to: date | None,
        change_reason: str,
        source_event_id: UUID | None = None,
    ) -> ConcurrentPositionRecord:
        """写入一条人员级组织关系，并做唯一性校验。

        Requirement: D-026 — 主组织关系同一时间只允许一条；兼岗可多条，
        但同一人员 + 同一组织的兼岗生效区间不得重叠。
        Requirement: D-104 — 兼岗是唯一权威载体，本方法是 HR 事件执行器的调用点。
        """
        if relation_type not in SUPPORTED_RELATION_TYPES:
            raise ApiError(
                status_code=422,
                code="ORGANIZATION_RELATION_TYPE_INVALID",
                message="人员级组织关系类型只支持 concurrent（兼岗）或 primary（主组织）",
            )
        if effective_to is not None and effective_to < effective_from:
            raise ApiError(
                status_code=422,
                code="CONCURRENT_POSITION_PERIOD_INVALID",
                message="失效日期不能早于生效日期",
                details=[{"field": "effective_to", "message": "失效日期不能早于生效日期"}],
            )
        reason = (change_reason or "").strip()
        if not reason:
            raise ApiError(
                status_code=422,
                code="CONCURRENT_POSITION_REASON_REQUIRED",
                message="变更原因不能为空",
                details=[{"field": "change_reason", "message": "变更原因不能为空"}],
            )
        if len(reason) > CHANGE_REASON_MAX_LENGTH:
            raise ApiError(
                status_code=422,
                code="CONCURRENT_POSITION_REASON_TOO_LONG",
                message=f"变更原因不能超过 {CHANGE_REASON_MAX_LENGTH} 个字符",
                details=[
                    {
                        "field": "change_reason",
                        "message": f"变更原因不能超过 {CHANGE_REASON_MAX_LENGTH} 个字符",
                    }
                ],
            )

        await self._ensure_person_exists(person_id)
        await self._ensure_organization_exists(organization_id)

        job_name: str | None = None
        if job_id is not None:
            # Requirement: D-104 — 职务必须在兼岗生效日已启用，避免写入无效任职。
            await ExtendedWorkforceService(
                self._session,
                actor_id=self._actor_id,
                trace_id=self._trace_id,
            ).ensure_job_effective(job_id, effective_from)
            job_name = await self._resolve_job_name(job_id, effective_from)

        # Requirement: D-104 — HR 事件重试不得重复写兼岗：同一来源事件只写一条。
        if source_event_id is not None:
            existing = await self._find_by_source_event(person_id, source_event_id)
            if existing is not None:
                return await self._get_record(existing.id)

        if relation_type == PRIMARY_RELATION_TYPE:
            await self._ensure_single_primary_organization(person_id, effective_from, effective_to)
        else:
            await self._ensure_no_overlapping_concurrent(
                person_id=person_id,
                organization_id=organization_id,
                effective_from=effective_from,
                effective_to=effective_to,
            )

        note = self._encode_note(
            job_id=job_id,
            job_name=job_name,
            change_reason=reason,
            source_event_id=source_event_id,
        )
        relation = OrganizationPersonRelation(
            organization_id=organization_id,
            person_id=person_id,
            relation_type=relation_type,
            bp_type=None,
            effective_from=effective_from,
            effective_to=effective_to,
            note=note,
        )
        self._session.add(relation)
        await self._session.flush()
        self._audit(
            action="create",
            relation=relation,
            reason=reason,
            before={},
            after={
                "organization_id": str(relation.organization_id),
                "person_id": str(relation.person_id),
                "relation_type": relation.relation_type,
                "job_id": str(job_id) if job_id else None,
                "effective_from": relation.effective_from.isoformat(),
                "effective_to": (
                    relation.effective_to.isoformat() if relation.effective_to is not None else None
                ),
            },
        )
        return await self._get_record(relation.id)

    async def end_concurrent_position(
        self,
        relation_id: UUID,
        *,
        effective_to: date | None = None,
        reason: str | None = None,
    ) -> ConcurrentPositionRecord:
        """结束兼岗：只关闭生效区间，保留历史记录。

        Requirement: D-104 — 结束的是人员级兼岗关系，不是 employment 级任职。

        ``effective_to`` 为空时按业务日结束（HTTP 端点路径）；
        HR 事件 ``END_ASSIGNMENT`` 会传入事件生效日，使「审批通过的结束日」
        与「当天点按钮结束」两种来源得到一致的口径。
        """
        relation = await self._session.get(
            OrganizationPersonRelation,
            relation_id,
            with_for_update=True,
        )
        if relation is None or relation.relation_type != CONCURRENT_RELATION_TYPE:
            raise ApiError(
                status_code=404,
                code="CONCURRENT_POSITION_NOT_FOUND",
                message="兼岗不存在",
            )
        if relation.effective_to is not None:
            raise ApiError(
                status_code=409,
                code="CONCURRENT_POSITION_ALREADY_ENDED",
                message="兼岗已结束",
            )
        before = {
            "effective_to": relation.effective_to.isoformat() if relation.effective_to else None,
        }
        # 尚未生效的兼岗以生效开始日作为失效日，等价于「从未生效」的空区间。
        target = effective_to or self.business_date()
        relation.effective_to = max(target, relation.effective_from)
        await self._session.flush()
        self._audit(
            action="end",
            relation=relation,
            reason=reason or "结束兼岗",
            before=before,
            after={
                "effective_to": relation.effective_to.isoformat(),
            },
        )
        return await self._get_record(relation.id)

    # ------------------------------------------------------------------
    # 读取
    # ------------------------------------------------------------------
    async def list_concurrent_positions(
        self,
        *,
        effective_at: date | None,
        person_id: UUID | None,
        organization_id: UUID | None,
        page: int,
        page_size: int,
    ) -> tuple[list[ConcurrentPositionRecord], int]:
        filters: list[ColumnElement[bool]] = [
            OrganizationPersonRelation.relation_type == CONCURRENT_RELATION_TYPE,
        ]
        if effective_at is not None:
            # Requirement: D-104 — 有效期区间左闭右开 [effective_from, effective_to)。
            filters.append(OrganizationPersonRelation.effective_from <= effective_at)
            filters.append(
                or_(
                    OrganizationPersonRelation.effective_to.is_(None),
                    OrganizationPersonRelation.effective_to > effective_at,
                )
            )
        if person_id is not None:
            filters.append(OrganizationPersonRelation.person_id == person_id)
        if organization_id is not None:
            filters.append(OrganizationPersonRelation.organization_id == organization_id)

        total = await self._session.scalar(
            select(func.count())
            .select_from(OrganizationPersonRelation)
            .where(*filters)
        )
        rows = (
            await self._session.execute(
                select(OrganizationPersonRelation, Person.display_name)
                .outerjoin(Person, Person.id == OrganizationPersonRelation.person_id)
                .where(*filters)
                .order_by(
                    OrganizationPersonRelation.effective_from.desc(),
                    OrganizationPersonRelation.created_at.desc(),
                    OrganizationPersonRelation.id.asc(),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        records = await self._to_records(rows)
        return records, int(total or 0)

    async def list_person_concurrent_positions(
        self,
        *,
        person_id: UUID,
        effective_at: date | None = None,
    ) -> list[ConcurrentPositionRecord]:
        """读取某个人的全部兼岗（含生效区间），用于员工档案只读展示。"""
        exists = await self._session.scalar(select(Person.id).where(Person.id == person_id))
        if exists is None:
            raise ApiError(
                status_code=404,
                code="CONCURRENT_POSITION_PERSON_NOT_FOUND",
                message="人员不存在",
            )
        filters: list[ColumnElement[bool]] = [
            OrganizationPersonRelation.relation_type == CONCURRENT_RELATION_TYPE,
            OrganizationPersonRelation.person_id == person_id,
        ]
        if effective_at is not None:
            filters.append(OrganizationPersonRelation.effective_from <= effective_at)
            filters.append(
                or_(
                    OrganizationPersonRelation.effective_to.is_(None),
                    OrganizationPersonRelation.effective_to > effective_at,
                )
            )
        rows = (
            await self._session.execute(
                select(OrganizationPersonRelation, Person.display_name)
                .outerjoin(Person, Person.id == OrganizationPersonRelation.person_id)
                .where(*filters)
                .order_by(
                    OrganizationPersonRelation.effective_from.desc(),
                    OrganizationPersonRelation.id.asc(),
                )
            )
        ).all()
        return await self._to_records(rows)

    # ------------------------------------------------------------------
    # 内部校验
    # ------------------------------------------------------------------
    async def _ensure_person_exists(self, person_id: UUID) -> None:
        exists = await self._session.scalar(select(Person.id).where(Person.id == person_id))
        if exists is None:
            raise ApiError(
                status_code=422,
                code="CONCURRENT_POSITION_PERSON_NOT_FOUND",
                message="人员不存在",
                details=[{"field": "person_id", "message": "人员不存在"}],
            )

    async def _ensure_organization_exists(self, organization_id: UUID) -> None:
        exists = await self._session.scalar(
            select(Organization.id).where(Organization.id == organization_id)
        )
        if exists is None:
            raise ApiError(
                status_code=422,
                code="CONCURRENT_POSITION_ORGANIZATION_NOT_FOUND",
                message="组织不存在",
                details=[{"field": "organization_id", "message": "组织不存在"}],
            )

    async def _ensure_no_overlapping_concurrent(
        self,
        *,
        person_id: UUID,
        organization_id: UUID,
        effective_from: date,
        effective_to: date | None,
    ) -> None:
        """同一人员 + 同一组织的兼岗，生效区间不得重叠。

        Requirement: D-104 / D-026 — 兼岗可同时存在多个，但同组织重复兼岗要挡住。
        """
        filters: list[ColumnElement[bool]] = [
            OrganizationPersonRelation.relation_type == CONCURRENT_RELATION_TYPE,
            OrganizationPersonRelation.person_id == person_id,
            OrganizationPersonRelation.organization_id == organization_id,
        ]
        # 左闭右开区间重叠判定：existing_from < new_to 且 new_from < existing_to。
        if effective_to is not None:
            filters.append(OrganizationPersonRelation.effective_from < effective_to)
        filters.append(
            or_(
                OrganizationPersonRelation.effective_to.is_(None),
                OrganizationPersonRelation.effective_to > effective_from,
            )
        )
        overlap = await self._session.scalar(
            select(OrganizationPersonRelation.id).where(*filters).limit(1)
        )
        if overlap is not None:
            raise ApiError(
                status_code=409,
                code="CONCURRENT_POSITION_DUPLICATE",
                message="该人员在同一组织已存在生效区间重叠的兼岗",
            )

    async def _ensure_single_primary_organization(
        self,
        person_id: UUID,
        effective_from: date,
        effective_to: date | None,
    ) -> None:
        """同一时间只能有一个主组织。

        Requirement: D-026 — 主组织唯一；兼岗等其他关系可以同时存在多个。
        校验同时覆盖人员级关系表与既有 employment 级任职：
        D-104 之后 employment 级只保留为历史记录，但在历史载体上仍存在主组织语义，
        因此跨载体的重复主组织同样要挡住。
        """
        filters: list[ColumnElement[bool]] = [
            OrganizationPersonRelation.relation_type == PRIMARY_RELATION_TYPE,
            OrganizationPersonRelation.person_id == person_id,
        ]
        if effective_to is not None:
            filters.append(OrganizationPersonRelation.effective_from < effective_to)
        filters.append(
            or_(
                OrganizationPersonRelation.effective_to.is_(None),
                OrganizationPersonRelation.effective_to > effective_from,
            )
        )
        person_level = await self._session.scalar(
            select(OrganizationPersonRelation.id).where(*filters).limit(1)
        )
        if person_level is not None:
            raise ApiError(
                status_code=409,
                code="PRIMARY_ORGANIZATION_CONFLICT",
                message="同一时间只能有一个主组织",
            )

        employment_filters: list[ColumnElement[bool]] = [
            EmploymentAssignment.relation_type == PRIMARY_RELATION_TYPE,
            Employment.person_id == person_id,
        ]
        if effective_to is not None:
            employment_filters.append(EmploymentAssignment.effective_from < effective_to)
        employment_filters.append(
            or_(
                EmploymentAssignment.effective_to.is_(None),
                EmploymentAssignment.effective_to > effective_from,
            )
        )
        employment_level = await self._session.scalar(
            select(EmploymentAssignment.id)
            .join(Employment, Employment.id == EmploymentAssignment.employment_id)
            .where(*employment_filters)
            .limit(1)
        )
        if employment_level is not None:
            raise ApiError(
                status_code=409,
                code="PRIMARY_ORGANIZATION_CONFLICT",
                message="同一时间只能有一个主组织",
            )

    async def _find_by_source_event(
        self,
        person_id: UUID,
        source_event_id: UUID,
    ) -> OrganizationPersonRelation | None:
        """按来源事件查找已写入的关系，用于 HR 事件重试时的幂等。

        Requirement: D-104 — 事件执行器重试不得重复建兼岗。
        """
        rows = (
            await self._session.execute(
                select(OrganizationPersonRelation).where(
                    OrganizationPersonRelation.person_id == person_id,
                    OrganizationPersonRelation.relation_type == CONCURRENT_RELATION_TYPE,
                )
            )
        ).scalars().all()
        for relation in rows:
            note = self._decode_note(relation.note)
            if note.get("source_event_id") == str(source_event_id):
                return relation
        return None

    async def _resolve_job_name(self, job_id: UUID, effective_at: date) -> str | None:
        """取职务在生效日的名称（优先版本表，回落基础表）。"""
        version = await self._session.scalar(
            select(JobCatalogVersion)
            .where(
                JobCatalogVersion.job_id == job_id,
                JobCatalogVersion.effective_from <= effective_at,
                or_(
                    JobCatalogVersion.effective_to.is_(None),
                    JobCatalogVersion.effective_to >= effective_at,
                ),
            )
            .order_by(JobCatalogVersion.version.desc())
            .limit(1)
        )
        if version is not None:
            return version.name
        legacy = await self._session.get(JobCatalog, job_id)
        return legacy.name if legacy is not None else None

    # ------------------------------------------------------------------
    # 记录组装
    # ------------------------------------------------------------------
    async def _to_records(
        self,
        rows: list[tuple[OrganizationPersonRelation, str | None]],
    ) -> list[ConcurrentPositionRecord]:
        organization_ids = {relation.organization_id for relation, _ in rows}
        organization_names = await self._organization_names(organization_ids)
        records: list[ConcurrentPositionRecord] = []
        for relation, person_name in rows:
            note = self._decode_note(relation.note)
            job_id = note.get("job_id")
            records.append(
                ConcurrentPositionRecord(
                    id=relation.id,
                    person_id=relation.person_id,
                    person_name=person_name,
                    organization_id=relation.organization_id,
                    organization_name=organization_names.get(relation.organization_id),
                    job_id=UUID(str(job_id)) if job_id else None,
                    job_name=note.get("job_name"),
                    relation_type=relation.relation_type,
                    effective_from=relation.effective_from,
                    effective_to=relation.effective_to,
                    change_reason=note.get("reason"),
                )
            )
        return records

    async def _get_record(self, relation_id: UUID) -> ConcurrentPositionRecord:
        row = (
            await self._session.execute(
                select(OrganizationPersonRelation, Person.display_name)
                .outerjoin(Person, Person.id == OrganizationPersonRelation.person_id)
                .where(OrganizationPersonRelation.id == relation_id)
            )
        ).one_or_none()
        if row is None:
            raise ApiError(
                status_code=404,
                code="CONCURRENT_POSITION_NOT_FOUND",
                message="兼岗不存在",
            )
        records = await self._to_records([row])
        return records[0]

    async def _organization_names(self, organization_ids: set[UUID]) -> dict[UUID, str]:
        """按业务日取组织名称；取不到时回落到组织编码。"""
        if not organization_ids:
            return {}
        rows = (
            await self._session.execute(
                select(OrganizationVersion.organization_id, OrganizationVersion.name)
                .where(
                    OrganizationVersion.organization_id.in_(organization_ids),
                    OrganizationVersion.effective_from <= self.business_date(),
                    or_(
                        OrganizationVersion.effective_to.is_(None),
                        OrganizationVersion.effective_to >= self.business_date(),
                    ),
                )
                .order_by(OrganizationVersion.version.desc())
            )
        ).all()
        names: dict[UUID, str] = {}
        for organization_id, name in rows:
            names.setdefault(organization_id, name)
        missing = {item for item in organization_ids if item not in names}
        if missing:
            code_rows = (
                await self._session.execute(
                    select(Organization.id, Organization.code).where(Organization.id.in_(missing))
                )
            ).all()
            for organization_id, code in code_rows:
                names[organization_id] = code
        return names

    # ------------------------------------------------------------------
    # note 编码
    # ------------------------------------------------------------------
    @staticmethod
    def _encode_note(
        *,
        job_id: UUID | None,
        job_name: str | None,
        change_reason: str,
        source_event_id: UUID | None,
    ) -> str:
        """把职务引用、变更原因、来源事件编码进 note。

        取舍说明：organization_person_relations 没有 job_id 列，本轮明确不新建表，
        因此用 note（String(500)）承载结构化 JSON；读取时对历史非 JSON 值容错。
        """
        payload = {
            "v": 1,
            "job_id": str(job_id) if job_id is not None else None,
            "job_name": job_name,
            "reason": change_reason,
            "source_event_id": str(source_event_id) if source_event_id is not None else None,
        }
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        if len(encoded) > NOTE_MAX_LENGTH:
            raise ApiError(
                status_code=422,
                code="CONCURRENT_POSITION_PAYLOAD_TOO_LONG",
                message="兼岗信息超出可存储长度，请缩短变更原因",
            )
        return encoded

    @staticmethod
    def _decode_note(note: str | None) -> dict[str, Any]:
        if not note:
            return {}
        try:
            value = json.loads(note)
        except (TypeError, ValueError):
            return {}
        return value if isinstance(value, dict) else {}

    # ------------------------------------------------------------------
    # 审计
    # ------------------------------------------------------------------
    def _audit(
        self,
        *,
        action: str,
        relation: OrganizationPersonRelation,
        reason: str,
        before: dict[str, Any],
        after: dict[str, Any],
    ) -> None:
        # Requirement: 07-人员档案领域规范 §9/§10 — 审计记录变更前后值，且不落个人数据明文，
        # 因此审计载荷只写标识与日期，不写姓名等个人敏感信息。
        self._session.add(
            AuditLog(
                occurred_at=datetime.now(UTC),
                actor_id=self._actor_id,
                trace_id=self._trace_id,
                action=action,
                object_type="organization_person_relation",
                object_id=relation.id,
                reason=reason,
                before_payload=before,
                after_payload=after,
                source="api",
            )
        )
