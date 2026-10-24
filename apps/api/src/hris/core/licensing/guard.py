# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""只读演示模式的拦截层。

Requirement: D-108 — 三道拦截（计划 §7.2）：
- **第一道（引擎边界）**：Wave 2 拆包后的主力，Demo 引擎的写方法直接拒绝；
- **第二道（路由级默认拒写，本轮主力）**：`require_licensed_write(module)`；
- **第三道（服务层显式标注）**：`ensure_write_allowed(module)`。

路由级语义：
- `POST / PUT / PATCH / DELETE` → 需要 `entitlements[module].write`；
- `GET / HEAD / OPTIONS` → 放行（只读演示模式必须让全部功能可浏览）；
- **例外**：少数查询型 POST 必须**显式登记白名单**并在代码注释里写明理由，
  禁止「默认放行」。

拦截开关：`COREHR_LICENSE_ENFORCE`（默认关闭）。
关闭时依赖只做鉴权放行 —— 这是给「内部开发 / 迁移未跑」场景留的逃生门，
生产部署应置为 true 才是真正的只读演示模式。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.config import get_settings
from hris.core.database import session_factory
from hris.core.licensing.errors import LicenseRequiredError
from hris.core.licensing.service import LicenseService
from hris.modules.platform.dependencies import CurrentSession, DbSession
from hris.modules.platform.models import UserAccount


#: 只读方法：一律放行。
SAFE_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS"})
#: 写方法：需要对应模块的写授权。
WRITE_METHODS: frozenset[str] = frozenset({"POST", "PUT", "PATCH", "DELETE"})


@dataclass(frozen=True)
class ReadOnlyPostException:
    """查询型 POST 的白名单条目。

    Requirement: D-108 — 只登记**确实没有副作用**的查询型 POST，
    并在 reason 里写明为什么它不属于写操作。
    """

    path: str
    module: str
    reason: str


#: 查询型 POST 白名单：请求完整 path → 例外说明。
#:
#: 取舍说明：当前受保护的路由里没有查询型 POST，因此表为空；
#: 将来出现时必须显式登记（禁止默认放行），登记示例：
#:
#: ```python
#: READ_ONLY_POST_EXCEPTIONS["/api/v1/attendance/daily-results/query"] = ReadOnlyPostException(
#:     path="/api/v1/attendance/daily-results/query",
#:     module="attendance",
#:     reason="只读报表查询，不产生任何写副作用",
#: )
#: ```
READ_ONLY_POST_EXCEPTIONS: dict[str, ReadOnlyPostException] = {}


def register_read_only_post_exception(
    path: str,
    *,
    module: str,
    reason: str,
) -> None:
    """登记查询型 POST 白名单（必须写明理由）。"""
    READ_ONLY_POST_EXCEPTIONS[path] = ReadOnlyPostException(
        path=path, module=module, reason=reason
    )


def is_enforcement_enabled() -> bool:
    """拦截总开关（`COREHR_LICENSE_ENFORCE`，默认关闭）。"""
    return bool(get_settings().license_enforce)


def is_read_only_post(path: str) -> bool:
    """请求是否命中查询型 POST 白名单。"""
    return path in READ_ONLY_POST_EXCEPTIONS


def require_licensed_write(module: str) -> Callable[..., UserAccount]:
    """路由级默认拒写依赖。

    语义：写方法需要 `entitlements[module].write`；只读方法放行。
    """
    if not module:
        raise ValueError("module is required")

    async def dependency(
        request: Request,
        current: CurrentSession,
        db: DbSession,
    ) -> UserAccount:
        user, _ = current
        if not is_enforcement_enabled():
            return user
        method = request.method.upper()
        if method in SAFE_METHODS:
            return user
        if method == "POST" and is_read_only_post(request.url.path):
            return user
        state = await LicenseService(db).current_state()
        if not state.can_write(module):
            raise LicenseRequiredError(
                module=module,
                required="write",
                tier=state.tier.value if state.tier else None,
            )
        return user

    return dependency


def require_licensed_read(module: str) -> Callable[..., UserAccount]:
    """路由级读能力依赖。

    Requirement: D-108 — 读能力默认全开（只读演示模式要让人看得见全部功能），
    这里保留显式入口，供将来「连读都要授权」的合同场景使用。
    """
    if not module:
        raise ValueError("module is required")

    async def dependency(current: CurrentSession, db: DbSession) -> UserAccount:
        user, _ = current
        if not is_enforcement_enabled():
            return user
        state = await LicenseService(db).current_state()
        if not state.can_read(module):
            raise LicenseRequiredError(
                module=module,
                required="read",
                tier=state.tier.value if state.tier else None,
            )
        return user

    return dependency


async def ensure_write_allowed(
    module: str,
    *,
    session: AsyncSession | None = None,
) -> None:
    """服务层显式标注（第三道拦截）。

    用于审批执行、期间冻结、导入执行、敏感字段 reveal 这类高价值写路径：
    在 service 方法首行调用 `await ensure_write_allowed("attendance")`。
    """
    if not module:
        raise ValueError("module is required")
    if not is_enforcement_enabled():
        return
    if session is not None:
        state = await LicenseService(session).current_state()
    else:
        async with session_factory() as own_session:
            state = await LicenseService(own_session).current_state()
    if not state.can_write(module):
        raise LicenseRequiredError(
            module=module,
            required="write",
            tier=state.tier.value if state.tier else None,
        )
