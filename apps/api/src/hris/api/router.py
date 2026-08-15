from fastapi import APIRouter

from hris.modules.attendance.api import router as attendance_router
from hris.modules.system.api import router as system_router
from hris.modules.workflow.api import router as workflow_router


api_router = APIRouter()
api_router.include_router(system_router)
api_router.include_router(workflow_router, prefix="/api/v1")
api_router.include_router(attendance_router, prefix="/api/v1")
