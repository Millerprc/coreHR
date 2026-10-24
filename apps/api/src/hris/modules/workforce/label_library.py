# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.errors import ApiError
from hris.modules.platform.models import DataDictionary, DataDictionaryItem


# Requirement: HR-LABEL-011 — 员工标签库是一个基础资料字典，不新建独立表。
# 字典第 0 级字典项是标签类型，第 1 级字典项（父级指向类型）是该类型下的标签项。
LABEL_LIBRARY_DICTIONARY_CODE = "PERSON_LABEL_LIBRARY"
LABEL_LIBRARY_TYPE_LEVEL = 0


class LabelLibraryItemResponse(BaseModel):
    code: str
    name: str
    sort_order: int = 0


class LabelLibraryTypeResponse(BaseModel):
    type_code: str
    type_name: str
    items: list[LabelLibraryItemResponse]


class LabelLibraryListResponse(BaseModel):
    items: list[LabelLibraryTypeResponse]


class LabelLibraryService:
    """员工标签库的只读视图。

    标签库的维护（新增类型、扩展标签项、停用）复用基础资料的字典接口，
    本模块只负责按 workforce 域的权限口径读取与校验。
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_types(self) -> list[LabelLibraryTypeResponse]:
        dictionary = await self._require_dictionary()
        rows = list(
            (
                await self._session.scalars(
                    select(DataDictionaryItem)
                    .where(DataDictionaryItem.dictionary_id == dictionary.id)
                    .order_by(
                        DataDictionaryItem.level,
                        DataDictionaryItem.sort_order,
                        DataDictionaryItem.code,
                    )
                )
            ).all()
        )
        children: dict[UUID, list[DataDictionaryItem]] = {}
        for row in rows:
            if row.parent_item_id is not None:
                children.setdefault(row.parent_item_id, []).append(row)

        result: list[LabelLibraryTypeResponse] = []
        for type_row in rows:
            # Requirement: HR-LABEL-011 — 只返回启用中的标签类型与其启用中的标签项。
            if type_row.level != LABEL_LIBRARY_TYPE_LEVEL or not type_row.is_active:
                continue
            items = [
                LabelLibraryItemResponse(
                    code=child.code,
                    name=child.name,
                    sort_order=child.sort_order,
                )
                for child in children.get(type_row.id, [])
                if child.is_active
            ]
            result.append(
                LabelLibraryTypeResponse(
                    type_code=type_row.code,
                    type_name=type_row.name,
                    items=items,
                )
            )
        return result

    async def resolve(self, type_code: str, item_code: str) -> tuple[str, str]:
        """把标签库编码解析成落库的 (label_type, label_name)。

        label_type 存类型编码（稳定标识），label_name 存标签项名称（展示快照）。
        标签库项改名不会影响历史标签的展示。
        """
        dictionary = await self._require_dictionary()
        type_row = await self._session.scalar(
            select(DataDictionaryItem).where(
                DataDictionaryItem.dictionary_id == dictionary.id,
                DataDictionaryItem.code == type_code,
                DataDictionaryItem.level == LABEL_LIBRARY_TYPE_LEVEL,
                DataDictionaryItem.is_active.is_(True),
            )
        )
        if type_row is None:
            # Requirement: HR-LABEL-012 — 人工赋予的标签必须命中标签库。
            raise ApiError(
                status_code=422,
                code="PERSON_LABEL_LIBRARY_ITEM_NOT_FOUND",
                message=f"标签库中不存在启用的标签类型：{type_code}",
            )
        item_row = await self._session.scalar(
            select(DataDictionaryItem).where(
                DataDictionaryItem.dictionary_id == dictionary.id,
                DataDictionaryItem.parent_item_id == type_row.id,
                DataDictionaryItem.code == item_code,
                DataDictionaryItem.is_active.is_(True),
            )
        )
        if item_row is None:
            raise ApiError(
                status_code=422,
                code="PERSON_LABEL_LIBRARY_ITEM_NOT_FOUND",
                message=f"标签库中不存在启用的标签项：{type_code}/{item_code}",
            )
        return type_row.code, item_row.name

    async def _require_dictionary(self) -> DataDictionary:
        dictionary = await self._session.scalar(
            select(DataDictionary).where(
                DataDictionary.code == LABEL_LIBRARY_DICTIONARY_CODE,
            )
        )
        if dictionary is None:
            raise ApiError(
                status_code=404,
                code="PERSON_LABEL_LIBRARY_NOT_FOUND",
                message="员工标签库尚未初始化，请在基础资料中创建标签库",
            )
        return dictionary
