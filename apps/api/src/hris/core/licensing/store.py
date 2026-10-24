# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""授权事实的 DB 持久化。

Requirement: D-108 — 只存 token 摘要（sha256），**不存明文**；
明文 Token 只在激活请求里出现一次。

降级要求（计划 §9.3）：`license_registrations` 表不存在（迁移未跑）时，
licensing 模块降级为「无授权 → 只读」，**绝不能让服务起不来**。
因此所有读路径在探测到表缺失时返回空授权，写路径（激活）才报不可用。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.licensing.errors import LicenseStoreUnavailableError
from hris.modules.platform.models import LicenseRegistration


#: 当前有效授权可能处于的状态（其余状态视为历史记录，不再参与当前授权判定）。
CURRENT_STATUSES: tuple[str, ...] = ("active", "expired", "not_yet_valid", "revoked")

#: 被新授权顶替时写入的状态。
SUPERSEDED_STATUS = "superseded"


async def probe_table(session: AsyncSession) -> bool:
    """探测授权表是否可用。

    用 SAVEPOINT 包住探测语句：Postgres 在语句报错后会把事务置为 aborted，
    嵌套事务回滚后外层事务仍然可用，不会连累同一请求里的其它语句。
    """
    try:
        async with session.begin_nested():
            await session.execute(text("SELECT 1 FROM license_registrations LIMIT 1"))
    except DBAPIError:
        return False
    return True


async def load_current_registration(
    session: AsyncSession,
) -> LicenseRegistration | None:
    """读取当前授权记录；表不存在或没有授权时返回 None（= 只读演示模式）。"""
    if not await probe_table(session):
        return None
    result = await session.execute(
        select(LicenseRegistration)
        .where(LicenseRegistration.status.in_(CURRENT_STATUSES))
        .order_by(
            LicenseRegistration.activated_at.desc(),
            LicenseRegistration.created_at.desc(),
        )
        .limit(1)
    )
    return result.scalars().first()


async def save_activation(
    session: AsyncSession,
    *,
    license_id: str,
    licensee: str,
    licensee_short: str,
    tier: str,
    entitlements: dict[str, Any],
    token_digest: str,
    issued_at: datetime,
    not_before: datetime | None,
    expires_at: datetime | None,
    seat_limit: int | None,
    status: str,
    activated_by: str,
    source: str = "admin",
) -> LicenseRegistration:
    """写入激活事实。

    并发语义（计划 §9.2）：
    - 同一 `license_id` 重复激活 → **后激活覆盖前激活**（幂等，不产生双活）；
    - 并发插入同一 `license_id` → 唯一索引兜底，冲突方改走覆盖路径；
    - 其它 `license_id` 的有效授权 → 置为 `superseded`，保证全局单一有效授权。
    """
    if not await probe_table(session):
        raise LicenseStoreUnavailableError(
            "license_registrations 表不存在，请先执行数据库迁移"
        )

    now = datetime.now(UTC)
    values: dict[str, Any] = {
        "licensee": licensee,
        "licensee_short": licensee_short,
        "tier": tier,
        "entitlements": entitlements,
        "token_digest": token_digest,
        "issued_at": issued_at,
        "not_before": not_before,
        "expires_at": expires_at,
        "seat_limit": seat_limit,
        "status": status,
    }

    existing = await _lock_by_license_id(session, license_id)
    if existing is not None:
        _apply_values(existing, values)
        existing.activated_at = now
        existing.activated_by = activated_by
        existing.source = source
        await session.flush()
        await supersede_other_registrations(session, keep_license_id=license_id)
        return existing

    registration = LicenseRegistration(
        id=uuid4(),
        license_id=license_id,
        activated_at=now,
        activated_by=activated_by,
        source=source,
        **values,
    )
    try:
        async with session.begin_nested():
            session.add(registration)
            await session.flush()
    except IntegrityError:
        # 并发激活同一 license_id：唯一索引兜底，后激活覆盖前激活。
        concurrent = await _lock_by_license_id(session, license_id)
        if concurrent is None:
            raise
        _apply_values(concurrent, values)
        concurrent.activated_at = now
        concurrent.activated_by = activated_by
        concurrent.source = source
        await session.flush()
        await supersede_other_registrations(session, keep_license_id=license_id)
        return concurrent

    await supersede_other_registrations(session, keep_license_id=license_id)
    return registration


async def supersede_other_registrations(
    session: AsyncSession,
    *,
    keep_license_id: str,
) -> int:
    """把其它 license_id 的有效授权置为 `superseded`（保留审计链，不删除记录）。"""
    result = await session.execute(
        update(LicenseRegistration)
        .where(
            LicenseRegistration.license_id != keep_license_id,
            LicenseRegistration.status.in_(("active", "expired", "not_yet_valid")),
        )
        .values(status=SUPERSEDED_STATUS, updated_at=datetime.now(UTC))
    )
    return int(result.rowcount or 0)


async def deactivate_current_registration(session: AsyncSession) -> bool:
    """停用当前授权（回落只读演示模式）。返回是否确实停用了记录。"""
    registration = await load_current_registration(session)
    if registration is None:
        return False
    registration.status = SUPERSEDED_STATUS
    registration.updated_at = datetime.now(UTC)
    await session.flush()
    return True


def _apply_values(registration: LicenseRegistration, values: dict[str, Any]) -> None:
    for key, value in values.items():
        setattr(registration, key, value)


async def _lock_by_license_id(
    session: AsyncSession,
    license_id: str,
) -> LicenseRegistration | None:
    """按 license_id 取并锁定授权记录（行锁防并发双活）。"""
    return await session.scalar(
        select(LicenseRegistration)
        .where(LicenseRegistration.license_id == license_id)
        .with_for_update()
    )


__all__ = [
    "CURRENT_STATUSES",
    "LicenseRegistration",
    "SUPERSEDED_STATUS",
    "deactivate_current_registration",
    "load_current_registration",
    "probe_table",
    "save_activation",
    "supersede_other_registrations",
]
