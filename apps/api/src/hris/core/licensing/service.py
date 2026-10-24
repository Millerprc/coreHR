# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""LicenseService：当前授权状态、激活 / 停用、有效 entitlements 计算。

Requirement: D-108 — 授权判定的唯一收口点。性能约定（计划 §7.3）：
- 进程内 LRU 缓存，TTL 5 秒；
- Redis 共享缓存，TTL 30 秒（多副本部署避免各自回源）；
- 授权变更（激活 / 停用 / 吊销）**主动失效**两级缓存；
- Redis 不可用 → 回落到进程内 LRU + 直查 DB。
"""

from __future__ import annotations

import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.config import get_settings
from hris.core.errors import ApiError
from hris.core.licensing import store
from hris.core.licensing.errors import LicenseStoreUnavailableError
from hris.core.licensing.server import LicenseServerClient, get_server_client
from hris.core.licensing.token import (
    ERROR_INVALID_TOKEN,
    token_digest,
    verify_token,
)
from hris.core.licensing.types import (
    LicenseEntitlements,
    LicenseState,
    LicenseStatus,
    LicenseTier,
    VerificationResult,
)
from hris.modules.platform.audit_service import record_audit_event


logger = logging.getLogger(__name__)

#: 进程内缓存 TTL（秒）。
PROCESS_CACHE_TTL_SECONDS = 5.0
#: Redis 共享缓存 TTL（秒）。
REDIS_CACHE_TTL_SECONDS = 30
#: Redis 缓存键（全局单一有效授权）。
REDIS_STATE_KEY = "license:state:current"
#: 进程内缓存键。
_CACHE_KEY = "current"

#: Redis 连接 / 读写超时（秒）。在线缓存永远不能拖慢本地判定。
_REDIS_TIMEOUT_SECONDS = 0.5


class _ProcessStateCache:
    """进程内 LRU + TTL 缓存。"""

    def __init__(
        self,
        *,
        ttl: float = PROCESS_CACHE_TTL_SECONDS,
        maxsize: int = 32,
    ) -> None:
        self._ttl = ttl
        self._maxsize = maxsize
        self._entries: OrderedDict[str, tuple[float, LicenseState]] = OrderedDict()

    def get(self, key: str) -> LicenseState | None:
        item = self._entries.get(key)
        if item is None:
            return None
        expires_at, state = item
        if expires_at <= time.monotonic():
            self._entries.pop(key, None)
            return None
        self._entries.move_to_end(key)
        return state

    def set(self, key: str, state: LicenseState) -> None:
        self._entries[key] = (time.monotonic() + self._ttl, state)
        self._entries.move_to_end(key)
        while len(self._entries) > self._maxsize:
            self._entries.popitem(last=False)

    def clear(self) -> None:
        self._entries.clear()


_process_cache = _ProcessStateCache()
_redis_client: Redis | None = None
_redis_disabled = False


def _get_redis() -> Redis | None:
    global _redis_client, _redis_disabled
    if _redis_disabled:
        return None
    if _redis_client is None:
        settings = get_settings()
        if not settings.redis_url:
            _redis_disabled = True
            return None
        try:
            _redis_client = Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=_REDIS_TIMEOUT_SECONDS,
                socket_timeout=_REDIS_TIMEOUT_SECONDS,
            )
        except Exception:  # pragma: no cover - 客户端构造失败等价于 Redis 不可用
            logger.warning("授权状态 Redis 缓存不可用，回落到进程内缓存与直查数据库")
            _redis_disabled = True
            return None
    return _redis_client


async def _redis_get_state() -> LicenseState | None:
    client = _get_redis()
    if client is None:
        return None
    try:
        raw = await client.get(REDIS_STATE_KEY)
    except Exception:
        logger.warning("授权状态 Redis 缓存读取失败，回落到进程内缓存与直查数据库")
        return None
    if not raw:
        return None
    try:
        payload = json.loads(raw)
        return LicenseState.from_payload(payload)
    except (TypeError, ValueError):
        return None


async def _redis_set_state(state: LicenseState) -> None:
    client = _get_redis()
    if client is None:
        return
    try:
        await client.set(
            REDIS_STATE_KEY,
            json.dumps(state.to_payload(), ensure_ascii=False),
            ex=REDIS_CACHE_TTL_SECONDS,
        )
    except Exception:
        logger.warning("授权状态 Redis 缓存写入失败，回落到进程内缓存与直查数据库")


async def _redis_delete_state() -> None:
    client = _get_redis()
    if client is None:
        return
    try:
        await client.delete(REDIS_STATE_KEY)
    except Exception:
        logger.warning("授权状态 Redis 缓存失效失败，不影响授权事实")


async def clear_license_state_cache() -> None:
    """主动失效两级缓存（激活 / 停用 / 吊销后调用）。"""
    _process_cache.clear()
    await _redis_delete_state()


@dataclass(frozen=True)
class ActivationOutcome:
    """激活结果。"""

    state: LicenseState
    token_digest: str
    verification: VerificationResult


class LicenseService:
    """授权状态的读取与变更。"""

    def __init__(
        self,
        session: AsyncSession,
        *,
        server_client: LicenseServerClient | None = None,
    ) -> None:
        self._session = session
        self._server_client = server_client

    # ------------------------------------------------------------------ 读取

    async def current_state(self, *, use_cache: bool = True) -> LicenseState:
        """当前授权状态。

        Requirement: D-108 — 未授权 / 过期 / 吊销 / 未生效一律等价于只读演示模式。
        """
        if use_cache:
            cached = _process_cache.get(_CACHE_KEY)
            if cached is not None:
                return cached
            shared = await _redis_get_state()
            if shared is not None:
                _process_cache.set(_CACHE_KEY, shared)
                return shared

        registration = await store.load_current_registration(self._session)
        state = self._state_from_registration(registration)
        state = await self._apply_online_status(state)

        if use_cache:
            _process_cache.set(_CACHE_KEY, state)
            await _redis_set_state(state)
        return state

    def _state_from_registration(self, registration: Any) -> LicenseState:
        if registration is None:
            return LicenseState(
                status=LicenseStatus.NONE,
                readonly_mode=True,
                entitlements=LicenseEntitlements.readonly(),
            )

        now = datetime.now(UTC)
        status = resolve_registration_status(registration, now)
        tier = _parse_tier(registration.tier)
        if status is LicenseStatus.ACTIVE:
            entitlements = LicenseEntitlements.from_payload(registration.entitlements)
        else:
            # 非有效授权一律只读：读路径仍可用，写能力全部关闭。
            entitlements = LicenseEntitlements.readonly()
        readonly_mode = status is not LicenseStatus.ACTIVE or tier is LicenseTier.COMMUNITY
        return LicenseState(
            status=status,
            readonly_mode=readonly_mode,
            tier=tier,
            licensee=registration.licensee,
            licensee_short=registration.licensee_short,
            license_id=registration.license_id,
            entitlements=entitlements,
            issued_at=registration.issued_at,
            not_before=registration.not_before,
            expires_at=registration.expires_at,
            seat_limit=registration.seat_limit,
            activated_at=registration.activated_at,
        )

    async def _apply_online_status(self, state: LicenseState) -> LicenseState:
        """可选在线通道：仅在明确返回 revoked 时立即降级。

        Requirement: D-108 — 不可达时沿用最后一次已知状态，不降级授权状态。
        """
        client = self._server_client or get_server_client()
        if not client.enabled or state.status is not LicenseStatus.ACTIVE:
            return state
        if not state.license_id:
            return state
        remote = await client.fetch_status(state.license_id)
        if remote is None:
            return state
        if not remote.revoked:
            return state
        return LicenseState(
            status=LicenseStatus.REVOKED,
            readonly_mode=True,
            tier=state.tier,
            licensee=state.licensee,
            licensee_short=state.licensee_short,
            license_id=state.license_id,
            entitlements=LicenseEntitlements.readonly(),
            issued_at=state.issued_at,
            not_before=state.not_before,
            expires_at=state.expires_at,
            seat_limit=state.seat_limit,
            activated_at=state.activated_at,
        )

    # ------------------------------------------------------------------ 变更

    async def activate(
        self,
        token: str,
        *,
        actor_id: UUID | None,
        actor_name: str,
        trace_id: str,
    ) -> ActivationOutcome:
        """激活授权。

        Requirement: D-108 — 过期 Token **允许激活**（记为 expired，系统仍只读）；
        格式 / 签名非法一律拒绝，且不影响系统运行。
        """
        verification = verify_token(token)
        if not verification.ok:
            raise ApiError(
                status_code=400,
                code=verification.error_code or ERROR_INVALID_TOKEN,
                message=verification.message or "授权 Token 无效",
            )

        now = datetime.now(UTC)
        status = compute_activation_status(verification, now)
        entitlements = verification.entitlements or LicenseEntitlements.readonly()

        previous = await store.load_current_registration(self._session)
        before_payload = _registration_payload(previous)

        try:
            registration = await store.save_activation(
                self._session,
                license_id=verification.license_id or "",
                licensee=verification.licensee or verification.licensee_short or "未署名授权",
                licensee_short=verification.licensee_short or verification.licensee or "未署名授权",
                tier=(verification.tier or LicenseTier.COMMUNITY).value,
                entitlements=entitlements.to_payload(),
                token_digest=token_digest(token),
                issued_at=verification.issued_at or now,
                not_before=verification.not_before,
                expires_at=verification.expires_at,
                seat_limit=verification.seat_limit,
                status=status,
                activated_by=actor_name,
                source="admin",
            )
        except LicenseStoreUnavailableError as exc:
            raise ApiError(
                status_code=503,
                code="LICENSE_STORE_UNAVAILABLE",
                message="授权存储不可用，请先执行数据库迁移",
            ) from exc

        after_payload = _registration_payload(registration)
        await record_audit_event(
            self._session,
            actor_id=actor_id,
            trace_id=trace_id,
            action="platform.license.activate",
            object_type="license_registration",
            object_id=registration.id,
            reason="激活授权",
            before_payload=before_payload,
            # Requirement: D-108 — 审计 payload 不得包含 Token 明文。
            after_payload=after_payload,
            source="api",
        )

        await clear_license_state_cache()
        state = await self.current_state(use_cache=False)
        return ActivationOutcome(
            state=state,
            token_digest=token_digest(token),
            verification=verification,
        )

    async def deactivate(
        self,
        *,
        actor_id: UUID | None,
        actor_name: str,
        trace_id: str,
    ) -> LicenseState:
        """停用当前授权（回落到只读演示模式）。"""
        registration = await store.load_current_registration(self._session)
        changed = await store.deactivate_current_registration(self._session)
        if changed and registration is not None:
            await record_audit_event(
                self._session,
                actor_id=actor_id,
                trace_id=trace_id,
                action="platform.license.deactivate",
                object_type="license_registration",
                object_id=registration.id,
                reason="停用授权",
                before_payload=_registration_payload(registration),
                after_payload={},
                source="api",
            )
        await clear_license_state_cache()
        return await self.current_state(use_cache=False)


def resolve_registration_status(registration: Any, now: datetime) -> LicenseStatus:
    """注册记录 → 当前状态。

    Requirement: D-108 — 吊销优先于一切（计划 §9.1）。
    """
    stored = getattr(registration, "status", None)
    if stored == "revoked":
        return LicenseStatus.REVOKED
    not_before = getattr(registration, "not_before", None)
    if not_before is not None and now < _as_utc(not_before):
        return LicenseStatus.NOT_YET_VALID
    expires_at = getattr(registration, "expires_at", None)
    if expires_at is not None and now > _as_utc(expires_at):
        return LicenseStatus.EXPIRED
    return LicenseStatus.ACTIVE


def compute_activation_status(verification: VerificationResult, now: datetime) -> str:
    """激活时写入注册记录的状态。

    Requirement: D-108 — 过期 Token 允许激活，但记为 expired（系统仍只读）。
    """
    if verification.not_before is not None and now < _as_utc(verification.not_before):
        return LicenseStatus.NOT_YET_VALID.value
    if verification.expires_at is not None and now > _as_utc(verification.expires_at):
        return LicenseStatus.EXPIRED.value
    return LicenseStatus.ACTIVE.value


def _parse_tier(value: Any) -> LicenseTier | None:
    if not value:
        return None
    try:
        return LicenseTier(str(value))
    except ValueError:
        return None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _registration_payload(registration: Any) -> dict[str, Any]:
    """审计用的授权事实摘要（不含 Token 明文，也不含 Token 摘要）。"""
    if registration is None:
        return {}
    return {
        "license_id": registration.license_id,
        "licensee": registration.licensee,
        "licensee_short": registration.licensee_short,
        "tier": registration.tier,
        "status": registration.status,
        "entitlements": registration.entitlements,
        "issued_at": _iso(registration.issued_at),
        "not_before": _iso(registration.not_before),
        "expires_at": _iso(registration.expires_at),
        "seat_limit": registration.seat_limit,
        "activated_at": _iso(registration.activated_at),
        "activated_by": registration.activated_by,
    }


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _as_utc(value).isoformat()
