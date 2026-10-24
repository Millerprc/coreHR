# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from hris.core.errors import ApiError
from hris.modules.messaging.categories import MessageCategory, message_category_catalog
from hris.modules.messaging.channels import (
    DeliveryChannel,
    DeliveryOutcome,
    DeliveryOutcomeStatus,
    DeliveryStatus,
)
from hris.modules.messaging.dispatcher import MessageDispatcher
from hris.modules.messaging.models import Message, MessageDelivery
from hris.modules.messaging.service import (
    MessageRequest,
    MessageService,
    RecipientSelector,
)
from hris.modules.platform.models import UserAccount, UserSession
from hris.modules.platform.security import hash_password, token_digest


pytestmark = pytest.mark.asyncio


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class _AlwaysFailingChannel:
    """始终返回可重试失败的通道，用于验证退避与上限。"""

    code = DeliveryChannel.IN_APP.value

    def __init__(self) -> None:
        self.calls = 0

    async def deliver(self, message: Message, delivery: MessageDelivery) -> DeliveryOutcome:
        self.calls += 1
        return DeliveryOutcome(
            status=DeliveryOutcomeStatus.RETRYABLE,
            error_code="channel_timeout",
        )


class _ExplodingChannel:
    """抛出含个人信息的异常，用于验证错误信息脱敏。"""

    code = DeliveryChannel.IN_APP.value

    async def deliver(self, message: Message, delivery: MessageDelivery) -> DeliveryOutcome:
        raise RuntimeError("推送失败 13800138000")


