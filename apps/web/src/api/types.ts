// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

export type ModuleBuildStatus = "foundation" | "slice_available" | "uat_ready" | "planned"

export interface ModuleStatus {
  readonly phase: number
  readonly code: string
  readonly name: string
  readonly status: ModuleBuildStatus
  readonly available_capabilities: readonly string[]
  readonly available_endpoints: readonly string[]
  readonly pending_inputs: readonly string[]
}

export interface ModuleRegistryResponse {
  readonly items: readonly ModuleStatus[]
}
