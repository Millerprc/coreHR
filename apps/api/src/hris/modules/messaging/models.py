# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""Messaging kernel tables: inbox messages and the transactional delivery outbox.

Requirement: D-100 — 消息引擎是平台内核级基础服务，数据模型独立于任何业务域。
``messages`` 是收件人的站内信本体；``message_deliveries`` 是投递侧发件箱，
与业务写入同事务落库，保证「业务提交成功 ⇒ 消息必达」。
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from hris.shared.db.base import Base, UuidPrimaryKeyMixin


class Message(UuidPrimaryKeyMixin, Base):
    """站内信本体。一条记录只属于一个收件人。"""

    __tablename__ = "messages"
    __table_args__ = (
        # 幂等键与收件人组合唯一：同一业务事件对同一收件人重复投递不会产生第二条消息。
        UniqueConstraint("idempotency_key", "recipient_user_id"),
        # 收件箱列表、未读统计与 SSE 增量扫描都按「收件人 + 创建时间」走这条索引。
        Index("ix_messages_recipient_created", "recipient_user_id", "created_at"),
        # 未读徽标只关心未读行，用部分索引避免随消息总量线性变慢。
        Index(
            "ix_messages_unread",
            "recipient_user_id",
            postgresql_where=text("read_at IS NULL"),
        ),
    )

    recipient_user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("user_accounts.id"),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    source: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_ref_id: Mapped[UUID | None] = mapped_column(Uuid)
    idempotency_key: Mapped[UUID | None] = mapped_column(Uuid)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class MessageDelivery(UuidPrimaryKeyMixin, Base):
    """投递侧发件箱。一条消息在每个通道上各有一行投递记录。"""

    __tablename__ = "message_deliveries"
    __table_args__ = (
        # 同一消息在同一通道上只有一条投递记录，重复入队不会产生重复投递。
        UniqueConstraint("message_id", "channel"),
        # Worker 的领取条件是「待投递且到期」，这条复合索引直接服务该查询。
        Index("ix_message_deliveries_dispatch", "status", "next_attempt_at"),
    )

    message_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("messages.id"),
        nullable=False,
    )
    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(500))
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
