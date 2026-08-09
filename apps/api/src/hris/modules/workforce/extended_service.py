from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.errors import ApiError
from hris.modules.platform.models import NumberSequence
from hris.modules.workforce.extended_schemas import (
    AgreementRelationshipCreate,
    EmploymentAssignmentCreate,
    EmploymentCreate,
    HeadcountFreezeCreate,
    HeadcountPlanCreate,
    HeadcountSnapshotGenerate,
    JobCreate,
    LegalEntityCreate,
    OccupancyRuleCreate,
    PersonCreate,
    PersonUpdate,
)
from hris.modules.workforce.models import (
    AgreementRelationship,
    AuditLog,
    Employment,
    EmploymentAssignment,
    HeadcountPlan,
    HeadcountFreeze,
    HeadcountSnapshot,
    OccupancyRule,
    JobCatalog,
    LegalEntity,
    Organization,
    OrganizationVersion,
    Person,
    SnapshotBatch,
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

    async def update_person(self, person_id: UUID, payload: PersonUpdate) -> Person:
        person = await self._session.get(Person, person_id, with_for_update=True)
        if person is None:
            raise ApiError(status_code=404, code="PERSON_NOT_FOUND", message="人员不存在")
        changes = payload.model_dump(exclude={"change_reason"}, exclude_unset=True)
        if not changes:
            raise ApiError(status_code=422, code="PERSON_CHANGE_EMPTY", message="没有可保存的档案变更")
        before = {field: getattr(person, field) for field in changes}
        for field, value in changes.items():
            setattr(person, field, value)
        await self._session.flush()
        await self._session.refresh(person)
        self._audit(
            action="update",
            object_type="person",
            object_id=person.id,
            reason=payload.change_reason,
            before=self._json_values(before),
            after=self._json_values(changes),
        )
        return person

    @staticmethod
    def _json_values(values: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value.isoformat() if isinstance(value, (date, datetime)) else value
            for key, value in values.items()
        }

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
        if payload.relation_type == "primary":
            overlap_filters = [
                EmploymentAssignment.employment_id == payload.employment_id,
                EmploymentAssignment.relation_type == "primary",
                or_(
                    EmploymentAssignment.effective_to.is_(None),
                    EmploymentAssignment.effective_to >= payload.effective_from,
                ),
            ]
            if payload.effective_to is not None:
                overlap_filters.append(
                    EmploymentAssignment.effective_from <= payload.effective_to
                )
            overlap = await self._session.scalar(
                select(EmploymentAssignment.id).where(*overlap_filters).limit(1)
            )
            if overlap is not None:
                raise ApiError(
                    status_code=409,
                    code="PRIMARY_ASSIGNMENT_PERIOD_OVERLAP",
                    message="同一雇佣关系在该有效期间只能有一条主组织和主职务关系",
                )
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

    async def create_agreement_relationship(
        self,
        payload: AgreementRelationshipCreate,
    ) -> AgreementRelationship:
        if await self._session.get(Person, payload.person_id) is None:
            raise ApiError(status_code=404, code="PERSON_NOT_FOUND", message="人员不存在")
        if (
            payload.legal_entity_id is not None
            and await self._session.get(LegalEntity, payload.legal_entity_id) is None
        ):
            raise ApiError(status_code=404, code="LEGAL_ENTITY_NOT_FOUND", message="法人主体不存在")
        relationship = AgreementRelationship(
            **payload.model_dump(exclude={"change_reason"})
        )
        self._session.add(relationship)
        await self._session.flush()
        self._audit(
            action="create",
            object_type="agreement_relationship",
            object_id=relationship.id,
            reason=payload.change_reason,
            after={
                "person_id": str(relationship.person_id),
                "agreement_type_code": relationship.agreement_type_code,
                "effective_from": relationship.effective_from.isoformat(),
            },
        )
        return relationship

    async def person_archive(
        self,
        person_id: UUID,
    ) -> tuple[Person, list[Employment], list[EmploymentAssignment], list[AgreementRelationship]]:
        person = await self._session.get(Person, person_id)
        if person is None:
            raise ApiError(status_code=404, code="PERSON_NOT_FOUND", message="人员不存在")
        employments = list(
            (
                await self._session.scalars(
                    select(Employment)
                    .where(Employment.person_id == person_id)
                    .order_by(Employment.planned_start_date.desc())
                )
            ).all()
        )
        employment_ids = [item.id for item in employments]
        assignments: list[EmploymentAssignment] = []
        if employment_ids:
            assignments = list(
                (
                    await self._session.scalars(
                        select(EmploymentAssignment)
                        .where(EmploymentAssignment.employment_id.in_(employment_ids))
                        .order_by(EmploymentAssignment.effective_from.desc())
                    )
                ).all()
            )
        agreements = list(
            (
                await self._session.scalars(
                    select(AgreementRelationship)
                    .where(AgreementRelationship.person_id == person_id)
                    .order_by(AgreementRelationship.effective_from.desc())
                )
            ).all()
        )
        return person, employments, assignments, agreements

    async def list_persons(
        self,
        *,
        search: str | None,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Person], int]:
        filters = []
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(Person.display_name.ilike(pattern), Person.employee_number.ilike(pattern))
            )
        if status:
            filters.append(Person.status == status)
        count_query = select(func.count()).select_from(Person).where(*filters)
        item_query = (
            select(Person)
            .where(*filters)
            .order_by(Person.employee_number.nulls_last(), Person.display_name)
            .limit(limit)
            .offset(offset)
        )
        total = await self._session.scalar(count_query)
        items = list((await self._session.scalars(item_query)).all())
        return items, total or 0

    async def create_headcount_plan(self, payload: HeadcountPlanCreate) -> HeadcountPlan:
        if await self._session.get(Organization, payload.organization_id) is None:
            raise ApiError(status_code=404, code="ORGANIZATION_NOT_FOUND", message="组织不存在")
        if await self._session.get(JobCatalog, payload.job_id) is None:
            raise ApiError(status_code=404, code="JOB_NOT_FOUND", message="职务不存在")
        matching_freezes = await self._matching_freezes(
            period_month=payload.period_month,
            organization_id=payload.organization_id,
            job_id=payload.job_id,
        )
        if matching_freezes and not payload.override_freeze:
            raise ApiError(
                status_code=409,
                code="HEADCOUNT_PLAN_FROZEN",
                message="目标组织、职务和月份处于冻结范围内",
                details=[
                    {"field": "freeze_id", "value": str(item.id)}
                    for item in matching_freezes
                ],
            )
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
        plan = HeadcountPlan(
            **payload.model_dump(exclude={"override_freeze"}),
            version=version,
            is_current=True,
        )
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
                "freeze_override": payload.override_freeze,
            },
        )
        return plan

    async def create_occupancy_rule(
        self,
        payload: OccupancyRuleCreate,
    ) -> OccupancyRule:
        current = await self._session.scalar(
            select(OccupancyRule)
            .where(OccupancyRule.employee_type_code == payload.employee_type_code)
            .order_by(OccupancyRule.version.desc())
            .limit(1)
            .with_for_update()
        )
        version = 1
        if current is not None:
            if payload.effective_from <= current.effective_from:
                raise ApiError(
                    status_code=409,
                    code="OCCUPANCY_RULE_DATE_NOT_FORWARD",
                    message="新占编规则的生效日期必须晚于当前版本",
                )
            current.effective_to = payload.effective_from - timedelta(days=1)
            version = current.version + 1
        rule = OccupancyRule(
            **payload.model_dump(exclude={"change_reason"}),
            version=version,
        )
        self._session.add(rule)
        await self._session.flush()
        self._audit(
            action="create_version",
            object_type="occupancy_rule",
            object_id=rule.id,
            reason=payload.change_reason,
            after={
                "employee_type_code": rule.employee_type_code,
                "counts_for_headcount": rule.counts_for_headcount,
                "effective_from": rule.effective_from.isoformat(),
                "version": rule.version,
            },
        )
        return rule

    async def create_headcount_freeze(
        self,
        payload: HeadcountFreezeCreate,
    ) -> HeadcountFreeze:
        if (
            payload.organization_id is not None
            and await self._session.get(Organization, payload.organization_id) is None
        ):
            raise ApiError(status_code=404, code="ORGANIZATION_NOT_FOUND", message="组织不存在")
        if payload.job_id is not None and await self._session.get(JobCatalog, payload.job_id) is None:
            raise ApiError(status_code=404, code="JOB_NOT_FOUND", message="职务不存在")
        freeze = HeadcountFreeze(**payload.model_dump(), status="active")
        self._session.add(freeze)
        await self._session.flush()
        self._audit(
            action="create",
            object_type="headcount_freeze",
            object_id=freeze.id,
            reason=payload.reason,
            after={
                "freeze_type": freeze.freeze_type,
                "period_month": freeze.period_month.isoformat() if freeze.period_month else None,
                "organization_id": str(freeze.organization_id) if freeze.organization_id else None,
                "job_id": str(freeze.job_id) if freeze.job_id else None,
            },
        )
        return freeze

    async def close_headcount_freeze(self, freeze_id: UUID, reason: str) -> HeadcountFreeze:
        freeze = await self._session.get(HeadcountFreeze, freeze_id, with_for_update=True)
        if freeze is None:
            raise ApiError(status_code=404, code="HEADCOUNT_FREEZE_NOT_FOUND", message="冻结记录不存在")
        if freeze.status != "active":
            raise ApiError(status_code=409, code="HEADCOUNT_FREEZE_NOT_ACTIVE", message="冻结记录已结束")
        before = {"status": freeze.status, "ends_at": freeze.ends_at.isoformat() if freeze.ends_at else None}
        freeze.status = "closed"
        freeze.ends_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(freeze)
        self._audit(
            action="close",
            object_type="headcount_freeze",
            object_id=freeze.id,
            reason=reason,
            before=before,
            after={"status": freeze.status, "ends_at": freeze.ends_at.isoformat()},
        )
        return freeze

    async def _organization_in_scope(
        self,
        organization_id: UUID,
        scope_organization_id: UUID,
        as_of: date,
    ) -> bool:
        current: UUID | None = organization_id
        visited: set[UUID] = set()
        while current is not None and current not in visited:
            if current == scope_organization_id:
                return True
            visited.add(current)
            version = await self._session.scalar(
                select(OrganizationVersion)
                .where(
                    OrganizationVersion.organization_id == current,
                    OrganizationVersion.effective_from <= as_of,
                    or_(
                        OrganizationVersion.effective_to.is_(None),
                        OrganizationVersion.effective_to >= as_of,
                    ),
                )
                .order_by(OrganizationVersion.version.desc())
                .limit(1)
            )
            current = version.parent_organization_id if version is not None else None
        return False

    async def _matching_freezes(
        self,
        *,
        period_month: date,
        organization_id: UUID,
        job_id: UUID,
    ) -> list[HeadcountFreeze]:
        now = datetime.now(UTC)
        candidates = list(
            (
                await self._session.scalars(
                    select(HeadcountFreeze).where(
                        HeadcountFreeze.status == "active",
                        HeadcountFreeze.starts_at <= now,
                        or_(HeadcountFreeze.ends_at.is_(None), HeadcountFreeze.ends_at > now),
                        or_(
                            HeadcountFreeze.period_month.is_(None),
                            HeadcountFreeze.period_month == period_month,
                        ),
                        or_(HeadcountFreeze.job_id.is_(None), HeadcountFreeze.job_id == job_id),
                    )
                )
            ).all()
        )
        matches: list[HeadcountFreeze] = []
        for freeze in candidates:
            if freeze.organization_id is None or await self._organization_in_scope(
                organization_id,
                freeze.organization_id,
                period_month,
            ):
                matches.append(freeze)
        return matches

    async def _count_people(self, organization_id: UUID, job_id: UUID, as_of: date) -> int:
        value = await self._session.scalar(
            select(func.count(func.distinct(Employment.person_id)))
            .select_from(Employment)
            .join(
                EmploymentAssignment,
                EmploymentAssignment.employment_id == Employment.id,
            )
            .join(
                OccupancyRule,
                OccupancyRule.employee_type_code == Employment.employee_type_code,
            )
            .where(
                EmploymentAssignment.organization_id == organization_id,
                EmploymentAssignment.job_id == job_id,
                EmploymentAssignment.relation_type == "primary",
                EmploymentAssignment.effective_from <= as_of,
                or_(
                    EmploymentAssignment.effective_to.is_(None),
                    EmploymentAssignment.effective_to >= as_of,
                ),
                Employment.planned_start_date <= as_of,
                or_(Employment.end_date.is_(None), Employment.end_date >= as_of),
                Employment.status.not_in(("withdrawn", "terminated")),
                OccupancyRule.counts_for_headcount.is_(True),
                OccupancyRule.effective_from <= as_of,
                or_(OccupancyRule.effective_to.is_(None), OccupancyRule.effective_to >= as_of),
            )
        )
        return int(value or 0)

    async def generate_headcount_snapshot(
        self,
        payload: HeadcountSnapshotGenerate,
    ) -> SnapshotBatch:
        try:
            timezone = ZoneInfo(payload.timezone)
        except ZoneInfoNotFoundError as caught:
            raise ApiError(status_code=422, code="TIMEZONE_INVALID", message="时区不是有效的IANA时区") from caught
        local_date = payload.boundary_at.astimezone(timezone).date()
        if payload.snapshot_type == "month_start":
            expected_date = payload.period_month
        else:
            next_month = (
                date(payload.period_month.year + 1, 1, 1)
                if payload.period_month.month == 12
                else date(payload.period_month.year, payload.period_month.month + 1, 1)
            )
            expected_date = next_month - timedelta(days=1)
        if local_date != expected_date:
            raise ApiError(
                status_code=422,
                code="SNAPSHOT_BOUNDARY_DATE_INVALID",
                message="快照边界时刻与快照类型、月份和时区不一致",
            )
        latest = await self._session.scalar(
            select(SnapshotBatch)
            .where(
                SnapshotBatch.snapshot_type == payload.snapshot_type,
                SnapshotBatch.boundary_at == payload.boundary_at,
            )
            .order_by(SnapshotBatch.version.desc())
            .limit(1)
        )
        if (
            latest is not None
            and latest.timezone == payload.timezone
            and latest.rule_version == payload.rule_version
            and latest.parent_batch_id == payload.parent_batch_id
            and latest.reason == payload.reason
            and latest.status == "completed"
        ):
            return latest
        if latest is not None and payload.parent_batch_id is None:
            raise ApiError(
                status_code=409,
                code="SNAPSHOT_REVISION_PARENT_REQUIRED",
                message="该边界已存在快照，修订时必须关联原批次",
            )
        if payload.parent_batch_id is not None:
            parent = await self._session.get(SnapshotBatch, payload.parent_batch_id)
            if (
                parent is None
                or parent.snapshot_type != payload.snapshot_type
                or parent.period_month != payload.period_month
                or parent.boundary_at != payload.boundary_at
            ):
                raise ApiError(status_code=422, code="SNAPSHOT_PARENT_INVALID", message="修订快照的原批次无效")
        version = (
            await self._session.scalar(
                select(func.max(SnapshotBatch.version)).where(
                    SnapshotBatch.snapshot_type == payload.snapshot_type,
                    SnapshotBatch.boundary_at == payload.boundary_at,
                )
            )
            or 0
        ) + 1
        batch = SnapshotBatch(
            **payload.model_dump(exclude={"reason"}),
            version=version,
            status="running",
            reason=payload.reason,
        )
        self._session.add(batch)
        await self._session.flush()
        plans = list(
            (
                await self._session.scalars(
                    select(HeadcountPlan).where(
                        HeadcountPlan.period_month == payload.period_month,
                        HeadcountPlan.is_current.is_(True),
                    )
                )
            ).all()
        )
        self._session.add_all(
            [
                HeadcountSnapshot(
                    batch_id=batch.id,
                    organization_id=plan.organization_id,
                    job_id=plan.job_id,
                    headcount_plan_id=plan.id,
                    person_count=await self._count_people(
                        plan.organization_id,
                        plan.job_id,
                        local_date,
                    ),
                    evidence={
                        "as_of": local_date.isoformat(),
                        "rule_version": payload.rule_version,
                    },
                )
                for plan in plans
            ]
        )
        batch.status = "completed"
        await self._session.flush()
        self._audit(
            action="generate",
            object_type="headcount_snapshot_batch",
            object_id=batch.id,
            reason=payload.reason,
            after={
                "snapshot_type": batch.snapshot_type,
                "period_month": batch.period_month.isoformat(),
                "timezone": batch.timezone,
                "version": batch.version,
                "row_count": len(plans),
            },
        )
        return batch

    async def headcount_results(
        self,
        *,
        period_month: date,
        as_of: date,
        organization_id: UUID | None,
        job_id: UUID | None,
    ) -> list[dict[str, Any]]:
        filters = [
            HeadcountPlan.period_month == period_month,
            HeadcountPlan.is_current.is_(True),
        ]
        if organization_id is not None:
            filters.append(HeadcountPlan.organization_id == organization_id)
        if job_id is not None:
            filters.append(HeadcountPlan.job_id == job_id)
        plans = list((await self._session.scalars(select(HeadcountPlan).where(*filters))).all())
        snapshot_counts: dict[tuple[str, UUID, UUID], int] = {}
        for snapshot_type in ("month_start", "month_end"):
            batch = await self._session.scalar(
                select(SnapshotBatch)
                .where(
                    SnapshotBatch.snapshot_type == snapshot_type,
                    SnapshotBatch.period_month == period_month,
                    SnapshotBatch.status == "completed",
                )
                .order_by(SnapshotBatch.boundary_at.desc(), SnapshotBatch.version.desc())
                .limit(1)
            )
            if batch is not None:
                rows = list(
                    (
                        await self._session.scalars(
                            select(HeadcountSnapshot).where(HeadcountSnapshot.batch_id == batch.id)
                        )
                    ).all()
                )
                for row in rows:
                    snapshot_counts[(snapshot_type, row.organization_id, row.job_id)] = row.person_count
        results: list[dict[str, Any]] = []
        for plan in plans:
            organization = await self._session.get(Organization, plan.organization_id)
            job = await self._session.get(JobCatalog, plan.job_id)
            if organization is None or job is None:
                continue
            current_count = await self._count_people(plan.organization_id, plan.job_id, as_of)
            start_count = snapshot_counts.get(("month_start", plan.organization_id, plan.job_id))
            end_count = snapshot_counts.get(("month_end", plan.organization_id, plan.job_id))
            average = (
                (Decimal(start_count) + Decimal(end_count)) / Decimal(2)
                if start_count is not None and end_count is not None
                else None
            )
            results.append(
                {
                    "organization_id": plan.organization_id,
                    "organization_code": organization.code,
                    "job_id": plan.job_id,
                    "job_code": job.code,
                    "job_name": job.name,
                    "period_month": plan.period_month,
                    "planned_count": plan.planned_count,
                    "plan_version": plan.version,
                    "current_count": current_count,
                    "variance": plan.planned_count - Decimal(current_count),
                    "month_start_count": start_count,
                    "month_end_count": end_count,
                    "average_count": average,
                    "frozen": bool(
                        await self._matching_freezes(
                            period_month=plan.period_month,
                            organization_id=plan.organization_id,
                            job_id=plan.job_id,
                        )
                    ),
                }
            )
        return results

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
    OccupancyRuleCreate,
