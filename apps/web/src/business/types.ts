// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

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

// Requirement: D-108 — 离线签名模块级授权的前端契约。
// 授权状态只由后端 /api/v1/license 决定，前端不做任何本地判定。
export type LicenseStatus = "active" | "expired" | "revoked" | "not_yet_valid" | "none"

export type LicenseTier = "community" | "developer" | "commercial"

/** 授权模块键；与后端 entitlements 的键一一对应。 */
export type LicenseModuleKey =
  | "attendance"
  | "workflow"
  | "lifecycle"
  | "governance"
  | "workforce"
  | "performance"

export interface LicenseEntitlement {
  readonly read: boolean
  readonly write: boolean
}

export interface LicenseEntitlements {
  readonly [module: string]: LicenseEntitlement | undefined
}

export interface LicenseState {
  readonly status: LicenseStatus
  readonly readonly_mode: boolean
  readonly tier: LicenseTier | null
  readonly licensee: string | null
  readonly licensee_short: string | null
  readonly license_id: string | null
  readonly entitlements: LicenseEntitlements
  readonly issued_at: string | null
  readonly not_before: string | null
  readonly expires_at: string | null
  readonly seat_limit: number | null
  readonly activated_at: string | null
}

export interface LicenseActivationResult {
  readonly activated: boolean
  readonly status: LicenseStatus
  readonly tier: LicenseTier | null
  readonly licensee: string | null
  readonly entitlements: LicenseEntitlements
  readonly expires_at: string | null
}

export interface LicenseDeactivationResult {
  readonly status: LicenseStatus
  readonly readonly_mode: boolean
}
