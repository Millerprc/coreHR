// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import type { LicenseModuleKey } from "./types"


export type WorkspaceKey =
  | "dashboard"
  | "configuration"
  | "organization"
  | "positions"
  | "reporting"
  | "people"
  | "historical-roster"
  | "headcount"
  | "recruitment"
  | "lifecycle"
  | "attendance"
  | "governance"
  | "accounts"
  | "audit"
  | "license"


export interface WorkspaceDefinition {
  readonly key: WorkspaceKey
  readonly label: string
  /** 平台权限码（单值语义）：控制菜单入口是否可见。 */
  readonly permission?: string
  /**
   * Requirement: D-108 — 受模块级授权管理的入口。
   * 该字段只声明「这个入口归属哪些授权模块」，不参与 permission 过滤：
   * 被锁模块依然可见可进入，只是入口带锁标、进入后显示授权说明面板。
   * 一个入口可能归属多个模块（员工生命周期同时承载审批与流程引擎）。
   */
  readonly licensedModules?: readonly LicenseModuleKey[]
  readonly available: boolean
}


export interface OrganizationDetailRoute {
  readonly organizationId: string
  readonly effectiveAt: string | null
}


export const workspaces: readonly WorkspaceDefinition[] = [
  { key: "dashboard", label: "工作台", available: true },
  {
    key: "configuration",
    label: "基础资料",
    permission: "CONFIGURATION_VIEW",
    available: true,
  },
  {
    key: "organization",
    label: "部门管理",
    permission: "ORGANIZATION_VIEW",
    available: true,
  },
  {
    key: "positions",
    label: "职位管理",
    permission: "WORKFORCE_ADMIN",
    available: true,
  },
  {
    key: "reporting",
    label: "汇报关系",
    permission: "WORKFORCE_ADMIN",
    available: true,
  },
  { key: "people", label: "人员中心", permission: "WORKFORCE_ADMIN", available: true },
  // Requirement: D-102 — 历史花名册入口挂在人员中心之后，读权限与接口一致（PERSON_VIEW）。
  {
    key: "historical-roster",
    label: "历史花名册",
    permission: "PERSON_VIEW",
    available: true,
  },
  { key: "headcount", label: "编制管理", permission: "WORKFORCE_ADMIN", available: true },
  { key: "recruitment", label: "招聘需求", permission: "LIFECYCLE_ADMIN", available: true },
  // Requirement: D-108 — 员工生命周期同时承载审批与流程引擎，因此归属两个授权模块。
  {
    key: "lifecycle",
    label: "员工生命周期",
    permission: "LIFECYCLE_ADMIN",
    licensedModules: ["lifecycle", "workflow"],
    available: true,
  },
  {
    key: "attendance",
    label: "考勤管理",
    permission: "ATTENDANCE_ADMIN",
    licensedModules: ["attendance"],
    available: true,
  },
  {
    key: "governance",
    label: "数据治理",
    permission: "DATA_GOVERNANCE_VIEW",
    licensedModules: ["governance"],
    available: true,
  },
  { key: "accounts", label: "账号与权限", permission: "*", available: true },
  {
    key: "audit",
    label: "操作日志",
    permission: "DATA_GOVERNANCE_ADMIN",
    available: true,
  },
  // Requirement: D-108 — 授权管理入口只对主管理员开放（激活与停用都要求 * 权限）。
  { key: "license", label: "授权管理", permission: "*", available: true },
]


// Requirement: ORG-PROT-001 — 组织相关入口在侧栏中形成稳定分组，不再以扁平工作区散列。
export const organizationWorkspaceKeys: readonly WorkspaceKey[] = [
  "organization",
  "positions",
  "reporting",
  "headcount",
  "configuration",
]


export function isWorkspaceKey(key: string): key is WorkspaceKey {
  return workspaces.some((workspace) => workspace.key === key)
}


const organizationIdPattern = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i


function isIsoDate(value: string): boolean {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (!match) return false
  const [year, month, day] = match.slice(1).map(Number)
  const parsed = new Date(Date.UTC(year, month - 1, day))
  return parsed.getUTCFullYear() === year
    && parsed.getUTCMonth() === month - 1
    && parsed.getUTCDate() === day
}


// Requirement: ORG-PROT-002 — 部门详情使用可复制的新标签页地址，并保留按日期查看上下文。
export function organizationDetailRouteFromHash(hash: string): OrganizationDetailRoute | null {
  const normalized = hash.replace(/^#/, "")
  const [path, query = ""] = normalized.split("?", 2)
  const [workspace, organizationId, ...extra] = path.split("/")
  if (workspace !== "organization" || extra.length || !organizationIdPattern.test(organizationId ?? "")) {
    return null
  }
  const effectiveAt = new URLSearchParams(query).get("effective_at")
  if (effectiveAt !== null && !isIsoDate(effectiveAt)) return null
  return { organizationId, effectiveAt }
}


export function organizationDetailUrl(organizationId: string, effectiveAt: string): string {
  return `#organization/${encodeURIComponent(organizationId)}?effective_at=${encodeURIComponent(effectiveAt)}`
}


export function workspaceFromHash(hash: string): WorkspaceKey {
  if (organizationDetailRouteFromHash(hash)) return "organization"
  const key = hash.replace(/^#/, "").split("?", 1)[0]
  return isWorkspaceKey(key) && workspaces.some((workspace) => workspace.key === key && workspace.available)
    ? key
    : "dashboard"
}
