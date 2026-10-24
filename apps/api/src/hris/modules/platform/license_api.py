# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""授权管理 API。

Requirement: D-108 — 客户取得签发的 License Token 后激活对应模块的写能力；
未授权时系统处于只读演示模式，授权状态通过本组端点对外可见。

| 方法 | 路径 | 权限 | 用途 |
|---|---|---|---|
| GET | `/api/v1/license` | 登录即可 | 当前授权状态 |
| POST | `/api/v1/license/activate` | `*`（主管理员） | 提交 Token 激活 |
| POST | `/api/v1/license/deactivate` | `*` | 停用当前授权（回落到只读演示模式） |

取舍说明：激活 / 停用是写操作，必须走审计（`platform/audit_service.py`），
审计 payload 只放授权事实摘要，**不含 Token 明文**。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.database import get_db
from hris.core.licensing.service import LicenseService
from hris.core.licensing.types import LicenseState
from hris.modules.platform.dependencies import CurrentSession, require_permission
from hris.modules.platform.license_schemas import (
    LicenseActivateRequest,
    LicenseActivateResponse,
    LicenseDeactivateResponse,
    LicenseStateResponse,
    ModuleEntitlementResponse,
)
from hris.modules.platform.models import UserAccount


router = APIRouter(prefix="/api/v1/license", tags=["platform-license"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
#: 授权变更需要主管理员权限（`*` 通配权限）。
AdminAccount = Annotated[UserAccount, Depends(require_permission("*"))]


def _trace_id(request: Request) -> str:
    return str(getattr(request.state, "trace_id", "unavailable"))


def _entitlements(state: LicenseState) -> dict[str, ModuleEntitlementResponse]:
    return {
        name: ModuleEntitlementResponse(read=bool(item["read"]), write=bool(item["write"]))
        for name, item in state.entitlements.to_payload().items()
    }


@router.get("", response_model=LicenseStateResponse)
@router.get("/", response_model=LicenseStateResponse, include_in_schema=False)
async def current_license(current: CurrentSession, db: DbSession) -> LicenseStateResponse:
    """当前授权状态。登录即可查看。"""
    state = await LicenseService(db).current_state()
    return LicenseStateResponse(
        status=state.status,
        readonly_mode=state.readonly_mode,
        tier=state.tier,
        licensee=state.licensee,
        licensee_short=state.licensee_short,
        license_id=state.license_id,
        entitlements=_entitlements(state),
        issued_at=state.issued_at,
        not_before=state.not_before,
        expires_at=state.expires_at,
        seat_limit=state.seat_limit,
        activated_at=state.activated_at,
    )


@router.post("/activate", response_model=LicenseActivateResponse)
async def activate_license(
    payload: LicenseActivateRequest,
    request: Request,
    admin: AdminAccount,
    db: DbSession,
) -> LicenseActivateResponse:
    """提交 License Token 激活授权。

    Requirement: D-108 — 格式非法 → 400 `LICENSE_INVALID_TOKEN`；
    验签失败 → 400 `LICENSE_INVALID_SIGNATURE`；
    过期 Token **允许激活**，返回 status=expired，系统仍保持只读。
    """
    outcome = await LicenseService(db).activate(
        payload.token,
        actor_id=admin.id,
        actor_name=admin.username,
        trace_id=_trace_id(request),
    )
    state = outcome.state
    return LicenseActivateResponse(
        activated=True,
        status=state.status,
        tier=state.tier,
        licensee=state.licensee,
        entitlements=_entitlements(state),
        expires_at=state.expires_at,
    )


@router.post("/deactivate", response_model=LicenseDeactivateResponse)
async def deactivate_license(
    request: Request,
    admin: AdminAccount,
    db: DbSession,
) -> LicenseDeactivateResponse:
    """停用当前授权，回落到只读演示模式。"""
    state = await LicenseService(db).deactivate(
        actor_id=admin.id,
        actor_name=admin.username,
        trace_id=_trace_id(request),
    )
    return LicenseDeactivateResponse(
        status=state.status,
        readonly_mode=state.readonly_mode,
    )
