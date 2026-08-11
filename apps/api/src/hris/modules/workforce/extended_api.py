from datetime import date, datetime
from typing import Annotated, Any
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.database import get_db
from hris.core.config import get_settings
from hris.modules.platform.dependencies import require_permission
from hris.modules.platform.models import UserAccount
from hris.modules.workforce.extended_schemas import (
    AgreementRelationshipCreate,
    AgreementRelationshipResponse,
    EmployeeNumberResponse,
    EmploymentAssignmentCreate,
    EmploymentAssignmentResponse,
    EmploymentCreate,
    EmploymentResponse,
    HeadcountFreezeClose,
    HeadcountFreezeCreate,
    HeadcountFreezeResponse,
    HeadcountPlanCreate,
    HeadcountPlanResponse,
    HeadcountResultLine,
    HeadcountResultResponse,
    HeadcountSnapshotBatchResponse,
    HeadcountSnapshotGenerate,
    JobCreate,
    JobDimensionCreate,
    JobDimensionResponse,
    JobDimensionType,
    JobDimensionVersionCreate,
    JobResponse,
    JobVersionCreate,
    LegalEntityCreate,
    LegalEntityResponse,
    OccupancyRuleCreate,
    OccupancyRuleResponse,
    PageResponse,
    PersonArchiveResponse,
    PersonCreate,
    PersonResponse,
    PersonUpdate,
)
from hris.modules.workforce.extended_service import ExtendedWorkforceService
from hris.modules.workforce.models import (
    HeadcountFreeze,
    HeadcountPlan,
    LegalEntity,
    OccupancyRule,
)


