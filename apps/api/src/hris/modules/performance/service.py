# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""Business rules for maintaining performance OKR definitions."""

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from itertools import groupby
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.errors import ApiError
from hris.modules.performance.models import (
    CYCLE_STATUS_ACTIVE,
    CYCLE_STATUS_CLOSED,
    CYCLE_STATUS_DRAFT,
    CYCLE_STATUSES,
    CYCLE_TYPES,
    MAX_OKR_SCORE,
    MAX_OKR_WEIGHT,
    MIN_OKR_SCORE,
    OKR_STATUS_ARCHIVED,
    OKR_STATUS_DRAFT,
    OKR_STATUSES,
    PerformanceCycle,
    PerformanceKeyResult,
    PerformanceObjective,
)
from hris.modules.performance.schemas import (
    PerformanceCycleCreate,
    PerformanceCycleDetailResponse,
    PerformanceCycleUpdate,
    PerformanceKeyResultCreate,
    PerformanceKeyResultResponse,
    PerformanceKeyResultUpdate,
    PerformanceObjectiveCreate,
    PerformanceObjectiveGroupResponse,
    PerformanceObjectiveListResponse,
    PerformanceObjectiveResponse,
    PerformanceObjectiveScoreResponse,
    PerformanceObjectiveUpdate,
    PerformanceScorecardEntry,
    PerformanceScorecardResponse,
)
from hris.modules.workforce.models import AuditLog, Person


# Requirement: HR-PERF-002 — 周期状态只允许草稿→进行中→已关闭，已关闭为终态。
CYCLE_STATUS_TRANSITIONS: dict[str, set[str]] = {
    CYCLE_STATUS_DRAFT: {CYCLE_STATUS_ACTIVE, CYCLE_STATUS_CLOSED},
    CYCLE_STATUS_ACTIVE: {CYCLE_STATUS_CLOSED},
    CYCLE_STATUS_CLOSED: set(),
}

_SCORE_QUANTUM = Decimal("0.01")
_ZERO = Decimal("0")


def _decimal_text(value: Decimal | None) -> str | None:
    """Render a decimal for JSON audit payloads."""
    if value is None:
        return None
    return str(value)


