# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""人员基础信息「修正」的领域服务。

Requirement: D-095 — 「编辑」覆盖主档、「修正」不覆盖主档：
修正登记到 person_field_versions（按「人 + 字段」切片的生效日期版本），
当前结果 = 主档登记值 + 生效日期 ≤ 查询日期的最后一条修正。

审计与事件只记录字段名、版本与生效日期，不记录修正后的取值明文。
"""

from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.config import get_settings
from hris.core.errors import ApiError
from hris.modules.platform.models import UserAccount
from hris.modules.platform.numbering import next_number
from hris.modules.workforce.models import (
    AuditLog,
    Employment,
    HrEvent,
    Person,
    PersonFieldVersion,
)
from hris.modules.workforce.person_corrections_schemas import (
    PERSON_CORRECTABLE_FIELD_CODES,
    PERSON_FIELD_LABELS,
    PERSON_FIELD_VALUE_LIMITS,
    PersonFieldVersionCreate,
    PersonFieldVersionResponse,
)


# Requirement: D-095 — 修正事件的类型与对象类型。
# 事件只承载「哪个字段、从哪天起、第几版」这类元数据，
# 修正后的取值明文只留在 person_field_versions，不复制到事件与审计里。
PERSON_CORRECTION_EVENT_TYPE = "PERSON_CORRECTION"
PERSON_CORRECTION_OBJECT_TYPE = "person"


class PersonCorrectionService:
    def __init__(self, session: AsyncSession, *, actor_id: UUID, trace_id: str) -> None:
        self._session = session
        self._actor_id = actor_id
        self._trace_id = trace_id

    def _audit(
        self,
        *,
        action: str,
        object_type: str,
        object_id: UUID,
        reason: str,
        after: dict[str, Any],
    ) -> None:
        self._session.add(
            AuditLog(
                occurred_at=datetime.now(UTC),
                actor_id=self._actor_id,
                trace_id=self._trace_id,
                action=action,
                object_type=object_type,
                object_id=object_id,
                reason=reason,
                before_payload={},
                after_payload=after,
                source="api",
            )
        )

    async def list_field_versions(
        self,
        person_id: UUID,
        *,
        effective_at: date | None = None,
    ) -> list[tuple[PersonFieldVersion, str | None]]:
        """列出某人的修正记录（按生效日期倒序）。

        effective_at 传入时只返回「已生效」的记录（生效日期 ≤ 该日期）。
        """
        person = await self._session.get(Person, person_id)
        if person is None:
            raise ApiError(status_code=404, code="PERSON_NOT_FOUND", message="人员不存在")
        query = (
            select(PersonFieldVersion, UserAccount.display_name)
            .outerjoin(UserAccount, UserAccount.id == PersonFieldVersion.created_by)
            .where(PersonFieldVersion.person_id == person_id)
        )
        if effective_at is not None:
            query = query.where(PersonFieldVersion.effective_from <= effective_at)
        query = query.order_by(
            PersonFieldVersion.effective_from.desc(),
            PersonFieldVersion.version.desc(),
        )
        rows = (await self._session.execute(query)).all()
        return [(row[0], row[1]) for row in rows]

    @staticmethod
    def effective_overrides(
        versions: list[tuple[PersonFieldVersion, str | None]],
        effective_at: date,
    ) -> dict[str, str | None]:
        """算出查询日期上的生效取值。

        语义：主档是登记值，修正按生效日期切片；同一字段取生效日期 ≤ 查询日期
        的最后一条修正。只覆盖该条修正里声明的字段，其余字段保持主档值。
        """
        overrides: dict[str, str | None] = {}
        ordered = sorted(
            (record for record, _ in versions),
            key=lambda item: (item.effective_from, item.version),
        )
        for record in ordered:
            if record.effective_from > effective_at:
                continue
            overrides[record.field_code] = record.new_value
        return overrides

    @staticmethod
    def to_response(
        record: PersonFieldVersion,
        actor_name: str | None,
    ) -> PersonFieldVersionResponse:
        return PersonFieldVersionResponse(
            id=record.id,
            person_id=record.person_id,
            field_code=record.field_code,
            effective_from=record.effective_from,
            effective_to=record.effective_to,
            version=record.version,
            new_value=record.new_value,
            change_reason=record.change_reason,
            created_by=record.created_by,
            created_by_name=actor_name,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    @staticmethod
    def _normalize_value(field_code: str, value: str | None) -> str | None:
        """校验并归一化修正后的取值。

        取舍说明：主档上不允许为空的字段（法定姓名、显示姓名）不能被修正清空，
        否则档案读取时的当前生效结果会与主档的 NOT NULL 约束冲突。
        """
        label = PERSON_FIELD_LABELS.get(field_code, field_code)
        if field_code not in PERSON_CORRECTABLE_FIELD_CODES:
            raise ApiError(
                status_code=422,
                code="PERSON_FIELD_NOT_CORRECTABLE",
                message="该字段不支持修正",
            )
        if field_code == "birth_date":
            if value is None or not value.strip():
                return None
            normalized = value.strip()
            try:
                date.fromisoformat(normalized)
            except ValueError:
                raise ApiError(
                    status_code=422,
                    code="PERSON_FIELD_VALUE_INVALID",
                    message=f"{label}必须使用 YYYY-MM-DD 格式",
                ) from None
            return normalized
        minimum, maximum = PERSON_FIELD_VALUE_LIMITS[field_code]
        if value is None or not value.strip():
            if minimum > 0:
                raise ApiError(
                    status_code=422,
                    code="PERSON_FIELD_VALUE_INVALID",
                    message=f"{label}不能置空",
                )
            return None
        normalized = value.strip()
        if len(normalized) < minimum:
            raise ApiError(
                status_code=422,
                code="PERSON_FIELD_VALUE_INVALID",
                message=f"{label}取值长度不能少于 {minimum} 个字符",
            )
        if len(normalized) > maximum:
            raise ApiError(
                status_code=422,
                code="PERSON_FIELD_VALUE_INVALID",
                message=f"{label}取值长度不能超过 {maximum} 个字符",
            )
        return normalized

    async def _effective_anchor(self, person: Person) -> date:
        """修正生效日期的最早边界。

        Requirement: 修正支持往过去补录与向未来预约，但不允许修正到
        早于该员工的「最早雇佣生效日」。档案里没有雇佣记录时退回主档登记日
        （persons.created_at 的业务时区日期）——这是缺少雇佣锚点时的退化口径。
        """
        rows = (
            await self._session.execute(
                select(Employment.actual_start_date, Employment.planned_start_date).where(
                    Employment.person_id == person.id
                )
            )
        ).all()
        anchors = [
            actual or planned
            for actual, planned in rows
            if (actual or planned) is not None
        ]
        if anchors:
            return min(anchors)
        return person.created_at.astimezone(
            ZoneInfo(get_settings().business_timezone)
        ).date()

    async def create_field_version(
        self,
        person_id: UUID,
        payload: PersonFieldVersionCreate,
    ) -> PersonFieldVersion:
        person = await self._session.get(Person, person_id, with_for_update=True)
        if person is None:
            raise ApiError(status_code=404, code="PERSON_NOT_FOUND", message="人员不存在")
        if payload.field_code not in PERSON_CORRECTABLE_FIELD_CODES:
            raise ApiError(
                status_code=422,
                code="PERSON_FIELD_NOT_CORRECTABLE",
                message="该字段不支持修正",
            )
        new_value = self._normalize_value(payload.field_code, payload.new_value)
        anchor = await self._effective_anchor(person)
        if payload.effective_from < anchor:
            raise ApiError(
                status_code=422,
                code="PERSON_CORRECTION_EFFECTIVE_DATE_TOO_EARLY",
                message=f"生效日期不能早于 {anchor.isoformat()}",
            )
        same_day = await self._session.scalar(
            select(PersonFieldVersion).where(
                PersonFieldVersion.person_id == person_id,
                PersonFieldVersion.field_code == payload.field_code,
                PersonFieldVersion.effective_from == payload.effective_from,
            )
        )
        if same_day is not None:
            raise ApiError(
                status_code=409,
                code="PERSON_CORRECTION_EFFECTIVE_DATE_CONFLICT",
                message="同一字段在同一生效日期已存在修正记录",
            )
        current_max = await self._session.scalar(
            select(func.max(PersonFieldVersion.version)).where(
                PersonFieldVersion.person_id == person_id,
                PersonFieldVersion.field_code == payload.field_code,
            )
        )
        version = (current_max or 0) + 1
        predecessor = await self._session.scalar(
            select(PersonFieldVersion)
            .where(
                PersonFieldVersion.person_id == person_id,
                PersonFieldVersion.field_code == payload.field_code,
                PersonFieldVersion.effective_from < payload.effective_from,
            )
            .order_by(PersonFieldVersion.effective_from.desc())
            .limit(1)
        )
        successor = await self._session.scalar(
            select(PersonFieldVersion)
            .where(
                PersonFieldVersion.person_id == person_id,
                PersonFieldVersion.field_code == payload.field_code,
                PersonFieldVersion.effective_from > payload.effective_from,
            )
            .order_by(PersonFieldVersion.effective_from.asc())
            .limit(1)
        )
        record = PersonFieldVersion(
            person_id=person_id,
            field_code=payload.field_code,
            effective_from=payload.effective_from,
            effective_to=(
                successor.effective_from - timedelta(days=1) if successor is not None else None
            ),
            version=version,
            new_value=new_value,
            change_reason=payload.change_reason,
            created_by=self._actor_id,
        )
        self._session.add(record)
        if predecessor is not None:
            # 生效日期切片：上一版从新版本生效日的前一天起失效。
            predecessor.effective_to = payload.effective_from - timedelta(days=1)
        await self._session.flush()
        await self._session.refresh(record)
        await self._record_event(record)
        self._audit(
            action="person.corrected",
            object_type=PERSON_CORRECTION_OBJECT_TYPE,
            object_id=person_id,
            reason=payload.change_reason or "登记人员基础信息修正",
            after={
                "field_code": record.field_code,
                "effective_from": record.effective_from.isoformat(),
                "version": record.version,
                "field_version_id": str(record.id),
                "event_type": PERSON_CORRECTION_EVENT_TYPE,
            },
        )
        return record

    async def _record_event(self, record: PersonFieldVersion) -> None:
        """登记一条人事事件（已完成态），不进入异动执行器。"""
        number = await next_number(
            self._session,
            sequence_code="HR_EVENT_NUMBER",
            width=10,
            max_value=9999999999,
            prefix="E",
        )
        self._session.add(
            HrEvent(
                event_number=number,
                idempotency_key=None,
                request_checksum=None,
                event_type=PERSON_CORRECTION_EVENT_TYPE,
                object_type=PERSON_CORRECTION_OBJECT_TYPE,
                object_id=record.person_id,
                effective_date=record.effective_from,
                # 修正已经在本次事务里落库，事件直接置为完成态，
                # 不会被按「ready/scheduled/failed」捞起的异动执行器重复执行。
                status="completed",
                source="api",
                reason=record.change_reason or "登记人员基础信息修正",
                before_payload={},
                planned_payload={},
                actual_payload={
                    "field_code": record.field_code,
                    "version": record.version,
                    "effective_from": record.effective_from.isoformat(),
                    "effective_to": (
                        record.effective_to.isoformat() if record.effective_to else None
                    ),
                },
                workflow_instance_id=None,
                attempts=0,
                executed_at=datetime.now(UTC),
                version=1,
            )
        )
        await self._session.flush()
