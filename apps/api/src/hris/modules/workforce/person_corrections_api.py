# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""人员基础信息「修正」的接口。

Requirement: D-095 — 修正与编辑分成两个入口：
「编辑」沿用既有的 PATCH /persons/{person_id}（覆盖式、立即生效）；
「修正」走本模块的 POST /persons/{person_id}/corrections，产出带生效日期的
修正记录，不覆盖主档。

权限沿用既有权限码，不新增：修正写入用 PERSON_EDIT_BASIC，
修正记录读取用 PERSON_VIEW（与档案读取一致）。
"""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.database import get_db
from hris.modules.platform.dependencies import require_permissions
from hris.modules.platform.models import UserAccount
from hris.modules.workforce.person_corrections_schemas import (
    PersonFieldVersionCreate,
    PersonFieldVersionResponse,
)
from hris.modules.workforce.person_corrections_service import PersonCorrectionService


router = APIRouter(prefix="/api/v1/workforce/persons", tags=["phase-1-person-corrections"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
PersonViewer = Annotated[
    UserAccount,
    Depends(require_permissions("PERSON_VIEW", "PERSON_SENSITIVE_VIEW")),
]
PersonEditor = Annotated[
    UserAccount,
    Depends(
        require_permissions(
            "PERSON_VIEW",
            "PERSON_EDIT_BASIC",
            "PERSON_SENSITIVE_VIEW",
        )
    ),
]


def service(db: AsyncSession, user: UserAccount, request: Request) -> PersonCorrectionService:
    return PersonCorrectionService(
        db,
        actor_id=user.id,
        trace_id=str(request.state.trace_id),
    )


@router.post(
    "/{person_id}/corrections",
    response_model=PersonFieldVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_person_correction(
    person_id: UUID,
    payload: PersonFieldVersionCreate,
    request: Request,
    db: DbSession,
    user: PersonEditor,
) -> PersonFieldVersionResponse:
    record = await service(db, user, request).create_field_version(person_id, payload)
    return PersonCorrectionService.to_response(record, user.display_name)


@router.get("/{person_id}/corrections", response_model=list[PersonFieldVersionResponse])
async def list_person_corrections(
    person_id: UUID,
    request: Request,
    db: DbSession,
    user: PersonViewer,
    effective_at: date | None = Query(default=None),
) -> list[PersonFieldVersionResponse]:
    rows = await service(db, user, request).list_field_versions(
        person_id,
        effective_at=effective_at,
    )
    return [
        PersonCorrectionService.to_response(record, actor_name)
        for record, actor_name in rows
    ]
