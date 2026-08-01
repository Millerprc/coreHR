from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.errors import ApiError
from hris.modules.platform.models import NumberSequence
from hris.modules.workforce.extended_schemas import (
    EmploymentAssignmentCreate,
    EmploymentCreate,
    HeadcountPlanCreate,
    JobCreate,
    LegalEntityCreate,
    PersonCreate,
)
from hris.modules.workforce.models import (
    AuditLog,
    Employment,
    EmploymentAssignment,
    HeadcountPlan,
    JobCatalog,
    LegalEntity,
    Organization,
    Person,
)


class ExtendedWorkforceService:
    def __init__(self, session: AsyncSession, *, actor_id: UUID, trace_id: str) -> None:
        self._session = session
        self._actor_id = actor_id
        self._trace_id = trace_id

    async def _ensure_unique(self, model: type[Any], field: Any, value: str, code: str) -> None:
        if await self._session.scalar(select(model).where(field == value)) is not None:
            raise ApiError(status_code=409, code=code, message="业务编码已存在")

    def _audit(
        self,
        *,
        action: str,
        object_type: str,
        object_id: UUID,
        reason: str,
        after: dict[str, Any],
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
                before_payload={},
                after_payload=after,
                source="api",
            )
        )

    async def create_legal_entity(self, payload: LegalEntityCreate) -> LegalEntity:
        await self._ensure_unique(
            LegalEntity,
            LegalEntity.code,
            payload.code,
            "LEGAL_ENTITY_CODE_EXISTS",
        )
        entity = LegalEntity(**payload.model_dump(), status="active")
        self._session.add(entity)
        await self._session.flush()
        self._audit(
            action="create",
            object_type="legal_entity",
            object_id=entity.id,
            reason="创建法人主体",
            after={"code": entity.code, "name": entity.name},
        )
        return entity

    async def create_job(self, payload: JobCreate) -> JobCatalog:
        await self._ensure_unique(JobCatalog, JobCatalog.code, payload.code, "JOB_CODE_EXISTS")
        job = JobCatalog(**payload.model_dump(), status="active")
        self._session.add(job)
        await self._session.flush()
        self._audit(
            action="create",
            object_type="job",
            object_id=job.id,
            reason="创建职务",
            after={"code": job.code, "name": job.name},
        )
        return job

    async def _lock_sequence(self, code: str, width: int, max_value: int) -> NumberSequence:
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:sequence_code))"),
            {"sequence_code": f"corehr:{code}"},
        )
        sequence = await self._session.scalar(
            select(NumberSequence).where(NumberSequence.code == code).with_for_update()
        )
        if sequence is None:
            sequence = NumberSequence(
                code=code,
                current_value=0,
                width=width,
                max_value=max_value,
            )
            self._session.add(sequence)
            await self._session.flush()
        return sequence

    async def _allocate_employee_number(self, imported_value: str | None = None) -> str:
        sequence = await self._lock_sequence("EMPLOYEE_NUMBER", 6, 999999)
        if imported_value is not None:
            numeric_value = int(imported_value)
            sequence.current_value = max(sequence.current_value, numeric_value)
            return imported_value
        if sequence.current_value >= sequence.max_value:
            raise ApiError(status_code=409, code="EMPLOYEE_NUMBER_EXHAUSTED", message="六位工号空间已耗尽")
        sequence.current_value += 1
        return str(sequence.current_value).zfill(sequence.width)

    async def create_person(self, payload: PersonCreate) -> Person:
        employee_number = payload.employee_number
        if employee_number is not None:
            if await self._session.scalar(
                select(Person).where(Person.employee_number == employee_number)
            ) is not None:
                raise ApiError(status_code=409, code="EMPLOYEE_NUMBER_EXISTS", message="工号已被占用")
            employee_number = await self._allocate_employee_number(employee_number)
        elif payload.reserve_employee_number:
            employee_number = await self._allocate_employee_number()

        data = payload.model_dump(exclude={"reserve_employee_number", "change_reason"})
        data["employee_number"] = employee_number
        person = Person(**data, status="active")
        self._session.add(person)
        await self._session.flush()
        self._audit(
            action="create",
            object_type="person",
            object_id=person.id,
            reason=payload.change_reason,
            after={"employee_number": person.employee_number, "display_name": person.display_name},
        )
        return person

    async def reserve_employee_number(self, person_id: UUID) -> str:
        person = await self._session.get(Person, person_id, with_for_update=True)
        if person is None:
            raise ApiError(status_code=404, code="PERSON_NOT_FOUND", message="人员不存在")
        if person.employee_number is None:
            person.employee_number = await self._allocate_employee_number()
            self._audit(
                action="reserve_employee_number",
                object_type="person",
                object_id=person.id,
                reason="待入职档案占用工号",
                after={"employee_number": person.employee_number},
            )
        return person.employee_number

    async def create_employment(self, payload: EmploymentCreate) -> Employment:
        person = await self._session.get(Person, payload.person_id)
        if person is None:
            raise ApiError(status_code=404, code="PERSON_NOT_FOUND", message="人员不存在")
        if person.employee_number is None:
            person.employee_number = await self._allocate_employee_number()

        legal_ids = {
            payload.contract_legal_entity_id,
            payload.payroll_legal_entity_id or payload.contract_legal_entity_id,
            payload.social_insurance_legal_entity_id or payload.contract_legal_entity_id,
            payload.tax_legal_entity_id or payload.contract_legal_entity_id,
        }
        legal_count = await self._session.scalar(
            select(func.count()).select_from(LegalEntity).where(LegalEntity.id.in_(legal_ids))
        )
        if legal_count != len(legal_ids):
            raise ApiError(status_code=422, code="LEGAL_ENTITY_NOT_FOUND", message="四类主体中存在无效法人")

        overlap_filters = [
            Employment.person_id == payload.person_id,
            or_(Employment.end_date.is_(None), Employment.end_date >= payload.planned_start_date),
        ]
        if payload.end_date is not None:
            overlap_filters.append(Employment.planned_start_date <= payload.end_date)
        overlap = await self._session.scalar(select(Employment.id).where(*overlap_filters).limit(1))
        if overlap is not None:
            raise ApiError(
                status_code=409,
                code="EMPLOYMENT_PERIOD_OVERLAP",
                message="同一自然人在该有效期间已存在法人劳动关系",
            )

        employment = Employment(
            person_id=payload.person_id,
            employee_type_code=payload.employee_type_code,
            status="pending_start",
            planned_start_date=payload.planned_start_date,
            actual_start_date=payload.actual_start_date,
            probation_end_date=payload.probation_end_date,
            end_date=payload.end_date,
            contract_legal_entity_id=payload.contract_legal_entity_id,
            payroll_legal_entity_id=payload.payroll_legal_entity_id or payload.contract_legal_entity_id,
            social_insurance_legal_entity_id=(
                payload.social_insurance_legal_entity_id or payload.contract_legal_entity_id
            ),
            tax_legal_entity_id=payload.tax_legal_entity_id or payload.contract_legal_entity_id,
            version=1,
        )
        self._session.add(employment)
        await self._session.flush()
        self._audit(
            action="create",
            object_type="employment",
            object_id=employment.id,
            reason=payload.change_reason,
            after={
                "person_id": str(employment.person_id),
                "status": employment.status,
                "planned_start_date": employment.planned_start_date.isoformat(),
            },
        )
        return employment

    async def create_assignment(
        self,
        payload: EmploymentAssignmentCreate,
    ) -> EmploymentAssignment:
        if await self._session.get(Employment, payload.employment_id) is None:
            raise ApiError(status_code=404, code="EMPLOYMENT_NOT_FOUND", message="劳动关系不存在")
        if await self._session.get(Organization, payload.organization_id) is None:
            raise ApiError(status_code=404, code="ORGANIZATION_NOT_FOUND", message="组织不存在")
        if payload.job_id is not None and await self._session.get(JobCatalog, payload.job_id) is None:
            raise ApiError(status_code=404, code="JOB_NOT_FOUND", message="职务不存在")
        assignment = EmploymentAssignment(
            **payload.model_dump(exclude={"change_reason"}),
            version=1,
        )
        self._session.add(assignment)
        await self._session.flush()
        self._audit(
            action="create",
            object_type="employment_assignment",
            object_id=assignment.id,
            reason=payload.change_reason,
            after={
                "employment_id": str(assignment.employment_id),
                "organization_id": str(assignment.organization_id),
                "relation_type": assignment.relation_type,
            },
        )
        return assignment

    async def create_headcount_plan(self, payload: HeadcountPlanCreate) -> HeadcountPlan:
        if await self._session.get(Organization, payload.organization_id) is None:
            raise ApiError(status_code=404, code="ORGANIZATION_NOT_FOUND", message="组织不存在")
        if await self._session.get(JobCatalog, payload.job_id) is None:
            raise ApiError(status_code=404, code="JOB_NOT_FOUND", message="职务不存在")
        existing = await self._session.scalar(
            select(HeadcountPlan).where(
                HeadcountPlan.organization_id == payload.organization_id,
                HeadcountPlan.job_id == payload.job_id,
                HeadcountPlan.period_month == payload.period_month,
                HeadcountPlan.is_current.is_(True),
            )
        )
        version = 1
        if existing is not None:
            existing.is_current = False
            version = existing.version + 1
        plan = HeadcountPlan(**payload.model_dump(), version=version, is_current=True)
        self._session.add(plan)
        await self._session.flush()
        self._audit(
            action="create_version",
            object_type="headcount_plan",
            object_id=plan.id,
            reason=payload.change_reason,
            after={
                "period_month": plan.period_month.isoformat(),
                "planned_count": str(plan.planned_count),
                "version": plan.version,
            },
        )
        return plan

    async def list_models(
        self,
        model: type[Any],
        *,
        limit: int,
        offset: int,
        order_by: Any,
    ) -> tuple[list[Any], int]:
        total = await self._session.scalar(select(func.count()).select_from(model))
        items = list(
            (await self._session.scalars(select(model).order_by(order_by).limit(limit).offset(offset))).all()
        )
        return items, total or 0
