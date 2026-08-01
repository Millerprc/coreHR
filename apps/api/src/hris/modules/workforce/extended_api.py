from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.database import get_db
from hris.modules.platform.dependencies import require_permission
from hris.modules.platform.models import UserAccount
from hris.modules.workforce.extended_schemas import (
    EmployeeNumberResponse,
    EmploymentAssignmentCreate,
    EmploymentAssignmentResponse,
    EmploymentCreate,
    EmploymentResponse,
    HeadcountPlanCreate,
    HeadcountPlanResponse,
    JobCreate,
    JobResponse,
    LegalEntityCreate,
    LegalEntityResponse,
    PageResponse,
    PersonCreate,
    PersonResponse,
)
from hris.modules.workforce.extended_service import ExtendedWorkforceService
from hris.modules.workforce.models import HeadcountPlan, JobCatalog, LegalEntity, Person


router = APIRouter(prefix="/api/v1/workforce", tags=["phase-1-workforce-admin"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
AdminUser = Annotated[UserAccount, Depends(require_permission("WORKFORCE_ADMIN"))]


def service(db: AsyncSession, user: UserAccount, request: Request) -> ExtendedWorkforceService:
    return ExtendedWorkforceService(
        db,
        actor_id=user.id,
        trace_id=str(request.state.trace_id),
    )


@router.post("/legal-entities", response_model=LegalEntityResponse, status_code=201)
async def create_legal_entity(
    payload: LegalEntityCreate, request: Request, db: DbSession, user: AdminUser
) -> LegalEntityResponse:
    return LegalEntityResponse.model_validate(
        await service(db, user, request).create_legal_entity(payload)
    )


@router.get("/legal-entities", response_model=PageResponse)
async def list_legal_entities(
    request: Request,
    db: DbSession,
    user: AdminUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PageResponse:
    items, total = await service(db, user, request).list_models(
        LegalEntity, limit=limit, offset=offset, order_by=LegalEntity.code
    )
    return PageResponse(
        items=[LegalEntityResponse.model_validate(item).model_dump() for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/jobs", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    payload: JobCreate, request: Request, db: DbSession, user: AdminUser
) -> JobResponse:
    return JobResponse.model_validate(await service(db, user, request).create_job(payload))


@router.get("/jobs", response_model=PageResponse)
async def list_jobs(
    request: Request,
    db: DbSession,
    user: AdminUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PageResponse:
    items, total = await service(db, user, request).list_models(
        JobCatalog, limit=limit, offset=offset, order_by=JobCatalog.code
    )
    return PageResponse(
        items=[JobResponse.model_validate(item).model_dump() for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/persons", response_model=PersonResponse, status_code=status.HTTP_201_CREATED)
async def create_person(
    payload: PersonCreate, request: Request, db: DbSession, user: AdminUser
) -> PersonResponse:
    return PersonResponse.model_validate(await service(db, user, request).create_person(payload))


@router.get("/persons", response_model=PageResponse)
async def list_persons(
    request: Request,
    db: DbSession,
    user: AdminUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PageResponse:
    items, total = await service(db, user, request).list_models(
        Person, limit=limit, offset=offset, order_by=Person.employee_number
    )
    return PageResponse(
        items=[PersonResponse.model_validate(item).model_dump() for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/persons/{person_id}/reserve-number", response_model=EmployeeNumberResponse)
async def reserve_employee_number(
    person_id: UUID, request: Request, db: DbSession, user: AdminUser
) -> EmployeeNumberResponse:
    number = await service(db, user, request).reserve_employee_number(person_id)
    return EmployeeNumberResponse(person_id=person_id, employee_number=number)


@router.post("/employments", response_model=EmploymentResponse, status_code=201)
async def create_employment(
    payload: EmploymentCreate, request: Request, db: DbSession, user: AdminUser
) -> EmploymentResponse:
    return EmploymentResponse.model_validate(
        await service(db, user, request).create_employment(payload)
    )


@router.post(
    "/employment-assignments",
    response_model=EmploymentAssignmentResponse,
    status_code=201,
)
async def create_employment_assignment(
    payload: EmploymentAssignmentCreate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> EmploymentAssignmentResponse:
    return EmploymentAssignmentResponse.model_validate(
        await service(db, user, request).create_assignment(payload)
    )


@router.post("/headcount-plans", response_model=HeadcountPlanResponse, status_code=201)
async def create_headcount_plan(
    payload: HeadcountPlanCreate, request: Request, db: DbSession, user: AdminUser
) -> HeadcountPlanResponse:
    return HeadcountPlanResponse.model_validate(
        await service(db, user, request).create_headcount_plan(payload)
    )


@router.get("/headcount-plans", response_model=PageResponse)
async def list_headcount_plans(
    request: Request,
    db: DbSession,
    user: AdminUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PageResponse:
    items, total = await service(db, user, request).list_models(
        HeadcountPlan, limit=limit, offset=offset, order_by=HeadcountPlan.period_month
    )
    return PageResponse(
        items=[HeadcountPlanResponse.model_validate(item).model_dump() for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )
