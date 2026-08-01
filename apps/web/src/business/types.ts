export interface UserProfile {
  readonly id: string
  readonly username: string
  readonly display_name: string
  readonly status: string
  readonly roles: readonly string[]
  readonly permissions: readonly string[]
}

export interface LoginResponse {
  readonly access_token: string
  readonly token_type: "bearer"
  readonly expires_at: string
  readonly user: UserProfile
}

export interface ModuleStatus {
  readonly phase: number
  readonly code: string
  readonly name: string
  readonly status: string
  readonly available_endpoints: readonly string[]
  readonly pending_inputs: readonly string[]
}

export interface ModuleRegistry {
  readonly items: readonly ModuleStatus[]
}

export interface PageResult {
  readonly total: number
}
