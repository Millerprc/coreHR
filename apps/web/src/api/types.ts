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
