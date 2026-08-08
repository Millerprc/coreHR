from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.errors import ApiError
from hris.modules.platform.configuration_schemas import (
    DictionaryCreate,
    DictionaryItemCreate,
    DictionaryItemUpdate,
)
from hris.modules.platform.models import DataDictionary, DataDictionaryItem
from hris.modules.workforce.models import AuditLog


class ConfigurationService:
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

    async def create_dictionary(self, payload: DictionaryCreate) -> DataDictionary:
        existing = await self._session.scalar(
            select(DataDictionary).where(DataDictionary.code == payload.code)
        )
        if existing is not None:
            raise ApiError(
                status_code=409,
                code="DICTIONARY_CODE_CONFLICT",
                message="数据字典代码已存在",
            )

        dictionary = DataDictionary(
            **payload.model_dump(),
            source="manual",
            is_active=True,
        )
        try:
            async with self._session.begin_nested():
                self._session.add(dictionary)
                await self._session.flush()
        except IntegrityError as exc:
            raise ApiError(
                status_code=409,
                code="DICTIONARY_CODE_CONFLICT",
                message="数据字典代码已存在",
            ) from exc
        await self._audit(
            action="configuration.dictionary.create",
            object_type="data_dictionary",
            object_id=dictionary.id,
            reason=None,
            before={},
            after={
                "code": dictionary.code,
                "name": dictionary.name,
                "is_active": dictionary.is_active,
            },
        )
        return dictionary

    async def get_dictionary(self, dictionary_id: UUID) -> DataDictionary:
        dictionary = await self._session.get(DataDictionary, dictionary_id)
        if dictionary is None:
            raise ApiError(
                status_code=404,
                code="DICTIONARY_NOT_FOUND",
                message="数据字典不存在",
            )
        return dictionary

    async def list_dictionaries(
        self,
        limit: int,
        offset: int,
    ) -> tuple[list[DataDictionary], int]:
        total = await self._session.scalar(
            select(func.count()).select_from(DataDictionary)
        )
        items = list(
            (
                await self._session.scalars(
                    select(DataDictionary)
                    .order_by(DataDictionary.code)
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        return items, total or 0

    async def list_items(self, dictionary_id: UUID) -> list[DataDictionaryItem]:
        await self.get_dictionary(dictionary_id)
        return list(
            (
                await self._session.scalars(
                    select(DataDictionaryItem)
                    .where(DataDictionaryItem.dictionary_id == dictionary_id)
                    .order_by(
                        DataDictionaryItem.level,
                        DataDictionaryItem.sort_order,
                        DataDictionaryItem.code,
                    )
                )
            ).all()
        )

    async def create_item(
        self,
        dictionary_id: UUID,
        payload: DictionaryItemCreate,
    ) -> DataDictionaryItem:
        dictionary = await self.get_dictionary(dictionary_id)
        if not dictionary.is_active:
            raise ApiError(
                status_code=422,
                code="DICTIONARY_NOT_ACTIVE",
                message="数据字典未启用",
            )

        duplicate = await self._session.scalar(
            select(DataDictionaryItem).where(
                DataDictionaryItem.dictionary_id == dictionary_id,
                DataDictionaryItem.code == payload.code,
            )
        )
        if duplicate is not None:
            raise ApiError(
                status_code=409,
                code="DICTIONARY_ITEM_CODE_CONFLICT",
                message="字典项代码已存在",
            )

        level = 0
        if payload.parent_item_id is not None:
            parent = await self._valid_parent(
                dictionary_id,
                payload.parent_item_id,
            )
            level = parent.level + 1

        item = DataDictionaryItem(
            dictionary_id=dictionary_id,
            level=level,
            is_active=True,
            **payload.model_dump(),
        )
        try:
            async with self._session.begin_nested():
                self._session.add(item)
                await self._session.flush()
        except IntegrityError as exc:
            raise ApiError(
                status_code=409,
                code="DICTIONARY_ITEM_CODE_CONFLICT",
                message="字典项代码已存在",
            ) from exc
        await self._audit(
            action="configuration.item.create",
            object_type="data_dictionary_item",
            object_id=item.id,
            reason=None,
            before={},
            after=self._item_audit_payload(item),
        )
        return item

    async def update_item(
        self,
        item_id: UUID,
        payload: DictionaryItemUpdate,
    ) -> DataDictionaryItem:
        item = await self._get_item(item_id)
        before = self._item_audit_payload(item)
        changes = payload.model_dump(exclude_unset=True)

        previous_level = item.level
        if "parent_item_id" in changes:
            parent_id = changes["parent_item_id"]
            if parent_id is None:
                item.parent_item_id = None
                item.level = 0
            else:
                parent = await self._valid_parent(item.dictionary_id, parent_id)
                await self._reject_cycle(item.id, parent)
                item.parent_item_id = parent.id
                item.level = parent.level + 1

            level_delta = item.level - previous_level
            if level_delta:
                await self._shift_descendant_levels(item.id, level_delta)

        for field in ("name", "english_name", "sort_order", "description"):
            if field in changes:
                setattr(item, field, changes[field])

        await self._session.flush()
        await self._session.refresh(item)
        await self._audit(
            action="configuration.item.update",
            object_type="data_dictionary_item",
            object_id=item.id,
            reason=None,
            before=before,
            after=self._item_audit_payload(item),
        )
        return item

    async def deactivate_item(
        self,
        item_id: UUID,
        reason: str,
    ) -> DataDictionaryItem:
        item = await self._get_item(item_id)
        if not item.is_active:
            return item
        before = self._item_audit_payload(item)
        active_child = await self._session.scalar(
            select(DataDictionaryItem.id).where(
                DataDictionaryItem.parent_item_id == item.id,
                DataDictionaryItem.is_active.is_(True),
            )
        )
        if active_child is not None:
            raise ApiError(
                status_code=409,
                code="DICTIONARY_ITEM_IN_USE",
                message="字典项仍被有效子项引用，不能停用",
            )

        item.is_active = False
        await self._session.flush()
        await self._session.refresh(item)
        await self._audit(
            action="configuration.item.deactivate",
            object_type="data_dictionary_item",
            object_id=item.id,
            reason=reason,
            before=before,
            after=self._item_audit_payload(item),
        )
        return item

    async def _get_item(self, item_id: UUID) -> DataDictionaryItem:
        item = await self._session.get(DataDictionaryItem, item_id)
        if item is None:
            raise ApiError(
                status_code=404,
                code="DICTIONARY_ITEM_NOT_FOUND",
                message="字典项不存在",
            )
        return item

    async def _valid_parent(
        self,
        dictionary_id: UUID,
        parent_item_id: UUID,
    ) -> DataDictionaryItem:
        parent = await self._session.get(DataDictionaryItem, parent_item_id)
        if (
            parent is None
            or parent.dictionary_id != dictionary_id
            or not parent.is_active
        ):
            raise ApiError(
                status_code=422,
                code="DICTIONARY_ITEM_PARENT_INVALID",
                message="父字典项不存在、未启用或不属于同一字典",
            )
        return parent

    async def _reject_cycle(
        self,
        item_id: UUID,
        parent: DataDictionaryItem,
    ) -> None:
        current: DataDictionaryItem | None = parent
        visited: set[UUID] = set()
        while current is not None:
            if current.id == item_id or current.id in visited:
                raise ApiError(
                    status_code=422,
                    code="DICTIONARY_ITEM_PARENT_INVALID",
                    message="父子关系不能形成循环",
                )
            visited.add(current.id)
            if current.parent_item_id is None:
                return
            current = await self._session.get(
                DataDictionaryItem,
                current.parent_item_id,
            )

    async def _shift_descendant_levels(
        self,
        parent_id: UUID,
        delta: int,
    ) -> None:
        pending = [parent_id]
        while pending:
            children = list(
                (
                    await self._session.scalars(
                        select(DataDictionaryItem).where(
                            DataDictionaryItem.parent_item_id.in_(pending)
                        )
                    )
                ).all()
            )
            for child in children:
                child.level += delta
            pending = [child.id for child in children]

    @staticmethod
    def _item_audit_payload(item: DataDictionaryItem) -> dict[str, object]:
        return {
            "dictionary_id": str(item.dictionary_id),
            "parent_item_id": str(item.parent_item_id) if item.parent_item_id else None,
            "code": item.code,
            "name": item.name,
            "sort_order": item.sort_order,
            "level": item.level,
            "is_active": item.is_active,
        }

    async def _audit(
        self,
        *,
        action: str,
        object_type: str,
        object_id: UUID,
        reason: str | None,
        before: dict[str, object],
        after: dict[str, object],
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
