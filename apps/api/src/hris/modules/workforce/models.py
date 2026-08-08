from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from hris.shared.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class OrganizationType(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organization_types"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Organization(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)


class OrganizationVersion(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organization_versions"
    __table_args__ = (
        UniqueConstraint("organization_id", "version"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="effective_period_order",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    organization_type_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("organization_types.id"),
        nullable=False,
    )
    parent_organization_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("organizations.id"),
    )
    country_code: Mapped[str | None] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    change_reason: Mapped[str | None] = mapped_column(String(500))


class LegalEntity(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "legal_entities"
    __table_args__ = (
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="effective_period_order",
        ),
    )

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    registered_name: Mapped[str | None] = mapped_column(String(300))
    country_code: Mapped[str] = mapped_column(String(3), nullable=False)
    registration_number: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)


class OrganizationLegalEntity(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organization_legal_entities"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "legal_entity_id",
            "effective_from",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="effective_period_order",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    legal_entity_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("legal_entities.id"),
        nullable=False,
        index=True,
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class JobCatalog(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "job_catalog"
    __table_args__ = (
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="effective_period_order",
        ),
    )

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    level_code: Mapped[str | None] = mapped_column(String(50))
    grade_code: Mapped[str | None] = mapped_column(String(50))
    class_code: Mapped[str | None] = mapped_column(String(50))
    sequence_code: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class CostCenter(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cost_centers"
    __table_args__ = (
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="effective_period_order",
        ),
    )

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class OrganizationCostAllocation(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organization_cost_allocations"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "cost_center_id",
            "effective_from",
            "version",
        ),
        CheckConstraint(
            "allocation_percent > 0 AND allocation_percent <= 100",
            name="allocation_percent_range",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="effective_period_order",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    cost_center_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("cost_centers.id"),
        nullable=False,
    )
    allocation_percent: Mapped[Decimal] = mapped_column(
        Numeric(7, 4),
        nullable=False,
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class RevenueTarget(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "revenue_targets"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "year",
            "currency_code",
            "version",
        ),
        CheckConstraint("annual_amount >= 0", name="annual_amount_nonnegative"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    annual_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    change_reason: Mapped[str] = mapped_column(String(500), nullable=False)


class Person(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "persons"
    __table_args__ = (
        CheckConstraint(
            "employee_number IS NULL OR employee_number ~ '^[0-9]{6}$'",
            name="employee_number_format",
        ),
    )

    employee_number: Mapped[str | None] = mapped_column(
        String(6),
        unique=True,
        index=True,
    )
    display_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    former_name: Mapped[str | None] = mapped_column(String(200))
    gender_code: Mapped[str | None] = mapped_column(String(30))
    birth_date: Mapped[date | None] = mapped_column(Date)
    nationality_code: Mapped[str | None] = mapped_column(String(3))
    country_code: Mapped[str | None] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")


class PersonLabel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "person_labels"
    __table_args__ = (
        UniqueConstraint(
            "person_id",
            "label_type",
            "label_name",
            "effective_from",
            "source",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="effective_period_order",
        ),
    )

    person_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("persons.id"),
        nullable=False,
        index=True,
    )
    label_name: Mapped[str] = mapped_column(String(255), nullable=False)
    label_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Employment(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "employments"
    __table_args__ = (
        CheckConstraint(
            "end_date IS NULL OR end_date >= COALESCE(actual_start_date, planned_start_date)",
            name="employment_period_order",
        ),
    )

    person_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("persons.id"),
        nullable=False,
        index=True,
    )
    employee_type_code: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    planned_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_start_date: Mapped[date | None] = mapped_column(Date)
    probation_end_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    end_reason_code: Mapped[str | None] = mapped_column(String(50))
    contract_legal_entity_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("legal_entities.id"),
    )
    payroll_legal_entity_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("legal_entities.id"),
    )
    social_insurance_legal_entity_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("legal_entities.id"),
    )
    tax_legal_entity_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("legal_entities.id"),
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class EmploymentAssignment(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "employment_assignments"
    __table_args__ = (
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="effective_period_order",
        ),
    )

    employment_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("employments.id"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("job_catalog.id"))
    relation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    source_event_id: Mapped[UUID | None] = mapped_column(Uuid)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class OrganizationPersonRelation(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organization_person_relations"
    __table_args__ = (
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="effective_period_order",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    person_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("persons.id"),
        nullable=False,
        index=True,
    )
    relation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    bp_type: Mapped[str | None] = mapped_column(String(10))
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(String(500))


class ReportingRelation(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reporting_relations"
    __table_args__ = (
        CheckConstraint(
            "manager_person_id <> subordinate_person_id",
            name="different_people",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="effective_period_order",
        ),
    )

    manager_person_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("persons.id"),
        nullable=False,
        index=True,
    )
    subordinate_person_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("persons.id"),
        nullable=False,
        index=True,
    )
    relation_type: Mapped[str] = mapped_column(String(20), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)


class AgreementRelationship(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agreement_relationships"
    __table_args__ = (
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="effective_period_order",
        ),
    )

    person_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("persons.id"),
        nullable=False,
        index=True,
    )
    agreement_type_code: Mapped[str] = mapped_column(String(50), nullable=False)
    legal_entity_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("legal_entities.id"),
    )
    counterparty_name: Mapped[str | None] = mapped_column(String(300))
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(50), nullable=False)


