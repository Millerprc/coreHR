from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from hris.shared.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class WorkflowDefinition(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workflow_definitions"

    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    active_version: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)


class WorkflowVersion(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workflow_versions"
    __table_args__ = (
        UniqueConstraint("workflow_definition_id", "version"),
    )

    workflow_definition_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workflow_definitions.id"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    definition: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    change_reason: Mapped[str] = mapped_column(String(500), nullable=False)


class WorkflowInstance(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workflow_instances"

    instance_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )
    workflow_version_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workflow_versions.id"),
        nullable=False,
    )
    business_object_type: Mapped[str] = mapped_column(String(50), nullable=False)
    business_object_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    current_node_code: Mapped[str | None] = mapped_column(String(80))
    started_by: Mapped[UUID | None] = mapped_column(Uuid)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    context: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class WorkflowTask(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workflow_tasks"

    workflow_instance_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workflow_instances.id"),
        nullable=False,
        index=True,
    )
    node_code: Mapped[str] = mapped_column(String(80), nullable=False)
    sign_mode: Mapped[str] = mapped_column(String(10), nullable=False)
    assignee_type: Mapped[str] = mapped_column(String(30), nullable=False)
    assignee_ref: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    decision: Mapped[str | None] = mapped_column(String(30))
    comment: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[UUID | None] = mapped_column(Uuid)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Candidate(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "candidates"

    candidate_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    linked_person_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("persons.id"),
    )


class JobApplication(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "job_applications"
    __table_args__ = (
        UniqueConstraint("candidate_id", "recruitment_request_id"),
    )

    candidate_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("candidates.id"),
        nullable=False,
        index=True,
    )
    recruitment_request_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("recruitment_requests.id"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    current_stage: Mapped[str | None] = mapped_column(String(50))
    offer_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )


class ApplicationHireConversion(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "application_hire_conversions"

    application_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("job_applications.id"),
        unique=True,
        nullable=False,
    )
    candidate_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("candidates.id"),
        nullable=False,
        index=True,
    )
    person_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("persons.id"),
        nullable=False,
        index=True,
    )
    employment_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("employments.id"),
        unique=True,
        nullable=False,
    )
    assignment_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("employment_assignments.id"),
        unique=True,
        nullable=False,
    )
    idempotency_key: Mapped[UUID] = mapped_column(Uuid, unique=True, nullable=False)
    request_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    planned_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    employee_type_code: Mapped[str] = mapped_column(String(50), nullable=False)
    converted_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    converted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class ContractRecord(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "contract_records"
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
    employment_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("employments.id"),
    )
    contract_type_code: Mapped[str] = mapped_column(String(50), nullable=False)
    contract_number: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )
    legal_entity_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("legal_entities.id"),
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    metadata_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
