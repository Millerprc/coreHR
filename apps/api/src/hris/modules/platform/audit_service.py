# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import csv
from dataclasses import dataclass
from datetime import UTC, datetime
from io import StringIO
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.errors import ApiError
from hris.modules.platform.models import UserAccount
from hris.modules.workforce.models import AuditLog


AUDIT_EXPORT_MAX_ROWS = 50_000
AUDIT_EXPORT_FILENAME = "audit-logs.csv"
# Requirement: AUDIT-007 — 导出列顺序固定，且不包含 before_payload / after_payload。
AUDIT_CSV_COLUMNS = (
    "occurred_at",
    "actor_name",
    "action",
    "object_type",
    "object_id",
    "trace_id",
    "reason",
    "source",
)
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    occurred_at: datetime
    actor_id: UUID | None
    # Requirement: AUDIT-008 — actor_name 取 user_accounts.display_name，关联不到时为 null。
    actor_name: str | None
    trace_id: str
    action: str
    object_type: str
    object_id: UUID | None
    reason: str | None
    source: str


class AuditLogDetailResponse(AuditLogResponse):
    # Requirement: AUDIT-009 — payload 只在单条详情端点返回，列表与导出均不外泄。
    before_payload: dict[str, Any]
    after_payload: dict[str, Any]


class PageResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int


class ActionCountResponse(BaseModel):
    code: str
    count: int


class ActionListResponse(BaseModel):
    items: list[ActionCountResponse]


class AuditActorResponse(BaseModel):
    # Requirement: P-13 — 操作人下拉只需要账号标识与显示名；
    # 不返回邮箱、手机号等个人联系方式，也不返回账号状态与角色等账号管理信息。
    id: UUID
    display_name: str
    username: str


class AuditActorListResponse(BaseModel):
    items: list[AuditActorResponse]
    total: int


@dataclass(frozen=True)
class AuditLogRow:
    id: UUID
    occurred_at: datetime
    actor_id: UUID | None
    actor_name: str | None
    trace_id: str
    action: str
    object_type: str
    object_id: UUID | None
    reason: str | None
    source: str


@dataclass(frozen=True)
class AuditLogDetailRow(AuditLogRow):
    before_payload: dict[str, Any]
    after_payload: dict[str, Any]


def _as_utc(value: datetime | None) -> datetime | None:
    # Requirement: AUDIT-002 — 未带时区的时间按 UTC 解释，避免服务端时区导致区间漂移。
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@dataclass(frozen=True)
class AuditLogFilters:
    occurred_from: datetime | None = None
    occurred_to: datetime | None = None
    actor_id: UUID | None = None
    action: str | None = None
    object_type: str | None = None
    object_id: UUID | None = None
    trace_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "occurred_from", _as_utc(self.occurred_from))
        object.__setattr__(self, "occurred_to", _as_utc(self.occurred_to))
        object.__setattr__(self, "action", _clean_text(self.action))
        object.__setattr__(self, "object_type", _clean_text(self.object_type))
        object.__setattr__(self, "trace_id", _clean_text(self.trace_id))

    def validate(self) -> None:
        # Requirement: AUDIT-001 — 时间区间为闭区间过滤，起点晚于终点时直接拒绝。
        if (
            self.occurred_from is not None
            and self.occurred_to is not None
            and self.occurred_from > self.occurred_to
        ):
            raise ApiError(
                status_code=422,
                code="AUDIT_TIME_RANGE_INVALID",
                message="开始时间不能晚于结束时间",
                details=[
                    {
                        "occurred_from": self.occurred_from.isoformat(),
                        "occurred_to": self.occurred_to.isoformat(),
                    }
                ],
            )


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


