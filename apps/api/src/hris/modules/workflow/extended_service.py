# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.contracts.workflow import (
    NodeDwellStat,
    WorkflowDecisionCommand,
    WorkflowEngine,
    WorkflowStartCommand,
)
from hris.core.config import get_settings
from hris.core.errors import ApiError
from hris.core.personnel_security import (
    SensitiveDataError,
    normalize_document_number,
    protector_from_settings,
)
from hris.core.search import like_pattern
from hris.modules.platform.numbering import next_number
from hris.modules.workforce.batch_change_models import BATCH_CHANGE_BUSINESS_OBJECT_TYPE
from hris.modules.workflow.engine import resolve_engine
from hris.modules.workflow.extended_schemas import (
    ApplicationHireCreate,
    CandidateCreate,
    CandidateUpdate,
    ContractActionCreate,
    ContractCreate,
    ContractUpdate,
    HrEventCreate,
    HrEventRollbackCreate,
    JobApplicationCreate,
    JobApplicationUpdate,
    RecruitmentRequestCreate,
    RecruitmentRequestUpdate,
    WorkflowInstanceCreate,
    WorkflowTaskDecision,
)
from hris.modules.workflow.models import (
    ApplicationHireConversion,
    Candidate,
    ContractRecord,
    JobApplication,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowTask,
    WorkflowTransition,
    WorkflowVersion,
)
from hris.modules.workforce.concurrent_positions_service import ConcurrentPositionService
from hris.modules.workforce.extended_schemas import (
    EmploymentAssignmentCreate,
    EmploymentCreate,
    PersonCreate,
)
from hris.modules.workforce.extended_service import ExtendedWorkforceService
from hris.modules.workforce.personnel_schemas import PersonDocumentCreate
from hris.modules.workforce.personnel_service import PersonnelService
from hris.modules.workforce.models import (
    AgreementRelationship,
    AuditLog,
    Employment,
    EmploymentAssignment,
    HrEvent,
    JobCatalog,
    LegalEntity,
    Organization,
    OrganizationPersonRelation,
    Person,
    RecruitmentRequest,
)


