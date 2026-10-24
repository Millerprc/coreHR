# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""发假明细服务：发假额度规则、发放批次、发放明细行与自动计提。

Requirement: D-107 —— 计提频率、工龄折算、封顶、清零、结转上限、有效期、离职处理
只建可配置字段容器，取值语义待企业输入（`docs/input-packs/07-attendance-rule-input.md`
§4.5）。规则取值缺失时计提必须**跳过并记录可读原因**，不得用默认值硬算。

Requirement: D-097 —— 单个发放批次最多 1000 条明细，超限整批拒绝。

发放落账口径：发放时写一条 `leave_balance_transactions` 流水（`grant` 或 `accrual`），
由 `ExtendedAttendanceService.apply_balance_delta` 保证 `balance_before/after` 恒等约束。
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import func, or_, select

from hris.core.errors import ApiError
from hris.modules.attendance.extended_service import ExtendedAttendanceService
from hris.modules.attendance.grant_schemas import (
    LeaveGrantBatchCreate,
    LeaveGrantRuleCreate,
    LeaveGrantRuleUpdate,
)
from hris.modules.attendance.models import (
    LeaveGrantBatch,
    LeaveGrantItem,
    LeaveGrantRule,
    LeaveType,
)
from hris.modules.platform.numbering import next_number
from hris.modules.workforce.models import Employment


@dataclass(frozen=True)
class AccrualSkip:
    """被跳过的计提规则与可读原因（不含任何个人身份信息）。"""

    rule_id: str
    code: str
    reason: str


@dataclass
class AccrualRunResult:
    batch_id: UUID | None = None
    batch_number: str | None = None
    created_items: int = 0
    skipped: list[AccrualSkip] = field(default_factory=list)


