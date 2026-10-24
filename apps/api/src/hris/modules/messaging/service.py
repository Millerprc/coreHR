# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""Platform messaging service — the stable interface business modules publish through.

Requirement: D-100 — 消息引擎是平台内核级基础服务，业务模块只调用本模块的稳定接口。
关键性质：
1. 与业务**同事务**写入消息与投递记录，本模块不提交事务，随业务事务一起提交或回滚；
2. 支持 ``idempotency_key``，重复投递同一收件人不会产生第二条消息；
3. 收件人当前只接受显式用户 ID 列表，接口保留 ``recipient_selector`` 扩展位。
"""

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.errors import ApiError
from hris.modules.messaging.categories import MessageCategory
from hris.modules.messaging.channels import DeliveryChannel, DeliveryStatus
from hris.modules.messaging.models import Message, MessageDelivery


# Requirement: D-100 — 消息正文不得承载个人信息，证件号与手机号在入库前直接拒绝。
_CN_ID_NUMBER = re.compile(r"(?<![0-9A-Za-z])\d{17}[0-9Xx](?![0-9A-Za-z])")
_CN_MOBILE_NUMBER = re.compile(r"(?<![0-9])1[3-9]\d{9}(?![0-9])")

MAX_TITLE_LENGTH = 200
MAX_BODY_LENGTH = 5000
MAX_SOURCE_LENGTH = 100


@dataclass(frozen=True)
class RecipientSelector:
    """按角色 / 组织 / 人员广播的收件人选择器（扩展位）。

    Requirement: D-100 — 一期只支持显式用户 ID 列表；本结构先固定形状，
    将来由收件人解析服务把选择器展开成用户 ID 列表后再进入投递流程。
    """

    kind: str
    ref: str


@dataclass(frozen=True)
class MessageRequest:
    """一次投递请求。

    ``recipients`` 是收件人用户 ID 列表；``recipient_selector`` 是广播扩展位，
    一期传入会被明确拒绝而不是被静默忽略。
    """

    recipients: Sequence[UUID]
    category: MessageCategory | str
    title: str
    body: str
    source: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    source_ref_id: UUID | None = None
    idempotency_key: UUID | None = None
    channels: Sequence[DeliveryChannel] = (DeliveryChannel.IN_APP,)
    recipient_selector: RecipientSelector | None = None


@dataclass(frozen=True)
class PublishedMessage:
    """投递结果。``created`` 为 False 表示命中幂等键，未产生新消息。"""

    message_id: UUID
    recipient_user_id: UUID
    category: str
    created: bool
    delivery_ids: tuple[UUID, ...] = ()


class MessageService:
    """消息引擎的平台接口。"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def publish(self, request: MessageRequest) -> list[PublishedMessage]:
        """投递一条请求给全部收件人。

        本方法**不提交事务**：写入随调用方的事务一起提交，
        业务回滚时消息与投递记录一并回滚。
        """

        category = self._normalize_category(request.category)
        recipients = self._normalize_recipients(request)
        self._validate_content(request.title, request.body, request.source)
        self._validate_payload(request.payload)
        now = datetime.now(UTC)
        results: list[PublishedMessage] = []
        for recipient in recipients:
            results.append(
                await self._publish_one(
                    request=request,
                    recipient=recipient,
                    category=category,
                    now=now,
                )
            )
        await self._db.flush()
        return results

    async def publish_many(
        self,
        requests: Sequence[MessageRequest],
    ) -> list[PublishedMessage]:
        """批量投递。同一个事务内依次写入，任意一条失败整批回滚。"""

        results: list[PublishedMessage] = []
        for request in requests:
            results.extend(await self.publish(request))
        return results

    async def list_messages(
        self,
        user_id: UUID,
        *,
        limit: int = 20,
        offset: int = 0,
        unread_only: bool = False,
    ) -> tuple[list[Message], int]:
        """列出当前用户的收件箱消息（按创建时间倒序）。"""

        conditions = [Message.recipient_user_id == user_id]
        if unread_only:
            conditions.append(Message.read_at.is_(None))
        total = (
            await self._db.scalar(
                select(func.count()).select_from(Message).where(*conditions)
            )
        ) or 0
        rows = (
            await self._db.scalars(
                select(Message)
                .where(*conditions)
                .order_by(Message.created_at.desc(), Message.id.desc())
                .limit(limit)
                .offset(offset)
            )
        ).all()
        return list(rows), int(total)

    async def count_unread(self, user_id: UUID) -> int:
        """统计当前用户的未读消息数。"""

        total = (
            await self._db.scalar(
                select(func.count())
                .select_from(Message)
                .where(Message.recipient_user_id == user_id, Message.read_at.is_(None))
            )
        ) or 0
        return int(total)

    async def mark_read(self, user_id: UUID, message_id: UUID) -> Message:
        """把一条属于当前用户的消息标记为已读。"""

        message = await self._db.scalar(
            select(Message).where(
                Message.id == message_id,
                Message.recipient_user_id == user_id,
            )
        )
        if message is None:
            raise ApiError(
                status_code=404,
                code="MESSAGE_NOT_FOUND",
                message="消息不存在",
            )
        if message.read_at is None:
            message.read_at = datetime.now(UTC)
            await self._db.flush()
        return message

    async def _publish_one(
        self,
        *,
        request: MessageRequest,
        recipient: UUID,
        category: str,
        now: datetime,
    ) -> PublishedMessage:
        # Requirement: D-100 — 幂等由数据库唯一约束兜底，不用应用层先查后写，
        # 因此这里用 ON CONFLICT DO NOTHING 一次语句完成去重与写入。
        statement = (
            pg_insert(Message)
            .values(
                recipient_user_id=recipient,
                category=category,
                title=request.title,
                body=request.body,
                payload=dict(request.payload),
                source=request.source,
                source_ref_id=request.source_ref_id,
                idempotency_key=request.idempotency_key,
            )
            .on_conflict_do_nothing(
                index_elements=[Message.idempotency_key, Message.recipient_user_id]
            )
            .returning(Message.id)
        )
        message_id = (await self._db.execute(statement)).scalar_one_or_none()
        if message_id is None:
            existing_id = await self._db.scalar(
                select(Message.id).where(
                    Message.idempotency_key == request.idempotency_key,
                    Message.recipient_user_id == recipient,
                )
            )
            if existing_id is None:
                raise ApiError(
                    status_code=500,
                    code="MESSAGE_PUBLISH_FAILED",
                    message="消息写入失败",
                )
            return PublishedMessage(
                message_id=existing_id,
                recipient_user_id=recipient,
                category=category,
                created=False,
            )

        deliveries = [
            MessageDelivery(
                message_id=message_id,
                channel=channel.value,
                status=DeliveryStatus.PENDING.value,
                attempts=0,
                next_attempt_at=now,
            )
            for channel in request.channels
        ]
        self._db.add_all(deliveries)
        await self._db.flush()
        return PublishedMessage(
            message_id=message_id,
            recipient_user_id=recipient,
            category=category,
            created=True,
            delivery_ids=tuple(delivery.id for delivery in deliveries),
        )

    @staticmethod
    def _normalize_category(category: MessageCategory | str) -> str:
        try:
            return MessageCategory(category).value
        except ValueError as exc:
            raise ApiError(
                status_code=400,
                code="MESSAGE_CATEGORY_INVALID",
                message="消息分类不合法",
            ) from exc

    @staticmethod
    def _normalize_recipients(request: MessageRequest) -> list[UUID]:
        if request.recipient_selector is not None:
            # Requirement: D-100 — 一期只支持显式用户 ID 列表，广播选择器走扩展位，
            # 这里明确拒绝而不是静默忽略，避免业务方误以为已经广播。
            raise ApiError(
                status_code=400,
                code="MESSAGE_RECIPIENT_SELECTOR_UNSUPPORTED",
                message="一期仅支持按用户 ID 列表投递",
            )
        recipients = list(dict.fromkeys(request.recipients))
        if not recipients:
            raise ApiError(
                status_code=400,
                code="MESSAGE_RECIPIENTS_REQUIRED",
                message="至少需要一位收件人",
            )
        for recipient in recipients:
            if not isinstance(recipient, UUID):
                raise ApiError(
                    status_code=400,
                    code="MESSAGE_RECIPIENT_INVALID",
                    message="收件人必须是用户 ID",
                )
        return recipients

    @staticmethod
    def _validate_content(title: str, body: str, source: str) -> None:
        if not title.strip() or len(title) > MAX_TITLE_LENGTH:
            raise ApiError(
                status_code=400,
                code="MESSAGE_TITLE_INVALID",
                message="消息标题不合法",
            )
        if not body.strip() or len(body) > MAX_BODY_LENGTH:
            raise ApiError(
                status_code=400,
                code="MESSAGE_BODY_INVALID",
                message="消息正文不合法",
            )
        if not source.strip() or len(source) > MAX_SOURCE_LENGTH:
            raise ApiError(
                status_code=400,
                code="MESSAGE_SOURCE_INVALID",
                message="消息来源不合法",
            )
        for field_name, content in (("标题", title), ("正文", body)):
            if _CN_ID_NUMBER.search(content) or _CN_MOBILE_NUMBER.search(content):
                raise ApiError(
                    status_code=400,
                    code="MESSAGE_CONTENT_REJECTED",
                    message=f"消息{field_name}不得包含证件号或手机号",
                )

    @staticmethod
    def _validate_payload(payload: Mapping[str, Any]) -> None:
        try:
            json.dumps(dict(payload), ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise ApiError(
                status_code=400,
                code="MESSAGE_PAYLOAD_INVALID",
                message="消息上下文必须是可序列化的 JSON 对象",
            ) from exc
