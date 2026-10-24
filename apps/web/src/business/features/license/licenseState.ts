// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import type {
  LicenseEntitlements,
  LicenseModuleKey,
  LicenseState,
  LicenseStatus,
  LicenseTier,
} from "../../types"
import { LICENSE_STATUS_LABELS, LICENSE_TIER_LABELS } from "./licenseLabels"


// Requirement: D-108 — 授权判定只消费后端返回的事实：
// 前端不重算有效期、不推断模块写能力，只把 entitlements 翻译成界面语言。
const LICENSE_STATUSES: readonly LicenseStatus[] = ["active", "expired", "revoked", "not_yet_valid", "none"]
const LICENSE_TIERS: readonly LicenseTier[] = ["community", "developer", "commercial"]


function asText(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null
}


function asEntitlements(value: unknown): LicenseEntitlements {
  if (!value || typeof value !== "object") return {}
  const result: Record<string, { readonly read: boolean; readonly write: boolean }> = {}
  for (const [module, entitlement] of Object.entries(value as Record<string, unknown>)) {
    if (!entitlement || typeof entitlement !== "object") continue
    const entry = entitlement as { readonly read?: unknown; readonly write?: unknown }
    result[module] = { read: entry.read === true, write: entry.write === true }
  }
  return result
}


/**
 * 把后端授权响应归一化成前端状态。
 * 授权接口不可用或返回体不完整时按「未授权」处理，与后端「无授权 → 只读演示」的降级口径一致。
 */
export function normalizeLicenseState(raw: unknown): LicenseState {
  const data = (raw && typeof raw === "object" ? raw : {}) as Record<string, unknown>
  const status = LICENSE_STATUSES.includes(data.status as LicenseStatus)
    ? (data.status as LicenseStatus)
    : "none"
  const tier = LICENSE_TIERS.includes(data.tier as LicenseTier) ? (data.tier as LicenseTier) : null
  return {
    status,
    readonly_mode: data.readonly_mode === true || status !== "active",
    tier,
    licensee: asText(data.licensee),
    licensee_short: asText(data.licensee_short),
    license_id: asText(data.license_id),
    entitlements: asEntitlements(data.entitlements),
    issued_at: asText(data.issued_at),
    not_before: asText(data.not_before),
    expires_at: asText(data.expires_at),
    seat_limit: typeof data.seat_limit === "number" ? data.seat_limit : null,
    activated_at: asText(data.activated_at),
  }
}


/** 授权是否生效；未授权、过期、吊销、尚未生效一律按未生效处理。 */
export function isLicenseActive(state: LicenseState | null): boolean {
  return state?.status === "active"
}


/** 模块写能力：只有授权生效且该模块 write 为真才放行。 */
export function moduleWriteAllowed(state: LicenseState | null, module: LicenseModuleKey): boolean {
  if (!isLicenseActive(state)) return false
  return state?.entitlements[module]?.write === true
}


/** 模块读能力：未授权时读仍然可用，这是只读演示模式的前提。 */
export function moduleReadAllowed(state: LicenseState | null, module: LicenseModuleKey): boolean {
  if (!state) return true
  return state.entitlements[module]?.read !== false
}


/** 把 ISO 时间戳格式化为日期；无法解析时返回空串。 */
export function formatLicenseDate(value: string | null): string {
  if (!value) return ""
  const match = /^(\d{4}-\d{2}-\d{2})/.exec(value)
  return match ? match[1] : ""
}


/**
 * 顶栏徽标文案。
 * 已授权：被授权方 · 版本 · 至 有效期；其余状态：状态 · 只读演示（各状态可区分）。
 */
export function licenseBadgeText(state: LicenseState | null): string {
  if (!isLicenseActive(state) || !state) {
    return `${LICENSE_STATUS_LABELS[state?.status ?? "none"]} · 只读演示`
  }
  const licensee = state.licensee_short ?? state.licensee ?? "未署名客户"
  const tier = state.tier ? LICENSE_TIER_LABELS[state.tier] : "未知版本"
  const expires = formatLicenseDate(state.expires_at)
  return expires ? `${licensee} · ${tier} · 至 ${expires}` : `${licensee} · ${tier}`
}


/** 内容区水印文案：未授权显示未授权演示，已授权显示被授权方与许可证编号。 */
export function licenseWatermarkText(state: LicenseState | null): string {
  if (!isLicenseActive(state) || !state) return "coreHR · 未授权演示"
  const licensee = state.licensee_short ?? state.licensee ?? "授权客户"
  return state.license_id ? `coreHR · ${licensee} · ${state.license_id}` : `coreHR · ${licensee}`
}


/** 构建期烘焙的水印文案（vite define 注入）；未注入时返回空串。 */
export function bakedWatermarkText(): string {
  if (typeof __COREHR_WATERMARK__ === "undefined") return ""
  return __COREHR_WATERMARK__ ?? ""
}
