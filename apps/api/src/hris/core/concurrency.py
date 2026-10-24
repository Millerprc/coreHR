# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VersionCommand(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    expected_version: int = Field(ge=1)
    idempotency_key: UUID
    change_reason: str = Field(min_length=1, max_length=500)
