# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""Delivery dispatcher — claims pending outbox rows with PostgreSQL SKIP LOCKED.

Requirement: D-100 — 队列用 PostgreSQL ``FOR UPDATE SKIP LOCKED`` 实现，
Worker 是独立进程，多实例并行领取时不会重复消费同一条投递记录。
失败按指数退避重试，超过上限置为 ``failed`` 并记录**不含个人信息**的错误码。
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.redaction import sanitize_error_code as redact_error_code
from hris.modules.messaging.channels import (
    Channel,
    DeliveryOutcome,
    DeliveryOutcomeStatus,
    DeliveryStatus,
    build_channel_registry,
)
from hris.modules.messaging.models import Message, MessageDelivery


MAX_ATTEMPTS = 5
BASE_BACKOFF_SECONDS = 30
MAX_BACKOFF_SECONDS = 1800


@dataclass(frozen=True)
class DispatchReport:
    """单轮领取与投递的结果汇总。"""

    claimed: int
    delivered: int
    retried: int
    failed: int


def sanitize_error_code(value: str | None) -> str | None:
    """把错误信息收敛成不含个人信息的受控错误码。

    Requirement: D-110 — 收敛规则收敛到 ``hris.core.redaction`` 一处实现，
    消息投递与后台任务共用同一套规则，避免两条链路的错误码形状不一致。
    """

    return redact_error_code(value)


class MessageDispatcher:
    """领取并执行投递记录。"""

    def __init__(
        self,
        db: AsyncSession,
        *,
        channels: Mapping[str, Channel] | None = None,
        max_attempts: int = MAX_ATTEMPTS,
        base_backoff_seconds: int = BASE_BACKOFF_SECONDS,
        max_backoff_seconds: int = MAX_BACKOFF_SECONDS,
    ) -> None:
        self._db = db
        self._channels: Mapping[str, Channel] = (
            channels if channels is not None else build_channel_registry()
        )
        self._max_attempts = max_attempts
        self._base_backoff_seconds = base_backoff_seconds
        self._max_backoff_seconds = max_backoff_seconds

    async def dispatch_once(self, limit: int = 50) -> DispatchReport:
        """领取一批待投递记录并逐条投递。

        领取使用 ``FOR UPDATE SKIP LOCKED``：多个 Worker 实例并行执行时，
        同一批行只会被一个实例拿到，其余实例直接跳过。
        """

        now = datetime.now(UTC)
        rows = (
            await self._db.scalars(
                select(MessageDelivery)
                .where(
                    MessageDelivery.status == DeliveryStatus.PENDING.value,
                    MessageDelivery.next_attempt_at <= now,
                )
                .order_by(MessageDelivery.next_attempt_at, MessageDelivery.created_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).all()

        delivered = 0
        retried = 0
        failed = 0
        for delivery in rows:
            outcome = await self._deliver(delivery)
            if outcome.status == DeliveryOutcomeStatus.DELIVERED:
                delivery.status = DeliveryStatus.DELIVERED.value
                delivery.delivered_at = now
                delivery.last_error = None
                delivered += 1
            elif outcome.status == DeliveryOutcomeStatus.RETRYABLE:
                delivery.attempts += 1
                delivery.last_error = sanitize_error_code(outcome.error_code)
                if delivery.attempts >= self._max_attempts:
                    delivery.status = DeliveryStatus.FAILED.value
                    failed += 1
                else:
                    delivery.status = DeliveryStatus.PENDING.value
                    delivery.next_attempt_at = now + timedelta(
                        seconds=self._backoff_seconds(delivery.attempts)
                    )
                    retried += 1
            else:
                delivery.attempts += 1
                delivery.status = DeliveryStatus.FAILED.value
                delivery.last_error = sanitize_error_code(outcome.error_code)
                failed += 1

        if rows:
            await self._db.flush()
        return DispatchReport(
            claimed=len(rows),
            delivered=delivered,
            retried=retried,
            failed=failed,
        )

    def _backoff_seconds(self, attempts: int) -> int:
        return min(
            self._base_backoff_seconds * (2 ** max(attempts - 1, 0)),
            self._max_backoff_seconds,
        )

    async def _deliver(self, delivery: MessageDelivery) -> DeliveryOutcome:
        channel = self._channels.get(delivery.channel)
        if channel is None:
            return DeliveryOutcome(
                status=DeliveryOutcomeStatus.PERMANENT,
                error_code="channel_unknown",
            )
        message = await self._db.get(Message, delivery.message_id)
        if message is None:
            return DeliveryOutcome(
                status=DeliveryOutcomeStatus.PERMANENT,
                error_code="message_missing",
            )
        try:
            return await channel.deliver(message, delivery)
        except Exception as exc:  # noqa: BLE001 — 通道异常统一按可重试处理
            # Requirement: D-100 — 异常只保留异常类型名，不保留原始文本。
            return DeliveryOutcome(
                status=DeliveryOutcomeStatus.RETRYABLE,
                error_code=f"channel_exception:{type(exc).__name__}",
            )
