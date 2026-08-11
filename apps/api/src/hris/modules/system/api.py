from fastapi import APIRouter
from redis.asyncio import Redis
from sqlalchemy import text

from hris.core.config import get_settings
from hris.core.database import engine
from hris.core.errors import ApiError
from hris.modules.system.schemas import (
    HealthResponse,
    ModuleRegistryResponse,
    ModuleStatus,
)


router = APIRouter(tags=["system"])


@router.get("/health/live", response_model=HealthResponse)
async def health_live() -> HealthResponse:
    return HealthResponse(status="ok", service="corehr-api")


@router.get("/health/ready", response_model=HealthResponse)
async def health_ready() -> HealthResponse:
    checks: dict[str, str] = {}
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        checks["database"] = "ok"

        redis = Redis.from_url(get_settings().redis_url)
        try:
            await redis.ping()
            checks["redis"] = "ok"
        finally:
            await redis.aclose()
    except Exception as exc:
        raise ApiError(
            status_code=503,
            code="SERVICE_NOT_READY",
            message="服务依赖尚未就绪",
            details=[{"component": "dependency", "reason": type(exc).__name__}],
        ) from exc

    return HealthResponse(status="ok", service="corehr-api", checks=checks)


@router.get(
    "/api/v1/system/modules",
    response_model=ModuleRegistryResponse,
)
async def list_modules() -> ModuleRegistryResponse:
    return ModuleRegistryResponse(
        items=[
            ModuleStatus(
                phase=1,
                code="CORE_HR",
                name="组织、人事与编制",
                status="uat_ready",
                available_capabilities=[
                    "数据字典与六类非敏感主数据导入导出",
                    "有效日期组织、法人、负责人、BP、成本中心与收入目标",
                    "人员、劳动/协议关系、任职、编制、快照与招聘需求",
                ],
                available_endpoints=[
                    "/api/v1/workforce/organizations",
                    "/api/v1/workforce/persons",
                    "/api/v1/workforce/headcount-results",
                    "/api/v1/governance/import-batches",
                ],
                pending_inputs=[
                    "正式稳定编码对照",
                    "档案字段验收表与脱敏迁移样例",
                ],
            ),
            ModuleStatus(
                phase=2,
                code="WORKFLOW_LIFECYCLE",
                name="流程与人员生命周期",
                status="uat_ready",
                available_capabilities=[
                    "流程定义、版本发布、会签/或签、实例与审批任务",
                    "候选人、应聘、Offer确认与待入职衔接",
                    "入转调离兼事件、未来生效、合同/协议与回退",
                ],
                available_endpoints=[
                    "/api/v1/workflows/definitions",
                    "/api/v1/lifecycle/applications",
                    "/api/v1/lifecycle/contracts",
                    "/api/v1/lifecycle/hr-events",
                ],
                pending_inputs=[
                    "正式流程图与审批人规则",
                    "合同/协议字段、附件、提醒和电子签章规则",
                ],
            ),
            ModuleStatus(
                phase=3,
                code="ATTENDANCE",
                name="考勤",
                status="uat_ready",
                available_capabilities=[
                    "考勤规则、班次、排班与原始打卡",
                    "假期类型、请假/销假、年度余额账户与不可变流水",
                    "日报、月报、月结冻结、业务冻结与受控重算",
                ],
                available_endpoints=[
                    "/api/v1/attendance/rule-sets",
                    "/api/v1/attendance/leave-requests",
                    "/api/v1/attendance/daily-results",
                    "/api/v1/attendance/monthly-results",
                ],
                pending_inputs=[
                    "企业考勤与假期计提规则包",
                    "打卡接口契约与万人容量流量模型",
                ],
            ),
        ]
    )