class HeadcountPlan(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "headcount_plans"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "job_id",
            "period_month",
            "version",
        ),
        CheckConstraint("planned_count >= 0", name="planned_count_nonnegative"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("job_catalog.id"),
        nullable=False,
        index=True,
    )
    period_month: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    planned_count: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    change_reason: Mapped[str] = mapped_column(String(500), nullable=False)


class OccupancyRule(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "occupancy_rules"
    __table_args__ = (
        UniqueConstraint("employee_type_code", "effective_from", "version"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="effective_period_order",
        ),
    )

    employee_type_code: Mapped[str] = mapped_column(String(50), nullable=False)
    counts_for_headcount: Mapped[bool] = mapped_column(Boolean, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class HeadcountFreeze(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "headcount_freezes"

    freeze_type: Mapped[str] = mapped_column(String(20), nullable=False)
    period_month: Mapped[date | None] = mapped_column(Date, index=True)
    organization_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("organizations.id"),
    )
    job_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("job_catalog.id"))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(String(500), nullable=False)


class SnapshotBatch(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "snapshot_batches"
    __table_args__ = (
        UniqueConstraint("snapshot_type", "boundary_at", "version"),
    )

    snapshot_type: Mapped[str] = mapped_column(String(30), nullable=False)
    period_month: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    timezone: Mapped[str] = mapped_column(String(100), nullable=False)
    boundary_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    rule_version: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    parent_batch_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("snapshot_batches.id"),
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500))


class HeadcountSnapshot(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "headcount_snapshots"
    __table_args__ = (
        UniqueConstraint("batch_id", "organization_id", "job_id"),
    )

    batch_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("snapshot_batches.id"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("organizations.id"),
        nullable=False,
    )
    job_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("job_catalog.id"),
        nullable=False,
    )
    headcount_plan_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("headcount_plans.id"),
    )
    person_count: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class RecruitmentRequest(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recruitment_requests"
    __table_args__ = (
        CheckConstraint("requested_count > 0", name="requested_count_positive"),
    )

    request_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )
    organization_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("job_catalog.id"),
        nullable=False,
    )
    requested_count: Mapped[int] = mapped_column(Integer, nullable=False)
    target_month: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    workflow_instance_id: Mapped[UUID | None] = mapped_column(Uuid)


class HrEvent(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "hr_events"
    __table_args__ = (
        UniqueConstraint("event_number"),
    )

    event_number: Mapped[str] = mapped_column(String(50), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    object_type: Mapped[str] = mapped_column(String(50), nullable=False)
    object_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    before_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    planned_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    actual_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    workflow_instance_id: Mapped[UUID | None] = mapped_column(Uuid)
    related_event_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("hr_events.id"),
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class AuditLog(UuidPrimaryKeyMixin, Base):
    __tablename__ = "audit_logs"

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[UUID | None] = mapped_column(Uuid, index=True)
    trace_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    object_type: Mapped[str] = mapped_column(String(50), nullable=False)
    object_id: Mapped[UUID | None] = mapped_column(Uuid, index=True)
    reason: Mapped[str | None] = mapped_column(String(500))
    before_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    after_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
