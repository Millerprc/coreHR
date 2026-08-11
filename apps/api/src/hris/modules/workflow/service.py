from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.errors import ApiError
from hris.modules.workflow.models import WorkflowDefinition, WorkflowVersion
from hris.modules.workflow.schemas import WorkflowDefinitionCreate
from hris.modules.workforce.models import AuditLog


class WorkflowService:
    def __init__(self, session: AsyncSession, *, actor_id: UUID, trace_id: str) -> None:
        self._session = session
        self._actor_id = actor_id
        self._trace_id = trace_id

    def _audit(
        self,
        *,
        action: str,
        object_id: UUID,
        after: dict[str, Any],
    ) -> None:
        self._session.add(
            AuditLog(
                occurred_at=datetime.now(UTC),
                actor_id=self._actor_id,
                trace_id=self._trace_id,
                action=action,
                object_type="workflow_definition",
                object_id=object_id,
                reason=None,
                before_payload={},
                after_payload=after,
                source="api",
            )
        )

    async def create_definition(
        self,
        payload: WorkflowDefinitionCreate,
    ) -> WorkflowDefinition:
        existing = await self._session.scalar(
            select(WorkflowDefinition).where(
                WorkflowDefinition.code == payload.code
            )
        )
        if existing is not None:
            raise ApiError(
                status_code=409,
                code="WORKFLOW_DEFINITION_CODE_EXISTS",
                message="流程定义代码已存在",
            )

        node_codes = [node.code for node in payload.nodes]
        if len(set(node_codes)) != len(node_codes):
            raise ApiError(
                status_code=422,
                code="WORKFLOW_NODE_CODE_DUPLICATED",
                message="流程节点代码不能重复",
            )

        node_code_set = set(node_codes)
        invalid_edges = [
            edge
            for edge in payload.edges
            if edge.source not in node_code_set or edge.target not in node_code_set
        ]
        if invalid_edges:
            raise ApiError(
                status_code=422,
                code="WORKFLOW_EDGE_NODE_NOT_FOUND",
                message="流程连线引用了不存在的节点",
            )
        starts = [node for node in payload.nodes if node.node_type == "start"]
        ends = [node for node in payload.nodes if node.node_type == "end"]
        if len(starts) != 1 or len(ends) != 1:
            raise ApiError(
                status_code=422,
                code="WORKFLOW_BOUNDARY_COUNT_INVALID",
                message="流程必须且只能包含一个开始节点和一个结束节点",
            )
        edge_pairs = [(edge.source, edge.target) for edge in payload.edges]
        if len(set(edge_pairs)) != len(edge_pairs):
            raise ApiError(
                status_code=422,
                code="WORKFLOW_EDGE_DUPLICATED",
                message="流程连线不能重复",
            )
        if any(edge.target == starts[0].code for edge in payload.edges):
            raise ApiError(status_code=422, code="WORKFLOW_START_HAS_INBOUND", message="开始节点不能有入线")
        if any(edge.source == ends[0].code for edge in payload.edges):
            raise ApiError(status_code=422, code="WORKFLOW_END_HAS_OUTBOUND", message="结束节点不能有出线")
        edges_by_source: dict[str, list[Any]] = {}
        for edge in payload.edges:
            edges_by_source.setdefault(edge.source, []).append(edge)
        for outgoing in edges_by_source.values():
            conditioned = [edge for edge in outgoing if edge.condition is not None]
            if not conditioned:
                continue
            defaults = [edge for edge in outgoing if edge.condition is None]
            if len(defaults) > 1:
                raise ApiError(
                    status_code=422,
                    code="WORKFLOW_ROUTE_DEFAULT_DUPLICATED",
                    message="条件分支最多配置一条默认连线",
                )
            fingerprints = [edge.condition.model_dump_json() for edge in conditioned]
            if len(set(fingerprints)) != len(fingerprints):
                raise ApiError(
                    status_code=422,
                    code="WORKFLOW_EDGE_CONDITION_DUPLICATED",
                    message="同一节点不能配置重复条件",
                )
        adjacency: dict[str, list[str]] = {code: [] for code in node_codes}
        for source, target in edge_pairs:
            adjacency[source].append(target)
        visited: set[str] = set()
        active_path: set[str] = set()

        def visit(code: str) -> None:
            if code in active_path:
                raise ApiError(status_code=422, code="WORKFLOW_CYCLE_DETECTED", message="流程首版不允许环路")
            if code in visited:
                return
            active_path.add(code)
            for target in adjacency[code]:
                visit(target)
            active_path.remove(code)
            visited.add(code)

        visit(starts[0].code)
        if visited != node_code_set:
            raise ApiError(
                status_code=422,
                code="WORKFLOW_NODE_UNREACHABLE",
                message="所有流程节点都必须从开始节点可达",
            )

        definition = WorkflowDefinition(
            code=payload.code,
            name=payload.name,
            category=payload.category,
            description=payload.description,
            status="draft",
            active_version=None,
        )
        self._session.add(definition)
        await self._session.flush()

        version = WorkflowVersion(
            workflow_definition_id=definition.id,
            version=1,
            status="draft",
            definition={
                "nodes": [node.model_dump() for node in payload.nodes],
                "edges": [edge.model_dump() for edge in payload.edges],
            },
            change_reason=payload.change_reason,
        )
        self._session.add(version)
        await self._session.flush()
        self._audit(
            action="create",
            object_id=definition.id,
            after={"code": definition.code, "version": version.version, "status": definition.status},
        )
        return definition

    async def list_definitions(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[WorkflowDefinition], int]:
        total = await self._session.scalar(
            select(func.count()).select_from(WorkflowDefinition)
        )
        items = list(
            (
                await self._session.scalars(
                    select(WorkflowDefinition)
                    .order_by(WorkflowDefinition.code)
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        return items, total or 0

    async def definition_detail(
        self,
        definition_id: UUID,
    ) -> tuple[WorkflowDefinition, list[WorkflowVersion]]:
        definition = await self._session.get(WorkflowDefinition, definition_id)
        if definition is None:
            raise ApiError(status_code=404, code="WORKFLOW_NOT_FOUND", message="workflow definition not found")
        versions = list(
            (
                await self._session.scalars(
                    select(WorkflowVersion)
                    .where(WorkflowVersion.workflow_definition_id == definition_id)
                    .order_by(WorkflowVersion.version.desc())
                )
            ).all()
        )
        return definition, versions
