# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.config import get_settings
from hris.core.errors import ApiError
from hris.modules.workforce.label_library import LabelLibraryService
from hris.modules.workforce.models import AuditLog, Person, PersonLabel


LABEL_SOURCE_MANUAL = "MANUAL"
LABEL_SOURCE_AI = "AI"
LABEL_SOURCES = (LABEL_SOURCE_MANUAL, LABEL_SOURCE_AI)
LABEL_NAME_MAX_LENGTH = 255
LABEL_TYPE_MAX_LENGTH = 100
LABEL_SOURCE_MAX_LENGTH = 80
LABEL_STATUS_ACTIVE = "active"
LABEL_STATUS_ENDED = "ended"
# Requirement: HR-LABEL-013 — 单次批量赋予的标签条数上限。
LABEL_BATCH_MAX_ITEMS = 100


class PersonLabelCreate(BaseModel):
    label_name: str = Field(min_length=1, max_length=LABEL_NAME_MAX_LENGTH)
    label_type: str = Field(min_length=1, max_length=LABEL_TYPE_MAX_LENGTH)
    source: str = Field(
        default=LABEL_SOURCE_MANUAL,
        min_length=1,
        max_length=LABEL_SOURCE_MAX_LENGTH,
    )
    effective_from: date
    effective_to: date | None = None

    @field_validator("label_name", "label_type")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        # Requirement: HR-LABEL-002 — 标签名称与标签类型去除首尾空白后不能为空。
        stripped = value.strip()
        if not stripped:
            raise ValueError("标签名称和标签类型不能为空白")
        return stripped

    @field_validator("source")
    @classmethod
    def normalize_source(cls, value: str) -> str:
        # Requirement: HR-LABEL-003 — 来源仅允许 MANUAL 或 AI，AI 来源由服务端推导 AI 标记。
        normalized = value.strip().upper()
        if normalized not in LABEL_SOURCES:
            raise ValueError("标签来源仅支持 MANUAL 或 AI")
        return normalized

    @model_validator(mode="after")
    def validate_effective_period(self) -> "PersonLabelCreate":
        # Requirement: HR-LABEL-004 — 标签结束日期不得早于生效日期。
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to不能早于effective_from")
        return self


class PersonLabelBatchItem(BaseModel):
    label_type_code: str = Field(min_length=1, max_length=LABEL_TYPE_MAX_LENGTH)
    label_code: str = Field(min_length=1, max_length=LABEL_NAME_MAX_LENGTH)

    @field_validator("label_type_code", "label_code")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("标签类型编码和标签编码不能为空白")
        return stripped


