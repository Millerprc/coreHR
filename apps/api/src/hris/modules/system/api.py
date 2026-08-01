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
                status="slice_available",
                available_endpoints=[
                    "/api/v1/workforce/organization-types",
                    "/api/v1/workforce/organizations",
                ],
                pending_inputs=[
                    "企业现有职务体系表",
                    "员工档案表头和脱敏样例",
                ],
            ),
            ModuleStatus(
                phase=2,
                code="WORKFLOW_LIFECYCLE",
                name="流程与人员生命周期",
                status="slice_available",
                available_endpoints=["/api/v1/workflows/definitions"],
                pending_inputs=[
                    "入职、转正、调动、离职、兼岗流程图",
                    "合同与协议字段表",
                ],
            ),
            ModuleStatus(
                phase=3,
                code="ATTENDANCE",
                name="考勤",
                status="slice_available",
                available_endpoints=["/api/v1/attendance/rule-sets"],
                pending_inputs=[
                    "考勤、排班和假期规则",
                    "打卡来源和设备接口",
                ],
            ),
        ]
    )

