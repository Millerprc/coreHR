# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""Messaging API routes.

Requirement: D-100 — 消息引擎作为平台内核基础服务提供稳定接口，
所有接口只作用于**当前登录用户本人**的消息。
"""

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.database import get_db, session_factory
from hris.core.errors import ApiError
from hris.modules.messaging.categories import message_category_catalog
from hris.modules.messaging.models import Message
from hris.modules.messaging.schemas import (
    MessageCategoryResponse,
    MessageListResponse,
    MessageResponse,
    UnreadCountResponse,
)
from hris.modules.messaging.service import MessageService
from hris.modules.messaging.stream import (
    DEFAULT_STREAM_TIMEOUT_SECONDS,
    connection_registry,
    message_event_stream,
    message_payload,
)
from hris.modules.platform.dependencies import CurrentSession


router = APIRouter(prefix="/api/v1/messaging", tags=["messaging"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


def _to_response(message: Message) -> MessageResponse:
    payload = message_payload(message)
    return MessageResponse(
        id=UUID(payload["id"]),
        category=payload["category"],
        category_label=payload["category_label"],
        title=payload["title"],
        body=payload["body"],
        source=payload["source"],
        source_ref_id=(
            UUID(payload["source_ref_id"]) if payload["source_ref_id"] else None
        ),
        read_at=message.read_at,
        created_at=message.created_at,
    )


@router.get("/categories", response_model=list[MessageCategoryResponse])
async def list_message_categories() -> list[MessageCategoryResponse]:
    """返回消息分类编码与中文标签，供前端直接消费。"""

    return [
        MessageCategoryResponse(code=code, label=label)
        for code, label in message_category_catalog()
    ]


@router.get("/messages/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(db: DbSession, current: CurrentSession) -> UnreadCountResponse:
    """返回当前用户的未读消息数。"""

    user, _ = current
    count = await MessageService(db).count_unread(user.id)
    return UnreadCountResponse(unread_count=count)


@router.get("/messages", response_model=MessageListResponse)
async def list_messages(
    db: DbSession,
    current: CurrentSession,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    unread_only: bool = Query(default=False),
) -> MessageListResponse:
    """列出当前用户的收件箱消息。"""

    user, _ = current
    messages, total = await MessageService(db).list_messages(
        user.id,
        limit=limit,
        offset=offset,
        unread_only=unread_only,
    )
    return MessageListResponse(
        items=[_to_response(message) for message in messages],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/messages/{message_id}/read", response_model=MessageResponse)
async def mark_message_read(
    message_id: UUID,
    db: DbSession,
    current: CurrentSession,
) -> MessageResponse:
    """把一条属于当前用户的消息标记为已读。"""

    user, _ = current
    message = await MessageService(db).mark_read(user.id, message_id)
    return _to_response(message)


@router.get("/stream")
async def stream_messages(
    request: Request,
    current: CurrentSession,
    timeout: float = Query(default=DEFAULT_STREAM_TIMEOUT_SECONDS, ge=1, le=600),
    max_events: int = Query(default=0, ge=0, le=100),
    last_event_id: str | None = Query(default=None),
) -> StreamingResponse:
    """SSE 推送当前用户的新消息。

    Requirement: D-100 — 只推送本人消息；鉴权沿用现有 Bearer 会话机制。
    """

    user, _ = current
    if not connection_registry.acquire(user.id):
        raise ApiError(
            status_code=503,
            code="MESSAGE_STREAM_CAPACITY_EXCEEDED",
            message="实时消息连接数已达上限，请稍后重试",
        )
    resume_from = last_event_id or request.headers.get("last-event-id")

    async def guarded_stream() -> AsyncIterator[bytes]:
        try:
            async for chunk in message_event_stream(
                user_id=user.id,
                session_factory=session_factory,
                last_event_id=resume_from,
                timeout_seconds=timeout,
                max_events=max_events,
            ):
                yield chunk
        finally:
            connection_registry.release(user.id)

    try:
        return StreamingResponse(
            guarded_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception:
        connection_registry.release(user.id)
        raise
