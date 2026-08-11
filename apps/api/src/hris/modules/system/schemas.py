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