class LifecycleService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        actor_id: UUID,
        trace_id: str,
    ) -> None:
        self._session = session
        self._actor_id = actor_id
        self._trace_id = trace_id
        # Requirement: D-108 — 流程语义（状态机 / 选路 / 任务分派）在引擎里：
        # 装上私有包用商业实现，没装用公开壳（读直通数据库，写统一拒绝）。
        # 引擎通过 `on_workflow_finished` 回调把审批结论交回公开侧落地业务对象。
        self.engine: WorkflowEngine = resolve_engine(
            session,
            actor_id=actor_id,
            trace_id=trace_id,
            business_object_handler=self,
        )

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

    async def list_candidates(
        self,
        *,
        status: str | None,
        search: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Candidate], int]:
        filters = []
        if status is not None:
            filters.append(Candidate.status == status)
        if search:
            # Requirement: D-112 — 搜索词按字面量匹配，转义 LIKE 通配符。
            term = like_pattern(search)
            filters.append(
                or_(
                    Candidate.candidate_number.ilike(term, escape="\\"),
                    Candidate.display_name.ilike(term, escape="\\"),
                )
            )
        total = await self._session.scalar(
            select(func.count()).select_from(Candidate).where(*filters)
        )
        items = list(
            (
                await self._session.scalars(
                    select(Candidate)
                    .where(*filters)
                    .order_by(Candidate.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        return items, total or 0

    async def get_candidate(self, candidate_id: UUID) -> Candidate:
        candidate = await self._session.get(Candidate, candidate_id)
        if candidate is None:
            raise ApiError(status_code=404, code="CANDIDATE_NOT_FOUND", message="candidate not found")
        return candidate

    async def update_candidate(
        self,
        candidate_id: UUID,
        payload: CandidateUpdate,
    ) -> Candidate:
        candidate = await self._session.get(Candidate, candidate_id, with_for_update=True)
        if candidate is None:
            raise ApiError(status_code=404, code="CANDIDATE_NOT_FOUND", message="candidate not found")
        changes = payload.model_dump(exclude={"change_reason"}, exclude_unset=True)
        linked_person_id = changes.get("linked_person_id")
        if linked_person_id is not None and await self._session.get(Person, linked_person_id) is None:
            raise ApiError(status_code=404, code="PERSON_NOT_FOUND", message="person not found")
        before = {field: getattr(candidate, field) for field in changes}
        for field, value in changes.items():
            setattr(candidate, field, value)
        await self._session.flush()
        await self._session.refresh(candidate)
        self._audit(
            action="update",
            object_type="candidate",
            object_id=candidate.id,
            reason=payload.change_reason,
            before={field: str(value) if isinstance(value, UUID) else value for field, value in before.items()},
            after={field: str(value) if isinstance(value, UUID) else value for field, value in changes.items()},
        )
        return candidate

    async def create_recruitment_request(
        self,
        payload: RecruitmentRequestCreate,
    ) -> RecruitmentRequest:
        if await self._session.get(Organization, payload.organization_id) is None:
            raise ApiError(status_code=404, code="ORGANIZATION_NOT_FOUND", message="组织不存在")
        workforce = ExtendedWorkforceService(
            self._session,
            actor_id=self._actor_id,
            trace_id=self._trace_id,
        )
        business_today = self._business_today()
        target_date = (
            max(payload.target_month, business_today)
            if payload.target_month is not None
            else business_today
        )
        await workforce.ensure_job_effective(payload.job_id, target_date)
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
        if "target_month" in changes:
            business_today = self._business_today()
            target_month = changes["target_month"]
            target_date = (
                max(target_month, business_today)
                if target_month is not None
                else business_today
            )
            workforce = ExtendedWorkforceService(
                self._session,
                actor_id=self._actor_id,
                trace_id=self._trace_id,
            )
            await workforce.ensure_job_effective(
                recruitment_request.job_id,
                target_date,
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

    async def list_applications(
        self,
        *,
        status: str | None,
        candidate_id: UUID | None,
        recruitment_request_id: UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[list[JobApplication], int]:
        filters = []
        if status is not None:
            filters.append(JobApplication.status == status)
        if candidate_id is not None:
            filters.append(JobApplication.candidate_id == candidate_id)
        if recruitment_request_id is not None:
            filters.append(JobApplication.recruitment_request_id == recruitment_request_id)
        total = await self._session.scalar(
            select(func.count()).select_from(JobApplication).where(*filters)
        )
        items = list(
            (
                await self._session.scalars(
                    select(JobApplication)
                    .where(*filters)
                    .order_by(JobApplication.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        return items, total or 0

    async def get_application(self, application_id: UUID) -> JobApplication:
        application = await self._session.get(JobApplication, application_id)
        if application is None:
            raise ApiError(status_code=404, code="APPLICATION_NOT_FOUND", message="application not found")
        return application

    async def update_application(
        self,
        application_id: UUID,
        payload: JobApplicationUpdate,
    ) -> JobApplication:
        application = await self._session.get(JobApplication, application_id, with_for_update=True)
        if application is None:
            raise ApiError(status_code=404, code="APPLICATION_NOT_FOUND", message="application not found")
        changes = payload.model_dump(exclude={"change_reason"}, exclude_unset=True)
        allowed_transitions = {
            "active": {"active", "screening", "interview", "rejected", "withdrawn"},
            "screening": {"screening", "interview", "rejected", "withdrawn"},
            "interview": {"interview", "offer", "rejected", "withdrawn"},
            "offer": {"offer", "hired", "rejected", "withdrawn"},
            "hired": {"hired"},
            "rejected": {"rejected"},
            "withdrawn": {"withdrawn"},
        }
        next_status = changes.get("status")
        if (
            application.status != "hired"
            and "hired" in {next_status, changes.get("current_stage")}
        ):
            raise ApiError(
                status_code=409,
                code="APPLICATION_HIRE_COMMAND_REQUIRED",
                message="use the application hire command to create pending-start records",
            )
        if next_status is not None and next_status not in allowed_transitions.get(application.status, set()):
            raise ApiError(
                status_code=409,
                code="APPLICATION_STATUS_TRANSITION_INVALID",
                message="application status transition is not allowed",
            )
        before = {field: getattr(application, field) for field in changes}
        for field, value in changes.items():
            setattr(application, field, value)
        await self._session.flush()
        self._audit(
            action="update",
            object_type="job_application",
            object_id=application.id,
            reason=payload.change_reason,
            before=before,
            after=changes,
        )
        return application

    def _hire_checksum(self, application_id: UUID, payload: ApplicationHireCreate) -> str:
        value = {
            "application_id": str(application_id),
            **payload.model_dump(
                mode="json",
                exclude={"idempotency_key", "primary_document_number"},
            ),
        }
        if payload.primary_document_number is not None:
            try:
                value["primary_document_number_digest"] = protector_from_settings(
                    get_settings()
                ).digest(
                    payload.primary_document_number,
                    field_code="document_number",
                    normalizer=normalize_document_number,
                )
            except SensitiveDataError:
                raise ApiError(
                    status_code=503,
                    code="PERSONNEL_SENSITIVE_KEY_UNAVAILABLE",
                    message="人员敏感字段密钥未就绪，已拒绝本次操作",
                ) from None
        canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _hr_event_checksum(operation: str, value: dict[str, Any]) -> str:
        canonical = json.dumps(
            {"operation": operation, **value},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    async def _lock_idempotency(self, key: UUID) -> None:
        lock_key = key.int & ((1 << 63) - 1)
        await self._session.execute(select(func.pg_advisory_xact_lock(lock_key)))

    async def hire_application(
        self,
        application_id: UUID,
        payload: ApplicationHireCreate,
    ) -> ApplicationHireConversion:
        checksum = self._hire_checksum(application_id, payload)
        await self._lock_idempotency(payload.idempotency_key)
        existing_key = await self._session.scalar(
            select(ApplicationHireConversion).where(
                ApplicationHireConversion.idempotency_key == payload.idempotency_key
            )
        )
        if existing_key is not None:
            if existing_key.request_checksum != checksum:
                raise ApiError(
                    status_code=409,
                    code="IDEMPOTENCY_KEY_REUSED",
                    message="idempotency key has already been used with different hire data",
                )
            return existing_key

        application = await self._session.get(
            JobApplication,
            application_id,
            with_for_update=True,
        )
        if application is None:
            raise ApiError(
                status_code=404,
                code="APPLICATION_NOT_FOUND",
                message="application not found",
            )
        existing_application = await self._session.scalar(
            select(ApplicationHireConversion).where(
                ApplicationHireConversion.application_id == application_id
            )
        )
        if existing_application is not None:
            raise ApiError(
                status_code=409,
                code="APPLICATION_ALREADY_CONVERTED",
                message="application has already been converted to pending-start records",
            )
        if application.status not in {"offer", "hired"}:
            raise ApiError(
                status_code=409,
                code="APPLICATION_NOT_READY_FOR_HIRE",
                message="application must be at offer stage before hire confirmation",
            )

        candidate = await self._session.get(
            Candidate,
            application.candidate_id,
            with_for_update=True,
        )
        if candidate is None:
            raise ApiError(
                status_code=404,
                code="CANDIDATE_NOT_FOUND",
                message="candidate not found",
            )
        if candidate.status == "inactive":
            raise ApiError(
                status_code=409,
                code="CANDIDATE_INACTIVE",
                message="inactive candidate cannot be hired",
            )
        recruitment = await self._session.get(
            RecruitmentRequest,
            application.recruitment_request_id,
        )
        if recruitment is None:
            raise ApiError(
                status_code=404,
                code="RECRUITMENT_NOT_FOUND",
                message="recruitment request not found",
            )
        if recruitment.status == "cancelled":
            raise ApiError(
                status_code=409,
                code="RECRUITMENT_CANCELLED",
                message="cancelled recruitment request cannot produce a hire",
            )

        person_id = payload.existing_person_id or candidate.linked_person_id
        if (
            payload.existing_person_id is not None
            and candidate.linked_person_id is not None
            and payload.existing_person_id != candidate.linked_person_id
        ):
            raise ApiError(
                status_code=409,
                code="CANDIDATE_PERSON_MISMATCH",
                message="candidate is already linked to another person",
            )

        workforce = ExtendedWorkforceService(
            self._session,
            actor_id=self._actor_id,
            trace_id=self._trace_id,
        )
        if person_id is None:
            person = await workforce.create_person(
                PersonCreate(
                    legal_name=candidate.display_name,
                    display_name=candidate.display_name,
                    gender_code=payload.gender_code,
                    birth_date=payload.birth_date,
                    nationality_code=payload.nationality_code,
                    country_code=payload.country_code,
                    reserve_employee_number=True,
                    change_reason=payload.reason,
                )
            )
        else:
            person = await self._session.get(Person, person_id, with_for_update=True)
            if person is None:
                raise ApiError(
                    status_code=404,
                    code="PERSON_NOT_FOUND",
                    message="existing person not found",
                )

        if payload.primary_document_number is not None:
            personnel = PersonnelService(
                self._session,
                actor_id=self._actor_id,
                trace_id=self._trace_id,
            )
            await personnel.create_document(
                person.id,
                PersonDocumentCreate(
                    document_type_code=payload.primary_document_type_code or "",
                    document_number=payload.primary_document_number,
                    issuing_country_code=payload.primary_document_issuing_country_code or "",
                    issue_date=payload.primary_document_issue_date,
                    expiry_date=payload.primary_document_expiry_date,
                    is_primary=True,
                    verification_status="verified",
                    effective_from=payload.planned_start_date,
                    change_reason=payload.reason,
                ),
            )

        employment = await workforce.create_employment(
            EmploymentCreate(
                person_id=person.id,
                employee_type_code=payload.employee_type_code,
                planned_start_date=payload.planned_start_date,
                probation_end_date=payload.probation_end_date,
                contract_legal_entity_id=payload.contract_legal_entity_id,
                payroll_legal_entity_id=payload.payroll_legal_entity_id,
                social_insurance_legal_entity_id=payload.social_insurance_legal_entity_id,
                tax_legal_entity_id=payload.tax_legal_entity_id,
                change_reason=payload.reason,
            )
        )
        assignment = await workforce.create_assignment(
            EmploymentAssignmentCreate(
                employment_id=employment.id,
                organization_id=recruitment.organization_id,
                job_id=recruitment.job_id,
                relation_type="primary",
                effective_from=payload.planned_start_date,
                change_reason=payload.reason,
            )
        )

        candidate_before = {
            "status": candidate.status,
            "linked_person_id": (
                str(candidate.linked_person_id)
                if candidate.linked_person_id is not None
                else None
            ),
        }
        application_before = {
            "status": application.status,
            "current_stage": application.current_stage,
        }
        candidate.status = "converted"
        candidate.linked_person_id = person.id
        application.status = "hired"
        application.current_stage = "hired"
        application.offer_payload = {
            **application.offer_payload,
            "result": "accepted",
            "planned_start_date": payload.planned_start_date.isoformat(),
        }
        converted_at = datetime.now(UTC)
        conversion = ApplicationHireConversion(
            application_id=application.id,
            candidate_id=candidate.id,
            person_id=person.id,
            employment_id=employment.id,
            assignment_id=assignment.id,
            idempotency_key=payload.idempotency_key,
            request_checksum=checksum,
            planned_start_date=payload.planned_start_date,
            employee_type_code=payload.employee_type_code,
            converted_by=self._actor_id,
            converted_at=converted_at,
        )
        self._session.add(conversion)
        await self._session.flush()
        self._audit(
            action="hire",
            object_type="job_application",
            object_id=application.id,
            reason=payload.reason,
            before=application_before,
            after={
                "status": "hired",
                "person_id": str(person.id),
                "employment_id": str(employment.id),
                "assignment_id": str(assignment.id),
            },
        )
        self._audit(
            action="convert",
            object_type="candidate",
            object_id=candidate.id,
            reason=payload.reason,
            before=candidate_before,
            after={"status": "converted", "linked_person_id": str(person.id)},
        )
        self._audit(
            action="create",
            object_type="application_hire_conversion",
            object_id=conversion.id,
            reason=payload.reason,
            after={
                "application_id": str(application.id),
                "person_id": str(person.id),
                "employment_id": str(employment.id),
                "assignment_id": str(assignment.id),
                "planned_start_date": payload.planned_start_date.isoformat(),
            },
        )
        return conversion

    async def create_contract(self, payload: ContractCreate) -> ContractRecord:
        if await self._session.get(Person, payload.person_id) is None:
            raise ApiError(status_code=404, code="PERSON_NOT_FOUND", message="person not found")
        employment = None
        if payload.employment_id is not None:
            employment = await self._session.get(Employment, payload.employment_id)
            if employment is None:
                raise ApiError(
                    status_code=404,
                    code="EMPLOYMENT_NOT_FOUND",
                    message="employment not found",
                )
            if employment.person_id != payload.person_id:
                raise ApiError(
                    status_code=422,
                    code="CONTRACT_RELATION_PERSON_MISMATCH",
                    message="employment does not belong to the contract person",
                )
        agreement = None
        if payload.agreement_relationship_id is not None:
            agreement = await self._session.get(
                AgreementRelationship,
                payload.agreement_relationship_id,
            )
            if agreement is None:
                raise ApiError(
                    status_code=404,
                    code="AGREEMENT_RELATIONSHIP_NOT_FOUND",
                    message="agreement relationship not found",
                )
            if agreement.person_id != payload.person_id:
                raise ApiError(
                    status_code=422,
                    code="CONTRACT_RELATION_PERSON_MISMATCH",
                    message="agreement relationship does not belong to the contract person",
                )
        legal_entity_id = payload.legal_entity_id
        if legal_entity_id is None and employment is not None:
            legal_entity_id = employment.contract_legal_entity_id
        if legal_entity_id is None and agreement is not None:
            legal_entity_id = agreement.legal_entity_id
        if legal_entity_id is not None and await self._session.get(
            LegalEntity, legal_entity_id
        ) is None:
            raise ApiError(
                status_code=404,
                code="LEGAL_ENTITY_NOT_FOUND",
                message="legal entity not found",
            )
        if await self._session.scalar(
            select(ContractRecord.id).where(ContractRecord.contract_number == payload.contract_number)
        ) is not None:
            raise ApiError(
                status_code=409,
                code="CONTRACT_NUMBER_EXISTS",
                message="contract number already exists",
            )
        values = payload.model_dump(exclude={"change_reason"})
        values["legal_entity_id"] = legal_entity_id
        contract = ContractRecord(
            **values,
            predecessor_contract_id=None,
            version=1,
            status="active",
        )
        self._session.add(contract)
        await self._session.flush()
        self._audit(
            action="create",
            object_type="contract",
            object_id=contract.id,
            reason=payload.change_reason,
            after={
                "contract_number": contract.contract_number,
                "employment_id": str(contract.employment_id) if contract.employment_id else None,
                "agreement_relationship_id": (
                    str(contract.agreement_relationship_id)
                    if contract.agreement_relationship_id
                    else None
                ),
                "version": contract.version,
            },
        )
        return contract

    async def list_contracts(
        self,
        *,
        status: str | None,
        person_id: UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[list[ContractRecord], int]:
        filters = []
        if status is not None:
            filters.append(ContractRecord.status == status)
        if person_id is not None:
            filters.append(ContractRecord.person_id == person_id)
        total = await self._session.scalar(
            select(func.count()).select_from(ContractRecord).where(*filters)
        )
        items = list(
            (
                await self._session.scalars(
                    select(ContractRecord)
                    .where(*filters)
                    .order_by(ContractRecord.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        return items, total or 0

    async def get_contract(self, contract_id: UUID) -> ContractRecord:
        contract = await self._session.get(ContractRecord, contract_id)
        if contract is None:
            raise ApiError(status_code=404, code="CONTRACT_NOT_FOUND", message="contract not found")
        return contract

    async def update_contract(
        self,
        contract_id: UUID,
        payload: ContractUpdate,
    ) -> ContractRecord:
        contract = await self._session.get(ContractRecord, contract_id, with_for_update=True)
        if contract is None:
            raise ApiError(status_code=404, code="CONTRACT_NOT_FOUND", message="contract not found")
        changes = payload.model_dump(exclude={"change_reason"}, exclude_unset=True)
        legal_entity_id = changes.get("legal_entity_id")
        if legal_entity_id is not None and await self._session.get(
            LegalEntity,
            legal_entity_id,
        ) is None:
            raise ApiError(
                status_code=404,
                code="LEGAL_ENTITY_NOT_FOUND",
                message="legal entity not found",
            )
        before = {
            field: value.isoformat() if isinstance(value, date) else value
            for field in changes
            for value in [getattr(contract, field)]
        }
        for field, value in changes.items():
            setattr(contract, field, value)
        contract.version += 1
        await self._session.flush()
        self._audit(
            action="update",
            object_type="contract",
            object_id=contract.id,
            reason=payload.change_reason,
            before=before,
            after={
                field: value.isoformat() if isinstance(value, date) else value
                for field, value in changes.items()
            } | {"version": contract.version},
        )
        return contract

    async def create_contract_action(
        self,
        contract_id: UUID,
        payload: ContractActionCreate,
    ) -> HrEvent:
        event_types = {
            "amendment": "CONTRACT_AMENDMENT",
            "renewal": "CONTRACT_RENEWAL",
            "termination": "CONTRACT_TERMINATION",
            "cancellation": "CONTRACT_CANCELLATION",
        }
        planned_payload: dict[str, Any] = {}
        if payload.amendment is not None:
            planned_payload = payload.amendment.model_dump(
                mode="json",
                exclude_unset=True,
            )
        elif payload.renewal is not None:
            planned_payload = payload.renewal.model_dump(mode="json")
        return await self.create_hr_event(
            HrEventCreate(
                idempotency_key=payload.idempotency_key,
                event_type=event_types[payload.action_type],
                object_type="contract",
                object_id=contract_id,
                effective_date=payload.effective_date,
                execution_mode=payload.execution_mode,
                reason=payload.reason,
                planned_payload=planned_payload,
                workflow_instance_id=payload.workflow_instance_id,
            )
        )

    async def list_contract_expiry_alerts(
        self,
        *,
        as_of: date | None,
        days_ahead: int,
    ) -> tuple[list[dict[str, Any]], date]:
        alert_date = as_of or self._business_today()
        contracts = list(
            (
                await self._session.scalars(
                    select(ContractRecord)
                    .where(
                        ContractRecord.status == "active",
                        ContractRecord.effective_to.is_not(None),
                        ContractRecord.effective_to >= alert_date,
                        ContractRecord.effective_to <= alert_date + timedelta(days=days_ahead),
                    )
                    .order_by(ContractRecord.effective_to, ContractRecord.contract_number)
                )
            ).all()
        )
        items = []
        for contract in contracts:
            assert contract.effective_to is not None
            days_remaining = (contract.effective_to - alert_date).days
            if days_remaining > contract.expiry_notice_days:
                continue
            items.append(
                {
                    "contract_id": contract.id,
                    "contract_number": contract.contract_number,
                    "person_id": contract.person_id,
                    "effective_to": contract.effective_to,
                    "expiry_notice_days": contract.expiry_notice_days,
                    "days_remaining": days_remaining,
                    "status": contract.status,
                }
            )
        return items, alert_date

    async def process_contract_statuses(self, as_of: date | None) -> list[UUID]:
        process_date = as_of or self._business_today()
        contracts = list(
            (
                await self._session.scalars(
                    select(ContractRecord)
                    .where(
                        ContractRecord.status == "active",
                        ContractRecord.effective_to.is_not(None),
                        ContractRecord.effective_to < process_date,
                    )
                    .with_for_update()
                )
            ).all()
        )
        processed: list[UUID] = []
        for contract in contracts:
            before = self._contract_snapshot(contract)
            contract.status = "expired"
            contract.version += 1
            processed.append(contract.id)
            self._audit(
                action="expire",
                object_type="contract",
                object_id=contract.id,
                reason=f"status refresh as of {process_date.isoformat()}",
                before=before,
                after=self._contract_snapshot(contract),
            )
        await self._session.flush()
        return processed

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
        """发起流程实例。

        Requirement: D-108 — 写路径经引擎：装上私有包时由商业引擎执行；
        公开仓模式下 Demo 引擎统一拒绝（403 / `code=LICENSE_REQUIRED`）。
        """

        return await self.engine.start_workflow(
            WorkflowStartCommand(
                workflow_definition_id=payload.workflow_definition_id,
                business_object_type=payload.business_object_type,
                business_object_id=payload.business_object_id,
                context=payload.context,
            )
        )

    async def list_workflow_instances(
        self,
        *,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[WorkflowInstance], int]:
        """流程实例列表（读路径：与商业版共用同一份查询代码）。"""

        return await self.engine.list_instances(
            status=status,
            limit=limit,
            offset=offset,
        )

    async def workflow_instance_detail(
        self,
        instance_id: UUID,
    ) -> tuple[WorkflowInstance, list[WorkflowTask]]:
        """流程实例详情（读路径：与商业版共用同一份查询代码）。"""

        return await self.engine.get_instance_detail(instance_id)

    async def list_workflow_tasks(
        self,
        *,
        status: str | None,
        assignee_ref: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[WorkflowTask], int]:
        """审批任务列表（读路径：与商业版共用同一份查询代码）。"""

        return await self.engine.list_tasks(
            status=status,
            assignee_ref=assignee_ref,
            limit=limit,
            offset=offset,
        )

    async def decide_workflow_task(
        self,
        task_id: UUID,
        payload: WorkflowTaskDecision,
    ) -> WorkflowTask:
        """兼容入口：只接受同意 / 驳回。

        Requirement: D-095 — 撤销、退回各自有独立接口，不与驳回共用入口，
        三种语义在接口层就是分开的。
        """

        return await self.engine.decide_task(
            task_id,
            WorkflowDecisionCommand(
                decision=payload.decision,
                comment=payload.comment,
            ),
        )

    async def approve_workflow_task(
        self,
        task_id: UUID,
        comment: str | None = None,
    ) -> WorkflowTask:
        return await self.engine.approve_task(task_id, comment=comment)

    async def reject_workflow_task(
        self,
        task_id: UUID,
        comment: str | None = None,
    ) -> WorkflowTask:
        return await self.engine.reject_task(task_id, comment=comment)

    async def rollback_workflow_task(
        self,
        task_id: UUID,
        comment: str | None = None,
    ) -> WorkflowTask:
        """撤销：终止流程，实例落到「已撤销」，与驳回的「已驳回」不是同一个终态。"""

        return await self.engine.rollback_task(task_id, comment=comment)

    async def cancel_workflow_task(
        self,
        task_id: UUID,
        comment: str | None = None,
    ) -> WorkflowTask:
        """取消：终止流程，实例落到「已取消」。"""

        return await self.engine.cancel_task(task_id, comment=comment)

    async def transfer_workflow_task(
        self,
        task_id: UUID,
        *,
        assignee_type: str,
        assignee_ref: str,
        comment: str | None = None,
    ) -> WorkflowTask:
        """转办：把当前任务改派给其他办理人，节点不变。"""

        return await self.engine.transfer_task(
            task_id,
            assignee_type=assignee_type,
            assignee_ref=assignee_ref,
            comment=comment,
        )

    async def add_sign_workflow_task(
        self,
        task_id: UUID,
        *,
        assignee_type: str,
        assignee_ref: str,
        comment: str | None = None,
    ) -> WorkflowTask:
        """加签：在当前节点追加审批人，节点不变。"""

        return await self.engine.add_sign_task(
            task_id,
            assignee_type=assignee_type,
            assignee_ref=assignee_ref,
            comment=comment,
        )

    async def return_workflow_task(
        self,
        task_id: UUID,
        comment: str | None = None,
    ) -> WorkflowTask:
        """退回：回到上一个审批节点，实例落到「已退回」。"""

        return await self.engine.return_task(task_id, comment=comment)

    async def list_workflow_transitions(
        self,
        instance_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[WorkflowTransition], int]:
        """流转历史（读路径：与商业版共用同一份查询代码）。"""

        return await self.engine.list_transitions(
            instance_id,
            limit=limit,
            offset=offset,
        )

    async def workflow_node_dwell(
        self,
        instance_id: UUID,
        *,
        node_code: str | None = None,
    ) -> tuple[WorkflowInstance, list[NodeDwellStat]]:
        """节点停留统计（读路径：与商业版共用同一份查询代码）。"""

        return await self.engine.get_node_dwell(instance_id, node_code=node_code)

    async def on_workflow_finished(
        self,
        instance: WorkflowInstance,
        *,
        approved: bool,
    ) -> None:
        """引擎回调：流程实例终止时回写业务对象。

        Requirement: D-108 — 流程语义在引擎（可能位于私有包）里，
        业务对象的落地留在公开侧（人事事件 / 批量异动方案），两侧用这一个回调衔接。
        """

        await self._finish_workflow_business_object(instance, approved=approved)

    async def _finish_workflow_business_object(
        self,
        instance: WorkflowInstance,
        *,
        approved: bool,
    ) -> None:
        # Requirement: HR-BATCH-002 — 业务对象联动按类型分派，而不是为每类业务对象各写一段分支。
        # 批量异动方案整批共用同一个流程实例，审批结论落到整批明细上。
        if instance.business_object_type == BATCH_CHANGE_BUSINESS_OBJECT_TYPE:
            # 局部导入：批量异动服务复用了本模块的 LifecycleService，模块级导入会形成环。
            from hris.modules.workforce.batch_change_service import BatchChangeService

            batch_service = BatchChangeService(
                self._session,
                actor_id=self._actor_id,
                trace_id=self._trace_id,
            )
            if approved:
                await batch_service.mark_approved(instance.business_object_id)
            else:
                await batch_service.mark_rejected(instance.business_object_id)
            return
        if instance.business_object_type != "hr_event":
            return
        event = await self._session.get(HrEvent, instance.business_object_id, with_for_update=True)
        if event is None:
            raise ApiError(status_code=422, code="HR_EVENT_NOT_FOUND", message="流程关联的人事事件不存在")
        event.status = "ready" if approved else "rejected"
        if approved:
            await self._execute_hr_event_if_due(event)

    @staticmethod
    def _business_today() -> date:
        return datetime.now(ZoneInfo(get_settings().business_timezone)).date()

    async def _validate_hr_event(self, payload: HrEventCreate) -> None:
        employment_events = {
            "ONBOARDING",
            "CONFIRMATION",
            "TERMINATION",
            "WITHDRAWAL",
            "EMPLOYMENT_CORRECTION",
            "TRANSFER",
            "CONCURRENT_ASSIGNMENT",
            "SECONDMENT",
            "END_ASSIGNMENT",
        }
        contract_events = {
            "CONTRACT_AMENDMENT",
            "CONTRACT_RENEWAL",
            "CONTRACT_TERMINATION",
            "CONTRACT_CANCELLATION",
        }
        if payload.object_type == "employment":
            if payload.event_type not in employment_events:
                raise ApiError(
                    status_code=422,
                    code="HR_EVENT_TYPE_UNSUPPORTED",
                    message="event type is not registered for employment",
                )
            employment = await self._session.get(
                Employment,
                payload.object_id,
                with_for_update=payload.event_type == "ONBOARDING",
            )
            if employment is None:
                raise ApiError(
                    status_code=404,
                    code="EMPLOYMENT_NOT_FOUND",
                    message="employment not found",
                )
            if payload.event_type == "ONBOARDING":
                if employment.status != "pending_start":
                    raise ApiError(
                        status_code=409,
                        code="ONBOARDING_EMPLOYMENT_STATUS_INVALID",
                        message="only pending-start employment can be onboarded",
                    )
                open_event = await self._session.scalar(
                    select(HrEvent.id).where(
                        HrEvent.object_type == "employment",
                        HrEvent.object_id == payload.object_id,
                        HrEvent.event_type == "ONBOARDING",
                        HrEvent.status.in_(("pending_approval", "ready", "scheduled", "failed")),
                    )
                )
                if open_event is not None:
                    raise ApiError(
                        status_code=409,
                        code="ONBOARDING_EVENT_ALREADY_OPEN",
                        message="an unfinished onboarding event already exists",
                    )
            if payload.event_type in {"TRANSFER", "CONCURRENT_ASSIGNMENT", "SECONDMENT"}:
                if not payload.planned_payload.get("organization_id") or not payload.planned_payload.get("job_id"):
                    raise ApiError(
                        status_code=422,
                        code="HR_EVENT_ASSIGNMENT_TARGET_REQUIRED",
                        message="organization and job are required",
                    )
                try:
                    target_job_id = UUID(str(payload.planned_payload["job_id"]))
                except (TypeError, ValueError) as error:
                    raise ApiError(
                        status_code=422,
                        code="HR_EVENT_JOB_ID_INVALID",
                        message="job_id must be a valid UUID",
                    ) from error
                workforce = ExtendedWorkforceService(
                    self._session,
                    actor_id=self._actor_id,
                    trace_id=self._trace_id,
                )
                await workforce.ensure_job_effective(
                    target_job_id,
                    payload.effective_date,
                )
            # Requirement: D-104 — END_ASSIGNMENT 既可结束 employment 级任职，
            # 也可结束 person 级兼岗；两者只能给其一。
            if payload.event_type == "END_ASSIGNMENT" and not (
                payload.planned_payload.get("assignment_id")
                or payload.planned_payload.get("concurrent_position_id")
            ):
                raise ApiError(
                    status_code=422,
                    code="HR_EVENT_ASSIGNMENT_REQUIRED",
                    message="assignment_id is required",
                )
            return
        if payload.object_type != "contract":
            raise ApiError(
                status_code=422,
                code="HR_EVENT_OBJECT_TYPE_INVALID",
                message="event object must be employment or contract",
            )
        if payload.event_type not in contract_events:
            raise ApiError(
                status_code=422,
                code="HR_EVENT_TYPE_UNSUPPORTED",
                message="event type is not registered for contract",
            )
        contract = await self._session.get(ContractRecord, payload.object_id)
        if contract is None:
            raise ApiError(
                status_code=404,
                code="CONTRACT_NOT_FOUND",
                message="contract not found",
            )
        if contract.status not in {"active", "expired"}:
            raise ApiError(
                status_code=409,
                code="CONTRACT_ACTION_NOT_ALLOWED",
                message="contract status does not allow this action",
            )
        if payload.effective_date < contract.effective_from:
            raise ApiError(
                status_code=422,
                code="CONTRACT_EVENT_DATE_INVALID",
                message="contract event date cannot be earlier than contract start date",
            )
        planned = payload.planned_payload
        legal_entity_id = planned.get("legal_entity_id")
        if legal_entity_id is not None and await self._session.get(
            LegalEntity,
            UUID(str(legal_entity_id)),
        ) is None:
            raise ApiError(
                status_code=404,
                code="LEGAL_ENTITY_NOT_FOUND",
                message="legal entity not found",
            )
        if payload.event_type == "CONTRACT_AMENDMENT":
            allowed = {
                "signed_on",
                "effective_to",
                "legal_entity_id",
                "expiry_notice_days",
                "metadata_payload",
            }
            if not planned or set(planned) - allowed:
                raise ApiError(
                    status_code=422,
                    code="CONTRACT_AMENDMENT_INVALID",
                    message="contract amendment contains unsupported fields",
                )
            effective_to = self._date_value(planned.get("effective_to"))
            if effective_to is not None and effective_to < contract.effective_from:
                raise ApiError(
                    status_code=422,
                    code="CONTRACT_EFFECTIVE_PERIOD_INVALID",
                    message="contract end date cannot be earlier than its start date",
                )
        if payload.event_type == "CONTRACT_RENEWAL":
            number = str(planned.get("contract_number") or "").strip()
            if not number:
                raise ApiError(
                    status_code=422,
                    code="CONTRACT_RENEWAL_NUMBER_REQUIRED",
                    message="renewed contract number is required",
                )
            if contract.effective_to is not None and payload.effective_date <= contract.effective_to:
                raise ApiError(
                    status_code=422,
                    code="CONTRACT_RENEWAL_DATE_INVALID",
                    message="renewal must start after the current contract ends",
                )
            renewed_to = self._date_value(planned.get("effective_to"))
            if renewed_to is not None and renewed_to < payload.effective_date:
                raise ApiError(
                    status_code=422,
                    code="CONTRACT_EFFECTIVE_PERIOD_INVALID",
                    message="renewed contract end date cannot be earlier than its start date",
                )
            if await self._session.scalar(
                select(ContractRecord.id).where(ContractRecord.contract_number == number)
            ) is not None:
                raise ApiError(
                    status_code=409,
                    code="CONTRACT_NUMBER_EXISTS",
                    message="contract number already exists",
                )
        if (
            payload.event_type in {"CONTRACT_TERMINATION", "CONTRACT_CANCELLATION"}
            and contract.effective_to is not None
            and payload.effective_date > contract.effective_to
        ):
            raise ApiError(
                status_code=422,
                code="CONTRACT_EVENT_DATE_AFTER_END",
                message="contract close date cannot be later than the current contract end date",
            )

    @staticmethod
    def _date_value(value: Any) -> date | None:
        if value is None or isinstance(value, date):
            return value
        return date.fromisoformat(str(value))

    @staticmethod
    def _contract_snapshot(contract: ContractRecord) -> dict[str, Any]:
        fields = (
            "signed_on",
            "effective_from",
            "effective_to",
            "legal_entity_id",
            "expiry_notice_days",
            "status",
            "metadata_payload",
            "version",
        )
        return {
            field: (
                value.isoformat()
                if isinstance(value, date)
                else str(value)
                if isinstance(value, UUID)
                else value
            )
            for field in fields
            for value in [getattr(contract, field)]
        }

    async def _execute_employment_event(self, event: HrEvent, event_type: str) -> dict[str, Any]:
        employment = await self._session.get(Employment, event.object_id, with_for_update=True)
        if employment is None:
            raise ApiError(status_code=404, code="EMPLOYMENT_NOT_FOUND", message="劳动关系不存在")
        tracked_fields = [
            "employee_type_code",
            "status",
            "planned_start_date",
            "actual_start_date",
            "probation_end_date",
            "end_date",
            "end_reason_code",
            "contract_legal_entity_id",
            "payroll_legal_entity_id",
            "social_insurance_legal_entity_id",
            "tax_legal_entity_id",
        ]
        before = {
            field: (
                value.isoformat() if isinstance(value, date) else str(value) if isinstance(value, UUID) else value
            )
            for field in tracked_fields
            for value in [getattr(employment, field)]
        }
        changes: dict[str, Any]
        if event.event_type.startswith("ROLLBACK_"):
            changes = dict(event.planned_payload)
        elif event_type == "ONBOARDING":
            if employment.status != "pending_start":
                raise ApiError(
                    status_code=409,
                    code="ONBOARDING_EMPLOYMENT_STATUS_INVALID",
                    message="only pending-start employment can be onboarded",
                )
            changes = {"status": "active", "actual_start_date": event.effective_date}
        elif event_type == "CONFIRMATION":
            changes = {"status": "active", "probation_end_date": event.effective_date}
        elif event_type == "TERMINATION":
            changes = {
                "status": "terminated",
                "end_date": event.effective_date,
                "end_reason_code": event.planned_payload.get("end_reason_code"),
            }
        elif event_type == "WITHDRAWAL":
            changes = {"status": "withdrawn"}
            if event.effective_date >= employment.planned_start_date:
                changes["end_date"] = event.effective_date
        else:
            changes = dict(event.planned_payload)
        allowed_fields = set(tracked_fields)
        invalid = set(changes) - allowed_fields
        if invalid:
            raise ApiError(status_code=422, code="HR_EVENT_FIELD_NOT_ALLOWED", message="人事事件包含不可修改字段")
        date_fields = {"planned_start_date", "actual_start_date", "probation_end_date", "end_date"}
        uuid_fields = {
            "contract_legal_entity_id",
            "payroll_legal_entity_id",
            "social_insurance_legal_entity_id",
            "tax_legal_entity_id",
        }
        for field, value in changes.items():
            if field in date_fields:
                value = self._date_value(value)
            elif field in uuid_fields and value is not None:
                value = UUID(str(value))
            setattr(employment, field, value)
        employment.version += 1
        event.before_payload = before
        return {
            field: (
                value.isoformat() if isinstance(value, date) else str(value) if isinstance(value, UUID) else value
            )
            for field in changes
            if (value := getattr(employment, field)) is not None
        } | {"version": employment.version}

    async def _execute_assignment_event(self, event: HrEvent, event_type: str) -> dict[str, Any]:
        if event.event_type.startswith("ROLLBACK_") and event_type in {
            "CONCURRENT_ASSIGNMENT",
            "SECONDMENT",
            "END_ASSIGNMENT",
        }:
            original = await self._session.get(HrEvent, event.related_event_id) if event.related_event_id else None
            # Requirement: D-104 — 回退目标优先按 person 级兼岗处理：
            # CONCURRENT_ASSIGNMENT 事件写入的是 organization_person_relations，
            # 其 actual_payload 里是 concurrent_position_id，没有 assignment_id。
            concurrent_position_id = (
                original.actual_payload.get("concurrent_position_id") if original else None
            )
            if concurrent_position_id:
                relation = await self._session.get(
                    OrganizationPersonRelation,
                    UUID(str(concurrent_position_id)),
                    with_for_update=True,
                )
                if relation is None:
                    raise ApiError(
                        status_code=422,
                        code="ASSIGNMENT_ROLLBACK_TARGET_MISSING",
                        message="找不到要回退的兼岗关系",
                    )
                event.before_payload = {
                    "effective_to": relation.effective_to.isoformat() if relation.effective_to else None,
                }
                relation.effective_to = event.effective_date
                await self._session.flush()
                return {
                    "concurrent_position_id": str(relation.id),
                    "effective_to": event.effective_date.isoformat(),
                }
            assignment_id = original.actual_payload.get("assignment_id") if original else None
            assignment = await self._session.get(EmploymentAssignment, UUID(str(assignment_id))) if assignment_id else None
            if assignment is None:
                raise ApiError(status_code=422, code="ASSIGNMENT_ROLLBACK_TARGET_MISSING", message="找不到要回退的组织职务关系")
            event.before_payload = {"effective_to": assignment.effective_to.isoformat() if assignment.effective_to else None}
            assignment.effective_to = event.effective_date
            return {"assignment_id": str(assignment.id), "effective_to": event.effective_date.isoformat()}

        payload = event.planned_payload
        if event_type == "END_ASSIGNMENT":
            # Requirement: D-104 — 结束 person 级兼岗时，按 concurrent_position_id
            # 关闭 organization_person_relations 的生效区间；employment 级任职
            # 仍是「结束主职/借调」的对象，两条路径互斥。
            concurrent_position_id = payload.get("concurrent_position_id")
            if concurrent_position_id:
                concurrent = ConcurrentPositionService(
                    self._session,
                    actor_id=self._actor_id,
                    trace_id=self._trace_id,
                )
                record = await concurrent.end_concurrent_position(
                    UUID(str(concurrent_position_id)),
                    effective_to=event.effective_date,
                    reason=event.reason or "人事事件：结束兼岗",
                )
                event.before_payload = {
                    "effective_to": (
                        record.effective_to.isoformat() if record.effective_to else None
                    ),
                }
                return {
                    "concurrent_position_id": str(record.id),
                    "person_id": str(record.person_id),
                    "organization_id": str(record.organization_id),
                    "effective_to": (
                        record.effective_to.isoformat() if record.effective_to else None
                    ),
                }
            assignment = await self._session.get(
                EmploymentAssignment,
                UUID(str(payload["assignment_id"])),
                with_for_update=True,
            )
            if assignment is None or assignment.employment_id != event.object_id:
                raise ApiError(status_code=404, code="ASSIGNMENT_NOT_FOUND", message="组织职务关系不存在")
            event.before_payload = {"effective_to": assignment.effective_to.isoformat() if assignment.effective_to else None}
            assignment.effective_to = event.effective_date
            return {"assignment_id": str(assignment.id), "effective_to": event.effective_date.isoformat()}

        # Requirement: D-104 — 兼岗以 person 级组织关系为唯一权威载体：
        # 审批通过的 CONCURRENT_ASSIGNMENT 事件写 organization_person_relations
        # （relation_type='concurrent'），不再新增 employment 级 EmploymentAssignment 行；
        # 既有 employment 级兼岗行保留为历史记录，读取端不再以其为兼岗来源。
        if event_type == "CONCURRENT_ASSIGNMENT":
            employment = await self._session.get(Employment, event.object_id)
            if employment is None:
                raise ApiError(
                    status_code=422,
                    code="EMPLOYMENT_NOT_FOUND",
                    message="劳动关系不存在",
                )
            organization_id = UUID(str(payload["organization_id"]))
            job_id = UUID(str(payload["job_id"]))
            if await self._session.get(Organization, organization_id) is None:
                raise ApiError(status_code=404, code="ORGANIZATION_NOT_FOUND", message="组织不存在")
            workforce = ExtendedWorkforceService(
                self._session,
                actor_id=self._actor_id,
                trace_id=self._trace_id,
            )
            await workforce.ensure_job_effective(job_id, event.effective_date)
            concurrent = ConcurrentPositionService(
                self._session,
                actor_id=self._actor_id,
                trace_id=self._trace_id,
            )
            record = await concurrent.create_concurrent_position(
                person_id=employment.person_id,
                organization_id=organization_id,
                job_id=job_id,
                effective_from=event.effective_date,
                effective_to=self._date_value(payload.get("effective_to")),
                change_reason=event.reason or "人事事件：兼岗",
                source_event_id=event.id,
            )
            event.before_payload = {}
            return {
                "concurrent_position_id": str(record.id),
                "person_id": str(record.person_id),
                "organization_id": str(record.organization_id),
                "job_id": str(record.job_id) if record.job_id else None,
                "relation_type": record.relation_type,
            }

        relation_type = {
            "TRANSFER": "primary",
            "SECONDMENT": "secondment",
        }[event_type]
        organization_id = UUID(str(payload["organization_id"]))
        job_id = UUID(str(payload["job_id"]))
        if await self._session.get(Organization, organization_id) is None:
            raise ApiError(status_code=404, code="ORGANIZATION_NOT_FOUND", message="组织不存在")
        workforce = ExtendedWorkforceService(
            self._session,
            actor_id=self._actor_id,
            trace_id=self._trace_id,
        )
        await workforce.ensure_job_effective(job_id, event.effective_date)
        before: dict[str, Any] = {}
        if relation_type == "primary":
            current = await self._session.scalar(
                select(EmploymentAssignment)
                .where(
                    EmploymentAssignment.employment_id == event.object_id,
                    EmploymentAssignment.relation_type == "primary",
                    EmploymentAssignment.effective_from <= event.effective_date,
                    or_(
                        EmploymentAssignment.effective_to.is_(None),
                        EmploymentAssignment.effective_to >= event.effective_date,
                    ),
                )
                .order_by(EmploymentAssignment.version.desc())
                .limit(1)
                .with_for_update()
            )
            if current is not None:
                if current.effective_from >= event.effective_date:
                    raise ApiError(status_code=409, code="ASSIGNMENT_EVENT_DATE_NOT_FORWARD", message="变更生效日期必须晚于当前主关系生效日期")
                before = {
                    "organization_id": str(current.organization_id),
                    "job_id": str(current.job_id) if current.job_id else None,
                    "effective_from": current.effective_from.isoformat(),
                }
                current.effective_to = event.effective_date - timedelta(days=1)
        version = (
            await self._session.scalar(
                select(func.max(EmploymentAssignment.version)).where(
                    EmploymentAssignment.employment_id == event.object_id
                )
            )
            or 0
        ) + 1
        assignment = EmploymentAssignment(
            employment_id=event.object_id,
            organization_id=organization_id,
            job_id=job_id,
            relation_type=relation_type,
            effective_from=event.effective_date,
            effective_to=self._date_value(payload.get("effective_to")),
            source_event_id=event.id,
            version=version,
        )
        self._session.add(assignment)
        await self._session.flush()
        event.before_payload = before
        return {
            "assignment_id": str(assignment.id),
            "organization_id": str(assignment.organization_id),
            "job_id": str(assignment.job_id),
            "relation_type": assignment.relation_type,
            "version": assignment.version,
        }

    @staticmethod
    def _restore_contract_snapshot(
        contract: ContractRecord,
        snapshot: dict[str, Any],
    ) -> None:
        for field in (
            "signed_on",
            "effective_from",
            "effective_to",
            "legal_entity_id",
            "expiry_notice_days",
            "status",
            "metadata_payload",
        ):
            if field not in snapshot:
                continue
            value = snapshot[field]
            if field in {"signed_on", "effective_from", "effective_to"}:
                value = LifecycleService._date_value(value)
            elif field == "legal_entity_id" and value is not None:
                value = UUID(str(value))
            setattr(contract, field, value)

    async def _execute_contract_event(
        self,
        event: HrEvent,
        event_type: str,
    ) -> dict[str, Any]:
        contract = await self._session.get(
            ContractRecord,
            event.object_id,
            with_for_update=True,
        )
        if contract is None:
            raise ApiError(
                status_code=404,
                code="CONTRACT_NOT_FOUND",
                message="contract not found",
            )
        if event.event_type.startswith("ROLLBACK_"):
            original = (
                await self._session.get(HrEvent, event.related_event_id)
                if event.related_event_id
                else None
            )
            if original is None:
                raise ApiError(
                    status_code=422,
                    code="CONTRACT_ROLLBACK_SOURCE_MISSING",
                    message="original contract event not found",
                )
            expected_version = original.actual_payload.get("version")
            if expected_version is not None and contract.version != int(expected_version):
                raise ApiError(
                    status_code=409,
                    code="CONTRACT_ROLLBACK_NOT_LATEST",
                    message="rollback contract events in reverse order of execution",
                )
            event.before_payload = self._contract_snapshot(contract)
            if event_type == "CONTRACT_RENEWAL":
                successor_id = original.actual_payload.get("new_contract_id")
                successor = (
                    await self._session.get(
                        ContractRecord,
                        UUID(str(successor_id)),
                        with_for_update=True,
                    )
                    if successor_id
                    else None
                )
                if successor is None:
                    raise ApiError(
                        status_code=422,
                        code="CONTRACT_RENEWAL_SUCCESSOR_MISSING",
                        message="renewed contract not found",
                    )
                if successor.status != "active" or successor.version != 1:
                    raise ApiError(
                        status_code=409,
                        code="CONTRACT_ROLLBACK_SUCCESSOR_CHANGED",
                        message="renewed contract has later changes and cannot be cancelled directly",
                    )
                successor_before = self._contract_snapshot(successor)
                self._restore_contract_snapshot(contract, original.before_payload)
                contract.version += 1
                successor.status = "cancelled"
                successor.version += 1
                actual = self._contract_snapshot(contract) | {
                    "cancelled_contract_id": str(successor.id)
                }
                self._audit(
                    action="rollback_renewal",
                    object_type="contract",
                    object_id=contract.id,
                    reason=event.reason,
                    before=event.before_payload,
                    after=actual,
                )
                self._audit(
                    action="cancel_renewal",
                    object_type="contract",
                    object_id=successor.id,
                    reason=event.reason,
                    before=successor_before,
                    after=self._contract_snapshot(successor),
                )
                return actual
            self._restore_contract_snapshot(contract, original.before_payload)
            contract.version += 1
            actual = self._contract_snapshot(contract)
            self._audit(
                action=f"rollback_{event_type.lower()}",
                object_type="contract",
                object_id=contract.id,
                reason=event.reason,
                before=event.before_payload,
                after=actual,
            )
            return actual

        before = self._contract_snapshot(contract)
        event.before_payload = before
        if event_type == "CONTRACT_AMENDMENT":
            changes = dict(event.planned_payload)
            for field, value in changes.items():
                if field in {"signed_on", "effective_to"}:
                    value = self._date_value(value)
                elif field == "legal_entity_id" and value is not None:
                    value = UUID(str(value))
                setattr(contract, field, value)
            contract.version += 1
            actual = self._contract_snapshot(contract)
        elif event_type in {"CONTRACT_TERMINATION", "CONTRACT_CANCELLATION"}:
            contract.effective_to = event.effective_date
            contract.status = (
                "terminated" if event_type == "CONTRACT_TERMINATION" else "cancelled"
            )
            contract.version += 1
            actual = self._contract_snapshot(contract)
        elif event_type == "CONTRACT_RENEWAL":
            planned = event.planned_payload
            number = str(planned["contract_number"])
            if await self._session.scalar(
                select(ContractRecord.id).where(ContractRecord.contract_number == number)
            ) is not None:
                raise ApiError(
                    status_code=409,
                    code="CONTRACT_NUMBER_EXISTS",
                    message="contract number already exists",
                )
            legal_entity_id = planned.get("legal_entity_id") or contract.legal_entity_id
            successor = ContractRecord(
                person_id=contract.person_id,
                employment_id=contract.employment_id,
                agreement_relationship_id=contract.agreement_relationship_id,
                predecessor_contract_id=contract.id,
                contract_type_code=contract.contract_type_code,
                contract_number=number,
                legal_entity_id=(
                    UUID(str(legal_entity_id)) if legal_entity_id is not None else None
                ),
                signed_on=self._date_value(planned.get("signed_on")),
                effective_from=event.effective_date,
                effective_to=self._date_value(planned.get("effective_to")),
                expiry_notice_days=int(planned.get("expiry_notice_days", 30)),
                version=1,
                status="active",
                metadata_payload=dict(planned.get("metadata_payload") or {}),
            )
            if contract.effective_to is None:
                contract.effective_to = event.effective_date - timedelta(days=1)
            contract.status = "renewed"
            contract.version += 1
            self._session.add(successor)
            await self._session.flush()
            actual = self._contract_snapshot(contract) | {
                "new_contract_id": str(successor.id),
                "new_contract_number": successor.contract_number,
            }
            self._audit(
                action="create_renewal",
                object_type="contract",
                object_id=successor.id,
                reason=event.reason,
                after=self._contract_snapshot(successor)
                | {"predecessor_contract_id": str(contract.id)},
            )
        else:
            raise ApiError(
                status_code=422,
                code="HR_EVENT_TYPE_UNSUPPORTED",
                message="contract event type is not supported",
            )
        self._audit(
            action=event_type.lower(),
            object_type="contract",
            object_id=contract.id,
            reason=event.reason,
            before=before,
            after=actual,
        )
        return actual

    async def _execute_hr_event_if_due(self, event: HrEvent, as_of: date | None = None) -> bool:
        process_date = as_of or self._business_today()
        if event.effective_date > process_date:
            event.status = "scheduled"
            return False
        if event.status not in {"ready", "scheduled", "failed"}:
            return False
        event_type = event.event_type.removeprefix("ROLLBACK_")
        if event.object_type == "contract":
            actual = await self._execute_contract_event(event, event_type)
        elif event_type in {
            "ONBOARDING",
            "CONFIRMATION",
            "TERMINATION",
            "WITHDRAWAL",
            "EMPLOYMENT_CORRECTION",
        }:
            actual = await self._execute_employment_event(event, event_type)
        else:
            actual = await self._execute_assignment_event(event, event_type)
        event.actual_payload = actual
        event.status = "completed"
        event.attempts += 1
        event.last_error = None
        event.executed_at = datetime.now(UTC)
        await self._session.flush()
        self._audit(
            action="execute",
            object_type="hr_event",
            object_id=event.id,
            reason=event.reason,
            before=event.before_payload,
            after=event.actual_payload,
        )
        return True

    async def list_hr_events(
        self,
        *,
        status: str | None,
        object_type: str | None,
        object_id: UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[list[HrEvent], int]:
        filters = [HrEvent.status == status] if status else []
        if object_type is not None:
            filters.append(HrEvent.object_type == object_type)
        if object_id is not None:
            filters.append(HrEvent.object_id == object_id)
        total = await self._session.scalar(select(func.count()).select_from(HrEvent).where(*filters))
        items = list(
            (
                await self._session.scalars(
                    select(HrEvent)
                    .where(*filters)
                    .order_by(HrEvent.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        return items, total or 0

    async def get_hr_event(self, event_id: UUID) -> HrEvent:
        event = await self._session.get(HrEvent, event_id)
        if event is None:
            raise ApiError(status_code=404, code="HR_EVENT_NOT_FOUND", message="人事事件不存在")
        return event

    async def process_due_hr_events(
        self,
        as_of: date | None,
    ) -> tuple[list[UUID], list[dict[str, str]]]:
        process_date = as_of or self._business_today()
        event_ids = list(
            (
                await self._session.scalars(
                    select(HrEvent.id).where(
                        HrEvent.status.in_(("ready", "scheduled", "failed")),
                        HrEvent.effective_date <= process_date,
                    )
                )
            ).all()
        )
        processed: list[UUID] = []
        failed: list[dict[str, str]] = []
        for event_id in event_ids:
            try:
                async with self._session.begin_nested():
                    event = await self._session.get(HrEvent, event_id, with_for_update=True)
                    if event is not None and await self._execute_hr_event_if_due(event, process_date):
                        processed.append(event.id)
            except (ApiError, ValueError) as caught:
                event = await self._session.get(HrEvent, event_id, with_for_update=True)
                if event is not None:
                    event.status = "failed"
                    event.attempts += 1
                    event.last_error = str(caught)
                failed.append({"event_id": str(event_id), "error": str(caught)})
        return processed, failed

    async def create_hr_event(self, payload: HrEventCreate) -> HrEvent:
        checksum = self._hr_event_checksum("create", payload.model_dump(mode="json"))
        if payload.idempotency_key is not None:
            await self._lock_idempotency(payload.idempotency_key)
            existing = await self._session.scalar(
                select(HrEvent).where(HrEvent.idempotency_key == payload.idempotency_key)
            )
            if existing is not None:
                if existing.request_checksum != checksum:
                    raise ApiError(
                        status_code=409,
                        code="HR_EVENT_IDEMPOTENCY_CONFLICT",
                        message="idempotency key was used with different event data",
                    )
                return existing
        await self._validate_hr_event(payload)
        number = await next_number(
            self._session,
            sequence_code="HR_EVENT_NUMBER",
            width=10,
            max_value=9999999999,
            prefix="E",
        )
        event = HrEvent(
            event_number=number,
            idempotency_key=payload.idempotency_key,
            request_checksum=checksum if payload.idempotency_key is not None else None,
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
        if payload.execution_mode == "direct":
            await self._execute_hr_event_if_due(event)
        self._audit(
            action="create",
            object_type="hr_event",
            object_id=event.id,
            reason=event.reason,
            after={
                "event_number": event.event_number,
                "event_type": event.event_type,
                "object_type": event.object_type,
                "object_id": str(event.object_id),
                "status": event.status,
            },
        )
        return event

    async def rollback_hr_event(
        self,
        event_id: UUID,
        payload: HrEventRollbackCreate,
    ) -> HrEvent:
        checksum = self._hr_event_checksum(
            "rollback",
            {
                "event_id": str(event_id),
                **payload.model_dump(mode="json"),
            },
        )
        if payload.idempotency_key is not None:
            await self._lock_idempotency(payload.idempotency_key)
            existing = await self._session.scalar(
                select(HrEvent).where(HrEvent.idempotency_key == payload.idempotency_key)
            )
            if existing is not None:
                if existing.request_checksum != checksum:
                    raise ApiError(
                        status_code=409,
                        code="HR_EVENT_IDEMPOTENCY_CONFLICT",
                        message="idempotency key was used with different rollback data",
                    )
                return existing
        original = await self._session.get(HrEvent, event_id)
        if original is None:
            raise ApiError(status_code=404, code="HR_EVENT_NOT_FOUND", message="人事事件不存在")
        if original.status != "completed":
            raise ApiError(status_code=409, code="HR_EVENT_NOT_COMPLETED", message="只有已生效的人事事件可以回退")
        if original.object_type == "contract":
            contract = await self._session.get(
                ContractRecord,
                original.object_id,
                with_for_update=True,
            )
            if contract is None:
                raise ApiError(
                    status_code=404,
                    code="CONTRACT_NOT_FOUND",
                    message="contract not found",
                )
            expected_version = original.actual_payload.get("version")
            if expected_version is not None and contract.version != int(expected_version):
                raise ApiError(
                    status_code=409,
                    code="CONTRACT_ROLLBACK_NOT_LATEST",
                    message="rollback contract events in reverse order of execution",
                )
            if original.event_type == "CONTRACT_RENEWAL":
                successor_id = original.actual_payload.get("new_contract_id")
                successor = (
                    await self._session.get(ContractRecord, UUID(str(successor_id)))
                    if successor_id
                    else None
                )
                if successor is None:
                    raise ApiError(
                        status_code=422,
                        code="CONTRACT_RENEWAL_SUCCESSOR_MISSING",
                        message="renewed contract not found",
                    )
                if successor.status != "active" or successor.version != 1:
                    raise ApiError(
                        status_code=409,
                        code="CONTRACT_ROLLBACK_SUCCESSOR_CHANGED",
                        message="renewed contract has later changes and cannot be cancelled directly",
                    )
        number = await next_number(
            self._session,
            sequence_code="HR_EVENT_NUMBER",
            width=10,
            max_value=9999999999,
            prefix="E",
        )
        rollback = HrEvent(
            event_number=number,
            idempotency_key=payload.idempotency_key,
            request_checksum=checksum if payload.idempotency_key is not None else None,
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
        if payload.execution_mode == "direct":
            await self._execute_hr_event_if_due(rollback)
        self._audit(
            action="rollback_requested",
            object_type="hr_event",
            object_id=rollback.id,
            after={"related_event_id": str(original.id), "status": rollback.status},
        )
        return rollback
