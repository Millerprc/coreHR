# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""授权相关的统一错误。

Requirement: D-108 — 被授权模块拦截时统一 `403 / code=LICENSE_REQUIRED`，
`details` **只放** `{module, required, tier, contact_hint}`。

信息边界（计划 §7.1）：403 响应不得泄露业务策略细节
（不说明「你的规则应该怎么算」「这条路径缺哪个字段校验」）。
否则未授权方可以通过反复试错反推私有引擎的行为，等于把核心实现逐步还原出来。
本模块的所有错误文案都必须遵守这条约束。
"""

from __future__ import annotations

from typing import Any

from hris.core.errors import ApiError


LICENSE_REQUIRED_CODE = "LICENSE_REQUIRED"

#: 统一的申请指引。只说「去哪里拿授权」，不说任何业务策略。
DEFAULT_CONTACT_HINT = "请在「授权管理」中激活有效的授权 Token，或联系 coreHR 商务开通对应模块的写能力。"

#: `details` 允许出现的键白名单 —— 有守卫测试钉住，避免以后有人往里塞策略细节。
LICENSE_DETAIL_KEYS: frozenset[str] = frozenset(
    {"module", "required", "tier", "contact_hint"}
)


class LicenseRequiredError(ApiError):
    """写能力未获授权。

    Requirement: D-108 — `details` 只有四个键：缺失模块、所需能力、当前版本、申请指引。
    """

    def __init__(
        self,
        *,
        module: str,
        required: str = "write",
        tier: str | None = None,
        contact_hint: str = DEFAULT_CONTACT_HINT,
        message: str = "该操作需要有效授权",
    ) -> None:
        details: dict[str, Any] = {
            "module": module,
            "required": required,
            "tier": tier,
            "contact_hint": contact_hint,
        }
        super().__init__(
            status_code=403,
            code=LICENSE_REQUIRED_CODE,
            message=message,
            details=details,
        )


class LicenseStoreUnavailableError(RuntimeError):
    """`license_registrations` 表不可用（迁移未跑）。

    Requirement: D-108 — 表不存在时 licensing 模块降级为「无授权 → 只读」，
    绝不能让服务起不来；只有「激活写库」这一步会失败。
    """