class PerformanceService:
    def __init__(self, session: AsyncSession, *, actor_id: UUID, trace_id: str) -> None:
        self._session = session
        self._actor_id = actor_id
        self._trace_id = trace_id

    # ------------------------------------------------------------------
    # cycles
    # ------------------------------------------------------------------
    async def create_cycle(self, payload: PerformanceCycleCreate) -> PerformanceCycle:
        # Requirement: HR-PERF-001 — 周期类型与日期区间由服务端校验，编码唯一。
        cycle_type = payload.cycle_type.strip().lower()
        if cycle_type not in CYCLE_TYPES:
            raise ApiError(
                status_code=422,
                code="PERFORMANCE_CYCLE_TYPE_INVALID",
                message="周期类型仅支持 quarterly、annual、special",
            )
        if payload.end_date < payload.start_date:
            raise ApiError(
                status_code=422,
                code="PERFORMANCE_CYCLE_DATE_ORDER_INVALID",
                message="周期结束日期不能早于开始日期",
            )
        code = payload.code.strip().upper()
        existing = await self._session.scalar(
            select(PerformanceCycle).where(PerformanceCycle.code == code)
        )
        if existing is not None:
            raise ApiError(
                status_code=409,
                code="PERFORMANCE_CYCLE_CODE_CONFLICT",
                message="绩效周期编码已存在",
            )

        cycle = PerformanceCycle(
            code=code,
            name=payload.name.strip(),
            cycle_type=cycle_type,
            start_date=payload.start_date,
            end_date=payload.end_date,
            status=CYCLE_STATUS_DRAFT,
        )
        try:
            async with self._session.begin_nested():
                self._session.add(cycle)
                await self._session.flush()
        except IntegrityError as exc:
            raise ApiError(
                status_code=409,
                code="PERFORMANCE_CYCLE_CODE_CONFLICT",
                message="绩效周期编码已存在",
            ) from exc

        # Requirement: HR-PERF-015 — 回读数据库表示，保证响应中的数值精度与落库一致。
        await self._session.refresh(cycle)
        await self._audit(
            action="performance.cycle.create",
            object_type="performance_cycle",
            object_id=cycle.id,
            reason="创建绩效周期",
            before={},
            after=self._cycle_payload(cycle),
        )
        return cycle

    async def list_cycles(
        self,
        *,
        status: str | None,
        cycle_type: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[PerformanceCycle], int]:
        filters = []
        if status is not None:
            normalized = status.strip().lower()
            if normalized not in CYCLE_STATUSES:
                raise ApiError(
                    status_code=422,
                    code="PERFORMANCE_CYCLE_STATUS_INVALID",
                    message="周期状态仅支持 draft、active、closed",
                )
            filters.append(PerformanceCycle.status == normalized)
        if cycle_type is not None:
            normalized_type = cycle_type.strip().lower()
            if normalized_type not in CYCLE_TYPES:
                raise ApiError(
                    status_code=422,
                    code="PERFORMANCE_CYCLE_TYPE_INVALID",
                    message="周期类型仅支持 quarterly、annual、special",
                )
            filters.append(PerformanceCycle.cycle_type == normalized_type)

        total = await self._session.scalar(
            select(func.count()).select_from(PerformanceCycle).where(*filters)
        )
        items = list(
            (
                await self._session.scalars(
                    select(PerformanceCycle)
                    .where(*filters)
                    .order_by(
                        PerformanceCycle.start_date.desc(),
                        PerformanceCycle.code,
                    )
                    .limit(page_size)
                    .offset((page - 1) * page_size)
                )
            ).all()
        )
        return items, total or 0

    async def get_cycle_detail(self, cycle_id: UUID) -> PerformanceCycleDetailResponse:
        cycle = await self._get_cycle(cycle_id)
        objectives = list(
            (
                await self._session.scalars(
                    select(PerformanceObjective).where(
                        PerformanceObjective.cycle_id == cycle_id
                    )
                )
            ).all()
        )
        key_result_count = 0
        if objectives:
            key_result_count = (
                await self._session.scalar(
                    select(func.count())
                    .select_from(PerformanceKeyResult)
                    .where(
                        PerformanceKeyResult.objective_id.in_(
                            [objective.id for objective in objectives]
                        )
                    )
                )
                or 0
            )
        total_weight = sum(
            (objective.weight for objective in objectives), _ZERO
        )
        person_count = len({objective.person_id for objective in objectives})
        return PerformanceCycleDetailResponse(
            id=cycle.id,
            code=cycle.code,
            name=cycle.name,
            cycle_type=cycle.cycle_type,
            start_date=cycle.start_date,
            end_date=cycle.end_date,
            status=cycle.status,
            created_at=cycle.created_at,
            updated_at=cycle.updated_at,
            objective_count=len(objectives),
            person_count=person_count,
            key_result_count=key_result_count,
            objective_total_weight=total_weight,
        )

    async def update_cycle(
        self,
        cycle_id: UUID,
        payload: PerformanceCycleUpdate,
    ) -> PerformanceCycle:
        cycle = await self._get_cycle(cycle_id)
        changes = payload.model_dump(exclude_unset=True)

        # Requirement: HR-PERF-002 — 已关闭的周期不可再修改。
        if cycle.status == CYCLE_STATUS_CLOSED:
            raise ApiError(
                status_code=409,
                code="PERFORMANCE_CYCLE_CLOSED",
                message="绩效周期已关闭，不可修改",
            )

        if "cycle_type" in changes:
            normalized = str(changes["cycle_type"]).strip().lower()
            if normalized not in CYCLE_TYPES:
                raise ApiError(
                    status_code=422,
                    code="PERFORMANCE_CYCLE_TYPE_INVALID",
                    message="周期类型仅支持 quarterly、annual、special",
                )
            changes["cycle_type"] = normalized

        if "status" in changes:
            normalized_status = str(changes["status"]).strip().lower()
            if normalized_status not in CYCLE_STATUSES:
                raise ApiError(
                    status_code=422,
                    code="PERFORMANCE_CYCLE_STATUS_INVALID",
                    message="周期状态仅支持 draft、active、closed",
                )
            if normalized_status not in CYCLE_STATUS_TRANSITIONS[cycle.status]:
                raise ApiError(
                    status_code=422,
                    code="PERFORMANCE_CYCLE_STATUS_TRANSITION_INVALID",
                    message="绩效周期状态流转不被允许",
                )
            changes["status"] = normalized_status

        start_date = changes.get("start_date", cycle.start_date)
        end_date = changes.get("end_date", cycle.end_date)
        if end_date < start_date:
            raise ApiError(
                status_code=422,
                code="PERFORMANCE_CYCLE_DATE_ORDER_INVALID",
                message="周期结束日期不能早于开始日期",
            )

        before = self._cycle_payload(cycle)
        for field, value in changes.items():
            if field == "name":
                setattr(cycle, field, str(value).strip())
            else:
                setattr(cycle, field, value)
        await self._session.flush()
        await self._session.refresh(cycle)
        await self._audit(
            action="performance.cycle.update",
            object_type="performance_cycle",
            object_id=cycle.id,
            reason="修改绩效周期",
            before=before,
            after=self._cycle_payload(cycle),
        )
        return cycle

    # ------------------------------------------------------------------
    # objectives
    # ------------------------------------------------------------------
    async def create_objective(
        self,
        cycle_id: UUID,
        payload: PerformanceObjectiveCreate,
    ) -> PerformanceObjective:
        cycle = await self._get_cycle(cycle_id)
        # Requirement: HR-PERF-009 — 已关闭的周期不接受目标与关键结果写入。
        self._ensure_cycle_writable(cycle)
        await self._lock_cycle(cycle_id)

        # Requirement: HR-PERF-003 — 目标必须归属到已存在的人员档案。
        if await self._session.get(Person, payload.person_id) is None:
            raise ApiError(
                status_code=422,
                code="PERFORMANCE_PERSON_NOT_FOUND",
                message="人员档案不存在，无法创建绩效目标",
            )

        # Requirement: HR-PERF-004 — 目标权重必须落在 (0, 100]。
        weight = self._ensure_weight(
            payload.weight, "PERFORMANCE_OBJECTIVE_WEIGHT_INVALID"
        )
        # Requirement: HR-PERF-005 — 同一周期同一人的目标权重之和不得超过 100。
        current_total = await self._objective_weight_sum(cycle_id, payload.person_id)
        await self._ensure_objective_total(current_total, weight)

        sequence_no = await self._next_objective_sequence(cycle_id, payload.person_id)
        objective = PerformanceObjective(
            cycle_id=cycle_id,
            person_id=payload.person_id,
            title=payload.title.strip(),
            description=payload.description,
            weight=weight,
            status=OKR_STATUS_DRAFT,
            sequence_no=sequence_no,
        )
        async with self._session.begin_nested():
            self._session.add(objective)
            await self._session.flush()

        # Requirement: HR-PERF-015 — 回读数据库表示，保证响应中的数值精度与落库一致。
        await self._session.refresh(objective)
        await self._audit(
            action="performance.objective.create",
            object_type="performance_objective",
            object_id=objective.id,
            reason="创建绩效目标",
            before={},
            after=self._objective_payload(objective),
        )
        return objective

    async def list_objectives(
        self,
        cycle_id: UUID,
        *,
        person_id: UUID | None,
        status: str | None,
        include_archived: bool,
        group_by_person: bool,
    ) -> PerformanceObjectiveListResponse:
        await self._get_cycle(cycle_id)
        filters = [PerformanceObjective.cycle_id == cycle_id]
        if person_id is not None:
            filters.append(PerformanceObjective.person_id == person_id)
        if status is not None:
            normalized = status.strip().lower()
            if normalized not in OKR_STATUSES:
                raise ApiError(
                    status_code=422,
                    code="PERFORMANCE_OBJECTIVE_STATUS_INVALID",
                    message="目标状态仅支持 draft、submitted、approved、archived",
                )
            filters.append(PerformanceObjective.status == normalized)
        elif not include_archived:
            filters.append(PerformanceObjective.status != OKR_STATUS_ARCHIVED)

        objectives = list(
            (
                await self._session.scalars(
                    select(PerformanceObjective)
                    .where(*filters)
                    .order_by(
                        PerformanceObjective.person_id,
                        PerformanceObjective.sequence_no,
                        PerformanceObjective.id,
                    )
                )
            ).all()
        )
        key_results_by_objective = await self._load_key_results(
            [objective.id for objective in objectives]
        )
        responses = [
            self._objective_response(objective, key_results_by_objective)
            for objective in objectives
        ]

        groups: list[PerformanceObjectiveGroupResponse] = []
        if group_by_person:
            groups = self._build_person_groups(responses)

        return PerformanceObjectiveListResponse(
            items=[] if group_by_person else responses,
            total=len(responses),
            grouped_by_person=group_by_person,
            person_groups=groups,
        )

    async def update_objective(
        self,
        objective_id: UUID,
        payload: PerformanceObjectiveUpdate,
    ) -> PerformanceObjective:
        objective = await self._get_objective(objective_id)
        cycle = await self._get_cycle(objective.cycle_id)
        # Requirement: HR-PERF-009 — 已关闭的周期不接受目标与关键结果写入。
        self._ensure_cycle_writable(cycle)
        await self._lock_cycle(objective.cycle_id)

        changes = payload.model_dump(exclude_unset=True)
        before = self._objective_payload(objective)

        if "status" in changes:
            normalized = str(changes["status"]).strip().lower()
            if normalized not in OKR_STATUSES:
                raise ApiError(
                    status_code=422,
                    code="PERFORMANCE_OBJECTIVE_STATUS_INVALID",
                    message="目标状态仅支持 draft、submitted、approved、archived",
                )
            changes["status"] = normalized

        # Requirement: HR-PERF-013 — 权重或状态变更后必须重新校验周期内同一人权重之和。
        if "weight" in changes:
            changes["weight"] = self._ensure_weight(
                changes["weight"], "PERFORMANCE_OBJECTIVE_WEIGHT_INVALID"
            )
        candidate_status = changes.get("status", objective.status)
        candidate_weight = changes.get("weight", objective.weight)
        recheck = "weight" in changes or "status" in changes
        if recheck and candidate_status != OKR_STATUS_ARCHIVED:
            current_total = await self._objective_weight_sum(
                objective.cycle_id,
                objective.person_id,
                exclude_objective_id=objective.id,
            )
            await self._ensure_objective_total(current_total, candidate_weight)

        for field, value in changes.items():
            if field == "title":
                setattr(objective, field, str(value).strip())
            else:
                setattr(objective, field, value)
        await self._session.flush()
        await self._session.refresh(objective)
        await self._audit(
            action="performance.objective.update",
            object_type="performance_objective",
            object_id=objective.id,
            reason="修改绩效目标",
            before=before,
            after=self._objective_payload(objective),
        )
        return objective

    # ------------------------------------------------------------------
    # key results
    # ------------------------------------------------------------------
    async def create_key_result(
        self,
        objective_id: UUID,
        payload: PerformanceKeyResultCreate,
    ) -> PerformanceKeyResult:
        objective = await self._get_objective(objective_id)
        cycle = await self._get_cycle(objective.cycle_id)
        # Requirement: HR-PERF-009 — 已关闭的周期不接受目标与关键结果写入。
        self._ensure_cycle_writable(cycle)
        await self._lock_cycle(objective.cycle_id)

        # Requirement: HR-PERF-004 — 关键结果权重必须落在 (0, 100]。
        weight = self._ensure_weight(
            payload.weight, "PERFORMANCE_KEY_RESULT_WEIGHT_INVALID"
        )
        # Requirement: HR-PERF-006 — 同一目标下关键结果权重之和不得超过 100。
        current_total = await self._key_result_weight_sum(objective_id)
        await self._ensure_key_result_total(current_total, weight)

        sequence_no = await self._next_key_result_sequence(objective_id)
        key_result = PerformanceKeyResult(
            objective_id=objective_id,
            title=payload.title.strip(),
            description=payload.description,
            target_value=payload.target_value,
            actual_value=None,
            unit=payload.unit,
            weight=weight,
            score=None,
            status=OKR_STATUS_DRAFT,
            sequence_no=sequence_no,
        )
        async with self._session.begin_nested():
            self._session.add(key_result)
            await self._session.flush()

        # Requirement: HR-PERF-015 — 回读数据库表示，保证响应中的数值精度与落库一致。
        await self._session.refresh(key_result)
        await self._audit(
            action="performance.key_result.create",
            object_type="performance_key_result",
            object_id=key_result.id,
            reason="创建绩效关键结果",
            before={},
            after=self._key_result_payload(key_result),
        )
        return key_result

    async def update_key_result(
        self,
        key_result_id: UUID,
        payload: PerformanceKeyResultUpdate,
    ) -> PerformanceKeyResult:
        key_result = await self._get_key_result(key_result_id)
        objective = await self._get_objective(key_result.objective_id)
        cycle = await self._get_cycle(objective.cycle_id)
        # Requirement: HR-PERF-009 — 已关闭的周期不接受目标与关键结果写入。
        self._ensure_cycle_writable(cycle)
        await self._lock_cycle(objective.cycle_id)

        changes = payload.model_dump(exclude_unset=True)
        before = self._key_result_payload(key_result)

        if "status" in changes:
            normalized = str(changes["status"]).strip().lower()
            if normalized not in OKR_STATUSES:
                raise ApiError(
                    status_code=422,
                    code="PERFORMANCE_KEY_RESULT_STATUS_INVALID",
                    message="关键结果状态仅支持 draft、submitted、approved、archived",
                )
            changes["status"] = normalized

        # Requirement: HR-PERF-007 — 写入得分时必须落在 0 到 100 之间。
        if "score" in changes:
            changes["score"] = self._ensure_score(changes["score"])

        # Requirement: HR-PERF-006 — 权重或状态变更后必须重新校验目标下权重之和。
        if "weight" in changes:
            changes["weight"] = self._ensure_weight(
                changes["weight"], "PERFORMANCE_KEY_RESULT_WEIGHT_INVALID"
            )
        candidate_status = changes.get("status", key_result.status)
        candidate_weight = changes.get("weight", key_result.weight)
        recheck = "weight" in changes or "status" in changes
        if recheck and candidate_status != OKR_STATUS_ARCHIVED:
            current_total = await self._key_result_weight_sum(
                objective.id,
                exclude_key_result_id=key_result.id,
            )
            await self._ensure_key_result_total(current_total, candidate_weight)

        for field, value in changes.items():
            if field == "title":
                setattr(key_result, field, str(value).strip())
            else:
                setattr(key_result, field, value)
        await self._session.flush()
        await self._session.refresh(key_result)
        await self._audit(
            action="performance.key_result.update",
            object_type="performance_key_result",
            object_id=key_result.id,
            reason="修改绩效关键结果",
            before=before,
            after=self._key_result_payload(key_result),
        )
        return key_result

    async def delete_key_result(self, key_result_id: UUID) -> None:
        key_result = await self._get_key_result(key_result_id)
        objective = await self._get_objective(key_result.objective_id)
        cycle = await self._get_cycle(objective.cycle_id)
        # Requirement: HR-PERF-009 — 已关闭的周期不接受目标与关键结果写入。
        self._ensure_cycle_writable(cycle)
        await self._lock_cycle(objective.cycle_id)

        before = self._key_result_payload(key_result)
        await self._session.delete(key_result)
        await self._session.flush()
        await self._audit(
            action="performance.key_result.delete",
            object_type="performance_key_result",
            object_id=key_result_id,
            reason="删除绩效关键结果",
            before=before,
            after={},
        )

    # ------------------------------------------------------------------
    # scorecard
    # ------------------------------------------------------------------
    async def build_scorecard(self, cycle_id: UUID) -> PerformanceScorecardResponse:
        cycle = await self._get_cycle(cycle_id)
        objectives = list(
            (
                await self._session.scalars(
                    select(PerformanceObjective)
                    .where(
                        PerformanceObjective.cycle_id == cycle_id,
                        PerformanceObjective.status != OKR_STATUS_ARCHIVED,
                    )
                    .order_by(
                        PerformanceObjective.person_id,
                        PerformanceObjective.sequence_no,
                        PerformanceObjective.id,
                    )
                )
            ).all()
        )
        key_results_by_objective = await self._load_key_results(
            [objective.id for objective in objectives],
            include_archived=False,
        )

        entries: list[PerformanceScorecardEntry] = []
        for person_id, person_objectives in groupby(
            objectives, key=lambda objective: objective.person_id
        ):
            objective_rows = list(person_objectives)
            objective_total_weight = sum(
                (objective.weight for objective in objective_rows), _ZERO
            )
            key_result_count = 0
            key_result_total_weight = _ZERO
            scored_key_result_count = 0
            weighted_numerator = _ZERO
            has_score = False
            objective_scores: list[PerformanceObjectiveScoreResponse] = []

            for objective in objective_rows:
                key_results = key_results_by_objective.get(objective.id, [])
                objective_key_result_weight = sum(
                    (key_result.weight for key_result in key_results), _ZERO
                )
                scored = [
                    key_result for key_result in key_results if key_result.score is not None
                ]
                objective_score: Decimal | None = None
                if scored and objective_key_result_weight > _ZERO:
                    raw_score = sum(
                        (
                            key_result.score * key_result.weight
                            for key_result in scored
                            if key_result.score is not None
                        ),
                        _ZERO,
                    ) / objective_key_result_weight
                    objective_score = raw_score.quantize(
                        _SCORE_QUANTUM, rounding=ROUND_HALF_UP
                    )
                    weighted_numerator += objective.weight * raw_score
                    has_score = True
                key_result_count += len(key_results)
                key_result_total_weight += objective_key_result_weight
                scored_key_result_count += len(scored)
                objective_scores.append(
                    PerformanceObjectiveScoreResponse(
                        objective_id=objective.id,
                        title=objective.title,
                        weight=objective.weight,
                        key_result_count=len(key_results),
                        key_result_total_weight=objective_key_result_weight,
                        scored_key_result_count=len(scored),
                        objective_score=objective_score,
                    )
                )

            # Requirement: HR-PERF-012 — 全部未评分时加权得分为 null，不得用 0 顶替。
            weighted_score: Decimal | None = None
            if has_score and objective_total_weight > _ZERO:
                weighted_score = (weighted_numerator / objective_total_weight).quantize(
                    _SCORE_QUANTUM, rounding=ROUND_HALF_UP
                )
            entries.append(
                PerformanceScorecardEntry(
                    person_id=person_id,
                    objective_count=len(objective_rows),
                    objective_total_weight=objective_total_weight,
                    key_result_count=key_result_count,
                    key_result_total_weight=key_result_total_weight,
                    scored_key_result_count=scored_key_result_count,
                    weighted_score=weighted_score,
                    objectives=objective_scores,
                )
            )

        return PerformanceScorecardResponse(
            cycle_id=cycle.id,
            cycle_code=cycle.code,
            cycle_status=cycle.status,
            entries=entries,
            total=len(entries),
        )

    async def build_objective_response(
        self,
        objective: PerformanceObjective,
    ) -> PerformanceObjectiveResponse:
        """Return an objective with its key results attached."""
        key_results_by_objective = await self._load_key_results([objective.id])
        return self._objective_response(objective, key_results_by_objective)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    async def _get_cycle(self, cycle_id: UUID) -> PerformanceCycle:
        cycle = await self._session.get(PerformanceCycle, cycle_id)
        if cycle is None:
            raise ApiError(
                status_code=404,
                code="PERFORMANCE_CYCLE_NOT_FOUND",
                message="绩效周期不存在",
            )
        return cycle

    async def _get_objective(self, objective_id: UUID) -> PerformanceObjective:
        objective = await self._session.get(PerformanceObjective, objective_id)
        if objective is None:
            raise ApiError(
                status_code=404,
                code="PERFORMANCE_OBJECTIVE_NOT_FOUND",
                message="绩效目标不存在",
            )
        return objective

    async def _get_key_result(self, key_result_id: UUID) -> PerformanceKeyResult:
        key_result = await self._session.get(PerformanceKeyResult, key_result_id)
        if key_result is None:
            raise ApiError(
                status_code=404,
                code="PERFORMANCE_KEY_RESULT_NOT_FOUND",
                message="绩效关键结果不存在",
            )
        return key_result

    async def _lock_cycle(self, cycle_id: UUID) -> None:
        """Serialize concurrent weight updates inside the same cycle."""
        await self._session.scalar(
            select(PerformanceCycle)
            .where(PerformanceCycle.id == cycle_id)
            .with_for_update()
        )

    @staticmethod
    def _ensure_cycle_writable(cycle: PerformanceCycle) -> None:
        # Requirement: HR-PERF-009 — 已关闭的周期不接受目标与关键结果写入。
        if cycle.status == CYCLE_STATUS_CLOSED:
            raise ApiError(
                status_code=409,
                code="PERFORMANCE_CYCLE_CLOSED",
                message="绩效周期已关闭，不可维护目标与关键结果",
            )

    @staticmethod
    def _ensure_weight(weight: Decimal, error_code: str) -> Decimal:
        # Requirement: HR-PERF-004 — 权重必须落在 (0, 100]。
        if weight <= _ZERO or weight > MAX_OKR_WEIGHT:
            raise ApiError(
                status_code=422,
                code=error_code,
                message="权重必须大于0且不超过100",
            )
        return weight

    @staticmethod
    def _ensure_score(score: Decimal | None) -> Decimal | None:
        # Requirement: HR-PERF-007 — 得分必须落在 0 到 100 之间，null 表示未评分。
        if score is None:
            return None
        if score < MIN_OKR_SCORE or score > MAX_OKR_SCORE:
            raise ApiError(
                status_code=422,
                code="PERFORMANCE_SCORE_OUT_OF_RANGE",
                message="关键结果得分必须介于0到100之间",
            )
        return score

    @staticmethod
    async def _ensure_objective_total(
        current_total: Decimal,
        candidate_weight: Decimal,
    ) -> None:
        # Requirement: HR-PERF-005 — 同一周期同一人的目标权重之和不得超过 100。
        attempted = current_total + candidate_weight
        if attempted > MAX_OKR_WEIGHT:
            raise ApiError(
                status_code=422,
                code="PERFORMANCE_OBJECTIVE_WEIGHT_EXCEEDED",
                message="同一周期内同一人的目标权重之和不得超过100",
                details=[
                    {
                        "field": "weight",
                        "current_total": str(current_total),
                        "attempted_total": str(attempted),
                        "limit": str(MAX_OKR_WEIGHT),
                    }
                ],
            )

    @staticmethod
    async def _ensure_key_result_total(
        current_total: Decimal,
        candidate_weight: Decimal,
    ) -> None:
        # Requirement: HR-PERF-006 — 同一目标下关键结果权重之和不得超过 100。
        attempted = current_total + candidate_weight
        if attempted > MAX_OKR_WEIGHT:
            raise ApiError(
                status_code=422,
                code="PERFORMANCE_KEY_RESULT_WEIGHT_EXCEEDED",
                message="同一目标下关键结果权重之和不得超过100",
                details=[
                    {
                        "field": "weight",
                        "current_total": str(current_total),
                        "attempted_total": str(attempted),
                        "limit": str(MAX_OKR_WEIGHT),
                    }
                ],
            )

    async def _objective_weight_sum(
        self,
        cycle_id: UUID,
        person_id: UUID,
        *,
        exclude_objective_id: UUID | None = None,
    ) -> Decimal:
        filters = [
            PerformanceObjective.cycle_id == cycle_id,
            PerformanceObjective.person_id == person_id,
            PerformanceObjective.status != OKR_STATUS_ARCHIVED,
        ]
        if exclude_objective_id is not None:
            filters.append(PerformanceObjective.id != exclude_objective_id)
        total = await self._session.scalar(
            select(func.coalesce(func.sum(PerformanceObjective.weight), 0)).where(
                *filters
            )
        )
        return Decimal(str(total or 0))

    async def _key_result_weight_sum(
        self,
        objective_id: UUID,
        *,
        exclude_key_result_id: UUID | None = None,
    ) -> Decimal:
        filters = [
            PerformanceKeyResult.objective_id == objective_id,
            PerformanceKeyResult.status != OKR_STATUS_ARCHIVED,
        ]
        if exclude_key_result_id is not None:
            filters.append(PerformanceKeyResult.id != exclude_key_result_id)
        total = await self._session.scalar(
            select(func.coalesce(func.sum(PerformanceKeyResult.weight), 0)).where(
                *filters
            )
        )
        return Decimal(str(total or 0))

    async def _next_objective_sequence(self, cycle_id: UUID, person_id: UUID) -> int:
        count = await self._session.scalar(
            select(func.count())
            .select_from(PerformanceObjective)
            .where(
                PerformanceObjective.cycle_id == cycle_id,
                PerformanceObjective.person_id == person_id,
            )
        )
        return int(count or 0) + 1

    async def _next_key_result_sequence(self, objective_id: UUID) -> int:
        count = await self._session.scalar(
            select(func.count())
            .select_from(PerformanceKeyResult)
            .where(PerformanceKeyResult.objective_id == objective_id)
        )
        return int(count or 0) + 1

    async def _load_key_results(
        self,
        objective_ids: list[UUID],
        *,
        include_archived: bool = True,
    ) -> dict[UUID, list[PerformanceKeyResult]]:
        if not objective_ids:
            return {}
        filters = [PerformanceKeyResult.objective_id.in_(objective_ids)]
        if not include_archived:
            filters.append(PerformanceKeyResult.status != OKR_STATUS_ARCHIVED)
        rows = list(
            (
                await self._session.scalars(
                    select(PerformanceKeyResult)
                    .where(*filters)
                    .order_by(
                        PerformanceKeyResult.objective_id,
                        PerformanceKeyResult.sequence_no,
                        PerformanceKeyResult.id,
                    )
                )
            ).all()
        )
        grouped: dict[UUID, list[PerformanceKeyResult]] = defaultdict(list)
        for row in rows:
            grouped[row.objective_id].append(row)
        return grouped

    def _objective_response(
        self,
        objective: PerformanceObjective,
        key_results_by_objective: dict[UUID, list[PerformanceKeyResult]],
    ) -> PerformanceObjectiveResponse:
        key_results = key_results_by_objective.get(objective.id, [])
        return PerformanceObjectiveResponse(
            id=objective.id,
            cycle_id=objective.cycle_id,
            person_id=objective.person_id,
            title=objective.title,
            description=objective.description,
            weight=objective.weight,
            status=objective.status,
            sequence_no=objective.sequence_no,
            key_results=[
                PerformanceKeyResultResponse.model_validate(key_result)
                for key_result in key_results
            ],
            created_at=objective.created_at,
            updated_at=objective.updated_at,
        )

    def _build_person_groups(
        self,
        responses: list[PerformanceObjectiveResponse],
    ) -> list[PerformanceObjectiveGroupResponse]:
        groups: list[PerformanceObjectiveGroupResponse] = []
        for person_id, person_objectives in groupby(
            responses, key=lambda response: response.person_id
        ):
            rows = list(person_objectives)
            key_result_count = sum(len(row.key_results) for row in rows)
            key_result_total_weight = sum(
                (
                    key_result.weight
                    for row in rows
                    for key_result in row.key_results
                ),
                _ZERO,
            )
            groups.append(
                PerformanceObjectiveGroupResponse(
                    person_id=person_id,
                    objective_count=len(rows),
                    objective_total_weight=sum(
                        (row.weight for row in rows), _ZERO
                    ),
                    key_result_count=key_result_count,
                    key_result_total_weight=key_result_total_weight,
                    objectives=rows,
                )
            )
        return groups

    async def _audit(
        self,
        *,
        action: str,
        object_type: str,
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
                object_type=object_type,
                object_id=object_id,
                reason=reason,
                before_payload=before,
                after_payload=after,
                source="api",
            )
        )
        await self._session.flush()

    @staticmethod
    def _cycle_payload(cycle: PerformanceCycle) -> dict[str, Any]:
        # Requirement: HR-PERF-011 — 审计只记录业务标识与状态，不写入任何员工姓名。
        return {
            "code": cycle.code,
            "name": cycle.name,
            "cycle_type": cycle.cycle_type,
            "start_date": cycle.start_date.isoformat(),
            "end_date": cycle.end_date.isoformat(),
            "status": cycle.status,
        }

    @staticmethod
    def _objective_payload(objective: PerformanceObjective) -> dict[str, Any]:
        # Requirement: HR-PERF-011 — 审计只记录业务标识与状态，不写入任何员工姓名。
        return {
            "cycle_id": str(objective.cycle_id),
            "person_id": str(objective.person_id),
            "title": objective.title,
            "weight": _decimal_text(objective.weight),
            "status": objective.status,
            "sequence_no": objective.sequence_no,
        }

    @staticmethod
    def _key_result_payload(key_result: PerformanceKeyResult) -> dict[str, Any]:
        # Requirement: HR-PERF-011 — 审计只记录业务标识与状态，不写入任何员工姓名。
        return {
            "objective_id": str(key_result.objective_id),
            "title": key_result.title,
            "target_value": _decimal_text(key_result.target_value),
            "actual_value": _decimal_text(key_result.actual_value),
            "unit": key_result.unit,
            "weight": _decimal_text(key_result.weight),
            "score": _decimal_text(key_result.score),
            "status": key_result.status,
            "sequence_no": key_result.sequence_no,
        }
