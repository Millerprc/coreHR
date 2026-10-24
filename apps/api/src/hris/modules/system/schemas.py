# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str
    checks: dict[str, str] = {}


class ModuleStatus(BaseModel):
    phase: int
    code: str
    name: str
    status: Literal["foundation", "slice_available", "uat_ready", "planned"]
    available_capabilities: list[str]
    available_endpoints: list[str]
    pending_inputs: list[str]


class ModuleRegistryResponse(BaseModel):
    items: list[ModuleStatus]