class LeaveGrantService(ExtendedAttendanceService):
    """发假明细服务。

    继承假勤扩展服务，复用余额流水的写入与审计能力。
    """

    # —— 发假额度规则 ——

    async def create_leave_grant_rule(
        self,
        payload: LeaveGrantRuleCreate,
    ) -> LeaveGrantRule:
        leave_type = await self._session.get(LeaveType, payload.leave_type_id)
        if leave_type is None:
            raise ApiError(
                status_code=404,
                code="LEAVE_TYPE_NOT_FOUND",
                message="假期类型不存在",
            )
        # 同一代码继续创建时生成新版本（发假额度规则按生效起止日期版本化）。
        latest_version = (
            await self._session.scalar(
                select(func.max(LeaveGrantRule.version)).where(
                    LeaveGrantRule.code == payload.code
                )
            )
            or 0
        )
        rule = LeaveGrantRule(
            **payload.model_dump(),
            version=latest_version + 1,
            status="draft",
        )
        self._session.add(rule)
        await self._session.flush()
        self._audit(
            action="attendance.leave_grant_rule.create",
            object_type="leave_grant_rule",
            object_id=rule.id,
            after={
                "code": rule.code,
                "version": rule.version,
                "leave_type_id": str(rule.leave_type_id),
                "status": rule.status,
            },
        )
        return rule

    async def list_leave_grant_rules(
        self,
        *,
        leave_type_id: UUID | None,
        rule_status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[LeaveGrantRule], int]:
        filters = []
        if leave_type_id is not None:
            filters.append(LeaveGrantRule.leave_type_id == leave_type_id)
        if rule_status is not None:
            filters.append(LeaveGrantRule.status == rule_status)
        total = await self._session.scalar(
            select(func.count()).select_from(LeaveGrantRule).where(*filters)
        )
        items = list(
            (
                await self._session.scalars(
                    select(LeaveGrantRule)
                    .where(*filters)
                    .order_by(LeaveGrantRule.code, LeaveGrantRule.version.desc())
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        return items, total or 0

    async def update_leave_grant_rule(
        self,
        rule_id: UUID,
        payload: LeaveGrantRuleUpdate,
    ) -> LeaveGrantRule:
        rule = await self._session.get(LeaveGrantRule, rule_id, with_for_update=True)
        if rule is None:
            raise ApiError(
                status_code=404,
                code="LEAVE_GRANT_RULE_NOT_FOUND",
                message="发假额度规则不存在",
            )
        if rule.status != "draft":
            raise ApiError(
                status_code=409,
                code="LEAVE_GRANT_RULE_NOT_DRAFT",
                message="只有草稿状态的发假额度规则可以修改",
            )
        changes = payload.model_dump(exclude_unset=True)
        before = {field: str(getattr(rule, field)) for field in changes}
        for field, value in changes.items():
            setattr(rule, field, value)
        await self._session.flush()
        await self._session.refresh(rule)
        self._audit(
            action="attendance.leave_grant_rule.update",
            object_type="leave_grant_rule",
            object_id=rule.id,
            before=before,
            after={field: str(value) for field, value in changes.items()},
        )
        return rule

    async def activate_leave_grant_rule(self, rule_id: UUID) -> LeaveGrantRule:
        rule = await self._session.get(LeaveGrantRule, rule_id, with_for_update=True)
        if rule is None:
            raise ApiError(
                status_code=404,
                code="LEAVE_GRANT_RULE_NOT_FOUND",
                message="发假额度规则不存在",
            )
        if rule.status == "active":
            return rule
        rule.status = "active"
        await self._session.flush()
        await self._session.refresh(rule)
        self._audit(
            action="attendance.leave_grant_rule.activate",
            object_type="leave_grant_rule",
            object_id=rule.id,
            after={"code": rule.code, "version": rule.version, "status": rule.status},
        )
        return rule

    # —— 发放批次 ——

    async def create_leave_grant_batch(
        self,
        payload: LeaveGrantBatchCreate,
    ) -> LeaveGrantBatch:
        number = await next_number(
            self._session,
            sequence_code="LEAVE_GRANT_BATCH_NUMBER",
            width=8,
            max_value=99_999_999,
            prefix="LG",
        )
        batch = LeaveGrantBatch(
            batch_number=number,
            period_code=payload.period_code,
            period_type=payload.period_type,
            grant_date=payload.grant_date,
            status="draft",
            source=payload.source,
            created_by=self._actor_id,
        )
        self._session.add(batch)
        await self._session.flush()
        for item in payload.items:
            if await self._session.get(Employment, item.employment_id) is None:
                raise ApiError(
                    status_code=404,
                    code="EMPLOYMENT_NOT_FOUND",
                    message="劳动关系不存在",
                )
            if await self._session.get(LeaveType, item.leave_type_id) is None:
                raise ApiError(
                    status_code=404,
                    code="LEAVE_TYPE_NOT_FOUND",
                    message="假期类型不存在",
                )
            idempotency_key = item.idempotency_key or uuid5(
                NAMESPACE_URL,
                (
                    f"corehr:leave-grant:item:{batch.id}:"
                    f"{item.employment_id}:{item.leave_type_id}"
                ),
            )
            existing = await self._session.scalar(
                select(LeaveGrantItem.id).where(
                    LeaveGrantItem.idempotency_key == idempotency_key
                )
            )
            if existing is not None:
                raise ApiError(
                    status_code=409,
                    code="LEAVE_GRANT_ITEM_IDEMPOTENCY_CONFLICT",
                    message="发假明细幂等键已被使用",
                )
            self._session.add(
                LeaveGrantItem(
                    batch_id=batch.id,
                    employment_id=item.employment_id,
                    leave_type_id=item.leave_type_id,
                    grant_days=Decimal(item.grant_days),
                    valid_from=item.valid_from,
                    valid_to=item.valid_to,
                    rule_id=item.rule_id,
                    source=payload.source,
                    status="pending",
                    idempotency_key=idempotency_key,
                )
            )
        await self._session.flush()
        self._audit(
            action="attendance.leave_grant_batch.create",
            object_type="leave_grant_batch",
            object_id=batch.id,
            after={
                "batch_number": batch.batch_number,
                "period_code": batch.period_code,
                "status": batch.status,
            },
        )
        return batch

    async def list_leave_grant_batches(
        self,
        *,
        batch_status: str | None,
        period_code: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[LeaveGrantBatch], int]:
        filters = []
        if batch_status is not None:
            filters.append(LeaveGrantBatch.status == batch_status)
        if period_code is not None:
            filters.append(LeaveGrantBatch.period_code == period_code)
        total = await self._session.scalar(
            select(func.count()).select_from(LeaveGrantBatch).where(*filters)
        )
        items = list(
            (
                await self._session.scalars(
                    select(LeaveGrantBatch)
                    .where(*filters)
                    .order_by(LeaveGrantBatch.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        return items, total or 0

    async def get_leave_grant_batch(self, batch_id: UUID) -> LeaveGrantBatch:
        batch = await self._session.get(LeaveGrantBatch, batch_id)
        if batch is None:
            raise ApiError(
                status_code=404,
                code="LEAVE_GRANT_BATCH_NOT_FOUND",
                message="发假发放批次不存在",
            )
        return batch

    async def list_leave_grant_items(self, batch_id: UUID) -> list[LeaveGrantItem]:
        await self.get_leave_grant_batch(batch_id)
        items = list(
            (
                await self._session.scalars(
                    select(LeaveGrantItem)
                    .where(LeaveGrantItem.batch_id == batch_id)
                    .order_by(LeaveGrantItem.created_at)
                )
            ).all()
        )
        return items

    async def issue_leave_grant_batch(self, batch_id: UUID) -> LeaveGrantBatch:
        """发放批次：写余额流水并把批次置为已发放。"""
        batch = await self._session.get(LeaveGrantBatch, batch_id, with_for_update=True)
        if batch is None:
            raise ApiError(
                status_code=404,
                code="LEAVE_GRANT_BATCH_NOT_FOUND",
                message="发假发放批次不存在",
            )
        if batch.status != "draft":
            raise ApiError(
                status_code=409,
                code="LEAVE_GRANT_BATCH_NOT_DRAFT",
                message="只有草稿状态的发假批次可以发放",
            )
        items = list(
            (
                await self._session.scalars(
                    select(LeaveGrantItem)
                    .where(LeaveGrantItem.batch_id == batch.id)
                    .order_by(LeaveGrantItem.created_at)
                )
            ).all()
        )
        if not items:
            raise ApiError(
                status_code=409,
                code="LEAVE_GRANT_BATCH_EMPTY",
                message="发假批次没有可发放的明细",
            )
        for item in items:
            if item.status == "issued":
                continue
            leave_type = await self._session.get(LeaveType, item.leave_type_id)
            if leave_type is None:
                raise ApiError(
                    status_code=404,
                    code="LEAVE_TYPE_NOT_FOUND",
                    message="假期类型不存在",
                )
            if self._leave_balance_mode(leave_type) == "none":
                raise ApiError(
                    status_code=409,
                    code="LEAVE_BALANCE_NOT_TRACKED",
                    message="假期类型未配置余额核算，无法发放",
                )
            transaction = await self.apply_balance_delta(
                employment_id=item.employment_id,
                leave_type=leave_type,
                period_year=batch.grant_date.year,
                transaction_type=(
                    "accrual" if item.source == "rule_accrual" else "grant"
                ),
                amount=Decimal(item.grant_days),
                effective_date=batch.grant_date,
                source_type="leave_grant_item",
                source_id=item.id,
                idempotency_key=item.idempotency_key,
                reason=f"发假批次 {batch.batch_number} 发放",
                enforce_nonnegative=False,
            )
            item.account_id = transaction.account_id
            item.transaction_id = transaction.id
            item.status = "issued"
        batch.status = "issued"
        batch.issued_at = datetime.now(UTC)
        batch.issued_by = self._actor_id
        await self._session.flush()
        for item in items:
            await self._session.refresh(item)
        await self._session.refresh(batch)
        self._audit(
            action="attendance.leave_grant_batch.issue",
            object_type="leave_grant_batch",
            object_id=batch.id,
            reason=f"发假批次 {batch.batch_number} 发放",
            after={
                "batch_number": batch.batch_number,
                "status": batch.status,
                "item_count": len(items),
            },
        )
        return batch

    async def void_leave_grant_batch(
        self,
        batch_id: UUID,
        reason: str,
    ) -> LeaveGrantBatch:
        batch = await self._session.get(LeaveGrantBatch, batch_id, with_for_update=True)
        if batch is None:
            raise ApiError(
                status_code=404,
                code="LEAVE_GRANT_BATCH_NOT_FOUND",
                message="发假发放批次不存在",
            )
        if batch.status == "issued":
            raise ApiError(
                status_code=409,
                code="LEAVE_GRANT_BATCH_ALREADY_ISSUED",
                message="已发放的批次不能作废，请用调整流水冲正",
            )
        batch.status = "void"
        batch.voided_at = datetime.now(UTC)
        batch.voided_by = self._actor_id
        batch.void_reason = reason
        await self._session.flush()
        await self._session.refresh(batch)
        self._audit(
            action="attendance.leave_grant_batch.void",
            object_type="leave_grant_batch",
            object_id=batch.id,
            reason=reason,
            after={"batch_number": batch.batch_number, "status": batch.status},
        )
        return batch

    # —— 自动计提 ——

    async def run_accrual(
        self,
        *,
        period_code: str,
        period_type: str,
        grant_date: date,
        auto_issue: bool = False,
    ) -> AccrualRunResult:
        """按发假额度规则生成计提批次。

        Requirement: D-107 —— 规则取值缺失时跳过该规则并记录可读原因，
        绝不按默认值折算。本轮只支持「按人平铺额度、无工龄折算」的规则。
        """
        result = AccrualRunResult()
        rules = list(
            (
                await self._session.scalars(
                    select(LeaveGrantRule)
                    .where(
                        LeaveGrantRule.status == "active",
                        LeaveGrantRule.accrual_frequency == period_code,
                        LeaveGrantRule.effective_from <= grant_date,
                        or_(
                            LeaveGrantRule.effective_to.is_(None),
                            LeaveGrantRule.effective_to >= grant_date,
                        ),
                    )
                    .order_by(LeaveGrantRule.code, LeaveGrantRule.version)
                    # 多实例安全：行级冲突时直接跳过，不互相等待。
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        if not rules:
            return result
        employments = list(
            (
                await self._session.scalars(
                    select(Employment)
                    .where(Employment.status == "active")
                    .order_by(Employment.id)
                )
            ).all()
        )
        for rule in rules:
            skip = self._accrual_rule_skip_reason(rule)
            if skip is not None:
                result.skipped.append(
                    AccrualSkip(rule_id=str(rule.id), code=skip[0], reason=skip[1])
                )
                continue
            amount = Decimal(rule.entitlement_days or 0)
            if rule.cap_days is not None:
                amount = min(amount, Decimal(rule.cap_days))
            eligible = self._eligible_employments(rule, employments, grant_date)
            if not eligible:
                result.skipped.append(
                    AccrualSkip(
                        rule_id=str(rule.id),
                        code="LEAVE_GRANT_NO_ELIGIBLE_EMPLOYMENT",
                        reason="没有符合规则范围的在职劳动关系，跳过计提",
                    )
                )
                continue
            planned: list[tuple[Employment, UUID]] = []
            duplicated = False
            for employment in eligible:
                key = uuid5(
                    NAMESPACE_URL,
                    f"corehr:leave-grant:accrual:{rule.id}:{period_code}:{employment.id}",
                )
                existing = await self._session.scalar(
                    select(LeaveGrantItem.id).where(
                        LeaveGrantItem.idempotency_key == key
                    )
                )
                if existing is not None:
                    duplicated = True
                    continue
                planned.append((employment, key))
            if not planned:
                result.skipped.append(
                    AccrualSkip(
                        rule_id=str(rule.id),
                        code="LEAVE_GRANT_ALREADY_ACCRUED",
                        reason="该期间的计提明细已存在，跳过重复计提",
                    )
                )
                continue
            batch = await self._create_accrual_batch(
                rule=rule,
                period_code=period_code,
                period_type=period_type,
                grant_date=grant_date,
                amount=amount,
                planned=planned,
            )
            result.batch_id = batch.id
            result.batch_number = batch.batch_number
            result.created_items += len(planned)
            if duplicated:
                result.skipped.append(
                    AccrualSkip(
                        rule_id=str(rule.id),
                        code="LEAVE_GRANT_PARTIALLY_ACCRUED",
                        reason="部分明细在既有批次中已计提，本次只补齐未计提部分",
                    )
                )
            if auto_issue:
                await self.issue_leave_grant_batch(batch.id)
        return result

    @staticmethod
    def _accrual_rule_skip_reason(rule: LeaveGrantRule) -> tuple[str, str] | None:
        """返回 (错误码, 可读原因)；返回 None 表示该规则可以计提。"""
        if rule.entitlement_days is None:
            return (
                "LEAVE_GRANT_ENTITLEMENT_UNSET",
                "发假额度规则的额度天数待企业输入，跳过计提",
            )
        if rule.proration_method not in (None, "", "none"):
            return (
                "LEAVE_GRANT_PRORATION_UNSUPPORTED",
                "工龄折算方式待企业输入，跳过计提",
            )
        if rule.seniority_min_years is not None or rule.seniority_max_years is not None:
            return (
                "LEAVE_GRANT_SENIORITY_UNSUPPORTED",
                "工龄折算维度待企业输入，跳过计提",
            )
        return None

    @staticmethod
    def _eligible_employments(
        rule: LeaveGrantRule,
        employments: list[Employment],
        grant_date: date,
    ) -> list[Employment]:
        """按规则容器里的适用范围筛选在职劳动关系。

        Requirement: D-107 —— 适用范围是规则容器字段；未配置时覆盖全部在职劳动关系。
        """
        allowed_types = rule.rules.get("employee_type_codes")
        result: list[Employment] = []
        for employment in employments:
            if allowed_types and employment.employee_type_code not in allowed_types:
                continue
            start_date = employment.actual_start_date or employment.planned_start_date
            if start_date > grant_date:
                continue
            result.append(employment)
        return result

    async def _create_accrual_batch(
        self,
        *,
        rule: LeaveGrantRule,
        period_code: str,
        period_type: str,
        grant_date: date,
        amount: Decimal,
        planned: list[tuple[Employment, UUID]],
    ) -> LeaveGrantBatch:
        number = await next_number(
            self._session,
            sequence_code="LEAVE_GRANT_BATCH_NUMBER",
            width=8,
            max_value=99_999_999,
            prefix="LG",
        )
        batch = LeaveGrantBatch(
            batch_number=number,
            period_code=period_code,
            period_type=period_type,
            grant_date=grant_date,
            status="draft",
            source="rule_accrual",
            created_by=self._actor_id,
        )
        self._session.add(batch)
        await self._session.flush()
        for employment, idempotency_key in planned:
            self._session.add(
                LeaveGrantItem(
                    batch_id=batch.id,
                    employment_id=employment.id,
                    leave_type_id=rule.leave_type_id,
                    grant_days=amount,
                    valid_from=rule.valid_from,
                    valid_to=rule.valid_to,
                    rule_id=rule.id,
                    source="rule_accrual",
                    status="pending",
                    idempotency_key=idempotency_key,
                )
            )
        await self._session.flush()
        self._audit(
            action="attendance.leave_grant_batch.accrue",
            object_type="leave_grant_batch",
            object_id=batch.id,
            reason=f"按发假额度规则 {rule.code} v{rule.version} 自动计提",
            after={
                "batch_number": batch.batch_number,
                "period_code": period_code,
                "item_count": len(planned),
                "rule_code": rule.code,
            },
        )
        return batch
