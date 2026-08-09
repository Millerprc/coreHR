from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.errors import ApiError
from hris.modules.platform.numbering import next_number
from hris.modules.workflow.extended_schemas import (
    CandidateCreate,
    ContractCreate,
    HrEventCreate,
    HrEventRollbackCreate,
    JobApplicationCreate,
    RecruitmentRequestCreate,
    RecruitmentRequestUpdate,
    WorkflowInstanceCreate,
)
from hris.modules.workflow.models import (
    Candidate,
    ContractRecord,
    JobApplication,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowVersion,
)
from hris.modules.workforce.models import (
    AuditLog,
    Employment,
    HrEvent,
    JobCatalog,
    LegalEntity,
    Organization,
    Person,
    RecruitmentRequest,
)


class LifecycleService:
    def __init__(self, session: AsyncSession, *, actor_id: UUID, trace_id: str) -> None:
        self._session = session
        self._actor_id = actor_id
        self._trace_id = trace_id

    def _audit(
        self,
        *,
        action: str,
        object_type: str,
        object_id: UUID,
        after: dict[str, Any],
        reason: str | None = None,
        before: dict[str, Any] | None = None,
    ) -> None:
        self._session.add(
            AuditLog(
                occurred_at=datetime.now(UTC),
                actor_id=self._actor_id,
                trace_id=self._trace_id,
                action=action,
                object_type=object_type,
                object_id=object_id,
                reason=reason,
                before_payload=before or {},
                after_payload=after,
                source="api",
            )
        )

    async def create_candidate(self, payload: CandidateCreate) -> Candidate:
        number = payload.candidate_number or await next_number(
            self._session,
            sequence_code="CANDIDATE_NUMBER",
            width=8,
            max_value=99999999,
            prefix="C",
        )
        if await self._session.scalar(
            select(Candidate.id).where(Candidate.candidate_number == number)
        ) is not None:
            raise ApiError(status_code=409, code="CANDIDATE_NUMBER_EXISTS", message="候选人编号已存在")
        candidate = Candidate(
            candidate_number=number,
            display_name=payload.display_name,
            contact_payload=payload.contact_payload,
            status="active",
        )
        self._session.add(candidate)
        await self._session.flush()
        self._audit(
            action="create",
            object_type="candidate",
            object_id=candidate.id,
            after={"candidate_number": candidate.candidate_number},
        )
        return candidate

    async def create_recruitment_request(
        self,
        payload: RecruitmentRequestCreate,
    ) -> RecruitmentRequest:
        if await self._session.get(Organization, payload.organization_id) is None:
            raise ApiError(status_code=404, code="ORGANIZATION_NOT_FOUND", message="组织不存在")
        if await self._session.get(JobCatalog, payload.job_id) is None:
            raise ApiError(status_code=404, code="JOB_NOT_FOUND", message="职务不存在")
        number = payload.request_number or await next_number(
            self._session,
            sequence_code="RECRUITMENT_REQUEST_NUMBER",
            width=8,
            max_value=99999999,
            prefix="R",
        )
        if await self._session.scalar(
            select(RecruitmentRequest.id).where(RecruitmentRequest.request_number == number)
        ) is not None:
            raise ApiError(status_code=409, code="RECRUITMENT_NUMBER_EXISTS", message="招聘需求编号已存在")
        request = RecruitmentRequest(
            request_number=number,
            organization_id=payload.organization_id,
            job_id=payload.job_id,
            requested_count=payload.requested_count,
            target_month=payload.target_month,
            status="draft",
            reason=payload.reason,
        )
        self._session.add(request)
        await self._session.flush()
        self._audit(
            action="create",
            object_type="recruitment_request",
            object_id=request.id,
            after={"request_number": request.request_number},
        )
        return request

    async def get_recruitment_request(self, request_id: UUID) -> RecruitmentRequest:
        recruitment_request = await self._session.get(RecruitmentRequest, request_id)
        if recruitment_request is None:
            raise ApiError(status_code=404, code="RECRUITMENT_NOT_FOUND", message="招聘需求不存在")
        return recruitment_request

    async def list_recruitment_requests(
        self,
        *,
        status: str | None,
        organization_id: UUID | None,
        job_id: UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[list[RecruitmentRequest], int]:
        filters = []
        if status is not None:
            filters.append(RecruitmentRequest.status == status)
        if organization_id is not None:
            filters.append(RecruitmentRequest.organization_id == organization_id)
        if job_id is not None:
            filters.append(RecruitmentRequest.job_id == job_id)
        total = await self._session.scalar(
            select(func.count()).select_from(RecruitmentRequest).where(*filters)
        )
        items = list(
            (
                await self._session.scalars(
                    select(RecruitmentRequest)
                    .where(*filters)
                    .order_by(RecruitmentRequest.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        return items, total or 0

    async def update_recruitment_request(
        self,
        request_id: UUID,
        payload: RecruitmentRequestUpdate,
    ) -> RecruitmentRequest:
        recruitment_request = await self._session.get(
            RecruitmentRequest,
            request_id,
            with_for_update=True,
        )
        if recruitment_request is None:
            raise ApiError(status_code=404, code="RECRUITMENT_NOT_FOUND", message="招聘需求不存在")
        changes = payload.model_dump(exclude={"change_reason"}, exclude_unset=True)
        next_status = changes.get("status")
        allowed_transitions = {
            "draft": {"draft", "submitted", "cancelled", "closed"},
            "submitted": {"submitted", "cancelled", "closed"},
            "closed": {"closed"},
            "cancelled": {"cancelled"},
        }
        if next_status is not None and next_status not in allowed_transitions.get(
            recruitment_request.status,
            set(),
        ):
            raise ApiError(
                status_code=409,
                code="RECRUITMENT_STATUS_TRANSITION_INVALID",
                message="招聘需求状态不允许这样变更",
            )
        if recruitment_request.status in {"closed", "cancelled"} and any(
            field != "status" for field in changes
        ):
            raise ApiError(
                status_code=409,
                code="RECRUITMENT_REQUEST_FINALIZED",
                message="已关闭或取消的招聘需求不能直接修改",
            )
        before = {
            field: getattr(recruitment_request, field).isoformat()
            if hasattr(getattr(recruitment_request, field), "isoformat")
            else getattr(recruitment_request, field)
            for field in changes
        }
        for field, value in changes.items():
            setattr(recruitment_request, field, value)
        await self._session.flush()
        self._audit(
            action="update",
            object_type="recruitment_request",
            object_id=recruitment_request.id,
            reason=payload.change_reason,
            before=before,
            after={
                field: value.isoformat() if hasattr(value, "isoformat") else value
                for field, value in changes.items()
            },
        )
        return recruitment_request

    async def create_application(self, payload: JobApplicationCreate) -> JobApplication:
        if await self._session.get(Candidate, payload.candidate_id) is None:
            raise ApiError(status_code=404, code="CANDIDATE_NOT_FOUND", message="候选人不存在")
        if await self._session.get(RecruitmentRequest, payload.recruitment_request_id) is None:
            raise ApiError(status_code=404, code="RECRUITMENT_NOT_FOUND", message="招聘需求不存在")
        existing = await self._session.scalar(
            select(JobApplication.id).where(
                JobApplication.candidate_id == payload.candidate_id,
                JobApplication.recruitment_request_id == payload.recruitment_request_id,
            )
        )
        if existing is not None:
            raise ApiError(status_code=409, code="APPLICATION_EXISTS", message="该应聘记录已存在")
        application = JobApplication(
            **payload.model_dump(),
            status="active",
            offer_payload={},
        )
        self._session.add(application)
        await self._session.flush()
        self._audit(
            action="create",
            object_type="job_application",
            object_id=application.id,
            after={"status": application.status},
        )
        return application

    async def create_contract(self, payload: ContractCreate) -> ContractRecord:
        if await self._session.get(Person, payload.person_id) is None:
            raise ApiError(status_code=404, code="PERSON_NOT_FOUND", message="人员不存在")
        if payload.employment_id is not None and await self._session.get(
            Employment, payload.employment_id
        ) is None:
            raise ApiError(status_code=404, code="EMPLOYMENT_NOT_FOUND", message="劳动关系不存在")
        if payload.legal_entity_id is not None and await self._session.get(
            LegalEntity, payload.legal_entity_id
        ) is None:
            raise ApiError(status_code=404, code="LEGAL_ENTITY_NOT_FOUND", message="法人主体不存在")
        if await self._session.scalar(
            select(ContractRecord.id).where(ContractRecord.contract_number == payload.contract_number)
        ) is not None:
            raise ApiError(status_code=409, code="CONTRACT_NUMBER_EXISTS", message="合同编号已存在")
        contract = ContractRecord(**payload.model_dump(), status="active")
        self._session.add(contract)
        await self._session.flush()
        self._audit(
            action="create",
            object_type="contract",
            object_id=contract.id,
            after={"contract_number": contract.contract_number},
        )
        return contract

    async def publish_workflow(self, definition_id: UUID) -> tuple[int, str]:
        definition = await self._session.get(WorkflowDefinition, definition_id, with_for_update=True)
        if definition is None:
            raise ApiError(status_code=404, code="WORKFLOW_NOT_FOUND", message="流程定义不存在")
        version = await self._session.scalar(
            select(WorkflowVersion)
            .where(WorkflowVersion.workflow_definition_id == definition.id)
            .order_by(WorkflowVersion.version.desc())
            .limit(1)
        )
        if version is None:
            raise ApiError(status_code=422, code="WORKFLOW_VERSION_MISSING", message="流程版本不存在")
        nodes = version.definition.get("nodes", [])
        node_types = {node.get("node_type") for node in nodes}
        if "start" not in node_types or "end" not in node_types:
            raise ApiError(status_code=422, code="WORKFLOW_BOUNDARY_MISSING", message="流程必须包含开始和结束节点")
        version.status = "active"
        definition.active_version = version.version
        definition.status = "active"
        self._audit(
            action="publish",
            object_type="workflow_definition",
            object_id=definition.id,
            after={"version": version.version},
        )
        return version.version, definition.status

    async def start_workflow(self, payload: WorkflowInstanceCreate) -> WorkflowInstance:
        definition = await self._session.get(WorkflowDefinition, payload.workflow_definition_id)
        if definition is None or definition.status != "active" or definition.active_version is None:
            raise ApiError(status_code=422, code="WORKFLOW_NOT_ACTIVE", message="流程定义尚未发布")
        version = await self._session.scalar(
            select(WorkflowVersion).where(
                WorkflowVersion.workflow_definition_id == definition.id,
                WorkflowVersion.version == definition.active_version,
                WorkflowVersion.status == "active",
            )
        )
        if version is None:
            raise ApiError(status_code=422, code="WORKFLOW_VERSION_NOT_ACTIVE", message="生效流程版本不存在")
        start_node = next(
            (node for node in version.definition.get("nodes", []) if node.get("node_type") == "start"),
            None,
        )
        number = await next_number(
            self._session,
            sequence_code="WORKFLOW_INSTANCE_NUMBER",
            width=10,
            max_value=9999999999,
            prefix="W",
        )
        instance = WorkflowInstance(
            instance_number=number,
            workflow_version_id=version.id,
            business_object_type=payload.business_object_type,
            business_object_id=payload.business_object_id,
            status="running",
            current_node_code=start_node.get("code") if start_node else None,
            started_by=self._actor_id,
            started_at=datetime.now(UTC),
            context=payload.context,
        )
        self._session.add(instance)
        await self._session.flush()
        self._audit(
            action="start",
            object_type="workflow_instance",
            object_id=instance.id,
            after={"instance_number": instance.instance_number},
        )
        return instance

    async def create_hr_event(self, payload: HrEventCreate) -> HrEvent:
        number = await next_number(
            self._session,
            sequence_code="HR_EVENT_NUMBER",
            width=10,
            max_value=9999999999,
            prefix="E",
        )
        event = HrEvent(
            event_number=number,
            event_type=payload.event_type,
            object_type=payload.object_type,
            object_id=payload.object_id,
            effective_date=payload.effective_date,
            status="ready" if payload.execution_mode == "direct" else "pending_approval",
            source="api",
            reason=payload.reason,
            before_payload=payload.before_payload,
            planned_payload=payload.planned_payload,
            actual_payload={},
            workflow_instance_id=payload.workflow_instance_id,
            attempts=0,
            version=1,
        )
        self._session.add(event)
        await self._session.flush()
        self._audit(
            action="create",
            object_type="hr_event",
            object_id=event.id,
            after={"event_number": event.event_number, "status": event.status},
        )
        return event

    async def rollback_hr_event(
        self,
        event_id: UUID,
        payload: HrEventRollbackCreate,
    ) -> HrEvent:
        original = await self._session.get(HrEvent, event_id)
        if original is None:
            raise ApiError(status_code=404, code="HR_EVENT_NOT_FOUND", message="人事事件不存在")
        number = await next_number(
            self._session,
            sequence_code="HR_EVENT_NUMBER",
            width=10,
            max_value=9999999999,
            prefix="E",
        )
        rollback = HrEvent(
            event_number=number,
            event_type=f"ROLLBACK_{original.event_type}",
            object_type=original.object_type,
            object_id=original.object_id,
            effective_date=payload.effective_date,
            status="ready" if payload.execution_mode == "direct" else "pending_approval",
            source="rollback",
            reason=payload.reason,
            before_payload=original.actual_payload,
            planned_payload=original.before_payload,
            actual_payload={},
            related_event_id=original.id,
            attempts=0,
            version=1,
        )
        self._session.add(rollback)
        await self._session.flush()
        self._audit(
            action="rollback_requested",
            object_type="hr_event",
            object_id=rollback.id,
            after={"related_event_id": str(original.id), "status": rollback.status},
        )
        return rollback
