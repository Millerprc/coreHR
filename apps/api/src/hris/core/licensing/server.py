# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""可选在线通道客户端（默认不启用）。

Requirement: D-108 — **离线优先**：没有任何在线依赖是系统可用的前提。

- `COREHR_LICENSE_SERVER_URL` 未配置 → 纯离线，**不发起任何外部请求**；
- 配置了 → 拉取吊销 / 续期状态；
- 网络不可达 → **沿用最后一次已知状态**，不把授权降级为未授权
  （避免网络抖动误伤客户）；超过宽限期（7 天）仍沿用，由上层在 UI 标注同步过期；
- 在线通道明确返回 `revoked: true` → 立即进入只读模式，不等宽限期。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx

from hris.core.config import get_settings


logger = logging.getLogger(__name__)

#: 在线状态同步的宽限期：超过此时长仍未同步成功，UI 标注「授权状态同步已过期」。
SERVER_GRACE_PERIOD = timedelta(days=7)

#: 单次请求超时（秒）。在线通道永远不能拖慢本地判定。
SERVER_TIMEOUT_SECONDS = 2.0


@dataclass(frozen=True)
class ServerLicenseStatus:
    """在线通道返回的授权状态。"""

    license_id: str
    revoked: bool
    checked_at: datetime
    next_token: str | None = None


class LicenseServerClient:
    """License Center 在线通道客户端。

    取舍说明：本类是**可选**的，构造出来不代表会被调用；
    `enabled` 为 False 时所有方法都直接返回 None，不产生任何网络请求。
    """

    def __init__(self, base_url: str | None, *, timeout: float = SERVER_TIMEOUT_SECONDS) -> None:
        self._base_url = (base_url or "").strip().rstrip("/")
        self._timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self._base_url)

    @property
    def base_url(self) -> str:
        return self._base_url

    async def fetch_status(self, license_id: str) -> ServerLicenseStatus | None:
        """拉取指定 license_id 的在线状态。

        返回 None 表示「拿不到」（未启用 / 不可达 / 响应非法）；
        调用方必须沿用最后一次已知状态，不得据此降级授权。
        """
        if not self.enabled or not license_id:
            return None
        url = f"{self._base_url}/v1/licenses/{license_id}/status"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    logger.warning("授权在线通道返回 %s，沿用最后一次已知状态", response.status_code)
                    return None
                payload = response.json()
        except (httpx.HTTPError, ValueError):
            # 不可达不是故障：沿用最后一次已知状态。
            logger.warning("授权在线通道不可达，沿用最后一次已知状态")
            return None

        if not isinstance(payload, dict):
            return None
        return ServerLicenseStatus(
            license_id=str(payload.get("license_id") or license_id),
            revoked=bool(payload.get("revoked")),
            checked_at=datetime.now(UTC),
            next_token=payload.get("next_token") if isinstance(payload.get("next_token"), str) else None,
        )


def get_server_client() -> LicenseServerClient:
    """按当前配置构造在线通道客户端（未配置时为禁用状态）。"""
    return LicenseServerClient(get_settings().license_server_url)


def is_sync_stale(last_checked_at: datetime | None) -> bool:
    """在线状态同步是否已超过宽限期。"""
    if last_checked_at is None:
        return True
    if last_checked_at.tzinfo is None:
        last_checked_at = last_checked_at.replace(tzinfo=UTC)
    return datetime.now(UTC) - last_checked_at > SERVER_GRACE_PERIOD
