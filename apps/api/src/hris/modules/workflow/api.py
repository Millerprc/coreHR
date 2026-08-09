from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.database import get_db
from hris.modules.platform.dependencies import require_permission
from hris.modules.platform.models import UserAccount
from hris.modules.workflow.schemas import (
    WorkflowDefinitionCreate,
    WorkflowDefinitionDetailResponse,
    WorkflowDefinitionListResponse,
    WorkflowDefinitionResponse,
    WorkflowVersionResponse,
)
from hris.modules.workflow.service import WorkflowService


router = APIRouter(prefix="/workflows", tags=["phase-2-workflow"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
AdminUser = Annotated[UserAccount, Depends(require_permission("LIFECYCLE_ADMIN"))]


@router.post(
    "/definitions",
    response_model=WorkflowDefinitionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow_definition(
    payload: WorkflowDefinitionCreate,
    db: DbSession,
    _user: AdminUser,
) -> WorkflowDefinitionResponse:
    result = await WorkflowService(db).create_definition(payload)
    return WorkflowDefinitionResponse.model_validate(result)


@router.get(
    "/definitions",
    response_model=WorkflowDefinitionListResponse,
)
async def list_workflow_definitions(
    db: DbSession,
    _user: AdminUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> WorkflowDefinitionListResponse:
    items, total = await WorkflowService(db).list_definitions(
        limit=limit,
        offset=offset,
    )
    return WorkflowDefinitionListResponse(
        items=[
            WorkflowDefinitionResponse.model_validate(item)
            for item in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/definitions/{definition_id}",
    response_model=WorkflowDefinitionDetailResponse,
)
async def get_workflow_definition(
    definition_id: UUID,
    db: DbSession,
    _user: AdminUser,
) -> WorkflowDefinitionDetailResponse:
    definition, versions = await WorkflowService(db).definition_detail(definition_id)
    return WorkflowDefinitionDetailResponse(
        definition=WorkflowDefinitionResponse.model_validate(definition),
        versions=[WorkflowVersionResponse.model_validate(version) for version in versions],
    )
