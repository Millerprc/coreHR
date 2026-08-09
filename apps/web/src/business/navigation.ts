export type WorkspaceKey =
  | "dashboard"
  | "configuration"
  | "organization"
  | "people"
  | "headcount"
  | "recruitment"
  | "lifecycle"
  | "attendance"
  | "governance"


export interface WorkspaceDefinition {
  readonly key: WorkspaceKey
  readonly label: string
  readonly permission?: string
  readonly available: boolean
}


export const workspaces: readonly WorkspaceDefinition[] = [
  { key: "dashboard", label: "工作台", available: true },
  {
    key: "configuration",
    label: "配置中心",
    permission: "CONFIGURATION_VIEW",
    available: true,
  },
  {
    key: "organization",
    label: "组织中心",
    permission: "ORGANIZATION_VIEW",
    available: true,
  },
  { key: "people", label: "人员中心", permission: "WORKFORCE_ADMIN", available: true },
  { key: "headcount", label: "人力与编制", permission: "WORKFORCE_ADMIN", available: true },
  { key: "recruitment", label: "招聘需求", permission: "LIFECYCLE_ADMIN", available: true },
  { key: "lifecycle", label: "员工生命周期", permission: "LIFECYCLE_ADMIN", available: true },
  { key: "attendance", label: "考勤管理", permission: "ATTENDANCE_ADMIN", available: true },
  {
    key: "governance",
    label: "数据治理",
    permission: "DATA_GOVERNANCE_VIEW",
    available: true,
  },
]


export function workspaceFromHash(hash: string): WorkspaceKey {
  const key = hash.replace(/^#/, "") as WorkspaceKey
  return workspaces.some((workspace) => workspace.key === key && workspace.available)
    ? key
    : "dashboard"
}
