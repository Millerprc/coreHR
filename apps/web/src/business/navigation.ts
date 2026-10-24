export type WorkspaceKey =
  | "dashboard"
  | "configuration"
  | "organization"
  | "positions"
  | "people"
  | "headcount"
  | "recruitment"
  | "lifecycle"
  | "attendance"
  | "governance"
  | "accounts"


export interface WorkspaceDefinition {
  readonly key: WorkspaceKey
  readonly label: string
  readonly permission?: string
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
    available: false,
  },
  { key: "people", label: "人员中心", permission: "WORKFORCE_ADMIN", available: true },
  { key: "headcount", label: "编制管理", permission: "WORKFORCE_ADMIN", available: true },
  { key: "recruitment", label: "招聘需求", permission: "LIFECYCLE_ADMIN", available: true },
  { key: "lifecycle", label: "员工生命周期", permission: "LIFECYCLE_ADMIN", available: true },
  { key: "attendance", label: "考勤管理", permission: "ATTENDANCE_ADMIN", available: true },
  {
    key: "governance",
    label: "数据治理",
    permission: "DATA_GOVERNANCE_VIEW",
    available: true,
  },
  { key: "accounts", label: "账号与权限", permission: "*", available: true },
]


// Requirement: ORG-PROT-001 — 组织相关入口在侧栏中形成稳定分组，不再以扁平工作区散列。
export const organizationWorkspaceKeys: readonly WorkspaceKey[] = [
  "organization",
  "positions",
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
