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
    EmploymentLegalEntityRelationCreate,
    HeadcountFreezeCreate,
    HeadcountPlanCreate,
    HeadcountSnapshotGenerate,
    JobCreate,
    JobDimensionCreate,
    JobDimensionResponse,
    JobDimensionVersionCreate,
    JobResponse,
    JobVersionCreate,
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
    EmploymentLegalEntityRelation,
    HeadcountPlan,
    HeadcountFreeze,
    HeadcountSnapshot,
    OccupancyRule,
    JobCatalog,
    JobCatalogVersion,
    JobDimension,
    JobDimensionVersion,
    LegalEntity,
    Organization,
    OrganizationVersion,
    Person,
    PersonDocument,
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

    async def _dimension_at(
        self,
        *,
        dimension_type: str,
        code: str,
        effective_at: date,
        active_only: bool = True,
    ) -> tuple[JobDimension, JobDimensionVersion] | None:
        filters = [
            JobDimension.dimension_type == dimension_type,
            JobDimension.code == code,
            JobDimensionVersion.effective_from <= effective_at,
            or_(
                JobDimensionVersion.effective_to.is_(None),
                JobDimensionVersion.effective_to >= effective_at,
            ),
        ]
        if active_only:
            filters.append(JobDimensionVersion.status == "active")
        return (
            await self._session.execute(
                select(JobDimension, JobDimensionVersion)
                .join(
                    JobDimensionVersion,
                    JobDimensionVersion.dimension_id == JobDimension.id,
                )
                .where(*filters)
                .order_by(
                    JobDimensionVersion.effective_from.desc(),
                    JobDimensionVersion.version.desc(),
                )
                .limit(1)
            )
        ).one_or_none()

    async def _dimension_response(
        self,
        dimension: JobDimension,
        version: JobDimensionVersion,
    ) -> JobDimensionResponse:
        parent = (
            await self._session.get(JobDimension, version.parent_dimension_id)
            if version.parent_dimension_id is not None
            else None
        )
        return JobDimensionResponse(
            id=dimension.id,
            dimension_type=dimension.dimension_type,
            code=dimension.code,
            name=version.name,
            parent_dimension_id=parent.id if parent else None,
            parent_dimension_type=parent.dimension_type if parent else None,
            parent_dimension_code=parent.code if parent else None,
            sort_order=version.sort_order,
            status=version.status,
            effective_from=version.effective_from,
            effective_to=version.effective_to,
            version=version.version,
            notes=version.notes,
        )

    async def _resolve_parent_dimension(
        self,
        *,
        parent_type: str | None,
        parent_code: str | None,
        effective_at: date,
        child_id: UUID | None = None,
    ) -> JobDimension | None:
        if parent_type is None or parent_code is None:
            return None
        resolved = await self._dimension_at(
            dimension_type=parent_type,
            code=parent_code,
            effective_at=effective_at,
        )
        if resolved is None:
            raise ApiError(
                status_code=422,
                code="JOB_DIMENSION_PARENT_NOT_EFFECTIVE",
                message="父职务维度不存在或在生效日期未启用",
            )
        parent, parent_version = resolved
        visited: set[UUID] = set()
        while child_id is not None and parent is not None:
            if parent.id == child_id:
                raise ApiError(
                    status_code=422,
                    code="JOB_DIMENSION_PARENT_CYCLE",
                    message="职务维度父级不能形成循环",
                )
            if parent.id in visited or parent_version.parent_dimension_id is None:
                break
            visited.add(parent.id)
            next_parent = await self._session.get(
                JobDimension,
                parent_version.parent_dimension_id,
            )
            if next_parent is None:
                break
            next_version = await self._session.scalar(
                select(JobDimensionVersion)
                .where(
                    JobDimensionVersion.dimension_id == next_parent.id,
                    JobDimensionVersion.effective_from <= effective_at,
                    or_(
                        JobDimensionVersion.effective_to.is_(None),
                        JobDimensionVersion.effective_to >= effective_at,
                    ),
                )
                .order_by(JobDimensionVersion.version.desc())
                .limit(1)
            )
            if next_version is None:
                break
            parent, parent_version = next_parent, next_version
        return resolved[0]

    async def create_job_dimension(
        self,
        payload: JobDimensionCreate,
    ) -> JobDimensionResponse:
        existing = await self._session.scalar(
            select(JobDimension).where(
                JobDimension.dimension_type == payload.dimension_type,
                JobDimension.code == payload.code,
            )
        )
        if existing is not None:
            raise ApiError(
                status_code=409,
                code="JOB_DIMENSION_CODE_EXISTS",
                message="同类型职务维度代码已存在",
            )
        parent = await self._resolve_parent_dimension(
            parent_type=payload.parent_dimension_type,
            parent_code=payload.parent_dimension_code,
            effective_at=payload.effective_from,
        )
        dimension = JobDimension(
            dimension_type=payload.dimension_type,
            code=payload.code,
        )
        self._session.add(dimension)
        await self._session.flush()
        version = JobDimensionVersion(
            dimension_id=dimension.id,
            version=1,
            name=payload.name,
            parent_dimension_id=parent.id if parent else None,
            sort_order=payload.sort_order,
            status=payload.status,
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            is_current=True,
            notes=payload.notes,
            change_reason=payload.change_reason,
        )
        self._session.add(version)
        await self._session.flush()
        self._audit(
            action="create",
            object_type="job_dimension",
            object_id=dimension.id,
            reason=payload.change_reason,
            after={
                "dimension_type": dimension.dimension_type,
                "code": dimension.code,
                "version": 1,
            },
        )
        return await self._dimension_response(dimension, version)

    async def create_job_dimension_version(
        self,
        dimension_id: UUID,
        payload: JobDimensionVersionCreate,
    ) -> JobDimensionResponse:
        dimension = await self._session.get(JobDimension, dimension_id, with_for_update=True)
        if dimension is None:
            raise ApiError(status_code=404, code="JOB_DIMENSION_NOT_FOUND", message="职务维度不存在")
        latest = await self._session.scalar(
            select(JobDimensionVersion)
            .where(JobDimensionVersion.dimension_id == dimension.id)
            .order_by(JobDimensionVersion.version.desc())
            .limit(1)
            .with_for_update()
        )
        if latest is None:
            raise ApiError(status_code=409, code="JOB_DIMENSION_VERSION_MISSING", message="职务维度缺少初始版本")
        if payload.effective_from <= latest.effective_from:
            raise ApiError(
                status_code=409,
                code="JOB_DIMENSION_VERSION_DATE_NOT_FORWARD",
                message="新版本生效日期必须晚于最新版本",
            )
        parent = await self._resolve_parent_dimension(
            parent_type=payload.parent_dimension_type,
            parent_code=payload.parent_dimension_code,
            effective_at=payload.effective_from,
            child_id=dimension.id,
        )
        if latest.effective_to is None or latest.effective_to >= payload.effective_from:
            latest.effective_to = payload.effective_from - timedelta(days=1)
        latest.is_current = False
        version = JobDimensionVersion(
            dimension_id=dimension.id,
            version=latest.version + 1,
            name=payload.name,
            parent_dimension_id=parent.id if parent else None,
            sort_order=payload.sort_order,
            status=payload.status,
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            is_current=True,
            notes=payload.notes,
            change_reason=payload.change_reason,
        )
        self._session.add(version)
        await self._session.flush()
        self._audit(
            action="create_version",
            object_type="job_dimension",
            object_id=dimension.id,
            reason=payload.change_reason,
            before={"version": latest.version, "effective_to": latest.effective_to.isoformat()},
            after={"version": version.version, "effective_from": version.effective_from.isoformat()},
        )
        return await self._dimension_response(dimension, version)

    async def list_job_dimensions(
        self,
        *,
        dimension_type: str | None,
        effective_at: date,
        limit: int,
        offset: int,
    ) -> tuple[list[JobDimensionResponse], int]:
        filters = [
            JobDimensionVersion.effective_from <= effective_at,
            or_(
                JobDimensionVersion.effective_to.is_(None),
                JobDimensionVersion.effective_to >= effective_at,
            ),
        ]
        if dimension_type is not None:
            filters.append(JobDimension.dimension_type == dimension_type)
        pairs = (
            await self._session.execute(
                select(JobDimension, JobDimensionVersion)
                .join(
                    JobDimensionVersion,
                    JobDimensionVersion.dimension_id == JobDimension.id,
                )
                .where(*filters)
                .order_by(JobDimension.dimension_type, JobDimension.code)
                .limit(limit)
                .offset(offset)
            )
        ).all()
        items = [
            await self._dimension_response(dimension, version)
            for dimension, version in pairs
        ]
        total = await self._session.scalar(
            select(func.count(func.distinct(JobDimension.id)))
            .select_from(JobDimension)
            .join(
                JobDimensionVersion,
                JobDimensionVersion.dimension_id == JobDimension.id,
            )
            .where(*filters)
        )
        return items, total or 0

    async def _resolve_job_dimensions(
        self,
        *,
        level_code: str,
        grade_code: str,
        class_code: str,
        sequence_code: str,
        effective_at: date,
    ) -> dict[str, JobDimension]:
        result: dict[str, JobDimension] = {}
        for key, dimension_type, code in (
            ("level", "LEVEL", level_code),
            ("grade", "GRADE", grade_code),
            ("class", "CLASS", class_code),
            ("sequence", "SEQUENCE", sequence_code),
        ):
            resolved = await self._dimension_at(
                dimension_type=dimension_type,
                code=code,
                effective_at=effective_at,
            )
            if resolved is None:
                raise ApiError(
                    status_code=422,
                    code="JOB_DIMENSION_NOT_EFFECTIVE",
                    message=f"{dimension_type}维度代码不存在或在职务生效日未启用",
                )
            result[key] = resolved[0]
        return result

    @staticmethod
    def _job_response(
        job: JobCatalog,
        version: JobCatalogVersion,
        dimensions: dict[str, JobDimension],
    ) -> JobResponse:
        return JobResponse(
            id=job.id,
            code=job.code,
            name=version.name,
            level_code=dimensions["level"].code,
            grade_code=dimensions["grade"].code,
            class_code=dimensions["class"].code,
            sequence_code=dimensions["sequence"].code,
            status=version.status,
            effective_from=version.effective_from,
            effective_to=version.effective_to,
            version=version.version,
            source_job_id=version.source_job_id,
            notes=version.notes,
            attributes=version.attributes,
        )

    async def _job_version_at(
        self,
        job_id: UUID,
        effective_at: date,
        *,
        active_only: bool = True,
    ) -> JobCatalogVersion | None:
        filters = [
            JobCatalogVersion.job_id == job_id,
            JobCatalogVersion.effective_from <= effective_at,
            or_(
                JobCatalogVersion.effective_to.is_(None),
                JobCatalogVersion.effective_to >= effective_at,
            ),
        ]
        if active_only:
            filters.append(JobCatalogVersion.status == "active")
        return await self._session.scalar(
            select(JobCatalogVersion)
            .where(*filters)
            .order_by(
                JobCatalogVersion.effective_from.desc(),
                JobCatalogVersion.version.desc(),
            )
            .limit(1)
        )

    async def _job_effective_at(self, job_id: UUID, effective_at: date) -> bool:
        if await self._job_version_at(job_id, effective_at) is not None:
            return True
        legacy = await self._session.get(JobCatalog, job_id)
        return bool(
            legacy is not None
            and legacy.status == "active"
            and legacy.effective_from <= effective_at
            and (legacy.effective_to is None or legacy.effective_to >= effective_at)
        )

    async def ensure_job_effective(self, job_id: UUID, effective_at: date) -> None:
        if not await self._job_effective_at(job_id, effective_at):
            raise ApiError(
                status_code=422,
                code="JOB_NOT_EFFECTIVE",
                message="职务不存在或在目标生效日期未启用",
            )

    async def _job_dimensions_for_version(
        self,
        version: JobCatalogVersion,
    ) -> dict[str, JobDimension] | None:
        dimension_ids = {
            "level": version.level_dimension_id,
            "grade": version.grade_dimension_id,
            "class": version.class_dimension_id,
            "sequence": version.sequence_dimension_id,
        }
        if any(value is None for value in dimension_ids.values()):
            return None
        dimensions: dict[str, JobDimension] = {}
        for key, dimension_id in dimension_ids.items():
            dimension = await self._session.get(JobDimension, dimension_id)
            if dimension is None:
                return None
            dimensions[key] = dimension
        return dimensions

    async def create_job(self, payload: JobCreate) -> JobResponse:
        await self._ensure_unique(JobCatalog, JobCatalog.code, payload.code, "JOB_CODE_EXISTS")
        dimensions = await self._resolve_job_dimensions(
            level_code=payload.level_code,
            grade_code=payload.grade_code,
            class_code=payload.class_code,
            sequence_code=payload.sequence_code,
            effective_at=payload.effective_from,
        )
        job = JobCatalog(
            code=payload.code,
            name=payload.name,
            level_code=payload.level_code,
            grade_code=payload.grade_code,
            class_code=payload.class_code,
            sequence_code=payload.sequence_code,
            status=payload.status,
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            attributes=payload.attributes,
        )
        self._session.add(job)
        await self._session.flush()
        version = JobCatalogVersion(
            job_id=job.id,
            version=1,
            name=payload.name,
            level_dimension_id=dimensions["level"].id,
            grade_dimension_id=dimensions["grade"].id,
            class_dimension_id=dimensions["class"].id,
            sequence_dimension_id=dimensions["sequence"].id,
            status=payload.status,
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            is_current=True,
            source_job_id=payload.source_job_id,
            notes=payload.notes,
            attributes=payload.attributes,
            change_reason=payload.change_reason,
        )
        self._session.add(version)
        await self._session.flush()
        self._audit(
            action="create",
            object_type="job",
            object_id=job.id,
            reason=payload.change_reason,
            after={"code": job.code, "name": version.name, "version": 1},
        )
        return self._job_response(job, version, dimensions)

    async def create_job_version(
        self,
        job_id: UUID,
        payload: JobVersionCreate,
    ) -> JobResponse:
        job = await self._session.get(JobCatalog, job_id, with_for_update=True)
        if job is None:
            raise ApiError(status_code=404, code="JOB_NOT_FOUND", message="职务不存在")
        latest = await self._session.scalar(
            select(JobCatalogVersion)
            .where(JobCatalogVersion.job_id == job.id)
            .order_by(JobCatalogVersion.version.desc())
            .limit(1)
            .with_for_update()
        )
        if latest is None:
            raise ApiError(status_code=409, code="JOB_VERSION_MISSING", message="职务缺少初始版本")
        if payload.effective_from <= latest.effective_from:
            raise ApiError(
                status_code=409,
                code="JOB_VERSION_DATE_NOT_FORWARD",
                message="新版本生效日期必须晚于最新版本",
            )
        dimensions = await self._resolve_job_dimensions(
            level_code=payload.level_code,
            grade_code=payload.grade_code,
            class_code=payload.class_code,
            sequence_code=payload.sequence_code,
            effective_at=payload.effective_from,
        )
        if latest.effective_to is None or latest.effective_to >= payload.effective_from:
            latest.effective_to = payload.effective_from - timedelta(days=1)
        latest.is_current = False
        version = JobCatalogVersion(
            job_id=job.id,
            version=latest.version + 1,
            name=payload.name,
            level_dimension_id=dimensions["level"].id,
            grade_dimension_id=dimensions["grade"].id,
            class_dimension_id=dimensions["class"].id,
            sequence_dimension_id=dimensions["sequence"].id,
            status=payload.status,
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            is_current=True,
            source_job_id=payload.source_job_id,
            notes=payload.notes,
            attributes=payload.attributes,
            change_reason=payload.change_reason,
        )
        self._session.add(version)
        job.name = version.name
        job.level_code = dimensions["level"].code
        job.grade_code = dimensions["grade"].code
        job.class_code = dimensions["class"].code
        job.sequence_code = dimensions["sequence"].code
        job.status = version.status
        job.effective_from = version.effective_from
        job.effective_to = version.effective_to
        job.attributes = version.attributes
        await self._session.flush()
        self._audit(
            action="create_version",
            object_type="job",
            object_id=job.id,
            reason=payload.change_reason,
            before={"version": latest.version, "effective_to": latest.effective_to.isoformat()},
            after={"version": version.version, "effective_from": version.effective_from.isoformat()},
        )
        return self._job_response(job, version, dimensions)

    async def list_jobs(
        self,
        *,
        effective_at: date,
        limit: int,
        offset: int,
    ) -> tuple[list[JobResponse], int]:
        effective_filters = (
            JobCatalogVersion.effective_from <= effective_at,
            or_(
                JobCatalogVersion.effective_to.is_(None),
                JobCatalogVersion.effective_to >= effective_at,
            ),
        )
        pairs = (
            await self._session.execute(
                select(JobCatalog, JobCatalogVersion)
                .join(JobCatalogVersion, JobCatalogVersion.job_id == JobCatalog.id)
                .where(*effective_filters)
                .order_by(JobCatalog.code)
                .limit(limit)
                .offset(offset)
            )
        ).all()
        items: list[JobResponse] = []
        for job, version in pairs:
            dimensions = await self._job_dimensions_for_version(version)
            if dimensions is None:
                continue
            items.append(self._job_response(job, version, dimensions))
        total = await self._session.scalar(
            select(func.count(func.distinct(JobCatalog.id)))
            .select_from(JobCatalog)
            .join(JobCatalogVersion, JobCatalogVersion.job_id == JobCatalog.id)
            .where(*effective_filters)
        )
        return items, total or 0

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
            after={
                "employee_number": person.employee_number,
                "status": person.status,
                "changed_fields": sorted(data),
            },
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
        for field, value in changes.items():
            setattr(person, field, value)
        await self._session.flush()
        await self._session.refresh(person)
        self._audit(
            action="update",
            object_type="person",
            object_id=person.id,
            reason=payload.change_reason,
            before={"changed_fields": sorted(changes)},
            after={"changed_fields": sorted(changes)},
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
        primary_document = await self._session.scalar(
            select(PersonDocument.id).where(
                PersonDocument.person_id == payload.person_id,
                PersonDocument.is_primary.is_(True),
                PersonDocument.verification_status == "verified",
                PersonDocument.effective_from <= payload.planned_start_date,
                or_(
                    PersonDocument.effective_to.is_(None),
                    PersonDocument.effective_to >= payload.planned_start_date,
                ),
                or_(
                    PersonDocument.expiry_date.is_(None),
                    PersonDocument.expiry_date >= payload.planned_start_date,
                ),
            ).limit(1)
        )
        if primary_document is None:
            raise ApiError(
                status_code=422,
                code="VERIFIED_PRIMARY_DOCUMENT_REQUIRED",
                message="创建待入职劳动关系前，计划入职日必须存在一张已核验且有效的主要证件",
            )
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
        relation_values = {
            "contract": employment.contract_legal_entity_id,
            "payroll": employment.payroll_legal_entity_id,
            "social_insurance": employment.social_insurance_legal_entity_id,
            "tax": employment.tax_legal_entity_id,
        }
        self._session.add_all(
            [
                EmploymentLegalEntityRelation(
                    employment_id=employment.id,
                    relation_kind=relation_kind,
                    legal_entity_id=legal_entity_id,
                    effective_from=employment.planned_start_date,
                    version=1,
                    change_reason=payload.change_reason,
                )
                for relation_kind, legal_entity_id in relation_values.items()
            ]
        )
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

    async def list_employment_legal_entity_relations(
        self,
        employment_id: UUID,
        *,
        effective_at: date,
    ) -> list[EmploymentLegalEntityRelation]:
        if await self._session.get(Employment, employment_id) is None:
            raise ApiError(status_code=404, code="EMPLOYMENT_NOT_FOUND", message="劳动关系不存在")
        return list(
            (
                await self._session.scalars(
                    select(EmploymentLegalEntityRelation)
                    .where(
                        EmploymentLegalEntityRelation.employment_id == employment_id,
                        EmploymentLegalEntityRelation.effective_from <= effective_at,
                        or_(
                            EmploymentLegalEntityRelation.effective_to.is_(None),
                            EmploymentLegalEntityRelation.effective_to >= effective_at,
                        ),
                    )
                    .order_by(EmploymentLegalEntityRelation.relation_kind)
                )
            ).all()
        )

    async def create_employment_legal_entity_relation_version(
        self,
        employment_id: UUID,
        payload: EmploymentLegalEntityRelationCreate,
    ) -> EmploymentLegalEntityRelation:
        employment = await self._session.get(Employment, employment_id, with_for_update=True)
        if employment is None:
            raise ApiError(status_code=404, code="EMPLOYMENT_NOT_FOUND", message="劳动关系不存在")
        if await self._session.get(LegalEntity, payload.legal_entity_id) is None:
            raise ApiError(status_code=422, code="LEGAL_ENTITY_NOT_FOUND", message="法人主体不存在")
        current = await self._session.scalar(
            select(EmploymentLegalEntityRelation)
            .where(
                EmploymentLegalEntityRelation.employment_id == employment_id,
                EmploymentLegalEntityRelation.relation_kind == payload.relation_kind,
                EmploymentLegalEntityRelation.effective_to.is_(None),
            )
            .order_by(EmploymentLegalEntityRelation.version.desc())
            .limit(1)
            .with_for_update()
        )
        if current is None:
            raise ApiError(status_code=409, code="LEGAL_ENTITY_RELATION_BASE_MISSING", message="四类主体初始版本不存在")
        if payload.effective_from <= current.effective_from:
            raise ApiError(
                status_code=409,
                code="LEGAL_ENTITY_RELATION_DATE_NOT_FORWARD",
                message="新版本生效日期必须晚于当前版本",
            )
        current.effective_to = payload.effective_from - timedelta(days=1)
        relation = EmploymentLegalEntityRelation(
            employment_id=employment_id,
            relation_kind=payload.relation_kind,
            legal_entity_id=payload.legal_entity_id,
            effective_from=payload.effective_from,
            version=current.version + 1,
            change_reason=payload.change_reason,
        )
        projection_field = {
            "contract": "contract_legal_entity_id",
            "payroll": "payroll_legal_entity_id",
            "social_insurance": "social_insurance_legal_entity_id",
            "tax": "tax_legal_entity_id",
        }[payload.relation_kind]
        setattr(employment, projection_field, payload.legal_entity_id)
        self._session.add(relation)
        await self._session.flush()
        self._audit(
            action="version",
            object_type="employment_legal_entity_relation",
            object_id=relation.id,
            reason=payload.change_reason,
            before={
                "legal_entity_id": str(current.legal_entity_id),
                "effective_from": current.effective_from.isoformat(),
                "effective_to": current.effective_to.isoformat(),
                "version": current.version,
            },
            after={
                "legal_entity_id": str(relation.legal_entity_id),
                "effective_from": relation.effective_from.isoformat(),
                "version": relation.version,
            },
        )
        return relation

    async def create_assignment(
        self,
        payload: EmploymentAssignmentCreate,
    ) -> EmploymentAssignment:
        if await self._session.get(Employment, payload.employment_id) is None:
            raise ApiError(status_code=404, code="EMPLOYMENT_NOT_FOUND", message="劳动关系不存在")
        if await self._session.get(Organization, payload.organization_id) is None:
            raise ApiError(status_code=404, code="ORGANIZATION_NOT_FOUND", message="组织不存在")
        if (
            payload.job_id is not None
            and not await self._job_effective_at(payload.job_id, payload.effective_from)
        ):
            raise ApiError(
                status_code=422,
                code="JOB_NOT_EFFECTIVE",
                message="职务不存在或在任职生效日期未启用",
            )
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
    ) -> tuple[
        Person,
        list[Employment],
        list[EmploymentLegalEntityRelation],
        list[EmploymentAssignment],
        list[AgreementRelationship],
    ]:
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
        legal_entity_relations: list[EmploymentLegalEntityRelation] = []
        if employment_ids:
            legal_entity_relations = list(
                (
                    await self._session.scalars(
                        select(EmploymentLegalEntityRelation)
                        .where(EmploymentLegalEntityRelation.employment_id.in_(employment_ids))
                        .order_by(
                            EmploymentLegalEntityRelation.relation_kind,
                            EmploymentLegalEntityRelation.effective_from.desc(),
                        )
                    )
                ).all()
            )
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
        return person, employments, legal_entity_relations, assignments, agreements

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
        if not await self._job_effective_at(payload.job_id, payload.period_month):
            raise ApiError(
                status_code=422,
                code="JOB_NOT_EFFECTIVE",
                message="职务不存在或在目标月份未启用",
            )
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
            job_version = await self._job_version_at(plan.job_id, as_of)
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
                    "job_name": job_version.name if job_version else job.name,
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