@pytest_asyncio.fixture
async def committed_session(test_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """真实提交的会话：跨连接可见，用于验证并发领取与 SSE 推送。"""

    session = AsyncSession(bind=test_engine, expire_on_commit=False)
    try:
        yield session
    finally:
        await session.close()


@pytest_asyncio.fixture
async def committed_users(
    committed_session: AsyncSession,
) -> AsyncIterator[tuple[tuple[UUID, str], tuple[UUID, str]]]:
    """创建两个真实提交的用户与访问令牌，测试结束后清理。"""

    now = datetime.now(UTC)
    created: list[tuple[UUID, str]] = []
    for index in range(2):
        token = f"synthetic-messaging-token-{uuid4()}"
        user = UserAccount(
            username=f"synthetic-messaging-{uuid4()}",
            display_name=f"合成消息用户{index}",
            password_hash=hash_password("synthetic-test-password"),
            status="active",
            failed_attempts=0,
        )
        committed_session.add(user)
        await committed_session.flush()
        committed_session.add(
            UserSession(
                user_id=user.id,
                token_hash=token_digest(token),
                expires_at=now + timedelta(hours=1),
                last_seen_at=now,
            )
        )
        created.append((user.id, token))
    await committed_session.commit()
    try:
        yield created[0], created[1]
    finally:
        for user_id, _ in created:
            await committed_session.execute(
                delete(MessageDelivery).where(
                    MessageDelivery.message_id.in_(
                        select(Message.id).where(Message.recipient_user_id == user_id)
                    )
                )
            )
            await committed_session.execute(
                delete(Message).where(Message.recipient_user_id == user_id)
            )
            await committed_session.execute(
                delete(UserSession).where(UserSession.user_id == user_id)
            )
            await committed_session.execute(
                delete(UserAccount).where(UserAccount.id == user_id)
            )
        await committed_session.commit()


async def _count_messages(session: AsyncSession, source: str) -> int:
    total = await session.scalar(
        select(func.count()).select_from(Message).where(Message.source == source)
    )
    return int(total or 0)


async def test_publish_writes_message_and_delivery_in_the_same_transaction(
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    """Requirement: D-100 — 消息与投递记录随业务事务一起落库。"""

    user = await db_session.scalar(
        select(UserAccount).where(UserAccount.username == "synthetic-admin")
    )
    assert user is not None

    service = MessageService(db_session)
    results = await service.publish(
        MessageRequest(
            recipients=[user.id],
            category=MessageCategory.APPROVAL,
            title="有一条审批待办",
            body="流程 FY2026-0001 等待您处理。",
            source="test.publish",
            payload={"workflow_id": "synthetic"},
        )
    )

    assert len(results) == 1
    assert results[0].created is True
    assert len(results[0].delivery_ids) == 1

    message = await db_session.scalar(
        select(Message).where(Message.id == results[0].message_id)
    )
    assert message is not None
    assert message.recipient_user_id == user.id
    assert message.category == MessageCategory.APPROVAL.value
    assert message.read_at is None
    assert message.payload == {"workflow_id": "synthetic"}

    delivery = await db_session.scalar(
        select(MessageDelivery).where(
            MessageDelivery.message_id == results[0].message_id
        )
    )
    assert delivery is not None
    assert delivery.channel == DeliveryChannel.IN_APP.value
    assert delivery.status == DeliveryStatus.PENDING.value
    assert delivery.attempts == 0


async def test_publish_is_rolled_back_with_the_business_transaction(
    db_session: AsyncSession,
    committed_session: AsyncSession,
    admin_token: str,
) -> None:
    """Requirement: D-100 — 业务回滚时消息与投递记录一并回滚。"""

    user = await db_session.scalar(
        select(UserAccount).where(UserAccount.username == "synthetic-admin")
    )
    assert user is not None

    await MessageService(db_session).publish(
        MessageRequest(
            recipients=[user.id],
            category=MessageCategory.SYSTEM,
            title="随业务回滚的消息",
            body="业务事务回滚后不应留下消息。",
            source="test.rollback",
        )
    )
    assert await _count_messages(committed_session, "test.rollback") == 0

    await db_session.rollback()

    assert await _count_messages(committed_session, "test.rollback") == 0
    delivery_total = await committed_session.scalar(
        select(func.count())
        .select_from(MessageDelivery)
        .where(
            MessageDelivery.message_id.in_(
                select(Message.id).where(Message.source == "test.rollback")
            )
        )
    )
    assert int(delivery_total or 0) == 0


async def test_publish_is_committed_together_with_the_delivery_record(
    committed_session: AsyncSession,
    test_engine: AsyncEngine,
    committed_users: tuple[tuple[UUID, str], tuple[UUID, str]],
) -> None:
    """Requirement: D-100 — 业务提交后，消息与投递记录在同一条事务里一起落库。"""

    (user_id, _), _ = committed_users
    results = await MessageService(committed_session).publish(
        MessageRequest(
            recipients=[user_id],
            category=MessageCategory.TASK,
            title="提交后可见的消息",
            body="消息与投递记录应当同时可见。",
            source="test.commit",
        )
    )
    await committed_session.commit()

    reader_session = AsyncSession(bind=test_engine, expire_on_commit=False)
    try:
        message = await reader_session.scalar(
            select(Message).where(Message.id == results[0].message_id)
        )
        delivery = await reader_session.scalar(
            select(MessageDelivery).where(
                MessageDelivery.message_id == results[0].message_id
            )
        )
    finally:
        await reader_session.close()

    assert message is not None
    assert message.recipient_user_id == user_id
    assert delivery is not None
    assert delivery.channel == DeliveryChannel.IN_APP.value
    assert delivery.status == DeliveryStatus.PENDING.value


async def test_idempotency_key_does_not_create_duplicate_messages(
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    """Requirement: D-100 — 同一幂等键重复投递不产生第二条消息。"""

    user = await db_session.scalar(
        select(UserAccount).where(UserAccount.username == "synthetic-admin")
    )
    assert user is not None
    idempotency_key = uuid4()
    service = MessageService(db_session)
    request = MessageRequest(
        recipients=[user.id],
        category=MessageCategory.WORKFLOW,
        title="流程已通过",
        body="您的申请已通过审批。",
        source="test.idempotency",
        idempotency_key=idempotency_key,
    )

    first = await service.publish(request)
    second = await service.publish(request)

    assert first[0].created is True
    assert second[0].created is False
    assert first[0].message_id == second[0].message_id
    assert await _count_messages(db_session, "test.idempotency") == 1
    delivery_total = await db_session.scalar(
        select(func.count())
        .select_from(MessageDelivery)
        .where(
            MessageDelivery.message_id.in_(
                select(Message.id).where(Message.source == "test.idempotency")
            )
        )
    )
    assert int(delivery_total or 0) == 1


async def test_publish_rejects_personal_information_in_content(
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    """Requirement: D-100 — 消息正文不得承载证件号或手机号。"""

    user = await db_session.scalar(
        select(UserAccount).where(UserAccount.username == "synthetic-admin")
    )
    assert user is not None
    service = MessageService(db_session)

    with pytest.raises(ApiError) as mobile_error:
        await service.publish(
            MessageRequest(
                recipients=[user.id],
                category=MessageCategory.SYSTEM,
                title="联系方式更新",
                body="您的手机号 13800138000 已变更。",
                source="test.pii",
            )
        )
    assert mobile_error.value.code == "MESSAGE_CONTENT_REJECTED"

    with pytest.raises(ApiError) as id_error:
        await service.publish(
            MessageRequest(
                recipients=[user.id],
                category=MessageCategory.SYSTEM,
                title="证件信息",
                body="证件号 11010119900307461X 已登记。",
                source="test.pii",
            )
        )
    assert id_error.value.code == "MESSAGE_CONTENT_REJECTED"
    assert await _count_messages(db_session, "test.pii") == 0


async def test_publish_rejects_broadcast_selector_in_phase_one(
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    """Requirement: D-100 — 一期只支持用户 ID 列表，广播选择器被明确拒绝。"""

    user = await db_session.scalar(
        select(UserAccount).where(UserAccount.username == "synthetic-admin")
    )
    assert user is not None

    with pytest.raises(ApiError) as error:
        await MessageService(db_session).publish(
            MessageRequest(
                recipients=[],
                category=MessageCategory.SYSTEM,
                title="广播消息",
                body="按角色广播。",
                source="test.selector",
                recipient_selector=RecipientSelector(kind="role", ref="HR_ADMIN"),
            )
        )
    assert error.value.code == "MESSAGE_RECIPIENT_SELECTOR_UNSUPPORTED"


async def test_dispatcher_marks_pending_delivery_as_delivered(
    committed_session: AsyncSession,
    committed_users: tuple[tuple[UUID, str], tuple[UUID, str]],
) -> None:
    """Requirement: D-100 — Worker 领取待投递记录后置为已送达。"""

    (user_id, _), _ = committed_users
    results = await MessageService(committed_session).publish(
        MessageRequest(
            recipients=[user_id],
            category=MessageCategory.TASK,
            title="待投递消息",
            body="等待 Worker 处理。",
            source="test.dispatch",
        )
    )
    await committed_session.commit()

    dispatcher = MessageDispatcher(committed_session)
    report = await dispatcher.dispatch_once(limit=10)
    await committed_session.commit()

    assert report.claimed == 1
    assert report.delivered == 1
    delivery = await committed_session.scalar(
        select(MessageDelivery).where(
            MessageDelivery.message_id == results[0].message_id
        )
    )
    assert delivery is not None
    assert delivery.status == DeliveryStatus.DELIVERED.value
    assert delivery.delivered_at is not None
    assert delivery.last_error is None


async def test_dispatcher_retries_with_backoff_then_fails_after_max_attempts(
    committed_session: AsyncSession,
    committed_users: tuple[tuple[UUID, str], tuple[UUID, str]],
) -> None:
    """Requirement: D-100 — 失败重试带退避，超过上限置为失败并记录脱敏错误码。"""

    (user_id, _), _ = committed_users
    results = await MessageService(committed_session).publish(
        MessageRequest(
            recipients=[user_id],
            category=MessageCategory.TASK,
            title="重试消息",
            body="通道持续失败。",
            source="test.retry",
        )
    )
    await committed_session.commit()

    channel = _AlwaysFailingChannel()
    dispatcher = MessageDispatcher(
        committed_session,
        channels={DeliveryChannel.IN_APP.value: channel},
        max_attempts=2,
        base_backoff_seconds=0,
    )

    first = await dispatcher.dispatch_once(limit=10)
    await committed_session.commit()
    assert first.claimed == 1
    assert first.retried == 1
    assert first.failed == 0

    delivery = await committed_session.scalar(
        select(MessageDelivery).where(
            MessageDelivery.message_id == results[0].message_id
        )
    )
    assert delivery is not None
    assert delivery.status == DeliveryStatus.PENDING.value
    assert delivery.attempts == 1
    assert delivery.last_error == "channel_timeout"

    second = await dispatcher.dispatch_once(limit=10)
    await committed_session.commit()
    assert second.failed == 1

    delivery = await committed_session.scalar(
        select(MessageDelivery).where(
            MessageDelivery.message_id == results[0].message_id
        )
    )
    assert delivery is not None
    assert delivery.status == DeliveryStatus.FAILED.value
    assert delivery.attempts == 2
    assert delivery.last_error == "channel_timeout"
    assert channel.calls == 2


async def test_dispatcher_error_message_never_contains_personal_information(
    committed_session: AsyncSession,
    committed_users: tuple[tuple[UUID, str], tuple[UUID, str]],
) -> None:
    """Requirement: D-100 — 投递失败只记录脱敏错误码，不落个人信息。"""

    (user_id, _), _ = committed_users
    results = await MessageService(committed_session).publish(
        MessageRequest(
            recipients=[user_id],
            category=MessageCategory.TASK,
            title="异常消息",
            body="通道抛异常。",
            source="test.sanitize",
        )
    )
    await committed_session.commit()

    dispatcher = MessageDispatcher(
        committed_session,
        channels={DeliveryChannel.IN_APP.value: _ExplodingChannel()},
        max_attempts=5,
        base_backoff_seconds=0,
    )
    await dispatcher.dispatch_once(limit=10)
    await committed_session.commit()

    delivery = await committed_session.scalar(
        select(MessageDelivery).where(
            MessageDelivery.message_id == results[0].message_id
        )
    )
    assert delivery is not None
    assert delivery.last_error == "channel_exception:runtimeerror"
    assert "13800138000" not in (delivery.last_error or "")


async def test_dispatcher_skips_rows_locked_by_another_worker(
    committed_session: AsyncSession,
    test_engine: AsyncEngine,
    committed_users: tuple[tuple[UUID, str], tuple[UUID, str]],
) -> None:
    """Requirement: D-100 — SKIP LOCKED 让多个 Worker 实例安全并行领取。"""

    (user_id, _), _ = committed_users
    await MessageService(committed_session).publish(
        MessageRequest(
            recipients=[user_id],
            category=MessageCategory.TASK,
            title="并发领取消息",
            body="验证 SKIP LOCKED。",
            source="test.skip_locked",
        )
    )
    await committed_session.commit()

    other_session = AsyncSession(bind=test_engine, expire_on_commit=False)
    try:
        first_worker = MessageDispatcher(committed_session)
        await first_worker.dispatch_once(limit=10)
        # 第一个 Worker 已锁住该行但尚未提交，第二个 Worker 必须跳过它。
        second_report = await MessageDispatcher(other_session).dispatch_once(limit=10)
        assert second_report.claimed == 0
        await committed_session.commit()
        await other_session.rollback()
    finally:
        await other_session.close()


async def test_disabled_channels_are_marked_failed_without_retry(
    committed_session: AsyncSession,
    committed_users: tuple[tuple[UUID, str], tuple[UUID, str]],
) -> None:
    """Requirement: D-100 — 一期未启用的通道返回不可重试失败，不抛异常。"""

    (user_id, _), _ = committed_users
    results = await MessageService(committed_session).publish(
        MessageRequest(
            recipients=[user_id],
            category=MessageCategory.SYSTEM,
            title="邮件通道未启用",
            body="一期不实现邮件投递。",
            source="test.disabled_channel",
            channels=[DeliveryChannel.EMAIL],
        )
    )
    await committed_session.commit()

    report = await MessageDispatcher(committed_session).dispatch_once(limit=10)
    await committed_session.commit()

    assert report.claimed == 1
    assert report.failed == 1
    delivery = await committed_session.scalar(
        select(MessageDelivery).where(
            MessageDelivery.message_id == results[0].message_id
        )
    )
    assert delivery is not None
    assert delivery.status == DeliveryStatus.FAILED.value
    assert delivery.last_error == "channel_not_enabled"


async def test_categories_endpoint_returns_backend_labels(
    business_client: AsyncClient,
) -> None:
    """Requirement: D-100 — 分类标签由后端单一来源提供。"""

    response = await business_client.get("/api/v1/messaging/categories")

    assert response.status_code == 200
    payload = response.json()
    assert payload == [
        {"code": code, "label": label} for code, label in message_category_catalog()
    ]
    assert {"code": "approval", "label": "审批待办"} in payload


async def test_unread_count_and_mark_read_only_touch_own_messages(
    business_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
    restricted_token: str,
) -> None:
    """Requirement: D-100 — 未读数与标记已读只作用于本人消息。"""

    user = await db_session.scalar(
        select(UserAccount).where(UserAccount.username == "synthetic-admin")
    )
    assert user is not None
    other_user = await db_session.scalar(
        select(UserAccount).where(UserAccount.username == "synthetic-viewer")
    )
    assert other_user is not None

    service = MessageService(db_session)
    mine = await service.publish(
        MessageRequest(
            recipients=[user.id],
            category=MessageCategory.APPROVAL,
            title="我的待办",
            body="等待处理。",
            source="test.inbox",
        )
    )
    await service.publish(
        MessageRequest(
            recipients=[other_user.id],
            category=MessageCategory.APPROVAL,
            title="别人的待办",
            body="不应出现在我的收件箱。",
            source="test.inbox",
        )
    )

    unread = await business_client.get(
        "/api/v1/messaging/messages/unread-count", headers=_headers(admin_token)
    )
    assert unread.status_code == 200
    assert unread.json() == {"unread_count": 1}

    listing = await business_client.get(
        "/api/v1/messaging/messages", headers=_headers(admin_token)
    )
    assert listing.status_code == 200
    payload = listing.json()
    assert payload["total"] == 1
    assert [item["title"] for item in payload["items"]] == ["我的待办"]
    assert payload["items"][0]["category_label"] == "审批待办"

    marked = await business_client.post(
        f"/api/v1/messaging/messages/{mine[0].message_id}/read",
        headers=_headers(admin_token),
    )
    assert marked.status_code == 200
    assert marked.json()["read_at"] is not None

    unread = await business_client.get(
        "/api/v1/messaging/messages/unread-count", headers=_headers(admin_token)
    )
    assert unread.json() == {"unread_count": 0}


async def test_mark_read_rejects_message_of_another_user(
    business_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
    restricted_token: str,
) -> None:
    """Requirement: D-100 — 不能标记他人的消息。"""

    other_user = await db_session.scalar(
        select(UserAccount).where(UserAccount.username == "synthetic-viewer")
    )
    assert other_user is not None
    other_message = await MessageService(db_session).publish(
        MessageRequest(
            recipients=[other_user.id],
            category=MessageCategory.SYSTEM,
            title="他人消息",
            body="不可越权读取。",
            source="test.authorization",
        )
    )

    response = await business_client.post(
        f"/api/v1/messaging/messages/{other_message[0].message_id}/read",
        headers=_headers(admin_token),
    )

    assert response.status_code == 404
    assert response.json()["code"] == "MESSAGE_NOT_FOUND"


async def test_stream_requires_authentication(business_client: AsyncClient) -> None:
    """Requirement: D-100 — SSE 端点沿用现有会话鉴权。"""

    response = await business_client.get("/api/v1/messaging/stream")

    assert response.status_code == 401
    assert response.json()["code"] == "AUTHENTICATION_REQUIRED"


async def test_stream_pushes_only_the_current_users_messages(
    business_client: AsyncClient,
    committed_session: AsyncSession,
    test_engine: AsyncEngine,
    committed_users: tuple[tuple[UUID, str], tuple[UUID, str]],
) -> None:
    """Requirement: D-100 — SSE 只推送本人消息。"""

    (user_id, token), (other_user_id, _) = committed_users

    stream_task = asyncio.create_task(
        business_client.get(
            "/api/v1/messaging/stream?timeout=6",
            headers=_headers(token),
        )
    )
    await asyncio.sleep(1.0)

    publish_session = AsyncSession(bind=test_engine, expire_on_commit=False)
    try:
        service = MessageService(publish_session)
        await service.publish(
            MessageRequest(
                recipients=[user_id],
                category=MessageCategory.APPROVAL,
                title="属于本人的消息",
                body="应当被推送。",
                source="test.stream",
            )
        )
        await service.publish(
            MessageRequest(
                recipients=[other_user_id],
                category=MessageCategory.APPROVAL,
                title="属于他人的消息",
                body="不应被推送。",
                source="test.stream",
            )
        )
        await publish_session.commit()
    finally:
        await publish_session.close()

    response = await stream_task

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: message" in response.text
    assert "属于本人的消息" in response.text
    assert "属于他人的消息" not in response.text
