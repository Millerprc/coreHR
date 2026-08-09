from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.database import get_db
from hris.modules.platform.dependencies import require_permission
from hris.modules.platform.models import UserAccount
from hris.modules.workflow.extended_schemas import (
    CandidateCreate,
    CandidateResponse,
    ContractCreate,
    ContractResponse,
    HrEventCreate,
    HrEventResponse,
    HrEventRollbackCreate,
    JobApplicationCreate,
    JobApplicationResponse,
    RecruitmentRequestCreate,
    RecruitmentRequestPage,
    RecruitmentRequestResponse,
    RecruitmentRequestUpdate,
    WorkflowInstanceCreate,
    WorkflowInstanceResponse,
    WorkflowPublishResponse,
)
from hris.modules.workflow.extended_service import LifecycleService


router = APIRouter(prefix="/api/v1/lifecycle", tags=["phase-2-lifecycle-admin"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
AdminUser = Annotated[UserAccount, Depends(require_permission("LIFECYCLE_ADMIN"))]


def service(db: AsyncSession, user: UserAccount, request: Request) -> LifecycleService:
    return LifecycleService(db, actor_id=user.id, trace_id=str(request.state.trace_id))


@router.post("/candidates", response_model=CandidateResponse, status_code=201)
async def create_candidate(
    payload: CandidateCreate, request: Request, db: DbSession, user: AdminUser
) -> CandidateResponse:
    return CandidateResponse.model_validate(
        await service(db, user, request).create_candidate(payload)
    )


@router.post(
    "/recruitment-requests",
    response_model=RecruitmentRequestResponse,
    status_code=201,
)
async def create_recruitment_request(
    payload: RecruitmentRequestCreate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> RecruitmentRequestResponse:
    return RecruitmentRequestResponse.model_validate(
        await service(db, user, request).create_recruitment_request(payload)
    )


@router.get("/recruitment-requests", response_model=RecruitmentRequestPage)
async def list_recruitment_requests(
    request: Request,
    db: DbSession,
    user: AdminUser,
    request_status: str | None = Query(default=None, alias="status", max_length=30),
    organization_id: UUID | None = Query(default=None),
    job_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> RecruitmentRequestPage:
    items, total = await service(db, user, request).list_recruitment_requests(
        status=request_status,
        organization_id=organization_id,
        job_id=job_id,
        limit=limit,
        offset=offset,
    )
    return RecruitmentRequestPage(
        items=[RecruitmentRequestResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/recruitment-requests/{request_id}", response_model=RecruitmentRequestResponse)
async def get_recruitment_request(
    request_id: UUID,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> RecruitmentRequestResponse:
    return RecruitmentRequestResponse.model_validate(
        await service(db, user, request).get_recruitment_request(request_id)
    )


@router.patch("/recruitment-requests/{request_id}", response_model=RecruitmentRequestResponse)
async def update_recruitment_request(
    request_id: UUID,
    payload: RecruitmentRequestUpdate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> RecruitmentRequestResponse:
    return RecruitmentRequestResponse.model_validate(
        await service(db, user, request).update_recruitment_request(request_id, payload)
    )


@router.post("/applications", response_model=JobApplicationResponse, status_code=201)
async def create_application(
    payload: JobApplicationCreate, request: Request, db: DbSession, user: AdminUser
) -> JobApplicationResponse:
    return JobApplicationResponse.model_validate(
        await service(db, user, request).create_application(payload)
    )


@router.post("/contracts", response_model=ContractResponse, status_code=201)
async def create_contract(
    payload: ContractCreate, request: Request, db: DbSession, user: AdminUser
) -> ContractResponse:
    return ContractResponse.model_validate(
        await service(db, user, request).create_contract(payload)
    )


@router.post(
    "/workflows/{definition_id}/publish",
    response_model=WorkflowPublishResponse,
)
async def publish_workflow(
    definition_id: UUID, request: Request, db: DbSession, user: AdminUser
) -> WorkflowPublishResponse:
    version, workflow_status = await service(db, user, request).publish_workflow(definition_id)
    return WorkflowPublishResponse(
        definition_id=definition_id,
        version=version,
        status=workflow_status,
    )


@router.post(
    "/workflow-instances",
    response_model=WorkflowInstanceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_workflow(
    payload: WorkflowInstanceCreate, request: Request, db: DbSession, user: AdminUser
) -> WorkflowInstanceResponse:
    return WorkflowInstanceResponse.model_validate(
        await service(db, user, request).start_workflow(payload)
    )


@router.post("/hr-events", response_model=HrEventResponse, status_code=201)
async def create_hr_event(
    payload: HrEventCreate, request: Request, db: DbSession, user: AdminUser
) -> HrEventResponse:
    return HrEventResponse.model_validate(
        await service(db, user, request).create_hr_event(payload)
    )


@router.post("/hr-events/{event_id}/rollback", response_model=HrEventResponse, status_code=201)
async def rollback_hr_event(
    event_id: UUID,
    payload: HrEventRollbackCreate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> HrEventResponse:
    return HrEventResponse.model_validate(
        await service(db, user, request).rollback_hr_event(event_id, payload)
    )
