from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.config import get_settings
from hris.core.concurrency import VersionCommand
from hris.core.errors import ApiError
from hris.modules.platform.governance_models import OutboxEvent
from hris.modules.platform.numbering import next_number
from hris.modules.workforce.models import (
    AuditLog,
    CostCenter,
    LegalEntity,
    Organization,
    OrganizationCostAllocation,
    OrganizationLegalEntity,
    OrganizationType,
    OrganizationVersion,
    Person,
    RevenueTarget,
)
from hris.modules.workforce.organization_models import (
    BpServiceScope,
    OrganizationEvent,
    OrganizationLeader,
    PersonBpMembership,
    RevenueTargetMonth,
)
from hris.modules.workforce.organization_policy import (
    DomainViolation,
    assert_allocation_total,
    assert_no_cycle,
    assert_revenue_total,
)
from hris.modules.workforce.organization_schemas import (
    BpMembershipCreate,
    BpMembershipView,
    BpServiceScopeSet,
    CostAllocationLine,
    CostAllocationSet,
    CostAllocationView,
    CostCenterCreate,
    CostCenterView,
    OrganizationCreate,
    OrganizationEventView,
    OrganizationLeaderSet,
    OrganizationLegalEntitySet,
    OrganizationRelationsView,
    OrganizationTreeNode,
    OrganizationTypeCreate,
    OrganizationTypeUpdate,
    OrganizationTypeView,
    OrganizationVersionCreate,
    OrganizationView,
    RelationSetView,
    RevenueAggregationView,
    RevenueCurrencyTotal,
    RevenueTargetMonthInput,
    RevenueTargetSet,
    RevenueTargetView,
)


