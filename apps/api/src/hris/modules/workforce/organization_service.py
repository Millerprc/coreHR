from datetime import UTC, date, datetime, timedelta
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
    Organization,
    OrganizationType,
    OrganizationVersion,
)
from hris.modules.workforce.organization_models import OrganizationEvent
from hris.modules.workforce.organization_policy import DomainViolation, assert_no_cycle
from hris.modules.workforce.organization_schemas import (
    OrganizationCreate,
    OrganizationEventView,
    OrganizationTreeNode,
    OrganizationTypeCreate,
    OrganizationTypeUpdate,
    OrganizationTypeView,
    OrganizationVersionCreate,
    OrganizationView,
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
