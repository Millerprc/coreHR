# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""历史花名册的领域服务：按任意历史时点回看当时的员工名册。

Requirement: D-102 — 允许按任意历史时点查询花名册，且不新建第二套人员版本表。
底层 8/9 张花名册相关表已区间化（employments / employment_assignments /
organization_versions / job_catalog_versions ...），缺的是对外查询层。

时点取值口径（唯一口径，与 docs/review/moka-5-feature-decisions-2026-10-24.md §1.4 一致）：

    人员字段时点值(person, field, as_of)
      = persons 主档值（登记值）
        若存在 person_field_versions 记录 v 满足 v.effective_from <= as_of
          取其中 effective_from 最大的一条 v 的 v.new_value
        否则取主档值

    组织 / 雇佣 / 任职时点值
      = 区间化表中 effective_from <= as_of AND (effective_to IS NULL OR effective_to > as_of) 的记录

限制（如实实现，不得理想化）：没被修正过的人，其时点的姓名/证件等于当前值。
因此本结果是「登记值 + 已生效修正」的合成，不是完整的历史档案快照。
每行都带 field_history_available / corrected_fields 说明该行的字段值有多少修正历史支撑。
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import case, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.modules.workforce.models import (
    Employment,
    EmploymentAssignment,
    JobCatalog,
    JobCatalogVersion,
    Organization,
    OrganizationVersion,
    Person,
    PersonFieldVersion,
)
from hris.core.search import like_pattern
from hris.modules.workforce.person_corrections_service import PersonCorrectionService


# Requirement: D-102 — 字段级历史只覆盖「被修正过的字段」，
# 未被修正过的字段等于当前登记值；这条说明同时出现在接口响应与界面上。
FIELD_HISTORY_NOTE = (
    "时点的人员字段值 = 登记值 + 生效日期不晚于该时点的最后一条修正；"
    "未被修正过的字段等于当前值，本结果不是完整的历史档案快照。"
)

# Requirement: D-102 — 区间查询口径：effective_from <= as_of AND
# (effective_to IS NULL OR effective_to > as_of)。
# 说明：编制域的 _count_people 用的是 effective_to >= as_of，
# 本功能按决策文档的唯一口径取严格大于，边界日以本口径为准。
def interval_filters(model: Any, as_of: date) -> tuple[Any, ...]:
    return (
        model.effective_from <= as_of,
        or_(model.effective_to.is_(None), model.effective_to > as_of),
    )


# Requirement: D-102 — 在册口径复用编制域的雇佣过滤写法：
# 计划入职日已到、雇佣尚未结束、且不是撤回/终止状态。
# employments 表本身不是 effective_from/effective_to 区间表，
# 因此结束日沿用编制域的 end_date >= as_of。
EMPLOYMENT_EXCLUDED_STATUSES = ("withdrawn", "terminated")


@dataclass(frozen=True)
class HistoricalRosterRow:
    """花名册的一行：每一列都是该时点的值。"""

    person_id: UUID
    employee_number: str | None
    display_name: str | None
    legal_name: str | None
    organization_id: UUID | None
    organization_code: str | None
    organization_name: str | None
    job_id: UUID | None
    job_code: str | None
    job_name: str | None
    employment_status: str | None
    hire_date: date | None
    field_history_available: bool
    corrected_fields: list[str] = field(default_factory=list)