async def record_audit_event(
    session: AsyncSession,
    *,
    actor_id: UUID | None,
    trace_id: str,
    action: str,
    object_type: str,
    object_id: UUID | None = None,
    reason: str | None = None,
    before_payload: dict[str, Any] | None = None,
    after_payload: dict[str, Any] | None = None,
    source: str = "api",
) -> None:
    """写一条审计日志。

    Requirement: D-108 — 授权激活 / 停用是写操作，必须走审计；
    调用方负责保证 payload 里不含 Token 明文（只允许放摘要或标识）。

    取舍说明：审计写入散落在各 service 里已经出现多份重复实现，
    这里抽成一个共用入口，新增授权类写操作直接复用，不再各自拼 AuditLog。
    """
    session.add(
        AuditLog(
            occurred_at=datetime.now(UTC),
            actor_id=actor_id,
            trace_id=trace_id,
            action=action,
            object_type=object_type,
            object_id=object_id,
            reason=reason,
            before_payload=before_payload or {},
            after_payload=after_payload or {},
            source=source,
        )
    )
    await session.flush()


class AuditLogService:
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

    async def list_logs(
        self,
        filters: AuditLogFilters,
        *,
        page: int,
        page_size: int,
    ) -> tuple[list[AuditLogRow], int]:
        filters.validate()
        conditions = self._conditions(filters)
        total = await self._session.scalar(
            select(func.count()).select_from(AuditLog).where(*conditions)
        )
        rows = (
            await self._session.execute(
                self._select_columns()
                .where(*conditions)
                # Requirement: AUDIT-003 — 默认按发生时间倒序，同一时间按主键倒序。
                .order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
        ).all()
        return [self._to_row(row) for row in rows], total or 0

    async def action_counts(self) -> list[ActionCountResponse]:
        # Requirement: AUDIT-004 — action 按现有数据聚合，条目多的排在前面。
        count = func.count(AuditLog.id)
        rows = (
            await self._session.execute(
                select(AuditLog.action, count.label("action_count"))
                .group_by(AuditLog.action)
                .order_by(count.desc(), AuditLog.action)
            )
        ).all()
        return [
            ActionCountResponse(code=row.action, count=row.action_count)
            for row in rows
        ]

    async def list_actors(self) -> list[AuditActorResponse]:
        """返回审计页「操作人」下拉需要的账号清单。

        Requirement: P-13 — 审计页的操作人下拉原先复用主管理员专用的 /api/v1/platform/users，
        治理管理员必然 403；本方法配合 GET /api/v1/platform/audit/actors 提供只读替代数据源。

        取舍说明：
        1. 只返回 id、display_name、username 三个字段，不返回邮箱、手机号等个人联系方式。
        2. 不按账号状态过滤——审计记录里可能引用已停用账号的历史操作，过滤会漏掉操作人。
        3. 按 display_name 升序返回，同名时按 id 升序保证顺序稳定。
        """
        rows = (
            await self._session.execute(
                select(UserAccount.id, UserAccount.display_name, UserAccount.username)
                .order_by(UserAccount.display_name.asc(), UserAccount.id.asc())
            )
        ).all()
        return [
            AuditActorResponse(
                id=row.id,
                display_name=row.display_name,
                username=row.username,
            )
            for row in rows
        ]

    async def get_log(self, audit_log_id: UUID) -> AuditLogDetailRow:
        row = (
            await self._session.execute(
                self._select_columns(payloads=True).where(
                    AuditLog.id == audit_log_id
                )
            )
        ).one_or_none()
        if row is None:
            raise ApiError(
                status_code=404,
                code="AUDIT_LOG_NOT_FOUND",
                message="审计日志不存在",
            )
        return AuditLogDetailRow(
            **self._to_row(row).__dict__,
            before_payload=row._mapping["before_payload"] or {},
            after_payload=row._mapping["after_payload"] or {},
        )

    async def export_csv(self, filters: AuditLogFilters) -> tuple[bytes, str, int]:
        filters.validate()
        rows = (
            await self._session.execute(
                self._select_columns()
                .where(*self._conditions(filters))
                .order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
                .limit(AUDIT_EXPORT_MAX_ROWS + 1)
            )
        ).all()
        # Requirement: AUDIT-005 — 单次导出上限 50000 行，超出时提示缩小筛选范围。
        if len(rows) > AUDIT_EXPORT_MAX_ROWS:
            raise ApiError(
                status_code=422,
                code="AUDIT_EXPORT_TOO_LARGE",
                message="当前筛选结果超过单次导出上限，请缩小筛选范围后重试",
                details=[{"max_rows": AUDIT_EXPORT_MAX_ROWS}],
            )

        buffer = StringIO(newline="")
        writer = csv.DictWriter(
            buffer,
            fieldnames=list(AUDIT_CSV_COLUMNS),
            extrasaction="ignore",
            lineterminator="\r\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    column: self._safe_cell(row._mapping[column])
                    for column in AUDIT_CSV_COLUMNS
                }
            )

        self._session.add(
            AuditLog(
                occurred_at=datetime.now(UTC),
                actor_id=self._actor_id,
                trace_id=self._trace_id,
                action="platform.audit_logs.export",
                object_type="audit_log_export",
                object_id=None,
                reason="导出审计日志",
                before_payload={},
                # Requirement: AUDIT-010 — 导出审计只记录筛选条件与行数，不记录任何 payload 内容。
                after_payload={
                    "row_count": len(rows),
                    "filters": {
                        "occurred_from": (
                            filters.occurred_from.isoformat()
                            if filters.occurred_from
                            else None
                        ),
                        "occurred_to": (
                            filters.occurred_to.isoformat()
                            if filters.occurred_to
                            else None
                        ),
                        "actor_id": str(filters.actor_id) if filters.actor_id else None,
                        "action": filters.action,
                        "object_type": filters.object_type,
                        "object_id": str(filters.object_id) if filters.object_id else None,
                        "trace_id": filters.trace_id,
                    },
                },
                source="api",
            )
        )
        await self._session.flush()
        content = ("\ufeff" + buffer.getvalue()).encode("utf-8")
        return content, AUDIT_EXPORT_FILENAME, len(rows)

    @staticmethod
    def _select_columns(payloads: bool = False) -> Any:
        columns = [
            AuditLog.id,
            AuditLog.occurred_at,
            AuditLog.actor_id,
            # Requirement: AUDIT-008 — actor_name 联表 user_accounts，关联不到时为 null。
            UserAccount.display_name.label("actor_name"),
            AuditLog.trace_id,
            AuditLog.action,
            AuditLog.object_type,
            AuditLog.object_id,
            AuditLog.reason,
            AuditLog.source,
        ]
        if payloads:
            columns.extend([AuditLog.before_payload, AuditLog.after_payload])
        return (
            select(*columns)
            .select_from(AuditLog)
            .outerjoin(UserAccount, UserAccount.id == AuditLog.actor_id)
        )

    @staticmethod
    def _conditions(filters: AuditLogFilters) -> list[Any]:
        conditions: list[Any] = []
        if filters.occurred_from is not None:
            # Requirement: AUDIT-001 — 闭区间过滤，起点与终点都包含。
            conditions.append(AuditLog.occurred_at >= filters.occurred_from)
        if filters.occurred_to is not None:
            conditions.append(AuditLog.occurred_at <= filters.occurred_to)
        if filters.actor_id is not None:
            conditions.append(AuditLog.actor_id == filters.actor_id)
        if filters.action is not None:
            conditions.append(AuditLog.action == filters.action)
        if filters.object_type is not None:
            conditions.append(AuditLog.object_type == filters.object_type)
        if filters.object_id is not None:
            conditions.append(AuditLog.object_id == filters.object_id)
        if filters.trace_id is not None:
            conditions.append(AuditLog.trace_id == filters.trace_id)
        return conditions

    @staticmethod
    def _to_row(row: Any) -> AuditLogRow:
        mapping = row._mapping
        return AuditLogRow(
            id=mapping["id"],
            occurred_at=mapping["occurred_at"],
            actor_id=mapping["actor_id"],
            actor_name=mapping["actor_name"],
            trace_id=mapping["trace_id"],
            action=mapping["action"],
            object_type=mapping["object_type"],
            object_id=mapping["object_id"],
            reason=mapping["reason"],
            source=mapping["source"],
        )

    @staticmethod
    def _safe_cell(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, datetime):
            return value.isoformat()
        text = str(value).replace("\x00", "")
        candidate = text.lstrip(" ")
        if candidate.startswith(_FORMULA_PREFIXES):
            return "'" + text
        return text
