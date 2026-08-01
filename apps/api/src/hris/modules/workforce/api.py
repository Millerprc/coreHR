from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.database import get_db
from hris.modules.workforce.schemas import (
    OrganizationCreate,
    OrganizationListResponse,
    OrganizationResponse,
    OrganizationTypeCreate,
    OrganizationTypeResponse,
)
from hris.modules.workforce.service import WorkforceService


router = APIRouter(prefix="/workforce", tags=["phase-1-workforce"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.post(
    "/organization-types",
    response_model=OrganizationTypeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_organization_type(
    payload: OrganizationTypeCreate,
    db: DbSession,
) -> OrganizationTypeResponse:
    result = await WorkforceService(db).create_organization_type(payload)
    return OrganizationTypeResponse.model_validate(result)


@router.post(
    "/organizations",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_organization(
    payload: OrganizationCreate,
    db: DbSession,
) -> OrganizationResponse:
    return await WorkforceService(db).create_organization(payload)


@router.get("/organizations", response_model=OrganizationListResponse)
async def list_organizations(
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> OrganizationListResponse:
    items, total = await WorkforceService(db).list_organizations(
        limit=limit,
        offset=offset,
    )
    return OrganizationListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )

