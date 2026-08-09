from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.database import get_db
from hris.modules.platform.dependencies import require_permission
from hris.modules.platform.import_models import ImportBatch, ImportBatchRow
from hris.modules.platform.import_schemas import (
    ImportBatchExecute,
    ImportBatchListResponse,
    ImportBatchResponse,
    ImportBatchRowResponse,
    ImportBatchSummaryResponse,
    ImportBatchValidate,
    ImportEntityType,
    ImportTemplateResponse,
)
from hris.modules.platform.import_service import ImportService
from hris.modules.platform.models import UserAccount


router = APIRouter(prefix="/api/v1/governance", tags=["phase-1-data-governance"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
GovernanceViewer = Annotated[
    UserAccount,
    Depends(require_permission("DATA_GOVERNANCE_VIEW")),
]
GovernanceAdmin = Annotated[
    UserAccount,
    Depends(require_permission("DATA_GOVERNANCE_ADMIN")),
]


def _service(db: AsyncSession, user: UserAccount, request: Request) -> ImportService:
    return ImportService(
        db,
        actor_id=user.id,
        trace_id=str(request.state.trace_id),
    )


def _detail(batch: ImportBatch, rows: list[ImportBatchRow]) -> ImportBatchResponse:
    summary = ImportBatchSummaryResponse.model_validate(batch).model_dump()
    return ImportBatchResponse(
        **summary,
        rows=[ImportBatchRowResponse.model_validate(row) for row in rows],
    )


@router.get(
    "/import-templates/{entity_type}",
    response_model=ImportTemplateResponse,
)
async def get_import_template(
    entity_type: ImportEntityType,
    db: DbSession,
    user: GovernanceViewer,
    request: Request,
) -> ImportTemplateResponse:
    columns, required = _service(db, user, request).template(entity_type)
    return ImportTemplateResponse(
        entity_type=entity_type,
        columns=columns,
        required_columns=required,
    )


@router.post(
    "/import-batches/validate",
    response_model=ImportBatchResponse,
    status_code=status.HTTP_201_CREATED,
)
async def validate_import_batch(
    payload: ImportBatchValidate,
    db: DbSession,
    user: GovernanceAdmin,
    request: Request,
) -> ImportBatchResponse:
    batch, rows = await _service(db, user, request).validate_batch(payload)
    return _detail(batch, rows)


@router.get(
    "/import-batches",
    response_model=ImportBatchListResponse,
)
async def list_import_batches(
    db: DbSession,
    user: GovernanceViewer,
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ImportBatchListResponse:
    items, total = await _service(db, user, request).list_batches(
        limit=limit,
        offset=offset,
    )
    return ImportBatchListResponse(
        items=[ImportBatchSummaryResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/import-batches/{batch_id}",
    response_model=ImportBatchResponse,
)
async def get_import_batch(
    batch_id: UUID,
    db: DbSession,
    user: GovernanceViewer,
    request: Request,
) -> ImportBatchResponse:
    batch, rows = await _service(db, user, request).get_batch(batch_id)
    return _detail(batch, rows)


@router.post(
    "/import-batches/{batch_id}/execute",
    response_model=ImportBatchResponse,
)
async def execute_import_batch(
    batch_id: UUID,
    payload: ImportBatchExecute,
    db: DbSession,
    user: GovernanceAdmin,
    request: Request,
) -> ImportBatchResponse:
    batch, rows = await _service(db, user, request).execute_batch(
        batch_id,
        reason=payload.reason,
    )
    return _detail(batch, rows)
