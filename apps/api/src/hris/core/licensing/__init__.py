# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""coreHR 授权 SDK（Wave 1）。

Requirement: D-108 — 公开仓让人看得见全部功能与契约，核心业务引擎不公开；
客户取得签发的 License Token 后才解锁对应模块的**写能力**，
无授权时系统进入**只读演示模式**（功能全可浏览，写操作禁用并提示需要授权）。

本包是全仓**唯一**的授权判定入口（计划 §2.1 不变量 3）：
任何模块都不得自己实现一套授权逻辑，请直接使用这里的
`LicenseService` / `require_licensed_write` / `ensure_write_allowed`。

离线优先（不变量 4）：没有任何在线依赖是系统可用的前提。
"""

from hris.core.licensing.errors import (
    DEFAULT_CONTACT_HINT,
    LICENSE_DETAIL_KEYS,
    LICENSE_REQUIRED_CODE,
    LicenseRequiredError,
    LicenseStoreUnavailableError,
)
from hris.core.licensing.guard import (
    READ_ONLY_POST_EXCEPTIONS,
    ReadOnlyPostException,
    ensure_write_allowed,
    is_enforcement_enabled,
    is_read_only_post,
    register_read_only_post_exception,
    require_licensed_read,
    require_licensed_write,
)
from hris.core.licensing.service import (
    ActivationOutcome,
    LicenseService,
    clear_license_state_cache,
)
from hris.core.licensing.types import (
    LICENSED_MODULES,
    LicenseEntitlements,
    LicenseState,
    LicenseStatus,
    LicenseTier,
    ModuleEntitlement,
    VerificationResult,
)


__all__ = [
    "DEFAULT_CONTACT_HINT",
    "LICENSED_MODULES",
    "LICENSE_DETAIL_KEYS",
    "LICENSE_REQUIRED_CODE",
    "READ_ONLY_POST_EXCEPTIONS",
    "ActivationOutcome",
    "LicenseEntitlements",
    "LicenseRequiredError",
    "LicenseService",
    "LicenseState",
    "LicenseStatus",
    "LicenseStoreUnavailableError",
    "LicenseTier",
    "ModuleEntitlement",
    "ReadOnlyPostException",
    "VerificationResult",
    "clear_license_state_cache",
    "ensure_write_allowed",
    "is_enforcement_enabled",
    "is_read_only_post",
    "register_read_only_post_exception",
    "require_licensed_read",
    "require_licensed_write",
]
