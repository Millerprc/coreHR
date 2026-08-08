from fastapi import APIRouter, Depends

from hris.modules.attendance.api import router as attendance_configuration_router
from hris.modules.attendance.extended_api import router as attendance_operations_router
from hris.modules.platform.api import router as auth_router
from hris.modules.platform.configuration_api import router as configuration_router
from hris.modules.platform.dependencies import require_permission
from hris.modules.system.api import router as system_router
from hris.modules.workflow.api import router as workflow_configuration_router
from hris.modules.workflow.extended_api import router as lifecycle_router
from hris.modules.workforce.api import router as workforce_configuration_router
from hris.modules.workforce.extended_api import router as workforce_operations_router


business_router = APIRouter()
business_router.include_router(system_router)
business_router.include_router(auth_router)
business_router.include_router(configuration_router)
business_router.include_router(
    workforce_configuration_router,
    prefix="/api/v1",
    dependencies=[Depends(require_permission("WORKFORCE_ADMIN"))],
)
business_router.include_router(workforce_operations_router)
business_router.include_router(
    workflow_configuration_router,
    prefix="/api/v1",
    dependencies=[Depends(require_permission("LIFECYCLE_ADMIN"))],
)
business_router.include_router(lifecycle_router)
business_router.include_router(
    attendance_configuration_router,
    prefix="/api/v1",
    dependencies=[Depends(require_permission("ATTENDANCE_ADMIN"))],
)
business_router.include_router(attendance_operations_router)