class OrganizationService:
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
        self._timezone = ZoneInfo(get_settings().business_timezone)

    def business_date(self) -> date:
        return datetime.now(self._timezone).date()

    async def create_type(
        self,
        payload: OrganizationTypeCreate,
    ) -> OrganizationTypeView:
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:type_code))"),
            {"type_code": f"corehr:organization-type:{payload.code}"},
        )
        existing = await self._session.scalar(
            select(OrganizationType).where(OrganizationType.code == payload.code)
        )
        if existing is not None:
            raise ApiError(
                status_code=409,
                code="ORGANIZATION_TYPE_CODE_CONFLICT",
                message="组织类型代码已存在",
            )

        organization_type = OrganizationType(
            **payload.model_dump(),
            is_active=True,
        )
        self._session.add(organization_type)
        await self._session.flush()
        await self._audit(
            action="organization.type.create",
            object_type="organization_type",
            object_id=organization_type.id,
            reason="创建组织类型",
            before={},
            after=self._type_payload(organization_type),
        )
        await self._outbox(
            "organization.type.created",
            "organization_type",
            organization_type.id,
            {"organization_type_id": str(organization_type.id)},
        )
        return OrganizationTypeView.model_validate(organization_type)

    async def list_types(self, active_only: bool) -> list[OrganizationTypeView]:
        statement = select(OrganizationType)
        if active_only:
            statement = statement.where(OrganizationType.is_active.is_(True))
        items = (
            await self._session.scalars(
                statement.order_by(OrganizationType.sort_order, OrganizationType.code)
            )
        ).all()
        return [OrganizationTypeView.model_validate(item) for item in items]

    async def update_type(
        self,
        type_id: UUID,
        payload: OrganizationTypeUpdate,
    ) -> OrganizationTypeView:
        organization_type = await self._session.get(OrganizationType, type_id)
        if organization_type is None:
            raise ApiError(
                status_code=404,
                code="ORGANIZATION_TYPE_NOT_FOUND",
                message="组织类型不存在",
            )
        before = self._type_payload(organization_type)
        changes = payload.model_dump(
            include={"name", "sort_order", "is_active"},
            exclude_unset=True,
        )
        for field, value in changes.items():
            setattr(organization_type, field, value)
        await self._session.flush()
        await self._session.refresh(organization_type)
        await self._audit(
            action="organization.type.update",
            object_type="organization_type",
            object_id=organization_type.id,
            reason=payload.change_reason,
            before=before,
            after=self._type_payload(organization_type),
        )
        await self._outbox(
            "organization.type.updated",
            "organization_type",
            organization_type.id,
            {"organization_type_id": str(organization_type.id)},
        )
        return OrganizationTypeView.model_validate(organization_type)

    async def create(self, payload: OrganizationCreate) -> OrganizationView:
        await self._lock_idempotency(payload.command.idempotency_key)
        existing_event = await self._event_by_idempotency(
            payload.command.idempotency_key
        )
        if existing_event is not None:
            if existing_event.event_type != "CREATE":
                self._raise_idempotency_conflict()
            return await self.get_as_of(
                existing_event.organization_id,
                existing_event.effective_date,
            )
        if payload.command.expected_version != 1:
            self._raise_version_conflict(1, payload.command.expected_version)

        await self._organization_type(payload.organization_type_id, active_required=True)
        if payload.parent_organization_id is not None:
            await self._state_as_of(payload.parent_organization_id, payload.effective_from)

        code = await next_number(
            self._session,
            sequence_code="ORG_NUMBER",
            width=6,
            max_value=999_999,
        )
        organization = Organization(code=code)
        self._session.add(organization)
        await self._session.flush()

        parents = await self._parent_map_as_of(payload.effective_from)
        try:
            assert_no_cycle(
                organization.id,
                payload.parent_organization_id,
                parents,
            )
        except DomainViolation as exc:
            self._raise_domain(exc)

        version = OrganizationVersion(
            organization_id=organization.id,
            version=1,
            name=payload.name,
            organization_type_id=payload.organization_type_id,
            parent_organization_id=payload.parent_organization_id,
            country_code=payload.country_code,
            status="active",
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            is_current=payload.effective_from <= self.business_date()
            and (payload.effective_to is None or payload.effective_to >= self.business_date()),
            change_reason=payload.command.change_reason,
        )
        self._session.add(version)
        await self._session.flush()

        event = OrganizationEvent(
            organization_id=organization.id,
            event_type="CREATE",
            effective_date=payload.effective_from,
            status="applied",
            payload={"organization_id": str(organization.id), "version": 1},
            expected_version=1,
            idempotency_key=payload.command.idempotency_key,
            change_reason=payload.command.change_reason,
            applied_at=datetime.now(UTC),
        )
        self._session.add(event)
        await self._session.flush()
        await self._audit(
            action="organization.create",
            object_type="organization",
            object_id=organization.id,
            reason=payload.command.change_reason,
            before={},
            after=self._version_payload(version, code),
        )
        await self._outbox(
            "organization.created",
            "organization",
            organization.id,
            {"organization_id": str(organization.id), "version": 1},
        )
        return await self.get_as_of(organization.id, payload.effective_from)

    async def schedule_version(
        self,
        organization_id: UUID,
        payload: OrganizationVersionCreate,
    ) -> OrganizationEventView:
        await self._lock_idempotency(payload.command.idempotency_key)
        existing_event = await self._event_by_idempotency(
            payload.command.idempotency_key
        )
        if existing_event is not None:
            if (
                existing_event.event_type != "VERSION_CHANGE"
                or existing_event.organization_id != organization_id
            ):
                self._raise_idempotency_conflict()
            return OrganizationEventView.model_validate(existing_event)

        await self._lock_organization(organization_id)
        organization = await self._organization(organization_id)
        aggregate_version = await self._aggregate_version(organization_id)
        if payload.command.expected_version != aggregate_version:
            self._raise_version_conflict(
                aggregate_version,
                payload.command.expected_version,
            )

        latest_actual = await self._latest_actual_version(organization_id)
        if payload.effective_date <= latest_actual.effective_from:
            raise ApiError(
                status_code=422,
                code="EFFECTIVE_DATE_INVALID",
                message="新版本生效日期必须晚于当前版本起始日期",
            )
        latest_planned = await self._session.scalar(
            select(OrganizationEvent)
            .where(
                OrganizationEvent.organization_id == organization_id,
                OrganizationEvent.event_type == "VERSION_CHANGE",
                OrganizationEvent.status == "planned",
            )
            .order_by(OrganizationEvent.effective_date.desc())
            .limit(1)
        )
        if latest_planned is not None and payload.effective_date <= latest_planned.effective_date:
            raise ApiError(
                status_code=422,
                code="EFFECTIVE_DATE_SEQUENCE_INVALID",
                message="后续计划版本的生效日期必须晚于已有计划版本",
            )

        current_state = await self._state_as_of(organization_id, payload.effective_date)
        organization_type = await self._organization_type(
            payload.organization_type_id,
            active_required=False,
        )
        if (
            not organization_type.is_active
            and payload.organization_type_id != current_state["organization_type_id"]
        ):
            raise ApiError(
                status_code=422,
                code="ORGANIZATION_TYPE_NOT_ACTIVE",
                message="组织类型未启用",
            )
        if payload.parent_organization_id is not None:
            await self._state_as_of(
                payload.parent_organization_id,
                payload.effective_date,
            )

        parents = await self._parent_map_as_of(payload.effective_date)
        parents[organization.id] = payload.parent_organization_id
        try:
            assert_no_cycle(
                organization.id,
                payload.parent_organization_id,
                parents,
            )
        except DomainViolation as exc:
            self._raise_domain(exc)

        event = OrganizationEvent(
            organization_id=organization_id,
            event_type="VERSION_CHANGE",
            effective_date=payload.effective_date,
            status="planned",
            payload={
                "name": payload.name,
                "organization_type_id": str(payload.organization_type_id),
                "parent_organization_id": (
                    str(payload.parent_organization_id)
                    if payload.parent_organization_id
                    else None
                ),
                "country_code": payload.country_code,
                "status": payload.status,
            },
            expected_version=payload.command.expected_version,
            idempotency_key=payload.command.idempotency_key,
            change_reason=payload.command.change_reason,
        )
        self._session.add(event)
        await self._session.flush()
        await self._audit(
            action="organization.version.schedule",
            object_type="organization_event",
            object_id=event.id,
            reason=payload.command.change_reason,
            before={"version": aggregate_version},
            after={
                "organization_id": str(organization_id),
                "effective_date": payload.effective_date.isoformat(),
                "planned_version": aggregate_version + 1,
            },
        )
        await self._outbox(
            "organization.version.scheduled",
            "organization",
            organization_id,
            {
                "organization_id": str(organization_id),
                "event_id": str(event.id),
                "expected_version": aggregate_version,
            },
        )
        if payload.effective_date <= self.business_date():
            await self._apply_event(event)
        return OrganizationEventView.model_validate(event)

    async def cancel_event(
        self,
        event_id: UUID,
        command: VersionCommand,
    ) -> OrganizationEventView:
        event = await self._session.get(OrganizationEvent, event_id)
        if event is None:
            raise ApiError(
                status_code=404,
                code="ORGANIZATION_EVENT_NOT_FOUND",
                message="组织计划事件不存在",
            )
        if event.status == "cancelled":
            return OrganizationEventView.model_validate(event)
        if event.status != "planned":
            raise ApiError(
                status_code=409,
                code="ORGANIZATION_EVENT_NOT_CANCELLABLE",
                message="只有待生效事件可以取消",
            )

        await self._lock_organization(event.organization_id)
        aggregate_version = await self._aggregate_version(event.organization_id)
        if command.expected_version != aggregate_version:
            self._raise_version_conflict(aggregate_version, command.expected_version)
        latest = await self._session.scalar(
            select(OrganizationEvent)
            .where(
                OrganizationEvent.organization_id == event.organization_id,
                OrganizationEvent.status == "planned",
                OrganizationEvent.event_type == "VERSION_CHANGE",
            )
            .order_by(OrganizationEvent.expected_version.desc())
            .limit(1)
        )
        if latest is None or latest.id != event.id:
            raise ApiError(
                status_code=409,
                code="ORGANIZATION_EVENT_DEPENDENCY_EXISTS",
                message="该事件之后仍有计划版本，请先取消最后一个计划版本",
            )

        event.status = "cancelled"
        event.cancelled_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(event)
        await self._audit(
            action="organization.version.cancel",
            object_type="organization_event",
            object_id=event.id,
            reason=command.change_reason,
            before={"status": "planned"},
            after={"status": "cancelled"},
        )
        await self._outbox(
            "organization.version.cancelled",
            "organization",
            event.organization_id,
            {
                "organization_id": str(event.organization_id),
                "event_id": str(event.id),
            },
        )
        return OrganizationEventView.model_validate(event)

    async def apply_due_events(self, business_date: date) -> int:
        events = list(
            (
                await self._session.scalars(
                    select(OrganizationEvent)
                    .where(
                        OrganizationEvent.event_type == "VERSION_CHANGE",
                        OrganizationEvent.status == "planned",
                        OrganizationEvent.effective_date <= business_date,
                    )
                    .order_by(
                        OrganizationEvent.effective_date,
                        OrganizationEvent.expected_version,
                        OrganizationEvent.created_at,
                    )
                )
            ).all()
        )
        for event in events:
            await self._lock_organization(event.organization_id)
            await self._apply_event(event)
        return len(events)

    async def get_current_tree(self) -> list[OrganizationTreeNode]:
        effective_at = self.business_date()
        rows = (
            await self._session.execute(
                select(Organization, OrganizationVersion, OrganizationType)
                .join(
                    OrganizationVersion,
                    OrganizationVersion.organization_id == Organization.id,
                )
                .join(
                    OrganizationType,
                    OrganizationType.id == OrganizationVersion.organization_type_id,
                )
                .where(
                    OrganizationVersion.effective_from <= effective_at,
                    or_(
                        OrganizationVersion.effective_to.is_(None),
                        OrganizationVersion.effective_to >= effective_at,
                    ),
                    OrganizationVersion.status == "active",
                )
                .order_by(OrganizationType.sort_order, Organization.code)
            )
        ).all()

        nodes: dict[UUID, OrganizationTreeNode] = {}
        parents: dict[UUID, UUID | None] = {}
        order: dict[UUID, tuple[int, str]] = {}
        for organization, version, organization_type in rows:
            nodes[organization.id] = OrganizationTreeNode(
                id=organization.id,
                code=organization.code,
                name=version.name,
                organization_type_code=organization_type.code,
                status=version.status,
            )
            parents[organization.id] = version.parent_organization_id
            order[organization.id] = (organization_type.sort_order, organization.code)

        roots: list[OrganizationTreeNode] = []
        try:
            for organization_id, parent_id in parents.items():
                assert_no_cycle(organization_id, parent_id, parents)
        except DomainViolation as exc:
            raise ApiError(
                status_code=409,
                code="ORGANIZATION_TREE_INVALID",
                message=exc.message,
            ) from exc
        for organization_id, node in nodes.items():
            parent_id = parents[organization_id]
            if parent_id is None or parent_id not in nodes:
                roots.append(node)
            else:
                nodes[parent_id].children.append(node)

        def sort_tree(items: list[OrganizationTreeNode]) -> None:
            items.sort(key=lambda item: order[item.id])
            for item in items:
                sort_tree(item.children)

        sort_tree(roots)
        reachable: set[UUID] = set()

        def collect(items: list[OrganizationTreeNode]) -> None:
            for item in items:
                if item.id in reachable:
                    continue
                reachable.add(item.id)
                collect(item.children)

        collect(roots)
        if len(reachable) != len(nodes):
            raise ApiError(
                status_code=409,
                code="ORGANIZATION_TREE_INVALID",
                message="当前组织树存在循环或不可达节点",
            )
        return roots

    async def get_as_of(
        self,
        organization_id: UUID,
        effective_at: date,
    ) -> OrganizationView:
        organization = await self._organization(organization_id)
        state = await self._state_as_of(organization_id, effective_at)
        organization_type = await self._organization_type(
            state["organization_type_id"],
            active_required=False,
        )
        parent_code: str | None = None
        if state["parent_organization_id"] is not None:
            parent = await self._organization(state["parent_organization_id"])
            parent_code = parent.code
        planned_events = list(
            (
                await self._session.scalars(
                    select(OrganizationEvent)
                    .where(
                        OrganizationEvent.organization_id == organization_id,
                        OrganizationEvent.event_type == "VERSION_CHANGE",
                        OrganizationEvent.status == "planned",
                    )
                    .order_by(OrganizationEvent.effective_date)
                )
            ).all()
        )
        return OrganizationView(
            id=organization.id,
            code=organization.code,
            name=state["name"],
            organization_type_id=organization_type.id,
            organization_type_code=organization_type.code,
            organization_type_name=organization_type.name,
            parent_organization_id=state["parent_organization_id"],
            parent_organization_code=parent_code,
            country_code=state["country_code"],
            status=state["status"],
            effective_from=state["effective_from"],
            effective_to=state["effective_to"],
            version=state["version"],
            planned_events=[
                OrganizationEventView.model_validate(event) for event in planned_events
            ],
        )

    async def set_legal_entities(
        self,
        organization_id: UUID,
        payload: OrganizationLegalEntitySet,
    ) -> RelationSetView:
        await self._lock_idempotency(payload.command.idempotency_key)
        existing_event = await self._event_by_idempotency(
            payload.command.idempotency_key
        )
        if existing_event is not None:
            return self._relation_set_from_event(
                existing_event,
                expected_type="LEGAL_ENTITY_SET",
            )

        await self._lock_organization(organization_id)
        await self._organization(organization_id)
        related_ids = self._unique_ids(
            payload.legal_entity_ids,
            code="LEGAL_ENTITY_DUPLICATE",
            message="法人主体不能重复",
        )
        for legal_entity_id in related_ids:
            legal_entity = await self._session.get(LegalEntity, legal_entity_id)
            if (
                legal_entity is None
                or legal_entity.status != "active"
                or legal_entity.effective_from > payload.effective_from
                or (
                    legal_entity.effective_to is not None
                    and legal_entity.effective_to < payload.effective_from
                )
            ):
                raise ApiError(
                    status_code=422,
                    code="LEGAL_ENTITY_NOT_EFFECTIVE",
                    message="法人主体不存在或在指定日期无效",
                )

        current_version = await self._relation_version(
            organization_id,
            "LEGAL_ENTITY_SET",
        )
        self._assert_expected_version(current_version, payload.command)
        prior_rows = list(
            (
                await self._session.scalars(
                    select(OrganizationLegalEntity).where(
                        OrganizationLegalEntity.organization_id == organization_id,
                        or_(
                            OrganizationLegalEntity.effective_to.is_(None),
                            OrganizationLegalEntity.effective_to >= payload.effective_from,
                        ),
                    )
                )
            ).all()
        )
        self._assert_new_relation_period(
            [row.effective_from for row in prior_rows],
            payload.effective_from,
        )
        for row in prior_rows:
            row.effective_to = payload.effective_from - timedelta(days=1)
            row.is_current = False
        await self._session.flush()

        next_version = current_version + 1
        self._session.add_all(
            [
                OrganizationLegalEntity(
                    organization_id=organization_id,
                    legal_entity_id=legal_entity_id,
                    effective_from=payload.effective_from,
                    effective_to=payload.effective_to,
                    version=next_version,
                    is_current=True,
                )
                for legal_entity_id in related_ids
            ]
        )
        await self._session.flush()
        event = await self._record_relation_event(
            organization_id=organization_id,
            event_type="LEGAL_ENTITY_SET",
            effective_date=payload.effective_from,
            command=payload.command,
            version=next_version,
            related_ids=related_ids,
            effective_to=payload.effective_to,
        )
        await self._audit_relation_set(
            action="organization.legal_entities.set",
            organization_id=organization_id,
            reason=payload.command.change_reason,
            version=next_version,
            related_ids=related_ids,
        )
        await self._outbox(
            "organization.legal_entities.set",
            "organization",
            organization_id,
            {
                "organization_id": str(organization_id),
                "event_id": str(event.id),
                "version": next_version,
            },
        )
        return RelationSetView(
            organization_id=organization_id,
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            version=next_version,
            related_ids=related_ids,
        )

    async def set_leaders(
        self,
        organization_id: UUID,
        payload: OrganizationLeaderSet,
    ) -> RelationSetView:
        if len(payload.person_ids) > 3:
            raise ApiError(
                status_code=409,
                code="LEADER_LIMIT_EXCEEDED",
                message="同一组织同一期间最多设置三名主负责人",
            )
        related_ids = self._unique_ids(
            payload.person_ids,
            code="LEADER_DUPLICATE",
            message="组织负责人不能重复",
        )
        await self._lock_idempotency(payload.command.idempotency_key)
        existing_event = await self._event_by_idempotency(
            payload.command.idempotency_key
        )
        if existing_event is not None:
            return self._relation_set_from_event(
                existing_event,
                expected_type="LEADER_SET",
            )

        await self._lock_organization(organization_id)
        await self._organization(organization_id)
        for person_id in related_ids:
            person = await self._session.get(Person, person_id)
            if person is None or person.status != "active":
                raise ApiError(
                    status_code=422,
                    code="LEADER_PERSON_NOT_ACTIVE",
                    message="负责人不存在或未启用",
                )

        current_version = await self._relation_version(organization_id, "LEADER_SET")
        self._assert_expected_version(current_version, payload.command)
        prior_rows = list(
            (
                await self._session.scalars(
                    select(OrganizationLeader).where(
                        OrganizationLeader.organization_id == organization_id,
                        or_(
                            OrganizationLeader.effective_to.is_(None),
                            OrganizationLeader.effective_to >= payload.effective_from,
                        ),
                    )
                )
            ).all()
        )
        self._assert_new_relation_period(
            [row.effective_from for row in prior_rows],
            payload.effective_from,
        )
        for row in prior_rows:
            row.effective_to = payload.effective_from - timedelta(days=1)
        await self._session.flush()

        next_version = current_version + 1
        self._session.add_all(
            [
                OrganizationLeader(
                    organization_id=organization_id,
                    person_id=person_id,
                    effective_from=payload.effective_from,
                    effective_to=payload.effective_to,
                    version=next_version,
                    status="active",
                )
                for person_id in related_ids
            ]
        )
        await self._session.flush()
        event = await self._record_relation_event(
            organization_id=organization_id,
            event_type="LEADER_SET",
            effective_date=payload.effective_from,
            command=payload.command,
            version=next_version,
            related_ids=related_ids,
            effective_to=payload.effective_to,
        )
        await self._audit_relation_set(
            action="organization.leaders.set",
            organization_id=organization_id,
            reason=payload.command.change_reason,
            version=next_version,
            related_ids=related_ids,
        )
        await self._outbox(
            "organization.leaders.set",
            "organization",
            organization_id,
            {
                "organization_id": str(organization_id),
                "event_id": str(event.id),
                "version": next_version,
            },
        )
        return RelationSetView(
            organization_id=organization_id,
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            version=next_version,
            related_ids=related_ids,
        )

    async def create_bp_membership(
        self,
        payload: BpMembershipCreate,
    ) -> BpMembershipView:
        related_ids = self._unique_ids(
            payload.organization_ids,
            code="BP_SCOPE_DUPLICATE",
            message="BP服务组织不能重复",
        )
        await self._lock_idempotency(payload.command.idempotency_key)
        existing_event = await self._event_by_idempotency(
            payload.command.idempotency_key
        )
        if existing_event is not None:
            if existing_event.event_type != "BP_MEMBERSHIP_CREATE":
                self._raise_idempotency_conflict()
            membership_id = UUID(existing_event.payload["membership_id"])
            return await self._bp_membership_view(membership_id)

        await self._lock_person(payload.person_id)
        person = await self._session.get(Person, payload.person_id)
        if person is None or person.status != "active":
            raise ApiError(
                status_code=422,
                code="BP_PERSON_NOT_ACTIVE",
                message="BP人员不存在或未启用",
            )
        for organization_id in related_ids:
            await self._state_as_of(organization_id, payload.effective_from)

        overlap_filters = [
            PersonBpMembership.person_id == payload.person_id,
            PersonBpMembership.status == "active",
            or_(
                PersonBpMembership.effective_to.is_(None),
                PersonBpMembership.effective_to >= payload.effective_from,
            ),
        ]
        if payload.effective_to is not None:
            overlap_filters.append(
                PersonBpMembership.effective_from <= payload.effective_to
            )
        overlap = await self._session.scalar(
            select(PersonBpMembership.id).where(*overlap_filters).limit(1)
        )
        if overlap is not None:
            raise ApiError(
                status_code=409,
                code="BP_TYPE_OVERLAP",
                message="同一人员同一有效期间只能兼任一类BP",
            )

        current_version = (
            await self._session.scalar(
                select(func.max(PersonBpMembership.version)).where(
                    PersonBpMembership.person_id == payload.person_id
                )
            )
            or 1
        )
        self._assert_expected_version(current_version, payload.command)
        next_version = current_version + 1
        membership = PersonBpMembership(
            person_id=payload.person_id,
            bp_type=payload.bp_type,
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            version=next_version,
            status="active",
        )
        self._session.add(membership)
        await self._session.flush()
        self._session.add_all(
            [
                BpServiceScope(
                    membership_id=membership.id,
                    organization_id=organization_id,
                    effective_from=payload.effective_from,
                    effective_to=payload.effective_to,
                )
                for organization_id in related_ids
            ]
        )
        await self._session.flush()
        event = await self._record_relation_event(
            organization_id=related_ids[0],
            event_type="BP_MEMBERSHIP_CREATE",
            effective_date=payload.effective_from,
            command=payload.command,
            version=next_version,
            related_ids=related_ids,
            effective_to=payload.effective_to,
            extra_payload={"membership_id": str(membership.id)},
        )
        await self._audit(
            action="organization.bp_membership.create",
            object_type="bp_membership",
            object_id=membership.id,
            reason=payload.command.change_reason,
            before={},
            after={
                "person_id": str(payload.person_id),
                "bp_type": payload.bp_type,
                "organization_ids": [str(item) for item in related_ids],
                "version": next_version,
            },
        )
        await self._outbox(
            "organization.bp_membership.created",
            "person",
            payload.person_id,
            {
                "person_id": str(payload.person_id),
                "membership_id": str(membership.id),
                "event_id": str(event.id),
                "version": next_version,
            },
        )
        return await self._bp_membership_view(membership.id)

    async def set_bp_service_scopes(
        self,
        membership_id: UUID,
        payload: BpServiceScopeSet,
    ) -> BpMembershipView:
        related_ids = self._unique_ids(
            payload.organization_ids,
            code="BP_SCOPE_DUPLICATE",
            message="BP服务组织不能重复",
        )
        await self._lock_idempotency(payload.command.idempotency_key)
        existing_event = await self._event_by_idempotency(
            payload.command.idempotency_key
        )
        if existing_event is not None:
            if (
                existing_event.event_type != "BP_SCOPE_SET"
                or existing_event.payload.get("membership_id") != str(membership_id)
            ):
                self._raise_idempotency_conflict()
            return await self._bp_membership_view(membership_id)

        membership = await self._session.get(PersonBpMembership, membership_id)
        if membership is None or membership.status != "active":
            raise ApiError(
                status_code=404,
                code="BP_MEMBERSHIP_NOT_FOUND",
                message="BP兼任关系不存在或已失效",
            )
        await self._lock_person(membership.person_id)
        if payload.effective_from < membership.effective_from or (
            membership.effective_to is not None
            and payload.effective_from > membership.effective_to
        ):
            raise ApiError(
                status_code=422,
                code="BP_SCOPE_PERIOD_INVALID",
                message="BP服务范围生效日期必须位于兼任关系有效期内",
            )
        self._assert_expected_version(membership.version, payload.command)
        for organization_id in related_ids:
            await self._state_as_of(organization_id, payload.effective_from)

        prior_rows = list(
            (
                await self._session.scalars(
                    select(BpServiceScope).where(
                        BpServiceScope.membership_id == membership_id,
                        or_(
                            BpServiceScope.effective_to.is_(None),
                            BpServiceScope.effective_to >= payload.effective_from,
                        ),
                    )
                )
            ).all()
        )
        self._assert_new_relation_period(
            [row.effective_from for row in prior_rows],
            payload.effective_from,
        )
        for row in prior_rows:
            row.effective_to = payload.effective_from - timedelta(days=1)
        await self._session.flush()

        membership.version += 1
        self._session.add_all(
            [
                BpServiceScope(
                    membership_id=membership_id,
                    organization_id=organization_id,
                    effective_from=payload.effective_from,
                    effective_to=payload.effective_to,
                )
                for organization_id in related_ids
            ]
        )
        await self._session.flush()
        event = await self._record_relation_event(
            organization_id=related_ids[0],
            event_type="BP_SCOPE_SET",
            effective_date=payload.effective_from,
            command=payload.command,
            version=membership.version,
            related_ids=related_ids,
            effective_to=payload.effective_to,
            extra_payload={"membership_id": str(membership.id)},
        )
        await self._audit(
            action="organization.bp_scopes.set",
            object_type="bp_membership",
            object_id=membership.id,
            reason=payload.command.change_reason,
            before={},
            after={
                "organization_ids": [str(item) for item in related_ids],
                "version": membership.version,
            },
        )
        await self._outbox(
            "organization.bp_scopes.set",
            "person",
            membership.person_id,
            {
                "person_id": str(membership.person_id),
                "membership_id": str(membership.id),
                "event_id": str(event.id),
                "version": membership.version,
            },
        )
        return await self._bp_membership_view(membership.id)

    async def get_relations(
        self,
        organization_id: UUID,
        effective_at: date,
    ) -> OrganizationRelationsView:
        await self._state_as_of(organization_id, effective_at)
        legal_rows = list(
            (
                await self._session.scalars(
                    select(OrganizationLegalEntity)
                    .where(
                        OrganizationLegalEntity.organization_id == organization_id,
                        OrganizationLegalEntity.effective_from <= effective_at,
                        or_(
                            OrganizationLegalEntity.effective_to.is_(None),
                            OrganizationLegalEntity.effective_to >= effective_at,
                        ),
                    )
                    .order_by(OrganizationLegalEntity.legal_entity_id)
                )
            ).all()
        )
        leader_rows = list(
            (
                await self._session.scalars(
                    select(OrganizationLeader)
                    .where(
                        OrganizationLeader.organization_id == organization_id,
                        OrganizationLeader.effective_from <= effective_at,
                        or_(
                            OrganizationLeader.effective_to.is_(None),
                            OrganizationLeader.effective_to >= effective_at,
                        ),
                    )
                    .order_by(OrganizationLeader.person_id)
                )
            ).all()
        )
        bp_membership_ids = list(
            (
                await self._session.scalars(
                    select(PersonBpMembership.id)
                    .join(
                        BpServiceScope,
                        BpServiceScope.membership_id == PersonBpMembership.id,
                    )
                    .where(
                        BpServiceScope.organization_id == organization_id,
                        BpServiceScope.effective_from <= effective_at,
                        or_(
                            BpServiceScope.effective_to.is_(None),
                            BpServiceScope.effective_to >= effective_at,
                        ),
                        PersonBpMembership.effective_from <= effective_at,
                        or_(
                            PersonBpMembership.effective_to.is_(None),
                            PersonBpMembership.effective_to >= effective_at,
                        ),
                        PersonBpMembership.status == "active",
                    )
                    .distinct()
                    .order_by(PersonBpMembership.id)
                )
            ).all()
        )
        return OrganizationRelationsView(
            effective_at=effective_at,
            legal_entity_ids=[row.legal_entity_id for row in legal_rows],
            legal_entity_version=await self._relation_version_as_of(
                organization_id,
                "LEGAL_ENTITY_SET",
                effective_at,
            ),
            leader_person_ids=[row.person_id for row in leader_rows],
            leader_version=await self._relation_version_as_of(
                organization_id,
                "LEADER_SET",
                effective_at,
            ),
            bp_membership_ids=bp_membership_ids,
        )

    async def create_cost_center(
        self,
        payload: CostCenterCreate,
    ) -> CostCenterView:
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:cost_center_code))"),
            {"cost_center_code": f"corehr:cost-center:{payload.code}"},
        )
        existing = await self._session.scalar(
            select(CostCenter).where(CostCenter.code == payload.code)
        )
        if existing is not None:
            raise ApiError(
                status_code=409,
                code="COST_CENTER_CODE_CONFLICT",
                message="成本中心代码已存在",
            )
        cost_center = CostCenter(
            **payload.model_dump(),
            status="active",
            version=1,
        )
        self._session.add(cost_center)
        await self._session.flush()
        await self._audit(
            action="organization.cost_center.create",
            object_type="cost_center",
            object_id=cost_center.id,
            reason="创建成本中心",
            before={},
            after={
                "code": cost_center.code,
                "name": cost_center.name,
                "effective_from": cost_center.effective_from.isoformat(),
            },
        )
        await self._outbox(
            "organization.cost_center.created",
            "cost_center",
            cost_center.id,
            {"cost_center_id": str(cost_center.id), "version": 1},
        )
        return CostCenterView.model_validate(cost_center)

    async def list_cost_centers(self) -> list[CostCenterView]:
        items = (
            await self._session.scalars(
                select(CostCenter).order_by(CostCenter.code)
            )
        ).all()
        return [CostCenterView.model_validate(item) for item in items]

    async def set_cost_allocation(
        self,
        organization_id: UUID,
        payload: CostAllocationSet,
    ) -> CostAllocationView:
        await self._lock_idempotency(payload.command.idempotency_key)
        existing_event = await self._event_by_idempotency(
            payload.command.idempotency_key
        )
        if existing_event is not None:
            if (
                existing_event.event_type != "COST_ALLOCATION_SET"
                or existing_event.organization_id != organization_id
            ):
                self._raise_idempotency_conflict()
            return await self.get_cost_allocation_as_of(
                organization_id,
                existing_event.effective_date,
            )

        cost_center_ids = self._unique_ids(
            [line.cost_center_id for line in payload.lines],
            code="COST_CENTER_DUPLICATE",
            message="同一分摊版本不能重复使用成本中心",
        )
        try:
            assert_allocation_total(
                [line.allocation_percent for line in payload.lines]
            )
        except DomainViolation as exc:
            self._raise_validation_domain(exc)

        await self._lock_organization(organization_id)
        await self._state_as_of(organization_id, payload.effective_from)
        for cost_center_id in cost_center_ids:
            cost_center = await self._session.get(CostCenter, cost_center_id)
            if (
                cost_center is None
                or cost_center.status != "active"
                or cost_center.effective_from > payload.effective_from
                or (
                    cost_center.effective_to is not None
                    and cost_center.effective_to < payload.effective_from
                )
            ):
                raise ApiError(
                    status_code=422,
                    code="COST_CENTER_NOT_EFFECTIVE",
                    message="成本中心不存在或在指定日期无效",
                )

        current_version = await self._relation_version(
            organization_id,
            "COST_ALLOCATION_SET",
        )
        self._assert_expected_version(current_version, payload.command)
        prior_rows = list(
            (
                await self._session.scalars(
                    select(OrganizationCostAllocation).where(
                        OrganizationCostAllocation.organization_id == organization_id,
                        or_(
                            OrganizationCostAllocation.effective_to.is_(None),
                            OrganizationCostAllocation.effective_to
                            >= payload.effective_from,
                        ),
                    )
                )
            ).all()
        )
        before = (
            {
                "version": max(row.version for row in prior_rows),
                "lines": [
                    {
                        "cost_center_id": str(row.cost_center_id),
                        "allocation_percent": str(row.allocation_percent),
                    }
                    for row in prior_rows
                ],
            }
            if prior_rows
            else {}
        )
        self._assert_new_relation_period(
            [row.effective_from for row in prior_rows],
            payload.effective_from,
        )
        for row in prior_rows:
            row.effective_to = payload.effective_from - timedelta(days=1)
            row.is_current = False
        await self._session.flush()

        next_version = current_version + 1
        self._session.add_all(
            [
                OrganizationCostAllocation(
                    organization_id=organization_id,
                    cost_center_id=line.cost_center_id,
                    allocation_percent=line.allocation_percent,
                    effective_from=payload.effective_from,
                    effective_to=payload.effective_to,
                    version=next_version,
                    is_current=True,
                )
                for line in payload.lines
            ]
        )
        await self._session.flush()
        event = await self._record_relation_event(
            organization_id=organization_id,
            event_type="COST_ALLOCATION_SET",
            effective_date=payload.effective_from,
            effective_to=payload.effective_to,
            command=payload.command,
            version=next_version,
            related_ids=cost_center_ids,
        )
        await self._audit(
            action="organization.cost_allocation.set",
            object_type="organization",
            object_id=organization_id,
            reason=payload.command.change_reason,
            before=before,
            after={
                "version": next_version,
                "lines": [
                    {
                        "cost_center_id": str(line.cost_center_id),
                        "allocation_percent": str(line.allocation_percent),
                    }
                    for line in payload.lines
                ],
            },
        )
        await self._outbox(
            "organization.cost_allocation.set",
            "organization",
            organization_id,
            {
                "organization_id": str(organization_id),
                "event_id": str(event.id),
                "version": next_version,
            },
        )
        return await self.get_cost_allocation_as_of(
            organization_id,
            payload.effective_from,
        )

    async def get_cost_allocation_as_of(
        self,
        organization_id: UUID,
        effective_at: date,
    ) -> CostAllocationView:
        await self._state_as_of(organization_id, effective_at)
        rows = list(
            (
                await self._session.scalars(
                    select(OrganizationCostAllocation)
                    .where(
                        OrganizationCostAllocation.organization_id == organization_id,
                        OrganizationCostAllocation.effective_from <= effective_at,
                        or_(
                            OrganizationCostAllocation.effective_to.is_(None),
                            OrganizationCostAllocation.effective_to >= effective_at,
                        ),
                    )
                    .order_by(OrganizationCostAllocation.cost_center_id)
                )
            ).all()
        )
        if not rows:
            raise ApiError(
                status_code=404,
                code="COST_ALLOCATION_NOT_FOUND",
                message="指定日期没有成本分摊版本",
            )
        return CostAllocationView(
            organization_id=organization_id,
            effective_at=effective_at,
            version=max(row.version for row in rows),
            lines=[
                CostAllocationLine(
                    cost_center_id=row.cost_center_id,
                    allocation_percent=row.allocation_percent,
                )
                for row in rows
            ],
        )

    async def set_revenue_target(
        self,
        organization_id: UUID,
        payload: RevenueTargetSet,
    ) -> RevenueTargetView:
        await self._lock_idempotency(payload.command.idempotency_key)
        existing_event = await self._event_by_idempotency(
            payload.command.idempotency_key
        )
        if existing_event is not None:
            if (
                existing_event.event_type != "REVENUE_TARGET_SET"
                or existing_event.organization_id != organization_id
                or int(existing_event.payload.get("year", 0)) != payload.year
                or existing_event.payload.get("currency_code") != payload.currency_code
            ):
                self._raise_idempotency_conflict()
            return await self._revenue_target_view(
                UUID(existing_event.payload["revenue_target_id"])
            )

        month_values: dict[int, Decimal] = {}
        for month in payload.months:
            if month.month in month_values:
                raise ApiError(
                    status_code=422,
                    code="REVENUE_MONTH_SET_INVALID",
                    message="收入目标月份不能重复",
                )
            month_values[month.month] = month.amount
        try:
            assert_revenue_total(payload.annual_amount, month_values)
        except DomainViolation as exc:
            self._raise_validation_domain(exc)

        await self._lock_organization(organization_id)
        await self._state_as_of(organization_id, self.business_date())
        current_target = await self._session.scalar(
            select(RevenueTarget)
            .where(
                RevenueTarget.organization_id == organization_id,
                RevenueTarget.year == payload.year,
                RevenueTarget.currency_code == payload.currency_code,
                RevenueTarget.is_current.is_(True),
            )
            .order_by(RevenueTarget.version.desc())
            .limit(1)
        )
        current_version = current_target.version if current_target is not None else 1
        self._assert_expected_version(current_version, payload.command)
        before: dict[str, Any] = {}
        if current_target is not None:
            prior_months = (
                await self._session.scalars(
                    select(RevenueTargetMonth)
                    .where(
                        RevenueTargetMonth.revenue_target_id == current_target.id
                    )
                    .order_by(RevenueTargetMonth.month)
                )
            ).all()
            before = {
                "revenue_target_id": str(current_target.id),
                "year": current_target.year,
                "currency_code": current_target.currency_code,
                "annual_amount": str(current_target.annual_amount),
                "months": [
                    {"month": row.month, "amount": str(row.amount)}
                    for row in prior_months
                ],
                "version": current_target.version,
            }
            current_target.is_current = False
            await self._session.flush()

        next_version = current_version + 1
        target = RevenueTarget(
            organization_id=organization_id,
            year=payload.year,
            currency_code=payload.currency_code,
            annual_amount=payload.annual_amount,
            version=next_version,
            is_current=True,
            change_reason=payload.command.change_reason,
        )
        self._session.add(target)
        await self._session.flush()
        self._session.add_all(
            [
                RevenueTargetMonth(
                    revenue_target_id=target.id,
                    month=month,
                    amount=amount,
                )
                for month, amount in sorted(month_values.items())
            ]
        )
        await self._session.flush()
        event = await self._record_relation_event(
            organization_id=organization_id,
            event_type="REVENUE_TARGET_SET",
            effective_date=self.business_date(),
            command=payload.command,
            version=next_version,
            related_ids=[target.id],
            extra_payload={
                "revenue_target_id": str(target.id),
                "year": payload.year,
                "currency_code": payload.currency_code,
            },
        )
        await self._audit(
            action="organization.revenue_target.set",
            object_type="organization",
            object_id=organization_id,
            reason=payload.command.change_reason,
            before=before,
            after={
                "revenue_target_id": str(target.id),
                "year": payload.year,
                "currency_code": payload.currency_code,
                "annual_amount": str(payload.annual_amount),
                "version": next_version,
            },
        )
        await self._outbox(
            "organization.revenue_target.set",
            "organization",
            organization_id,
            {
                "organization_id": str(organization_id),
                "revenue_target_id": str(target.id),
                "event_id": str(event.id),
                "version": next_version,
            },
        )
        return await self._revenue_target_view(target.id)

    async def get_revenue_targets(
        self,
        organization_id: UUID,
        year: int,
    ) -> list[RevenueTargetView]:
        result = await self.aggregate_revenue_tree(
            organization_id,
            year,
            include_descendants=False,
        )
        return result.targets

    async def aggregate_revenue_tree(
        self,
        organization_id: UUID,
        year: int,
        *,
        include_descendants: bool,
    ) -> RevenueAggregationView:
        await self._organization(organization_id)
        organization_ids = {organization_id}
        if include_descendants:
            parents = await self._parent_map_as_of(self.business_date())
            pending = [organization_id]
            while pending:
                parent_id = pending.pop()
                children = [
                    child_id
                    for child_id, candidate_parent in parents.items()
                    if candidate_parent == parent_id and child_id not in organization_ids
                ]
                organization_ids.update(children)
                pending.extend(children)

        targets = list(
            (
                await self._session.scalars(
                    select(RevenueTarget).where(
                        RevenueTarget.organization_id.in_(organization_ids),
                        RevenueTarget.year == year,
                        RevenueTarget.is_current.is_(True),
                    )
                )
            ).all()
        )
        month_rows = (
            list(
                (
                    await self._session.scalars(
                        select(RevenueTargetMonth)
                        .where(
                            RevenueTargetMonth.revenue_target_id.in_(
                                [target.id for target in targets]
                            )
                        )
                        .order_by(
                            RevenueTargetMonth.revenue_target_id,
                            RevenueTargetMonth.month,
                        )
                    )
                ).all()
            )
            if targets
            else []
        )
        months_by_target: dict[UUID, list[RevenueTargetMonth]] = {}
        for month_row in month_rows:
            months_by_target.setdefault(month_row.revenue_target_id, []).append(
                month_row
            )

        totals: dict[str, RevenueCurrencyTotal] = {}
        own_targets: list[RevenueTargetView] = []
        for target in targets:
            target_months = months_by_target.get(target.id, [])
            currency_total = totals.setdefault(
                target.currency_code,
                RevenueCurrencyTotal(
                    annual_amount=Decimal("0.0000"),
                    months={month: Decimal("0.0000") for month in range(1, 13)},
                ),
            )
            currency_total.annual_amount += target.annual_amount
            for month_row in target_months:
                currency_total.months[month_row.month] += month_row.amount
            if target.organization_id == organization_id:
                own_targets.append(
                    RevenueTargetView(
                        id=target.id,
                        organization_id=target.organization_id,
                        year=target.year,
                        currency_code=target.currency_code,
                        annual_amount=target.annual_amount,
                        months=[
                            RevenueTargetMonthInput(
                                month=row.month,
                                amount=row.amount,
                            )
                            for row in target_months
                        ],
                        version=target.version,
                    )
                )

        return RevenueAggregationView(
            organization_id=organization_id,
            year=year,
            include_descendants=include_descendants,
            targets=sorted(own_targets, key=lambda item: item.currency_code),
            totals_by_currency=totals,
        )

    async def _state_as_of(
        self,
        organization_id: UUID,
        effective_at: date,
    ) -> dict[str, Any]:
        await self._organization(organization_id)
        version = await self._session.scalar(
            select(OrganizationVersion)
            .where(
                OrganizationVersion.organization_id == organization_id,
                OrganizationVersion.effective_from <= effective_at,
                or_(
                    OrganizationVersion.effective_to.is_(None),
                    OrganizationVersion.effective_to >= effective_at,
                ),
            )
            .order_by(OrganizationVersion.version.desc())
            .limit(1)
        )
        if version is None:
            raise ApiError(
                status_code=404,
                code="ORGANIZATION_NOT_EFFECTIVE",
                message="指定日期没有有效组织版本",
            )
        state: dict[str, Any] = {
            "name": version.name,
            "organization_type_id": version.organization_type_id,
            "parent_organization_id": version.parent_organization_id,
            "country_code": version.country_code,
            "status": version.status,
            "effective_from": version.effective_from,
            "effective_to": version.effective_to,
            "version": version.version,
        }
        planned_events = (
            await self._session.scalars(
                select(OrganizationEvent)
                .where(
                    OrganizationEvent.organization_id == organization_id,
                    OrganizationEvent.event_type == "VERSION_CHANGE",
                    OrganizationEvent.status == "planned",
                    OrganizationEvent.effective_date <= effective_at,
                )
                .order_by(
                    OrganizationEvent.effective_date,
                    OrganizationEvent.expected_version,
                )
            )
        ).all()
        for event in planned_events:
            state.update(
                {
                    "name": event.payload["name"],
                    "organization_type_id": UUID(event.payload["organization_type_id"]),
                    "parent_organization_id": (
                        UUID(event.payload["parent_organization_id"])
                        if event.payload["parent_organization_id"]
                        else None
                    ),
                    "country_code": event.payload["country_code"],
                    "status": event.payload["status"],
                    "effective_from": event.effective_date,
                    "effective_to": None,
                    "version": event.expected_version + 1,
                }
            )
        return state

    async def _parent_map_as_of(self, effective_at: date) -> dict[UUID, UUID | None]:
        organization_ids = list((await self._session.scalars(select(Organization.id))).all())
        parents: dict[UUID, UUID | None] = {}
        for organization_id in organization_ids:
            try:
                state = await self._state_as_of(organization_id, effective_at)
            except ApiError as exc:
                if exc.code == "ORGANIZATION_NOT_EFFECTIVE":
                    continue
                raise
            parents[organization_id] = state["parent_organization_id"]
        return parents

    async def _aggregate_version(self, organization_id: UUID) -> int:
        actual = await self._latest_actual_version(organization_id)
        last_expected = await self._session.scalar(
            select(func.max(OrganizationEvent.expected_version)).where(
                OrganizationEvent.organization_id == organization_id,
                OrganizationEvent.event_type == "VERSION_CHANGE",
                OrganizationEvent.status == "planned",
            )
        )
        return max(actual.version, (last_expected + 1) if last_expected else 0)

    async def _latest_actual_version(
        self,
        organization_id: UUID,
    ) -> OrganizationVersion:
        version = await self._session.scalar(
            select(OrganizationVersion)
            .where(OrganizationVersion.organization_id == organization_id)
            .order_by(OrganizationVersion.version.desc())
            .limit(1)
        )
        if version is None:
            raise ApiError(
                status_code=404,
                code="ORGANIZATION_VERSION_NOT_FOUND",
                message="组织版本不存在",
            )
        return version

    async def _apply_event(self, event: OrganizationEvent) -> None:
        latest = await self._latest_actual_version(event.organization_id)
        if latest.version != event.expected_version:
            self._raise_version_conflict(latest.version, event.expected_version)
        before = self._version_payload(latest, None)
        latest.effective_to = event.effective_date - timedelta(days=1)
        latest.is_current = False
        await self._session.flush()

        next_version = OrganizationVersion(
            organization_id=event.organization_id,
            version=latest.version + 1,
            name=event.payload["name"],
            organization_type_id=UUID(event.payload["organization_type_id"]),
            parent_organization_id=(
                UUID(event.payload["parent_organization_id"])
                if event.payload["parent_organization_id"]
                else None
            ),
            country_code=event.payload["country_code"],
            status=event.payload["status"],
            effective_from=event.effective_date,
            effective_to=None,
            is_current=event.effective_date <= self.business_date(),
            change_reason=event.change_reason,
        )
        self._session.add(next_version)
        event.status = "applied"
        event.applied_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(event)
        await self._audit(
            action="organization.version.apply",
            object_type="organization",
            object_id=event.organization_id,
            reason=event.change_reason,
            before=before,
            after=self._version_payload(next_version, None),
        )
        await self._outbox(
            "organization.version.applied",
            "organization",
            event.organization_id,
            {
                "organization_id": str(event.organization_id),
                "event_id": str(event.id),
                "version": next_version.version,
            },
        )

    async def _relation_version(
        self,
        organization_id: UUID,
        event_type: str,
    ) -> int:
        last_expected = await self._session.scalar(
            select(func.max(OrganizationEvent.expected_version)).where(
                OrganizationEvent.organization_id == organization_id,
                OrganizationEvent.event_type == event_type,
                OrganizationEvent.status == "applied",
            )
        )
        return (last_expected + 1) if last_expected is not None else 1

    async def _relation_version_as_of(
        self,
        organization_id: UUID,
        event_type: str,
        effective_at: date,
    ) -> int:
        event = await self._session.scalar(
            select(OrganizationEvent)
            .where(
                OrganizationEvent.organization_id == organization_id,
                OrganizationEvent.event_type == event_type,
                OrganizationEvent.status == "applied",
                OrganizationEvent.effective_date <= effective_at,
            )
            .order_by(
                OrganizationEvent.effective_date.desc(),
                OrganizationEvent.created_at.desc(),
            )
            .limit(1)
        )
        return int(event.payload["version"]) if event is not None else 1

    async def _record_relation_event(
        self,
        *,
        organization_id: UUID,
        event_type: str,
        effective_date: date,
        command: VersionCommand,
        version: int,
        related_ids: list[UUID],
        effective_to: date | None = None,
        extra_payload: dict[str, Any] | None = None,
    ) -> OrganizationEvent:
        event_payload: dict[str, Any] = {
            "version": version,
            "related_ids": [str(item) for item in related_ids],
            "effective_to": effective_to.isoformat() if effective_to else None,
        }
        if extra_payload:
            event_payload.update(extra_payload)
        event = OrganizationEvent(
            organization_id=organization_id,
            event_type=event_type,
            effective_date=effective_date,
            status="applied",
            payload=event_payload,
            expected_version=command.expected_version,
            idempotency_key=command.idempotency_key,
            change_reason=command.change_reason,
            applied_at=datetime.now(UTC),
        )
        self._session.add(event)
        await self._session.flush()
        return event

    def _relation_set_from_event(
        self,
        event: OrganizationEvent,
        *,
        expected_type: str,
    ) -> RelationSetView:
        if event.event_type != expected_type:
            self._raise_idempotency_conflict()
        return RelationSetView(
            organization_id=event.organization_id,
            effective_from=event.effective_date,
            effective_to=(
                date.fromisoformat(event.payload["effective_to"])
                if event.payload.get("effective_to")
                else None
            ),
            version=int(event.payload["version"]),
            related_ids=[UUID(item) for item in event.payload["related_ids"]],
        )

    async def _audit_relation_set(
        self,
        *,
        action: str,
        organization_id: UUID,
        reason: str,
        version: int,
        related_ids: list[UUID],
    ) -> None:
        await self._audit(
            action=action,
            object_type="organization",
            object_id=organization_id,
            reason=reason,
            before={},
            after={
                "version": version,
                "related_ids": [str(item) for item in related_ids],
            },
        )

    async def _bp_membership_view(
        self,
        membership_id: UUID,
    ) -> BpMembershipView:
        membership = await self._session.get(PersonBpMembership, membership_id)
        if membership is None:
            raise ApiError(
                status_code=404,
                code="BP_MEMBERSHIP_NOT_FOUND",
                message="BP兼任关系不存在",
            )
        latest_scope_date = await self._session.scalar(
            select(func.max(BpServiceScope.effective_from)).where(
                BpServiceScope.membership_id == membership_id
            )
        )
        organization_ids: list[UUID] = []
        if latest_scope_date is not None:
            organization_ids = list(
                (
                    await self._session.scalars(
                        select(BpServiceScope.organization_id)
                        .where(
                            BpServiceScope.membership_id == membership_id,
                            BpServiceScope.effective_from == latest_scope_date,
                        )
                        .order_by(BpServiceScope.organization_id)
                    )
                ).all()
            )
        return BpMembershipView(
            id=membership.id,
            person_id=membership.person_id,
            bp_type=membership.bp_type,
            organization_ids=organization_ids,
            effective_from=membership.effective_from,
            effective_to=membership.effective_to,
            version=membership.version,
            status=membership.status,
        )

    async def _revenue_target_view(
        self,
        target_id: UUID,
    ) -> RevenueTargetView:
        target = await self._session.get(RevenueTarget, target_id)
        if target is None:
            raise ApiError(
                status_code=404,
                code="REVENUE_TARGET_NOT_FOUND",
                message="收入目标不存在",
            )
        month_rows = (
            await self._session.scalars(
                select(RevenueTargetMonth)
                .where(RevenueTargetMonth.revenue_target_id == target_id)
                .order_by(RevenueTargetMonth.month)
            )
        ).all()
        return RevenueTargetView(
            id=target.id,
            organization_id=target.organization_id,
            year=target.year,
            currency_code=target.currency_code,
            annual_amount=target.annual_amount,
            months=[
                RevenueTargetMonthInput(month=row.month, amount=row.amount)
                for row in month_rows
            ],
            version=target.version,
        )

    @staticmethod
    def _unique_ids(
        values: list[UUID],
        *,
        code: str,
        message: str,
    ) -> list[UUID]:
        if len(set(values)) != len(values):
            raise ApiError(status_code=422, code=code, message=message)
        return values

    @staticmethod
    def _assert_new_relation_period(
        prior_starts: list[date],
        effective_from: date,
    ) -> None:
        if any(start >= effective_from for start in prior_starts):
            raise ApiError(
                status_code=422,
                code="EFFECTIVE_DATE_SEQUENCE_INVALID",
                message="新关系版本的生效日期必须晚于已有有效版本",
            )

    @staticmethod
    def _assert_expected_version(
        current_version: int,
        command: VersionCommand,
    ) -> None:
        if command.expected_version != current_version:
            OrganizationService._raise_version_conflict(
                current_version,
                command.expected_version,
            )

    async def _lock_person(self, person_id: UUID) -> None:
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:person_key))"),
            {"person_key": f"corehr:person:{person_id}"},
        )

    async def _organization(self, organization_id: UUID) -> Organization:
        organization = await self._session.get(Organization, organization_id)
        if organization is None:
            raise ApiError(
                status_code=404,
                code="ORGANIZATION_NOT_FOUND",
                message="组织不存在",
            )
        return organization

    async def _organization_type(
        self,
        type_id: UUID,
        *,
        active_required: bool,
    ) -> OrganizationType:
        organization_type = await self._session.get(OrganizationType, type_id)
        if organization_type is None:
            raise ApiError(
                status_code=422,
                code="ORGANIZATION_TYPE_NOT_FOUND",
                message="组织类型不存在",
            )
        if active_required and not organization_type.is_active:
            raise ApiError(
                status_code=422,
                code="ORGANIZATION_TYPE_NOT_ACTIVE",
                message="组织类型未启用",
            )
        return organization_type

    async def _event_by_idempotency(
        self,
        idempotency_key: UUID,
    ) -> OrganizationEvent | None:
        return await self._session.scalar(
            select(OrganizationEvent).where(
                OrganizationEvent.idempotency_key == idempotency_key
            )
        )

    async def _lock_organization(self, organization_id: UUID) -> None:
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:aggregate_key))"),
            {"aggregate_key": f"corehr:organization:{organization_id}"},
        )

    async def _lock_idempotency(self, idempotency_key: UUID) -> None:
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:idempotency_key))"),
            {"idempotency_key": f"corehr:idempotency:{idempotency_key}"},
        )

    async def _audit(
        self,
        *,
        action: str,
        object_type: str,
        object_id: UUID,
        reason: str,
        before: dict[str, Any],
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
                before_payload=before,
                after_payload=after,
                source="api",
            )
        )
        await self._session.flush()

    async def _outbox(
        self,
        event_type: str,
        aggregate_type: str,
        aggregate_id: UUID,
        payload: dict[str, Any],
    ) -> None:
        self._session.add(
            OutboxEvent(
                event_type=event_type,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                payload=payload,
                occurred_at=datetime.now(UTC),
                attempt_count=0,
            )
        )
        await self._session.flush()

    @staticmethod
    def _type_payload(organization_type: OrganizationType) -> dict[str, Any]:
        return {
            "code": organization_type.code,
            "name": organization_type.name,
            "sort_order": organization_type.sort_order,
            "is_active": organization_type.is_active,
        }

    @staticmethod
    def _version_payload(
        version: OrganizationVersion,
        code: str | None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "organization_id": str(version.organization_id),
            "version": version.version,
            "name": version.name,
            "organization_type_id": str(version.organization_type_id),
            "parent_organization_id": (
                str(version.parent_organization_id)
                if version.parent_organization_id
                else None
            ),
            "country_code": version.country_code,
            "status": version.status,
            "effective_from": version.effective_from.isoformat(),
            "effective_to": (
                version.effective_to.isoformat() if version.effective_to else None
            ),
        }
        if code is not None:
            result["code"] = code
        return result

    @staticmethod
    def _raise_version_conflict(expected: int, received: int) -> None:
        raise ApiError(
            status_code=409,
            code="VERSION_CONFLICT",
            message="数据版本已变化，请刷新后重试",
            details=[{"expected": expected, "received": received}],
        )

    @staticmethod
    def _raise_idempotency_conflict() -> None:
        raise ApiError(
            status_code=409,
            code="IDEMPOTENCY_KEY_CONFLICT",
            message="幂等键已被其他命令使用",
        )

    @staticmethod
    def _raise_domain(exc: DomainViolation) -> None:
        raise ApiError(
            status_code=409,
            code=exc.code,
            message=exc.message,
        ) from exc

    @staticmethod
    def _raise_validation_domain(exc: DomainViolation) -> None:
        raise ApiError(
            status_code=422,
            code=exc.code,
            message=exc.message,
        ) from exc
