# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

from fastapi import APIRouter, Depends

from hris.core.licensing.guard import require_licensed_write
from hris.modules.attendance.api import router as attendance_configuration_router
from hris.modules.attendance.extended_api import router as attendance_operations_router
from hris.modules.performance.api import router as performance_router
from hris.modules.platform.api import router as auth_router
from hris.modules.platform.account_admin_api import router as account_admin_router
from hris.modules.platform.audit_api import router as audit_router
from hris.modules.platform.configuration_api import router as configuration_router
from hris.modules.platform.dependencies import require_permission
from hris.modules.platform.import_api import router as import_router
from hris.modules.platform.license_api import router as license_router
from hris.modules.system.api import router as system_router
from hris.modules.workflow.api import router as workflow_configuration_router
from hris.modules.workflow.extended_api import router as lifecycle_router
from hris.modules.workforce.batch_change_api import router as batch_change_router
from hris.modules.workforce.concurrent_positions_api import router as concurrent_positions_router
from hris.modules.workforce.extended_api import router as workforce_operations_router
from hris.modules.workforce.historical_roster_api import router as historical_roster_router
from hris.modules.workforce.labels_api import router as labels_router
from hris.modules.workforce.organization_api import router as organization_router
from hris.modules.workforce.person_corrections_api import router as person_corrections_router
from hris.modules.workforce.personnel_api import router as personnel_router
from hris.modules.workforce.reporting_api import router as reporting_router


business_router = APIRouter()
business_router.include_router(system_router)
business_router.include_router(auth_router)
business_router.include_router(account_admin_router)
business_router.include_router(configuration_router)
business_router.include_router(import_router)
business_router.include_router(organization_router)
business_router.include_router(workforce_operations_router)
business_router.include_router(historical_roster_router)
business_router.include_router(person_corrections_router)
business_router.include_router(personnel_router)
business_router.include_router(labels_router)
business_router.include_router(reporting_router)
business_router.include_router(concurrent_positions_router)
business_router.include_router(audit_router)
business_router.include_router(batch_change_router)
business_router.include_router(performance_router)
# Requirement: D-108 — 授权管理端点（状态 / 激活 / 停用）。
business_router.include_router(license_router)
business_router.include_router(
    workflow_configuration_router,
    prefix="/api/v1",
    dependencies=[Depends(require_permission("LIFECYCLE_ADMIN"))],
)
business_router.include_router(lifecycle_router)
business_router.include_router(
    attendance_configuration_router,
    prefix="/api/v1",
    dependencies=[
        # Requirement: C5 — 考勤高风险动作拆独立权限码。
        # 规则集路由原先在挂载处统一挂 `require_permission("ATTENDANCE_ADMIN")`，
        # 会让「规则发布」端点同时要求 ATTENDANCE_ADMIN 与新码，导致独立权限码形同虚设。
        # 因此这里不再挂域级码：每个端点自己在 modules/attendance/api.py 声明权限
        # （普通规则集操作用 ATTENDANCE_ADMIN，规则发布用 ATTENDANCE_RULE_PUBLISH），
        # 与核心应用 hris.main:app 的挂载口径保持一致（那边同样只有端点级依赖）。
        # Requirement: D-108 — 路由级默认拒写（第二道拦截）。
        # 该依赖在 COREHR_LICENSE_ENFORCE=false 时只放行，因此既有集成测试不受影响；
        # 置 true 后，未授权时考勤配置写操作统一 403 LICENSE_REQUIRED。
        Depends(require_licensed_write("attendance")),
    ],
)
business_router.include_router(
    attendance_operations_router,
    # Requirement: D-108 — 考勤运营端点同样挂路由级默认拒写。
    # 注意：attendance_operations_router 自带 "/api/v1/attendance" 前缀，
    # 这里**不追加 prefix**，避免破坏既有路由路径。
    dependencies=[Depends(require_licensed_write("attendance"))],
)
