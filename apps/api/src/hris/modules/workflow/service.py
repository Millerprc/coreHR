from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.errors import ApiError
from hris.modules.workflow.models import WorkflowDefinition, WorkflowVersion
from hris.modules.workflow.schemas import WorkflowDefinitionCreate


class WorkflowService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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