class HistoricalRosterService:
    """只读服务：不产生写操作，因此不需要 actor_id / trace_id。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def roster(
        self,
        *,
        as_of: date,
        search: str | None,
        organization_id: UUID | None,
        employment_status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[HistoricalRosterRow], int]:
        """返回该时点的在册名册。

        as_of 允许未来日期：未来时点没有数据时返回空列表，而不是 422。
        （与组织架构 as_of 的规则不同，D-013 只约束组织树只展示当前有效树。）
        """
        employment_conditions = [
            Employment.person_id == Person.id,
            Employment.planned_start_date <= as_of,
            or_(Employment.end_date.is_(None), Employment.end_date >= as_of),
            Employment.status.not_in(EMPLOYMENT_EXCLUDED_STATUSES),
        ]
        if employment_status:
            employment_conditions.append(Employment.status == employment_status)

        filters: list[Any] = [
            exists(select(Employment.id).where(*employment_conditions)),
        ]
        if organization_id is not None:
            # 主组织筛选落在该时点有效的主职关系上。
            filters.append(
                exists(
                    select(EmploymentAssignment.id)
                    .join(Employment, Employment.id == EmploymentAssignment.employment_id)
                    .where(
                        Employment.person_id == Person.id,
                        *employment_conditions,
                        EmploymentAssignment.relation_type == "primary",
                        EmploymentAssignment.organization_id == organization_id,
                        *interval_filters(EmploymentAssignment, as_of),
                    )
                )
            )
        if search:
            # Requirement: D-112 — 搜索词按字面量匹配，转义 LIKE 通配符。
            pattern = like_pattern(search)
            # 搜索按「时点姓名」匹配，而不是主档姓名：
            # 修正过的姓名在历史时点才是该人当时的姓名。
            filters.append(
                or_(
                    Person.employee_number.ilike(pattern, escape="\\"),
                    self._time_point_display_name(as_of).ilike(pattern, escape="\\"),
                )
            )

        total = await self._session.scalar(
            select(func.count()).select_from(Person).where(*filters)
        )
        persons = list(
            (
                await self._session.scalars(
                    select(Person)
                    .where(*filters)
                    .order_by(
                        Person.employee_number.nulls_last(),
                        Person.display_name,
                        Person.id,
                    )
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        if not persons:
            return [], int(total or 0)

        rows = await self._build_rows(persons, as_of=as_of, employment_status=employment_status)
        return rows, int(total or 0)

    def _time_point_display_name(self, as_of: date) -> Any:
        """时点姓名 = 登记姓名 + 生效日期 ≤ as_of 的最后一条 display_name 修正。

        Requirement: D-102 — 修正把姓名清空（new_value 为空）时，
        该时点姓名就是空值，因此这里用 CASE 区分「有修正」与「无修正」，
        不把「被清空」当成「没有修正」。
        """
        corrected_value = (
            select(PersonFieldVersion.new_value)
            .where(
                PersonFieldVersion.person_id == Person.id,
                PersonFieldVersion.field_code == "display_name",
                PersonFieldVersion.effective_from <= as_of,
            )
            .order_by(
                PersonFieldVersion.effective_from.desc(),
                PersonFieldVersion.version.desc(),
            )
            .limit(1)
            .scalar_subquery()
        )
        correction_count = (
            select(func.count())
            .select_from(PersonFieldVersion)
            .where(
                PersonFieldVersion.person_id == Person.id,
                PersonFieldVersion.field_code == "display_name",
                PersonFieldVersion.effective_from <= as_of,
            )
            .correlate(Person)
            .scalar_subquery()
        )
        return case((correction_count > 0, corrected_value), else_=Person.display_name)

    async def _build_rows(
        self,
        persons: list[Person],
        *,
        as_of: date,
        employment_status: str | None = None,
    ) -> list[HistoricalRosterRow]:
        person_ids = [person.id for person in persons]

        employment_conditions = [
            Employment.person_id.in_(person_ids),
            Employment.planned_start_date <= as_of,
            or_(Employment.end_date.is_(None), Employment.end_date >= as_of),
            Employment.status.not_in(EMPLOYMENT_EXCLUDED_STATUSES),
        ]
        if employment_status:
            # 与筛选口径一致：列表里显示的在职状态就是被筛选的那个状态。
            employment_conditions.append(Employment.status == employment_status)
        employment_result = await self._session.scalars(
            select(Employment).where(*employment_conditions)
        )
        employments = list(employment_result.all())
        employment_by_person: dict[UUID, Employment] = {}
        for employment in employments:
            current = employment_by_person.get(employment.person_id)
            if current is None or self._employment_rank(employment) > self._employment_rank(current):
                # 同一时点多段雇佣（再入职）时取最新的一段。
                employment_by_person[employment.person_id] = employment

        assignment_by_employment: dict[UUID, EmploymentAssignment] = {}
        if employment_by_person:
            assignment_result = await self._session.scalars(
                select(EmploymentAssignment).where(
                    EmploymentAssignment.employment_id.in_(
                        [employment.id for employment in employment_by_person.values()]
                    ),
                    EmploymentAssignment.relation_type == "primary",
                    *interval_filters(EmploymentAssignment, as_of),
                )
            )
            assignments = list(assignment_result.all())
            for assignment in assignments:
                current = assignment_by_employment.get(assignment.employment_id)
                if current is None or (
                    assignment.effective_from,
                    assignment.version,
                ) > (current.effective_from, current.version):
                    assignment_by_employment[assignment.employment_id] = assignment

        organization_ids = {
            assignment.organization_id
            for assignment in assignment_by_employment.values()
            if assignment.organization_id is not None
        }
        organization_codes = await self._organization_codes(organization_ids)
        organization_names = await self._organization_names(organization_ids, as_of=as_of)

        job_ids = {
            assignment.job_id
            for assignment in assignment_by_employment.values()
            if assignment.job_id is not None
        }
        job_codes = await self._job_codes(job_ids)
        job_names = await self._job_names(job_ids, as_of=as_of)

        overrides_by_person = await self._field_overrides(person_ids, as_of=as_of)

        rows: list[HistoricalRosterRow] = []
        for person in persons:
            employment = employment_by_person.get(person.id)
            assignment = (
                assignment_by_employment.get(employment.id) if employment is not None else None
            )
            overrides = overrides_by_person.get(person.id, {})
            display_name = overrides.get("display_name", person.display_name)
            legal_name = overrides.get("legal_name", person.legal_name)
            corrected_fields = sorted(overrides.keys())
            rows.append(
                HistoricalRosterRow(
                    person_id=person.id,
                    employee_number=person.employee_number,
                    display_name=display_name,
                    legal_name=legal_name,
                    organization_id=assignment.organization_id if assignment else None,
                    organization_code=(
                        organization_codes.get(assignment.organization_id)
                        if assignment
                        else None
                    ),
                    organization_name=(
                        organization_names.get(assignment.organization_id)
                        if assignment
                        else None
                    ),
                    job_id=assignment.job_id if assignment else None,
                    job_code=(job_codes.get(assignment.job_id) if assignment else None),
                    job_name=(job_names.get(assignment.job_id) if assignment else None),
                    employment_status=employment.status if employment else None,
                    hire_date=(
                        (employment.actual_start_date or employment.planned_start_date)
                        if employment
                        else None
                    ),
                    # 该行的字段值有多少修正历史支撑：
                    # False 意味着这一行的姓名/证件等于当前登记值。
                    field_history_available=bool(corrected_fields),
                    corrected_fields=corrected_fields,
                )
            )
        return rows

    @staticmethod
    def _employment_rank(employment: Employment) -> tuple[date, UUID]:
        return (employment.planned_start_date, employment.id)

    async def _organization_codes(self, organization_ids: set[UUID]) -> dict[UUID, str]:
        if not organization_ids:
            return {}
        rows = (
            await self._session.execute(
                select(Organization.id, Organization.code).where(
                    Organization.id.in_(organization_ids)
                )
            )
        ).all()
        return {row[0]: row[1] for row in rows}

    async def _organization_names(
        self,
        organization_ids: set[UUID],
        *,
        as_of: date,
    ) -> dict[UUID, str]:
        """该时点有效的组织名称（组织名在 organization_versions 里按生效日期切片）。"""
        if not organization_ids:
            return {}
        rows = (
            await self._session.execute(
                select(OrganizationVersion.organization_id, OrganizationVersion.name)
                .where(
                    OrganizationVersion.organization_id.in_(organization_ids),
                    *interval_filters(OrganizationVersion, as_of),
                )
                .order_by(OrganizationVersion.version.desc())
            )
        ).all()
        names: dict[UUID, str] = {}
        for organization_id, name in rows:
            names.setdefault(organization_id, name)
        return names

    async def _job_codes(self, job_ids: set[UUID]) -> dict[UUID, str]:
        if not job_ids:
            return {}
        rows = (
            await self._session.execute(
                select(JobCatalog.id, JobCatalog.code).where(JobCatalog.id.in_(job_ids))
            )
        ).all()
        return {row[0]: row[1] for row in rows}

    async def _job_names(self, job_ids: set[UUID], *, as_of: date) -> dict[UUID, str]:
        """该时点有效的职务名称（职务名在 job_catalog_versions 里按生效日期切片）。"""
        if not job_ids:
            return {}
        rows = (
            await self._session.execute(
                select(JobCatalogVersion.job_id, JobCatalogVersion.name)
                .where(
                    JobCatalogVersion.job_id.in_(job_ids),
                    *interval_filters(JobCatalogVersion, as_of),
                )
                .order_by(JobCatalogVersion.version.desc())
            )
        ).all()
        names: dict[UUID, str] = {}
        for job_id, name in rows:
            names.setdefault(job_id, name)
        return names

    async def _field_overrides(
        self,
        person_ids: list[UUID],
        *,
        as_of: date,
    ) -> dict[UUID, dict[str, str | None]]:
        """每个人的时点字段修正值。

        Requirement: D-102 — 取值口径直接复用修正服务的既有实现
        （person_corrections_service.effective_overrides），
        保证花名册与人员档案给出同一个时点结果。
        """
        if not person_ids:
            return {}
        version_result = await self._session.scalars(
            select(PersonFieldVersion).where(
                PersonFieldVersion.person_id.in_(person_ids),
                PersonFieldVersion.effective_from <= as_of,
            )
        )
        records = list(version_result.all())
        grouped: dict[UUID, list[tuple[PersonFieldVersion, str | None]]] = {}
        for record in records:
            grouped.setdefault(record.person_id, []).append((record, None))
        return {
            person_id: PersonCorrectionService.effective_overrides(versions, as_of)
            for person_id, versions in grouped.items()
        }
