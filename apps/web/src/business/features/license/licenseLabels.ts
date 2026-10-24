// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import type { LicenseModuleKey, LicenseStatus, LicenseTier } from "../../types"


// Requirement: D-108 — 授权模块、版本与状态的显示文案只在这里维护一份：
// 顶栏徽标、侧栏锁标、授权管理页与锁定说明面板共用同一套名称，不在两处各写一遍。
export const LICENSE_MODULE_LABELS: Readonly<Record<LicenseModuleKey, string>> = {
  attendance: "考勤管理",
  workflow: "审批与流程引擎",
  lifecycle: "员工生命周期",
  governance: "数据治理导入",
  workforce: "人员与组织核心",
  performance: "绩效管理",
}


export const LICENSE_TIER_LABELS: Readonly<Record<LicenseTier, string>> = {
  community: "Community",
  developer: "Developer",
  commercial: "Commercial",
}


export const LICENSE_STATUS_LABELS: Readonly<Record<LicenseStatus, string>> = {
  active: "已授权",
  expired: "已过期",
  revoked: "已吊销",
  not_yet_valid: "尚未生效",
  none: "未授权",
}


export function licenseModuleNames(modules: readonly LicenseModuleKey[]): string {
  return modules.map((module) => LICENSE_MODULE_LABELS[module]).join("、")
}
