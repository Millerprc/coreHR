from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.errors import ApiError
from hris.modules.attendance.models import AttendanceRuleSet
from hris.modules.attendance.schemas import (
    AttendanceRuleSetCreate,
    AttendanceRuleSetUpdate,
    AttendanceRuleSetVersionCreate,
)
from hris.modules.workforce.models import AuditLog


class AttendanceService:
    def __init__(self, session: AsyncSession, *, actor_id: UUID, trace_id: str) -> None:
        self._session = session
        self._actor_id = actor_id
        self._trace_id = trace_id

    def _audit(
        self,
        *,
        action: str,
        object_id: UUID,
        after: dict[str, Any],
        before: dict[str, Any] | None = None,
    ) -> None:
        self._session.add(
            AuditLog(
                occurred_at=datetime.now(UTC),
                actor_id=self._actor_id,
                trace_id=self._trace_id,
                action=action,
                object_type="attendance_rule_set",
                object_id=object_id,
                reason=None,
                before_payload=before or {},
                after_payload=after,
                source="api",
            )
        )

    async def create_rule_set(
        self,
        payload: AttendanceRuleSetCreate,
    ) -> AttendanceRuleSet:
        existing = await self._session.scalar(
            select(AttendanceRuleSet).where(
                AttendanceRuleSet.code == payload.code,
                AttendanceRuleSet.version == 1,
            )
        )
        if existing is not None:
            raise ApiError(
                status_code=409,
                code="ATTENDANCE_RULE_SET_CODE_EXISTS",
                message="考勤规则集代码已存在",
            )

        rule_set = AttendanceRuleSet(
            **payload.model_dump(),
            version=1,
            status="draft",
        )
        self._session.add(rule_set)
        await self._session.flush()
        self._audit(
            action="create",
            object_id=rule_set.id,
            after={"code": rule_set.code, "version": rule_set.version, "status": rule_set.status},
        )
        return rule_set

    async def list_rule_sets(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[AttendanceRuleSet], int]:
        total = await self._session.scalar(
            select(func.count()).select_from(AttendanceRuleSet)
        )
        items = list(
            (
                await self._session.scalars(
                    select(AttendanceRuleSet)
                    .order_by(AttendanceRuleSet.code, AttendanceRuleSet.version.desc())
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        return items, total or 0

    async def get_rule_set(self, rule_set_id: UUID) -> AttendanceRuleSet:
        rule_set = await self._session.get(AttendanceRuleSet, rule_set_id)
        if rule_set is None:
            raise ApiError(status_code=404, code="RULE_SET_NOT_FOUND", message="attendance rule set not found")
        return rule_set

    async def update_rule_set(
        self,
        rule_set_id: UUID,
        payload: AttendanceRuleSetUpdate,
    ) -> AttendanceRuleSet:
        rule_set = await self._session.get(AttendanceRuleSet, rule_set_id, with_for_update=True)
        if rule_set is None:
            raise ApiError(status_code=404, code="RULE_SET_NOT_FOUND", message="attendance rule set not found")
        if rule_set.status != "draft":
            raise ApiError(status_code=409, code="RULE_SET_NOT_DRAFT", message="only draft rule sets can be edited")
        changes = payload.model_dump(exclude_unset=True)
        effective_from = changes.get("effective_from", rule_set.effective_from)
        effective_to = changes.get("effective_to", rule_set.effective_to)
        if effective_to is not None and effective_to < effective_from:
            raise ApiError(status_code=422, code="RULE_SET_PERIOD_INVALID", message="invalid effective period")
        before = {field: str(getattr(rule_set, field)) for field in changes}
        for field, value in changes.items():
            setattr(rule_set, field, value)
        await self._session.flush()
        await self._session.refresh(rule_set)
        self._audit(
            action="update",
            object_id=rule_set.id,
            before=before,
            after={field: str(getattr(rule_set, field)) for field in changes},
        )
        return rule_set

    async def create_rule_set_version(
        self,
        rule_set_id: UUID,
        payload: AttendanceRuleSetVersionCreate,
    ) -> AttendanceRuleSet:
        source = await self.get_rule_set(rule_set_id)
        next_version = (
            await self._session.scalar(
                select(func.max(AttendanceRuleSet.version)).where(AttendanceRuleSet.code == source.code)
            )
            or 0
        ) + 1
        version = AttendanceRuleSet(
            code=source.code,
            name=payload.name or source.name,
            timezone=payload.timezone or source.timezone,
            version=next_version,
            status="draft",
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            rules=source.rules if payload.rules is None else payload.rules,
        )
        self._session.add(version)
        await self._session.flush()
        self._audit(
            action="create_version",
            object_id=version.id,
            after={"code": version.code, "version": version.version, "status": version.status},
        )
        return version

    async def publish_rule_set(self, rule_set_id: UUID) -> AttendanceRuleSet:
        rule_set = await self._session.get(AttendanceRuleSet, rule_set_id, with_for_update=True)
        if rule_set is None:
            raise ApiError(status_code=404, code="RULE_SET_NOT_FOUND", message="attendance rule set not found")
        if rule_set.status == "active":
            return rule_set
        previous = list(
            (
                await self._session.scalars(
                    select(AttendanceRuleSet).where(
                        AttendanceRuleSet.code == rule_set.code,
                        AttendanceRuleSet.status == "active",
                        AttendanceRuleSet.id != rule_set.id,
                    )
                )
            ).all()
        )
        for item in previous:
            item.status = "archived"
            if item.effective_from < rule_set.effective_from and (
                item.effective_to is None or item.effective_to >= rule_set.effective_from
            ):
                item.effective_to = rule_set.effective_from - timedelta(days=1)
        rule_set.status = "active"
        await self._session.flush()
        await self._session.refresh(rule_set)
        self._audit(
            action="publish",
            object_id=rule_set.id,
            after={"code": rule_set.code, "version": rule_set.version, "status": rule_set.status},
        )
        return rule_set
