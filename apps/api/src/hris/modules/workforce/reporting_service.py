# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement

from hris.core.config import get_settings
from hris.core.errors import ApiError
from hris.modules.workforce.models import AuditLog, Person, ReportingRelation


DIRECT_RELATION_TYPE = "direct"
DOTTED_RELATION_TYPE = "dotted"
SUPPORTED_RELATION_TYPES = (DIRECT_RELATION_TYPE, DOTTED_RELATION_TYPE)


@dataclass(frozen=True, slots=True)
class ReportingRelationRecord:
    """汇报关系在接口层对外暴露的只读视图。"""

    id: UUID
    manager_person_id: UUID
    manager_name: str | None
    subordinate_person_id: UUID
    subordinate_name: str | None
    relation_type: str
    effective_from: date
    effective_to: date | None


class ReportingRelationService:
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

    async def create_relation(
        self,
        *,
        manager_person_id: UUID,
        subordinate_person_id: UUID,
        relation_type: str,
        effective_from: date,
        effective_to: date | None,
    ) -> ReportingRelationRecord:
        # Requirement: ORG-REPORT-001 — 汇报关系类型只允许实线 direct 与虚线 dotted。
        if relation_type not in SUPPORTED_RELATION_TYPES:
            raise ApiError(
                status_code=422,
                code="REPORTING_RELATION_TYPE_INVALID",
                message="汇报关系类型只支持 direct（直属）或 dotted（虚线）",
            )
        # Requirement: ORG-REPORT-002 — 上级与下级不能是同一个员工。
        if manager_person_id == subordinate_person_id:
            raise ApiError(
                status_code=422,
                code="REPORTING_SELF_REFERENCE_INVALID",
                message="上级与下级不能为同一人",
                details=[
                    {"field": "manager_person_id", "message": "上级与下级不能为同一人"}
                ],
            )
        # Requirement: ORG-REPORT-003 — 上级与下级必须是已存在的员工。
        await self._ensure_person_exists(manager_person_id, "manager_person_id")
        await self._ensure_person_exists(subordinate_person_id, "subordinate_person_id")
        # Requirement: ORG-REPORT-004 — 结束日期不得早于开始日期。
        if effective_to is not None and effective_to < effective_from:
            raise ApiError(
                status_code=422,
                code="REPORTING_PERIOD_INVALID",
                message="结束日期不能早于开始日期",
                details=[
                    {"field": "effective_to", "message": "结束日期不能早于开始日期"}
                ],
            )
        # Requirement: ORG-REPORT-005 — 同类型汇报关系不得成环。
        # 实线与虚线各自成环是数据错误；虚线指向实线上级（虚线实线并存）是合法场景，
        # 因此环检测只在同类型边之间进行。
        await self._ensure_no_cycle(
            manager_person_id=manager_person_id,
            subordinate_person_id=subordinate_person_id,
            relation_type=relation_type,
            effective_from=effective_from,
        )
        # Requirement: ORG-REPORT-006 — 同一上级、下级、类型与生效日的组合不得重复。
        await self._ensure_not_duplicated(
            manager_person_id=manager_person_id,
            subordinate_person_id=subordinate_person_id,
            relation_type=relation_type,
            effective_from=effective_from,
        )
        relation = ReportingRelation(
            manager_person_id=manager_person_id,
            subordinate_person_id=subordinate_person_id,
            relation_type=relation_type,
            effective_from=effective_from,
            effective_to=effective_to,
        )
        self._session.add(relation)
        await self._session.flush()
        self._audit(
            action="create",
            relation=relation,
            reason="创建汇报关系",
        )
        return await self._get_record(relation.id)

    async def list_relations(
        self,
        *,
        effective_at: date | None,
        manager_person_id: UUID | None,
        subordinate_person_id: UUID | None,
        page: int,
        page_size: int,
    ) -> tuple[list[ReportingRelationRecord], int]:
        filters: list[ColumnElement[bool]] = []
        if effective_at is not None:
            # Requirement: ORG-REPORT-007 — effective_at 只返回该日期落在
            # [effective_from, effective_to) 区间内的记录，effective_to 为空表示当前有效。
            filters.append(ReportingRelation.effective_from <= effective_at)
            filters.append(
                or_(
                    ReportingRelation.effective_to.is_(None),
                    ReportingRelation.effective_to > effective_at,
                )
            )
        if manager_person_id is not None:
            filters.append(ReportingRelation.manager_person_id == manager_person_id)
        if subordinate_person_id is not None:
            filters.append(ReportingRelation.subordinate_person_id == subordinate_person_id)

        total = await self._session.scalar(
            select(func.count()).select_from(ReportingRelation).where(*filters)
        )
        manager = aliased(Person)
        subordinate = aliased(Person)
        rows = (
            await self._session.execute(
                select(
                    ReportingRelation,
                    manager.display_name,
                    subordinate.display_name,
                )
                .outerjoin(manager, manager.id == ReportingRelation.manager_person_id)
                .outerjoin(
                    subordinate,
                    subordinate.id == ReportingRelation.subordinate_person_id,
                )
                .where(*filters)
                .order_by(
                    ReportingRelation.effective_from.desc(),
                    ReportingRelation.created_at.desc(),
                    ReportingRelation.id.asc(),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        records = [
            ReportingRelationRecord(
                id=relation.id,
                manager_person_id=relation.manager_person_id,
                manager_name=manager_name,
                subordinate_person_id=relation.subordinate_person_id,
                subordinate_name=subordinate_name,
                relation_type=relation.relation_type,
                effective_from=relation.effective_from,
                effective_to=relation.effective_to,
            )
            for relation, manager_name, subordinate_name in rows
        ]
        return records, int(total or 0)

    async def end_relation(self, relation_id: UUID) -> ReportingRelationRecord:
        relation = await self._session.get(
            ReportingRelation,
            relation_id,
            with_for_update=True,
        )
        if relation is None:
            raise ApiError(
                status_code=404,
                code="REPORTING_RELATION_NOT_FOUND",
                message="汇报关系不存在",
            )
        # Requirement: ORG-REPORT-008 — 已结束的汇报关系不能再次结束。
        if relation.effective_to is not None:
            raise ApiError(
                status_code=409,
                code="REPORTING_RELATION_ALREADY_ENDED",
                message="汇报关系已结束",
            )
        # Requirement: ORG-REPORT-009 — 软结束保留历史记录，仅把结束日期设为当天；
        # 尚未生效的关系以生效开始日作为结束日期，保证结束日期不早于开始日期。
        relation.effective_to = max(self.business_date(), relation.effective_from)
        await self._session.flush()
        self._audit(
            action="end",
            relation=relation,
            reason="结束汇报关系",
        )
        return await self._get_record(relation.id)

    async def _ensure_person_exists(self, person_id: UUID, field: str) -> None:
        exists = await self._session.scalar(
            select(Person.id).where(Person.id == person_id)
        )
        if exists is None:
            raise ApiError(
                status_code=422,
                code="REPORTING_PERSON_NOT_FOUND",
                message="上级或下级员工不存在",
                details=[{"field": field, "message": "员工不存在"}],
            )

    async def _ensure_no_cycle(
        self,
        *,
        manager_person_id: UUID,
        subordinate_person_id: UUID,
        relation_type: str,
        effective_from: date,
    ) -> None:
        visited: set[UUID] = {manager_person_id}
        frontier: list[UUID] = [manager_person_id]
        while frontier:
            current = frontier.pop()
            manager_ids = await self._session.scalars(
                select(ReportingRelation.manager_person_id)
                .where(
                    ReportingRelation.subordinate_person_id == current,
                    ReportingRelation.relation_type == relation_type,
                    ReportingRelation.effective_from <= effective_from,
                    or_(
                        ReportingRelation.effective_to.is_(None),
                        ReportingRelation.effective_to > effective_from,
                    ),
                )
                .distinct()
            )
            for manager_id in manager_ids:
                if manager_id == subordinate_person_id:
                    raise ApiError(
                        status_code=422,
                        code="REPORTING_CYCLE_DETECTED",
                        message="汇报关系不能形成循环",
                    )
                if manager_id in visited:
                    continue
                visited.add(manager_id)
                frontier.append(manager_id)

    async def _ensure_not_duplicated(
        self,
        *,
        manager_person_id: UUID,
        subordinate_person_id: UUID,
        relation_type: str,
        effective_from: date,
    ) -> None:
        existing = await self._session.scalar(
            select(ReportingRelation.id).where(
                ReportingRelation.manager_person_id == manager_person_id,
                ReportingRelation.subordinate_person_id == subordinate_person_id,
                ReportingRelation.relation_type == relation_type,
                ReportingRelation.effective_from == effective_from,
            )
        )
        if existing is not None:
            raise ApiError(
                status_code=409,
                code="REPORTING_RELATION_DUPLICATE",
                message="相同的汇报关系在同一天已存在",
            )

    async def _get_record(self, relation_id: UUID) -> ReportingRelationRecord:
        manager = aliased(Person)
        subordinate = aliased(Person)
        row = (
            await self._session.execute(
                select(
                    ReportingRelation,
                    manager.display_name,
                    subordinate.display_name,
                )
                .outerjoin(manager, manager.id == ReportingRelation.manager_person_id)
                .outerjoin(
                    subordinate,
                    subordinate.id == ReportingRelation.subordinate_person_id,
                )
                .where(ReportingRelation.id == relation_id)
            )
        ).one_or_none()
        if row is None:
            raise ApiError(
                status_code=404,
                code="REPORTING_RELATION_NOT_FOUND",
                message="汇报关系不存在",
            )
        relation, manager_name, subordinate_name = row
        return ReportingRelationRecord(
            id=relation.id,
            manager_person_id=relation.manager_person_id,
            manager_name=manager_name,
            subordinate_person_id=relation.subordinate_person_id,
            subordinate_name=subordinate_name,
            relation_type=relation.relation_type,
            effective_from=relation.effective_from,
            effective_to=relation.effective_to,
        )

    def _audit(
        self,
        *,
        action: str,
        relation: ReportingRelation,
        reason: str,
    ) -> None:
        self._session.add(
            AuditLog(
                occurred_at=datetime.now(UTC),
                actor_id=self._actor_id,
                trace_id=self._trace_id,
                action=action,
                object_type="reporting_relation",
                object_id=relation.id,
                reason=reason,
                before_payload={},
                after_payload={
                    "manager_person_id": str(relation.manager_person_id),
                    "subordinate_person_id": str(relation.subordinate_person_id),
                    "relation_type": relation.relation_type,
                    "effective_from": relation.effective_from.isoformat(),
                    "effective_to": (
                        relation.effective_to.isoformat()
                        if relation.effective_to is not None
                        else None
                    ),
                },
                source="api",
            )
        )
