from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.database import get_db
from hris.modules.platform.configuration_schemas import (
    DictionaryCreate,
    DictionaryItemCreate,
    DictionaryItemDeactivate,
    DictionaryItemListResponse,
    DictionaryItemResponse,
    DictionaryItemUpdate,
    DictionaryListResponse,
    DictionaryResponse,
)
from hris.modules.platform.configuration_service import ConfigurationService
from hris.modules.platform.dependencies import require_permission
from hris.modules.platform.models import UserAccount


router = APIRouter(prefix="/api/v1/configuration", tags=["phase-1-configuration"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
ConfigurationViewer = Annotated[
    UserAccount,
    Depends(require_permission("CONFIGURATION_VIEW")),
]
ConfigurationAdmin = Annotated[
    UserAccount,
    Depends(require_permission("CONFIGURATION_ADMIN")),
]


@router.post(
    "/dictionaries",
    response_model=DictionaryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_dictionary(
    payload: DictionaryCreate,
    db: DbSession,
    user: ConfigurationAdmin,
    request: Request,
) -> DictionaryResponse:
    result = await ConfigurationService(
        db,
        actor_id=user.id,
        trace_id=str(request.state.trace_id),
    ).create_dictionary(payload)
    return DictionaryResponse.model_validate(result)


@router.get("/dictionaries", response_model=DictionaryListResponse)
async def list_dictionaries(
    db: DbSession,
    user: ConfigurationViewer,
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> DictionaryListResponse:
    items, total = await ConfigurationService(
        db,
        actor_id=user.id,
        trace_id=str(request.state.trace_id),
    ).list_dictionaries(limit, offset)
    return DictionaryListResponse(
        items=[DictionaryResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/dictionaries/{dictionary_id}", response_model=DictionaryResponse)
async def get_dictionary(
    dictionary_id: UUID,
    db: DbSession,
    user: ConfigurationViewer,
    request: Request,
) -> DictionaryResponse:
    result = await ConfigurationService(
        db,
        actor_id=user.id,
        trace_id=str(request.state.trace_id),
    ).get_dictionary(dictionary_id)
    return DictionaryResponse.model_validate(result)


@router.get(
    "/dictionaries/{dictionary_id}/items",
    response_model=DictionaryItemListResponse,
)
async def list_dictionary_items(
    dictionary_id: UUID,
    db: DbSession,
    user: ConfigurationViewer,
    request: Request,
) -> DictionaryItemListResponse:
    items = await ConfigurationService(
        db,
        actor_id=user.id,
        trace_id=str(request.state.trace_id),
    ).list_items(dictionary_id)
    return DictionaryItemListResponse(
        items=[DictionaryItemResponse.model_validate(item) for item in items],
        total=len(items),
    )


@router.post(
    "/dictionaries/{dictionary_id}/items",
    response_model=DictionaryItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_dictionary_item(
    dictionary_id: UUID,
    payload: DictionaryItemCreate,
    db: DbSession,
    user: ConfigurationAdmin,
    request: Request,
) -> DictionaryItemResponse:
    result = await ConfigurationService(
        db,
        actor_id=user.id,
        trace_id=str(request.state.trace_id),
    ).create_item(dictionary_id, payload)
    return DictionaryItemResponse.model_validate(result)


@router.patch(
    "/dictionary-items/{item_id}",
    response_model=DictionaryItemResponse,
)
async def update_dictionary_item(
    item_id: UUID,
    payload: DictionaryItemUpdate,
    db: DbSession,
    user: ConfigurationAdmin,
    request: Request,
) -> DictionaryItemResponse:
    result = await ConfigurationService(
        db,
        actor_id=user.id,
        trace_id=str(request.state.trace_id),
    ).update_item(item_id, payload)
    return DictionaryItemResponse.model_validate(result)


@router.post(
    "/dictionary-items/{item_id}/deactivate",
    response_model=DictionaryItemResponse,
)
async def deactivate_dictionary_item(
    item_id: UUID,
    payload: DictionaryItemDeactivate,
    db: DbSession,
    user: ConfigurationAdmin,
    request: Request,
) -> DictionaryItemResponse:
    result = await ConfigurationService(
        db,
        actor_id=user.id,
        trace_id=str(request.state.trace_id),
    ).deactivate_item(item_id, payload.reason)
    return DictionaryItemResponse.model_validate(result)
