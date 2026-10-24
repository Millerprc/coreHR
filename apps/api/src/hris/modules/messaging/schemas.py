# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""Messaging API response schemas.

Requirement: D-100 — 消息分类标签由后端统一给出，前端不另写一套标签映射。
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class MessageCategoryResponse(BaseModel):
    """消息分类编码与中文标签。"""

    code: str
    label: str


class MessageResponse(BaseModel):
    """一条站内信。``body`` 是纯文本，前端只按文本渲染。"""

    id: UUID
    category: str
    category_label: str
    title: str
    body: str
    source: str
    source_ref_id: UUID | None = None
    read_at: datetime | None = None
    created_at: datetime


class MessageListResponse(BaseModel):
    """收件箱列表。"""

    items: list[MessageResponse] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class UnreadCountResponse(BaseModel):
    """未读数。"""

    unread_count: int
