from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.database import get_db
from hris.modules.attendance.schemas import (
    AttendanceRuleSetCreate,
    AttendanceRuleSetListResponse,
    AttendanceRuleSetResponse,
)
from hris.modules.attendance.service import AttendanceService


router = APIRouter(prefix="/attendance", tags=["phase-3-attendance"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.post(
    "/rule-sets",
    response_model=AttendanceRuleSetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_attendance_rule_set(
    payload: AttendanceRuleSetCreate,
    db: DbSession,
) -> AttendanceRuleSetResponse:
    result = await AttendanceService(db).create_rule_set(payload)
    return AttendanceRuleSetResponse.model_validate(result)


@router.get("/rule-sets", response_model=AttendanceRuleSetListResponse)
async def list_attendance_rule_sets(
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AttendanceRuleSetListResponse:
    items, total = await AttendanceService(db).list_rule_sets(
        limit=limit,
        offset=offset,
    )
    return AttendanceRuleSetListResponse(
        items=[AttendanceRuleSetResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )

