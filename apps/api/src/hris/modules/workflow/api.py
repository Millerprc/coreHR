from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.database import get_db
from hris.modules.workflow.schemas import (
    WorkflowDefinitionCreate,
    WorkflowDefinitionListResponse,
    WorkflowDefinitionResponse,
)
from hris.modules.workflow.service import WorkflowService


router = APIRouter(prefix="/workflows", tags=["phase-2-workflow"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.post(
    "/definitions",
    response_model=WorkflowDefinitionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow_definition(
    payload: WorkflowDefinitionCreate,
    db: DbSession,
) -> WorkflowDefinitionResponse:
    result = await WorkflowService(db).create_definition(payload)
    return WorkflowDefinitionResponse.model_validate(result)


@router.get(
    "/definitions",
    response_model=WorkflowDefinitionListResponse,
)
async def list_workflow_definitions(
    db: DbSession,
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

