# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""Server-Sent Events push for the messaging kernel.

Requirement: D-100 — 实时推送用 SSE，服务端只推送**本人**的消息。
浏览器端用 ``fetch`` + ``ReadableStream`` 消费（``EventSource`` 无法带 Authorization 头）。
"""

import asyncio
import json
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from hris.modules.messaging.categories import message_category_label
from hris.modules.messaging.models import Message


DEFAULT_STREAM_TIMEOUT_SECONDS = 120.0
DEFAULT_POLL_INTERVAL_SECONDS = 1.0
DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 15.0
# 连接数上限按数据库连接池收敛：每条 SSE 连接在鉴权阶段占用一条会话连接。
MAX_TOTAL_CONNECTIONS = 20
MAX_CONNECTIONS_PER_USER = 3


class ConnectionRegistry:
    """进程内连接计数，用于限制并发连接数并保证连接释放。"""

    def __init__(
        self,
        *,
        max_total: int = MAX_TOTAL_CONNECTIONS,
        max_per_user: int = MAX_CONNECTIONS_PER_USER,
    ) -> None:
        self._max_total = max_total
        self._max_per_user = max_per_user
        self._total = 0
        self._by_user: dict[UUID, int] = {}

    def acquire(self, user_id: UUID) -> bool:
        """登记一个连接；超过上限时返回 False。"""

        current_user = self._by_user.get(user_id, 0)
        if self._total >= self._max_total or current_user >= self._max_per_user:
            return False
        self._total += 1
        self._by_user[user_id] = current_user + 1
        return True

    def release(self, user_id: UUID) -> None:
        """释放连接计数。"""

        current_user = self._by_user.get(user_id, 0)
        if current_user <= 1:
            self._by_user.pop(user_id, None)
        else:
            self._by_user[user_id] = current_user - 1
        self._total = max(self._total - 1, 0)

    @property
    def total(self) -> int:
        return self._total


connection_registry = ConnectionRegistry()


def sse_comment(text: str) -> bytes:
    """SSE 注释行，用作心跳。"""

    return f": {text}\n\n".encode("utf-8")


def sse_event(data: dict[str, Any], *, event: str = "message", event_id: str | None = None) -> bytes:
    """把一条事件序列化成 SSE 帧。"""

    lines: list[str] = []
    if event_id:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data, ensure_ascii=False)}")
    return ("\n".join(lines) + "\n\n").encode("utf-8")


def message_payload(message: Message) -> dict[str, Any]:
    """消息在推送与列表接口中共用的载荷形状。"""

    return {
        "id": str(message.id),
        "category": message.category,
        "category_label": message_category_label(message.category),
        "title": message.title,
        "body": message.body,
        "source": message.source,
        "source_ref_id": str(message.source_ref_id) if message.source_ref_id else None,
        "read_at": message.read_at.isoformat() if message.read_at else None,
        "created_at": message.created_at.isoformat(),
    }


async def _resolve_cursor(
    session: AsyncSession,
    user_id: UUID,
    last_event_id: str | None,
) -> tuple[datetime, UUID | None]:
    """确定增量扫描起点。

    带 ``Last-Event-ID`` 重连时从该条消息之后继续；否则从当前时刻开始。
    """

    if last_event_id:
        try:
            message_id = UUID(last_event_id)
        except ValueError:
            message_id = None
        if message_id is not None:
            message = await session.scalar(
                select(Message).where(
                    Message.id == message_id,
                    Message.recipient_user_id == user_id,
                )
            )
            if message is not None:
                return message.created_at, message.id
    # Requirement: D-100 — 游标用数据库时钟，避免应用与数据库之间的时钟偏差漏掉消息。
    database_now = await session.scalar(select(func.now()))
    return (database_now or datetime.now(UTC)), None


async def _fetch_new_messages(
    session: AsyncSession,
    user_id: UUID,
    cursor: tuple[datetime, UUID | None],
    *,
    limit: int = 50,
) -> list[Message]:
    """读取游标之后的新消息。"""

    created_at, message_id = cursor
    if message_id is None:
        statement = (
            select(Message)
            .where(
                Message.recipient_user_id == user_id,
                Message.created_at > created_at,
            )
            .order_by(Message.created_at, Message.id)
            .limit(limit)
        )
    else:
        statement = (
            select(Message)
            .where(
                Message.recipient_user_id == user_id,
                tuple_(Message.created_at, Message.id) > (created_at, message_id),
            )
            .order_by(Message.created_at, Message.id)
            .limit(limit)
        )
    return list((await session.scalars(statement)).all())


async def message_event_stream(
    *,
    user_id: UUID,
    session_factory: async_sessionmaker[AsyncSession],
    last_event_id: str | None = None,
    timeout_seconds: float = DEFAULT_STREAM_TIMEOUT_SECONDS,
    max_events: int = 0,
    poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
    heartbeat_interval: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
) -> AsyncIterator[bytes]:
    """产出属于 ``user_id`` 的消息事件流。

    每次轮询都开一条短事务的独立会话，避免长连接占住业务事务与连接池。
    """

    emitted = 0
    last_heartbeat = 0.0
    deadline = time.monotonic() + timeout_seconds
    async with session_factory() as session:
        cursor = await _resolve_cursor(session, user_id, last_event_id)
    while True:
        async with session_factory() as session:
            messages = await _fetch_new_messages(session, user_id, cursor)
        for message in messages:
            cursor = (message.created_at, message.id)
            yield sse_event(message_payload(message), event_id=str(message.id))
            emitted += 1
            if max_events and emitted >= max_events:
                return

        now = time.monotonic()
        if now >= deadline:
            yield sse_comment("stream timeout")
            return
        if now - last_heartbeat >= heartbeat_interval:
            last_heartbeat = now
            yield sse_comment("keep-alive")
        await asyncio.sleep(min(poll_interval, max(deadline - now, 0.0)))