class PersonLabelBatchCreate(BaseModel):
    effective_from: date
    source: str = Field(default=LABEL_SOURCE_MANUAL, max_length=LABEL_SOURCE_MAX_LENGTH)
    labels: list[PersonLabelBatchItem] = Field(min_length=1, max_length=LABEL_BATCH_MAX_ITEMS)

    @field_validator("source")
    @classmethod
    def normalize_source(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in LABEL_SOURCES:
            raise ValueError("标签来源仅支持 MANUAL 或 AI")
        return normalized

    @model_validator(mode="after")
    def reject_duplicated_items(self) -> "PersonLabelBatchCreate":
        # Requirement: HR-LABEL-014 — 同一批次内不允许出现重复的标签库编码组合。
        seen: set[tuple[str, str]] = set()
        for item in self.labels:
            key = (item.label_type_code, item.label_code)
            if key in seen:
                raise ValueError(
                    f"同一批次内标签重复：{item.label_type_code}/{item.label_code}"
                )
            seen.add(key)
        return self


class PersonLabelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    person_id: UUID
    label_name: str
    label_type: str
    source: str
    effective_from: date
    effective_to: date | None
    status: str
    is_ai_generated: bool


class PersonLabelBatchResponse(BaseModel):
    created: list[PersonLabelResponse]


class PersonLabelListResponse(BaseModel):
    items: list[PersonLabelResponse]
    total: int


class PageResponse(BaseModel):
    items: list[PersonLabelResponse]
    total: int
    page: int
    page_size: int


class LabelTypeItem(BaseModel):
    code: str
    name: str
    count: int


class LabelTypeListResponse(BaseModel):
    items: list[LabelTypeItem]


class PersonLabelService:
    def __init__(self, session: AsyncSession, *, actor_id: UUID, trace_id: str) -> None:
        self._session = session
        self._actor_id = actor_id
        self._trace_id = trace_id
        self._timezone = ZoneInfo(get_settings().business_timezone)

    def business_date(self) -> date:
        return datetime.now(self._timezone).date()

    async def create_label(
        self,
        person_id: UUID,
        payload: PersonLabelCreate,
    ) -> PersonLabel:
        # Requirement: HR-LABEL-001 — 标签只能挂在已存在的人员档案上。
        if await self._session.get(Person, person_id) is None:
            raise ApiError(
                status_code=422,
                code="PERSON_LABEL_PERSON_NOT_FOUND",
                message="人员档案不存在，无法创建员工标签",
            )

        # Requirement: HR-LABEL-005 — 人员、类型、名称、生效日与来源的组合唯一。
        existing = await self._session.scalar(
            select(PersonLabel).where(
                PersonLabel.person_id == person_id,
                PersonLabel.label_type == payload.label_type,
                PersonLabel.label_name == payload.label_name,
                PersonLabel.effective_from == payload.effective_from,
                PersonLabel.source == payload.source,
            )
        )
        if existing is not None:
            raise ApiError(
                status_code=409,
                code="PERSON_LABEL_DUPLICATE",
                message="同一人员、类型、名称、生效日期与来源的标签已存在",
            )

        label = PersonLabel(
            person_id=person_id,
            label_name=payload.label_name,
            label_type=payload.label_type,
            source=payload.source,
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            status=LABEL_STATUS_ACTIVE,
            # Requirement: HR-LABEL-003 — AI 标记由来源推导，调用方不能直接指定。
            is_ai_generated=payload.source == LABEL_SOURCE_AI,
        )
        try:
            async with self._session.begin_nested():
                self._session.add(label)
                await self._session.flush()
        except IntegrityError as exc:
            raise ApiError(
                status_code=409,
                code="PERSON_LABEL_DUPLICATE",
                message="同一人员、类型、名称、生效日期与来源的标签已存在",
            ) from exc

        await self._audit(
            action="person_label.create",
            object_id=label.id,
            reason="创建员工标签",
            before={},
            after=self._label_payload(label),
        )
        return label

    async def create_labels_batch(
        self,
        person_id: UUID,
        payload: PersonLabelBatchCreate,
    ) -> list[PersonLabel]:
        """从标签库批量多选赋予员工标签。

        Requirement: HR-LABEL-015 — 整批原子：任一条在标签库中找不到，整批拒绝且不落任何数据。
        """
        if await self._session.get(Person, person_id) is None:
            raise ApiError(
                status_code=422,
                code="PERSON_LABEL_PERSON_NOT_FOUND",
                message="人员档案不存在，无法创建员工标签",
            )

        library = LabelLibraryService(self._session)
        resolved: list[tuple[str, str]] = []
        for item in payload.labels:
            resolved.append(await library.resolve(item.label_type_code, item.label_code))

        for label_type, label_name in resolved:
            existing = await self._session.scalar(
                select(PersonLabel).where(
                    PersonLabel.person_id == person_id,
                    PersonLabel.label_type == label_type,
                    PersonLabel.label_name == label_name,
                    PersonLabel.effective_from == payload.effective_from,
                    PersonLabel.source == payload.source,
                )
            )
            if existing is not None:
                raise ApiError(
                    status_code=409,
                    code="PERSON_LABEL_DUPLICATE",
                    message="同一人员、类型、名称、生效日期与来源的标签已存在",
                )

        labels: list[PersonLabel] = []
        async with self._session.begin_nested():
            for label_type, label_name in resolved:
                label = PersonLabel(
                    person_id=person_id,
                    label_name=label_name,
                    label_type=label_type,
                    source=payload.source,
                    effective_from=payload.effective_from,
                    effective_to=None,
                    status=LABEL_STATUS_ACTIVE,
                    # Requirement: HR-LABEL-003 — AI 标记由来源推导，调用方不能直接指定。
                    is_ai_generated=payload.source == LABEL_SOURCE_AI,
                )
                self._session.add(label)
                labels.append(label)
            await self._session.flush()

        for label in labels:
            await self._audit(
                action="person_label.create",
                object_id=label.id,
                reason="批量创建员工标签",
                before={},
                after=self._label_payload(label),
            )
        return labels

    async def list_person_labels(
        self,
        person_id: UUID,
        effective_at: date,
    ) -> list[PersonLabel]:
        # Requirement: HR-LABEL-001 — 按人查询只对已存在的人员档案开放。
        if await self._session.get(Person, person_id) is None:
            raise ApiError(
                status_code=422,
                code="PERSON_LABEL_PERSON_NOT_FOUND",
                message="人员档案不存在，无法查询员工标签",
            )
        # Requirement: HR-LABEL-006 — 只返回生效区间覆盖查询日期的标签，半开区间左闭右开。
        statement = (
            select(PersonLabel)
            .where(
                PersonLabel.person_id == person_id,
                PersonLabel.effective_from <= effective_at,
                or_(
                    PersonLabel.effective_to.is_(None),
                    PersonLabel.effective_to > effective_at,
                ),
            )
            .order_by(PersonLabel.effective_from.desc(), PersonLabel.id)
        )
        return list((await self._session.scalars(statement)).all())

    async def list_labels(
        self,
        *,
        label_type: str | None,
        source: str | None,
        person_id: UUID | None,
        include_expired: bool,
        page: int,
        page_size: int,
    ) -> tuple[list[PersonLabel], int]:
        filters = []
        if label_type:
            filters.append(PersonLabel.label_type == label_type.strip())
        if source:
            filters.append(PersonLabel.source == source.strip().upper())
        if person_id is not None:
            filters.append(PersonLabel.person_id == person_id)
        if not include_expired:
            # Requirement: HR-LABEL-007 — 默认只返回当前有效标签（未结束或结束日晚于业务当天）。
            today = self.business_date()
            filters.append(
                or_(
                    PersonLabel.effective_to.is_(None),
                    PersonLabel.effective_to > today,
                )
            )
        total = await self._session.scalar(
            select(func.count()).select_from(PersonLabel).where(*filters)
        )
        items = list(
            (
                await self._session.scalars(
                    select(PersonLabel)
                    .where(*filters)
                    .order_by(
                        PersonLabel.label_type,
                        PersonLabel.label_name,
                        PersonLabel.effective_from.desc(),
                        PersonLabel.id,
                    )
                    .limit(page_size)
                    .offset((page - 1) * page_size)
                )
            ).all()
        )
        return items, total or 0

    async def list_label_types(self) -> list[LabelTypeItem]:
        today = self.business_date()
        # Requirement: HR-LABEL-009 — 标签类型按现有数据聚合，当前有效数量多的排在前面。
        valid_filter = or_(
            PersonLabel.effective_to.is_(None),
            PersonLabel.effective_to > today,
        )
        valid_count = func.count(PersonLabel.id).filter(valid_filter)
        rows = (
            await self._session.execute(
                select(PersonLabel.label_type, valid_count.label("valid_count"))
                .group_by(PersonLabel.label_type)
                .order_by(valid_count.desc(), PersonLabel.label_type)
            )
        ).all()
        return [
            LabelTypeItem(
                code=row.label_type,
                # Requirement: HR-LABEL-009 — 标签类型没有独立字典表，名称沿用类型编码。
                name=row.label_type,
                count=row.valid_count,
            )
            for row in rows
        ]

    async def end_label(self, label_id: UUID) -> None:
        label = await self._session.get(PersonLabel, label_id)
        if label is None:
            raise ApiError(
                status_code=404,
                code="PERSON_LABEL_NOT_FOUND",
                message="员工标签不存在",
            )
        today = self.business_date()
        # Requirement: HR-LABEL-008 — 已结束的标签不能重复结束。
        if label.effective_to is not None:
            raise ApiError(
                status_code=409,
                code="PERSON_LABEL_ALREADY_ENDED",
                message="员工标签已结束",
            )
        # Requirement: HR-LABEL-008 — 结束日期不得早于生效日期，尚未生效的标签不能软结束。
        if label.effective_from > today:
            raise ApiError(
                status_code=409,
                code="PERSON_LABEL_NOT_EFFECTIVE",
                message="员工标签尚未生效，无法结束",
            )
        before = self._label_payload(label)
        label.effective_to = today
        label.status = LABEL_STATUS_ENDED
        await self._session.flush()
        await self._audit(
            action="person_label.end",
            object_id=label.id,
            reason="结束员工标签",
            before=before,
            after=self._label_payload(label),
        )

    async def _audit(
        self,
        *,
        action: str,
        object_id: UUID,
        reason: str,
        before: dict[str, Any],
        after: dict[str, Any],
    ) -> None:
        self._session.add(
            AuditLog(
                occurred_at=datetime.now(UTC),
                actor_id=self._actor_id,
                trace_id=self._trace_id,
                action=action,
                object_type="person_label",
                object_id=object_id,
                reason=reason,
                before_payload=before,
                after_payload=after,
                source="api",
            )
        )
        await self._session.flush()

    @staticmethod
    def _label_payload(label: PersonLabel) -> dict[str, Any]:
        # Requirement: HR-LABEL-010 — 审计日志只记录标签业务字段，不写入人员姓名等个人信息。
        return {
            "person_id": str(label.person_id),
            "label_type": label.label_type,
            "label_name": label.label_name,
            "source": label.source,
            "status": label.status,
            "effective_from": label.effective_from.isoformat(),
            "effective_to": label.effective_to.isoformat() if label.effective_to else None,
            "is_ai_generated": label.is_ai_generated,
        }
