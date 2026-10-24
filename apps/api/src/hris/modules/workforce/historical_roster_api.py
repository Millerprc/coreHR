# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""历史花名册的接口：按任意历史时点回看当时的员工名册。

Requirement: D-102 — 允许按任意历史时点查询；不新建第二套人员版本表，
时点值 = 区间化表的生效切片 + 主档登记值 + 已生效的字段级修正。

错误口径：
- as_of 缺失或格式非法 → 422（FastAPI 参数校验，REQUEST_VALIDATION_FAILED）。
- as_of 是未来日期 → 不报错，返回空列表（历史花名册要能查「今天」，
  未来时点没有数据就是空结果；这与组织架构 as_of 的规则不同，
  D-013 只约束组织树只展示当前有效树）。

权限：读复用 PERSON_VIEW（与人员档案读取同一枚权限码）。
本接口只返回花名册级别的基础字段（工号、姓名、主组织、职位、在职状态、入职日期），
不返回证件号、联系方式等敏感子记录，因此不额外要求 PERSON_SENSITIVE_VIEW。
"""

from dataclasses import asdict
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.database import get_db
from hris.modules.platform.dependencies import require_permission
from hris.modules.platform.models import UserAccount
from hris.modules.workforce.historical_roster_service import (
    FIELD_HISTORY_NOTE,
    HistoricalRosterService,
)


router = APIRouter(prefix="/api/v1/workforce", tags=["phase-1-historical-roster"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
PersonViewer = Annotated[UserAccount, Depends(require_permission("PERSON_VIEW"))]


class HistoricalRosterRow(BaseModel):
    """花名册的一行：每一列都是该时点的值。"""

    person_id: UUID
    employee_number: str | None
    display_name: str | None
    legal_name: str | None
    organization_id: UUID | None
    organization_code: str | None
    organization_name: str | None
    job_id: UUID | None
    job_code: str | None
    job_name: str | None
    employment_status: str | None
    hire_date: date | None
    # Requirement: D-102 — 该行是否有时点字段修正历史支撑。
    # False 意味着这一行的姓名等字段等于当前登记值，不是历史回放结果。
    field_history_available: bool
    corrected_fields: list[str]


class HistoricalRosterResponse(BaseModel):
    as_of: date
    items: list[HistoricalRosterRow]
    total: int
    limit: int
    offset: int
    # Requirement: D-102 — 把「不是完整历史回放」这一限制写进响应契约本身。
    field_history_note: str


@router.get("/people/roster-history", response_model=HistoricalRosterResponse)
async def get_historical_roster(
    db: DbSession,
    user: PersonViewer,
    as_of: date = Query(),
    search: str | None = Query(default=None, max_length=200),
    organization_id: UUID | None = Query(default=None),
    employment_status: str | None = Query(default=None, max_length=30),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> HistoricalRosterResponse:
    """按 as_of 时点返回在册员工名册。

    as_of 必填；未来日期允许，结果为空列表而不是 422。
    """
    items, total = await HistoricalRosterService(db).roster(
        as_of=as_of,
        search=search,
        organization_id=organization_id,
        employment_status=employment_status,
        limit=limit,
        offset=offset,
    )
    return HistoricalRosterResponse(
        as_of=as_of,
        items=[HistoricalRosterRow(**asdict(row)) for row in items],
        total=total,
        limit=limit,
        offset=offset,
        field_history_note=FIELD_HISTORY_NOTE,
    )
