from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.database import get_db
from hris.modules.platform.dependencies import require_permission
from hris.modules.platform.models import UserAccount
from hris.modules.workflow.extended_schemas import (
    ApplicationHireConversionResponse,
    ApplicationHireCreate,
    CandidateCreate,
    CandidatePage,
    CandidateResponse,
    CandidateUpdate,
    ContractActionCreate,
    ContractCreate,
    ContractExpiryAlert,
    ContractExpiryAlertPage,
    ContractPage,
    ContractResponse,
    ContractStatusProcessRequest,
    ContractStatusProcessResponse,
    ContractUpdate,
    HrEventCreate,
    HrEventPage,
    HrEventProcessRequest,
    HrEventProcessResponse,
    HrEventResponse,
    HrEventRollbackCreate,
    JobApplicationCreate,
    JobApplicationPage,
    JobApplicationResponse,
    JobApplicationUpdate,
    RecruitmentRequestCreate,
    RecruitmentRequestPage,
    RecruitmentRequestResponse,
    RecruitmentRequestUpdate,
    WorkflowInstanceCreate,
    WorkflowInstanceDetailResponse,
    WorkflowInstancePage,
    WorkflowInstanceResponse,
    WorkflowPublishResponse,
    WorkflowTaskDecision,
    WorkflowTaskPage,
    WorkflowTaskResponse,
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


@router.get("/candidates", response_model=CandidatePage)
async def list_candidates(
    request: Request,
    db: DbSession,
    user: AdminUser,
    candidate_status: str | None = Query(default=None, alias="status", max_length=30),
    search: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> CandidatePage:
    items, total = await service(db, user, request).list_candidates(
        status=candidate_status,
        search=search,
        limit=limit,
        offset=offset,
    )
    return CandidatePage(
        items=[CandidateResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/candidates/{candidate_id}", response_model=CandidateResponse)
async def get_candidate(
    candidate_id: UUID,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> CandidateResponse:
    return CandidateResponse.model_validate(
        await service(db, user, request).get_candidate(candidate_id)
    )


@router.patch("/candidates/{candidate_id}", response_model=CandidateResponse)
async def update_candidate(
    candidate_id: UUID,
    payload: CandidateUpdate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> CandidateResponse:
    return CandidateResponse.model_validate(
        await service(db, user, request).update_candidate(candidate_id, payload)
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


@router.get("/applications", response_model=JobApplicationPage)
async def list_applications(
    request: Request,
    db: DbSession,
    user: AdminUser,
    application_status: str | None = Query(default=None, alias="status", max_length=30),
    candidate_id: UUID | None = Query(default=None),
    recruitment_request_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> JobApplicationPage:
    items, total = await service(db, user, request).list_applications(
        status=application_status,
        candidate_id=candidate_id,
        recruitment_request_id=recruitment_request_id,
        limit=limit,
        offset=offset,
    )
    return JobApplicationPage(
        items=[JobApplicationResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/applications/{application_id}", response_model=JobApplicationResponse)
async def get_application(
    application_id: UUID,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> JobApplicationResponse:
    return JobApplicationResponse.model_validate(
        await service(db, user, request).get_application(application_id)
    )


@router.patch("/applications/{application_id}", response_model=JobApplicationResponse)
async def update_application(
    application_id: UUID,
    payload: JobApplicationUpdate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> JobApplicationResponse:
    return JobApplicationResponse.model_validate(
        await service(db, user, request).update_application(application_id, payload)
    )


@router.post(
    "/applications/{application_id}/hire",
    response_model=ApplicationHireConversionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def hire_application(
    application_id: UUID,
    payload: ApplicationHireCreate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> ApplicationHireConversionResponse:
    return ApplicationHireConversionResponse.model_validate(
        await service(db, user, request).hire_application(application_id, payload)
    )


@router.post("/contracts", response_model=ContractResponse, status_code=201)
async def create_contract(
    payload: ContractCreate, request: Request, db: DbSession, user: AdminUser
) -> ContractResponse:
    return ContractResponse.model_validate(
        await service(db, user, request).create_contract(payload)
    )


@router.get("/contracts", response_model=ContractPage)
async def list_contracts(
    request: Request,
    db: DbSession,
    user: AdminUser,
    contract_status: str | None = Query(default=None, alias="status", max_length=30),
    person_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ContractPage:
    items, total = await service(db, user, request).list_contracts(
        status=contract_status,
        person_id=person_id,
        limit=limit,
        offset=offset,
    )
    return ContractPage(
        items=[ContractResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/contracts/expiry-alerts", response_model=ContractExpiryAlertPage)
async def list_contract_expiry_alerts(
    request: Request,
    db: DbSession,
    user: AdminUser,
    as_of: date | None = Query(default=None),
    days_ahead: int = Query(default=90, ge=0, le=3650),
) -> ContractExpiryAlertPage:
    items, alert_date = await service(db, user, request).list_contract_expiry_alerts(
        as_of=as_of,
        days_ahead=days_ahead,
    )
    return ContractExpiryAlertPage(
        items=[ContractExpiryAlert.model_validate(item) for item in items],
        total=len(items),
        as_of=alert_date,
        days_ahead=days_ahead,
    )


@router.post(
    "/contracts/process-statuses",
    response_model=ContractStatusProcessResponse,
)
async def process_contract_statuses(
    payload: ContractStatusProcessRequest,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> ContractStatusProcessResponse:
    processed = await service(db, user, request).process_contract_statuses(payload.as_of)
    return ContractStatusProcessResponse(processed_ids=processed)


@router.post(
    "/contracts/{contract_id}/actions",
    response_model=HrEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_contract_action(
    contract_id: UUID,
    payload: ContractActionCreate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> HrEventResponse:
    return HrEventResponse.model_validate(
        await service(db, user, request).create_contract_action(contract_id, payload)
    )


@router.get("/contracts/{contract_id}", response_model=ContractResponse)
async def get_contract(
    contract_id: UUID,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> ContractResponse:
    return ContractResponse.model_validate(
        await service(db, user, request).get_contract(contract_id)
    )


@router.patch("/contracts/{contract_id}", response_model=ContractResponse)
async def update_contract(
    contract_id: UUID,
    payload: ContractUpdate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> ContractResponse:
    return ContractResponse.model_validate(
        await service(db, user, request).update_contract(contract_id, payload)
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


@router.get("/workflow-instances", response_model=WorkflowInstancePage)
async def list_workflow_instances(
    request: Request,
    db: DbSession,
    user: AdminUser,
    instance_status: str | None = Query(default=None, alias="status", max_length=30),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> WorkflowInstancePage:
    items, total = await service(db, user, request).list_workflow_instances(
        status=instance_status,
        limit=limit,
        offset=offset,
    )
    return WorkflowInstancePage(
        items=[WorkflowInstanceResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/workflow-instances/{instance_id}",
    response_model=WorkflowInstanceDetailResponse,
)
async def get_workflow_instance(
    instance_id: UUID,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> WorkflowInstanceDetailResponse:
    instance, tasks = await service(db, user, request).workflow_instance_detail(instance_id)
    return WorkflowInstanceDetailResponse(
        instance=WorkflowInstanceResponse.model_validate(instance),
        tasks=[WorkflowTaskResponse.model_validate(task) for task in tasks],
    )


@router.post("/workflow-tasks/{task_id}/decision", response_model=WorkflowTaskResponse)
async def decide_workflow_task(
    task_id: UUID,
    payload: WorkflowTaskDecision,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> WorkflowTaskResponse:
    return WorkflowTaskResponse.model_validate(
        await service(db, user, request).decide_workflow_task(task_id, payload)
    )


@router.get("/workflow-tasks", response_model=WorkflowTaskPage)
async def list_workflow_tasks(
    request: Request,
    db: DbSession,
    user: AdminUser,
    task_status: str | None = Query(default=None, alias="status", max_length=30),
    assignee_ref: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> WorkflowTaskPage:
    items, total = await service(db, user, request).list_workflow_tasks(
        status=task_status,
        assignee_ref=assignee_ref,
        limit=limit,
        offset=offset,
    )
    return WorkflowTaskPage(
        items=[WorkflowTaskResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/hr-events", response_model=HrEventResponse, status_code=201)
async def create_hr_event(
    payload: HrEventCreate, request: Request, db: DbSession, user: AdminUser
) -> HrEventResponse:
    return HrEventResponse.model_validate(
        await service(db, user, request).create_hr_event(payload)
    )


@router.get("/hr-events", response_model=HrEventPage)
async def list_hr_events(
    request: Request,
    db: DbSession,
    user: AdminUser,
    event_status: str | None = Query(default=None, alias="status", max_length=30),
    object_type: str | None = Query(default=None, max_length=50),
    object_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> HrEventPage:
    items, total = await service(db, user, request).list_hr_events(
        status=event_status,
        object_type=object_type,
        object_id=object_id,
        limit=limit,
        offset=offset,
    )
    return HrEventPage(
        items=[HrEventResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/hr-events/{event_id}", response_model=HrEventResponse)
async def get_hr_event(
    event_id: UUID,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> HrEventResponse:
    return HrEventResponse.model_validate(
        await service(db, user, request).get_hr_event(event_id)
    )


@router.post("/hr-events/process", response_model=HrEventProcessResponse)
async def process_hr_events(
    payload: HrEventProcessRequest,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> HrEventProcessResponse:
    processed, failed = await service(db, user, request).process_due_hr_events(payload.as_of)
    return HrEventProcessResponse(processed_ids=processed, failed=failed)


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
