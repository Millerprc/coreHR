# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""Delivery channel ports.

Requirement: D-100 — 业务域只调用消息引擎接口，不直接调用任何通道；
通道端口保持稳定，新增通道不改动业务模块。
一期只实现站内信通道，短信与邮件注册为「未启用」占位实现，
返回不可重试的失败结果而不是抛异常（见 docs/review/message-engine-selection-2026-10-24.md §3.3）。
"""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from hris.modules.messaging.models import Message, MessageDelivery


class DeliveryChannel(str, Enum):
    """稳定通道编码。"""

    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"


class DeliveryStatus(str, Enum):
    """投递记录状态。"""

    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"


class DeliveryOutcomeStatus(str, Enum):
    """单次投递尝试的结果三态，决定后续是重试还是直接判失败。"""

    DELIVERED = "delivered"
    RETRYABLE = "retryable"
    PERMANENT = "permanent"


@dataclass(frozen=True)
class DeliveryOutcome:
    """通道投递结果。

    ``error_code`` 只允许写入受控的错误码，禁止写入原始异常文本，
    避免把收件人地址等个人信息落进 ``message_deliveries.last_error``。
    """

    status: DeliveryOutcomeStatus
    error_code: str | None = None


class Channel(Protocol):
    """通道端口。业务域不直接依赖本协议，只依赖消息引擎接口。"""

    code: str

    async def deliver(self, message: Message, delivery: MessageDelivery) -> DeliveryOutcome:
        """执行一次投递并返回三态结果。"""


class InAppChannel:
    """站内信通道。

    消息本体在 ``MessageService.publish`` 阶段已随业务事务写入，
    这里的投递动作只确认投递记录达成「已送达」状态。
    """

    code = DeliveryChannel.IN_APP.value

    async def deliver(self, message: Message, delivery: MessageDelivery) -> DeliveryOutcome:
        return DeliveryOutcome(status=DeliveryOutcomeStatus.DELIVERED)


class DisabledChannel:
    """一期未启用的通道占位实现（邮件 / 短信）。"""

    def __init__(self, code: str) -> None:
        self.code = code

    async def deliver(self, message: Message, delivery: MessageDelivery) -> DeliveryOutcome:
        return DeliveryOutcome(
            status=DeliveryOutcomeStatus.PERMANENT,
            error_code="channel_not_enabled",
        )


def build_channel_registry() -> dict[str, Channel]:
    """装配通道注册表。"""

    return {
        DeliveryChannel.IN_APP.value: InAppChannel(),
        DeliveryChannel.EMAIL.value: DisabledChannel(DeliveryChannel.EMAIL.value),
        DeliveryChannel.SMS.value: DisabledChannel(DeliveryChannel.SMS.value),
    }