router = APIRouter(prefix="/api/v1/workforce", tags=["phase-1-workforce-admin"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
AdminUser = Annotated[UserAccount, Depends(require_permission("WORKFORCE_ADMIN"))]


def service(db: AsyncSession, user: UserAccount, request: Request) -> ExtendedWorkforceService:
    return ExtendedWorkforceService(
        db,
        actor_id=user.id,
        trace_id=str(request.state.trace_id),
    )


def business_date() -> date:
    return datetime.now(ZoneInfo(get_settings().business_timezone)).date()


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
    return await service(db, user, request).create_job(payload)


@router.post(
    "/jobs/{job_id}/versions",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_job_version(
    job_id: UUID,
    payload: JobVersionCreate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> JobResponse:
    return await service(db, user, request).create_job_version(job_id, payload)


@router.get("/jobs", response_model=PageResponse)
async def list_jobs(
    request: Request,
    db: DbSession,
    user: AdminUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    effective_at: date | None = Query(default=None),
) -> PageResponse:
    items, total = await service(db, user, request).list_jobs(
        effective_at=effective_at or business_date(),
        limit=limit,
        offset=offset,
    )
    return PageResponse(
        items=[item.model_dump() for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/job-dimensions",
    response_model=JobDimensionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_job_dimension(
    payload: JobDimensionCreate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> JobDimensionResponse:
    return await service(db, user, request).create_job_dimension(payload)


@router.post(
    "/job-dimensions/{dimension_id}/versions",
    response_model=JobDimensionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_job_dimension_version(
    dimension_id: UUID,
    payload: JobDimensionVersionCreate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> JobDimensionResponse:
    return await service(db, user, request).create_job_dimension_version(
        dimension_id,
        payload,
    )


@router.get("/job-dimensions", response_model=PageResponse)
async def list_job_dimensions(
    request: Request,
    db: DbSession,
    user: AdminUser,
    dimension_type: JobDimensionType | None = Query(default=None),
    effective_at: date | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PageResponse:
    items, total = await service(db, user, request).list_job_dimensions(
        dimension_type=dimension_type,
        effective_at=effective_at or business_date(),
        limit=limit,
        offset=offset,
    )
    return PageResponse(
        items=[item.model_dump() for item in items],
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
    search: str | None = Query(default=None, max_length=200),
    person_status: str | None = Query(default=None, alias="status", max_length=30),
) -> PageResponse:
    items, total = await service(db, user, request).list_persons(
        search=search,
        status=person_status,
        limit=limit,
        offset=offset,
    )
    return PageResponse(
        items=[PersonResponse.model_validate(item).model_dump() for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/persons/{person_id}", response_model=PersonArchiveResponse)
async def get_person_archive(
    person_id: UUID, request: Request, db: DbSession, user: AdminUser
) -> PersonArchiveResponse:
    person, employments, assignments, agreements = await service(
        db, user, request
    ).person_archive(person_id)
    return PersonArchiveResponse(
        person=PersonResponse.model_validate(person),
        employments=[EmploymentResponse.model_validate(item) for item in employments],
        assignments=[
            EmploymentAssignmentResponse.model_validate(item) for item in assignments
        ],
        agreements=[
            AgreementRelationshipResponse.model_validate(item) for item in agreements
        ],
    )


@router.patch("/persons/{person_id}", response_model=PersonResponse)
async def update_person(
    person_id: UUID,
    payload: PersonUpdate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> PersonResponse:
    return PersonResponse.model_validate(
        await service(db, user, request).update_person(person_id, payload)
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


@router.post(
    "/agreement-relationships",
    response_model=AgreementRelationshipResponse,
    status_code=201,
)
async def create_agreement_relationship(
    payload: AgreementRelationshipCreate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> AgreementRelationshipResponse:
    return AgreementRelationshipResponse.model_validate(
        await service(db, user, request).create_agreement_relationship(payload)
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


@router.post("/occupancy-rules", response_model=OccupancyRuleResponse, status_code=201)
async def create_occupancy_rule(
    payload: OccupancyRuleCreate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> OccupancyRuleResponse:
    return OccupancyRuleResponse.model_validate(
        await service(db, user, request).create_occupancy_rule(payload)
    )


@router.get("/occupancy-rules", response_model=PageResponse)
async def list_occupancy_rules(
    request: Request,
    db: DbSession,
    user: AdminUser,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PageResponse:
    items, total = await service(db, user, request).list_models(
        OccupancyRule,
        limit=limit,
        offset=offset,
        order_by=OccupancyRule.employee_type_code,
    )
    return PageResponse(
        items=[OccupancyRuleResponse.model_validate(item).model_dump() for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/headcount-freezes", response_model=HeadcountFreezeResponse, status_code=201)
async def create_headcount_freeze(
    payload: HeadcountFreezeCreate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> HeadcountFreezeResponse:
    return HeadcountFreezeResponse.model_validate(
        await service(db, user, request).create_headcount_freeze(payload)
    )


@router.get("/headcount-freezes", response_model=PageResponse)
async def list_headcount_freezes(
    request: Request,
    db: DbSession,
    user: AdminUser,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PageResponse:
    items, total = await service(db, user, request).list_models(
        HeadcountFreeze,
        limit=limit,
        offset=offset,
        order_by=HeadcountFreeze.starts_at.desc(),
    )
    return PageResponse(
        items=[HeadcountFreezeResponse.model_validate(item).model_dump() for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/headcount-freezes/{freeze_id}/close", response_model=HeadcountFreezeResponse)
async def close_headcount_freeze(
    freeze_id: UUID,
    payload: HeadcountFreezeClose,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> HeadcountFreezeResponse:
    return HeadcountFreezeResponse.model_validate(
        await service(db, user, request).close_headcount_freeze(freeze_id, payload.reason)
    )


@router.post(
    "/headcount-snapshots",
    response_model=HeadcountSnapshotBatchResponse,
    status_code=201,
)
async def generate_headcount_snapshot(
    payload: HeadcountSnapshotGenerate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> HeadcountSnapshotBatchResponse:
    return HeadcountSnapshotBatchResponse.model_validate(
        await service(db, user, request).generate_headcount_snapshot(payload)
    )


@router.get("/headcount-results", response_model=HeadcountResultResponse)
async def get_headcount_results(
    request: Request,
    db: DbSession,
    user: AdminUser,
    period_month: date = Query(),
    as_of: date | None = Query(default=None),
    organization_id: UUID | None = Query(default=None),
    job_id: UUID | None = Query(default=None),
) -> HeadcountResultResponse:
    query_date = as_of or date.today()
    items = await service(db, user, request).headcount_results(
        period_month=period_month,
        as_of=query_date,
        organization_id=organization_id,
        job_id=job_id,
    )
    return HeadcountResultResponse(
        period_month=period_month,
        as_of=query_date,
        items=[HeadcountResultLine.model_validate(item) for item in items],
    )
