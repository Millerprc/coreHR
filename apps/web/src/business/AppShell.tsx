// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import {
  Alert,
  Button,
  Card,
  Layout,
  Menu,
  Skeleton,
  Space,
  Tag,
  Tooltip,
  Typography,
} from "antd"
import { useCallback, useEffect, useMemo, useState } from "react"

import { getLicense, getPageCount, logout } from "./client"
import { MetricStrip } from "./components/MetricStrip"
import { DictionaryWorkspace } from "./features/configuration/DictionaryWorkspace"
import { GovernanceWorkspace } from "./features/governance/GovernanceWorkspace"
import { LicenseBadge } from "./features/license/LicenseBadge"
import { LicenseBanner } from "./features/license/LicenseBanner"
import { LicenseWorkspace } from "./features/license/LicenseWorkspace"
import { licenseModuleNames } from "./features/license/licenseLabels"
import {
  bakedWatermarkText,
  licenseWatermarkText,
  moduleWriteAllowed,
  normalizeLicenseState,
} from "./features/license/licenseState"
import { AccountWorkspace } from "./features/platform/AccountWorkspace"
import { AuditLogWorkspace } from "./features/platform/AuditLogWorkspace"
import { AttendanceWorkspace } from "./features/attendance/AttendanceWorkspace"
import { LifecycleWorkspace } from "./features/lifecycle/LifecycleWorkspace"
import { MessageBell } from "./features/messaging/MessageBell"
import { OrganizationDetailWorkspace } from "./features/organization/OrganizationDetailWorkspace"
import { OrganizationWorkspace } from "./features/organization/OrganizationWorkspace"
import { PositionWorkspace } from "./features/organization/PositionWorkspace"
import { ReportingWorkspace } from "./features/organization/ReportingWorkspace"
import { HeadcountWorkspace } from "./features/workforce/HeadcountWorkspace"
import { HistoricalRosterWorkspace } from "./features/workforce/HistoricalRosterWorkspace"
import { PeopleWorkspace } from "./features/workforce/PeopleWorkspace"
import { RecruitmentWorkspace } from "./features/workforce/RecruitmentWorkspace"
import { workforceApi } from "./features/workforce/api"
import {
  isWorkspaceKey,
  organizationDetailRouteFromHash,
  organizationWorkspaceKeys,
  workspaceFromHash,
  workspaces,
} from "./navigation"
import type { OrganizationDetailRoute, WorkspaceDefinition } from "./navigation"
import type { WorkspaceKey } from "./navigation"
import type { LicenseModuleKey, LicenseState, UserProfile } from "./types"


const { Content, Header, Sider } = Layout


interface AppShellProps {
  readonly token: string
  readonly user: UserProfile
  readonly onSignedOut: () => void
}


interface DashboardCounts {
  readonly organizations: number
  readonly persons: number
  readonly jobs: number
  readonly legalEntities: number
  readonly headcountPlans: number
}


function DashboardWorkspace({
  token,
  onNavigate,
}: {
  readonly token: string
  readonly onNavigate: (key: WorkspaceKey) => void
}) {
  const [counts, setCounts] = useState<DashboardCounts | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void Promise.all([
      workforceApi.organizations(token).then((items) => items.length),
      getPageCount("/api/v1/workforce/persons", token),
      getPageCount("/api/v1/workforce/jobs", token),
      getPageCount("/api/v1/workforce/legal-entities", token),
      getPageCount("/api/v1/workforce/headcount-plans", token),
    ])
      .then(([organizations, persons, jobs, legalEntities, headcountPlans]) => {
        setCounts({ organizations, persons, jobs, legalEntities, headcountPlans })
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : "工作台加载失败"))
  }, [token])

  return (
    <section aria-labelledby="dashboard-title" className="workspace-section">
      <div className="workspace-heading">
        <div>
          <Typography.Title id="dashboard-title" level={2}>工作台</Typography.Title>
          <Typography.Paragraph type="secondary">查看基础人力数据，并进入当前已经开放的管理工作区。</Typography.Paragraph>
        </div>
        <Tag color="processing">第一阶段 Core HR</Tag>
      </div>
      {error && <Alert type="error" showIcon title={error} />}
      {!counts ? <Skeleton active paragraph={{ rows: 6 }} /> : (
        /* Requirement: D-091 — 指标条统一由公共组件承载，工作台与职位管理共用同一结构。 */
        <MetricStrip items={[
          { label: "有效组织", value: counts.organizations },
          { label: "人员档案", value: counts.persons },
          { label: "职务", value: counts.jobs },
          { label: "法人主体", value: counts.legalEntities },
          { label: "编制月度版本", value: counts.headcountPlans },
        ]} />
      )}
      {/* Requirement: ORG-PROT-001 — 工作台入口与组织管理菜单使用同一套产品术语。 */}
      <div className="workspace-entry-grid">
        <Card variant="outlined" title="基础资料">
          <Typography.Paragraph>维护稳定业务代码、字典层级和启停状态。</Typography.Paragraph>
          <Button onClick={() => onNavigate("configuration")}>进入基础资料</Button>
        </Card>
        <Card variant="outlined" title="部门管理">
          <Typography.Paragraph>维护当前组织树、未来变更、法人、负责人、BP及财务维度。</Typography.Paragraph>
          <Button type="primary" onClick={() => onNavigate("organization")}>进入部门管理</Button>
        </Card>
        <Card variant="outlined" title="人员中心">
          <Typography.Paragraph>维护自然人、劳动关系、主组织职务和协议关系。</Typography.Paragraph>
          <Button onClick={() => onNavigate("people")}>进入人员中心</Button>
        </Card>
        <Card variant="outlined" title="编制管理">
          <Typography.Paragraph>维护月度编制、占编规则、冻结和快照结果。</Typography.Paragraph>
          <Button onClick={() => onNavigate("headcount")}>进入编制管理</Button>
        </Card>
        <Card variant="outlined" title="招聘需求">
          <Typography.Paragraph>创建招聘需求并查看不阻断业务的编制参考。</Typography.Paragraph>
          <Button onClick={() => onNavigate("recruitment")}>进入招聘需求</Button>
        </Card>
        <Card variant="outlined" title="职位管理">
          <Typography.Paragraph>维护职务与职级、职等、职类、序列维度，并按生效日期管理版本。</Typography.Paragraph>
          <Button onClick={() => onNavigate("positions")}>进入职位管理</Button>
        </Card>
        <Card variant="outlined" title="汇报关系">
          <Typography.Paragraph>维护上下级汇报链路，支持直属与虚线关系，并查看关系图。</Typography.Paragraph>
          <Button onClick={() => onNavigate("reporting")}>进入汇报关系</Button>
        </Card>
        <Card variant="outlined" title="操作日志">
          <Typography.Paragraph>查询关键业务动作的审计留痕，支持按时间、动作与对象筛选并导出。</Typography.Paragraph>
          <Button onClick={() => onNavigate("audit")}>进入操作日志</Button>
        </Card>
      </div>
    </section>
  )
}


function PendingWorkspace({ label }: { readonly label: string }) {
  return (
    <section className="workspace-section">
      <Typography.Title level={2}>{label}</Typography.Title>
      <Alert type="info" showIcon title="该工作区将在第一阶段后续批次开放" description="当前不会显示假功能或占位业务表单。" />
    </section>
  )
}


export function AppShell({ token, user, onSignedOut }: AppShellProps) {
  const [selected, setSelected] = useState<WorkspaceKey>(() => workspaceFromHash(window.location.hash))
  const [organizationDetailRoute, setOrganizationDetailRoute] = useState<OrganizationDetailRoute | null>(
    () => organizationDetailRouteFromHash(window.location.hash),
  )
  const [signingOut, setSigningOut] = useState(false)
  const [openMenuKeys, setOpenMenuKeys] = useState<readonly string[]>(["organization-management"])
  // Requirement: D-108 — 授权状态只由后端给出；读取失败时按未授权（只读演示）处理。
  const [license, setLicense] = useState<LicenseState | null>(null)
  const [licenseLoaded, setLicenseLoaded] = useState(false)

  const can = useCallback(
    (permission: string) => user.permissions.includes("*") || user.permissions.includes(permission),
    [user.permissions],
  )

  const loadLicense = useCallback(async () => {
    try {
      setLicense(normalizeLicenseState(await getLicense(token)))
    } catch {
      setLicense(normalizeLicenseState(null))
    } finally {
      setLicenseLoaded(true)
    }
  }, [token])

  useEffect(() => { void loadLicense() }, [loadLicense])

  const isModuleLocked = useCallback(
    (module: LicenseModuleKey) => !moduleWriteAllowed(license, module),
    [license],
  )

  const navigate = useCallback((key: WorkspaceKey) => {
    window.location.hash = key
    setSelected(key)
    setOrganizationDetailRoute(null)
  }, [])

  useEffect(() => {
    const handleHashChange = () => {
      setSelected(workspaceFromHash(window.location.hash))
      setOrganizationDetailRoute(organizationDetailRouteFromHash(window.location.hash))
    }
    window.addEventListener("hashchange", handleHashChange)
    return () => window.removeEventListener("hashchange", handleHashChange)
  }, [])

  const visibleWorkspaces = useMemo(
    () => workspaces.filter((workspace) => !workspace.permission || can(workspace.permission)),
    [can],
  )

  const menuItems = useMemo(() => {
    // Requirement: D-108 — 被锁模块的菜单项保留可见，带锁标与「需要 XX 模块授权」提示。
    const menuLabel = (workspace: WorkspaceDefinition): React.ReactNode => {
      const locked = (workspace.licensedModules ?? []).filter((module) => isModuleLocked(module))
      if (locked.length === 0) return workspace.label
      return (
        <Tooltip title={`需要 ${licenseModuleNames(locked)} 模块授权`}>
          <span className="workspace-menu-label">
            {workspace.label}
            <span className="license-lock" role="img" aria-label="需要授权" />
          </span>
        </Tooltip>
      )
    }
    const item = (key: WorkspaceKey) => {
      const workspace = visibleWorkspaces.find((candidate) => candidate.key === key)
      return workspace ? {
        key: workspace.key,
        label: menuLabel(workspace),
        disabled: !workspace.available,
      } : null
    }
    const organizationChildren = organizationWorkspaceKeys
      .map(item)
      .filter((workspace): workspace is NonNullable<typeof workspace> => workspace !== null)
    const standalone = visibleWorkspaces
      .filter((workspace) => workspace.key !== "dashboard" && !organizationWorkspaceKeys.includes(workspace.key))
      .map((workspace) => ({
        key: workspace.key,
        label: menuLabel(workspace),
        disabled: !workspace.available,
      }))

    // Requirement: ORG-PROT-001 — 组织管理菜单展开后呈现部门、职位、编制和基础资料入口。
    return [
      item("dashboard"),
      organizationChildren.length ? {
        key: "organization-management",
        label: "组织管理",
        children: organizationChildren,
      } : null,
      ...standalone,
    ].filter((workspace): workspace is NonNullable<typeof workspace> => workspace !== null)
  }, [visibleWorkspaces, isModuleLocked])

  const selectedWorkspace = workspaces.find((workspace) => workspace.key === selected)
  const selectedInOrganization = organizationWorkspaceKeys.includes(selected)
  // Requirement: D-091 — 面包屑分组与画板一致：组织管理分组内的入口带分组名，
  // 操作日志按画板归在「数据治理」分组下。
  const breadcrumbGroup = selectedInOrganization
    ? "组织管理"
    : selected === "audit" ? "数据治理" : null

  useEffect(() => {
    if (!selectedInOrganization) return
    setOpenMenuKeys((current) => current.includes("organization-management")
      ? current
      : [...current, "organization-management"])
  }, [selected, selectedInOrganization])

  async function signOut(): Promise<void> {
    setSigningOut(true)
    await logout(token).catch(() => undefined)
    onSignedOut()
  }

  let content: React.ReactNode
  if (selected === "configuration") {
    content = <DictionaryWorkspace token={token} canAdmin={can("CONFIGURATION_ADMIN")} />
  } else if (selected === "organization") {
    // Requirement: ORG-PROT-002 — 详情Hash在独立标签页直接打开，不先渲染部门列表。
    content = organizationDetailRoute ? (
      <OrganizationDetailWorkspace
        token={token}
        canAdmin={can("ORGANIZATION_ADMIN")}
        organizationId={organizationDetailRoute.organizationId}
        initialEffectiveAt={organizationDetailRoute.effectiveAt}
      />
    ) : (
      <OrganizationWorkspace token={token} canAdmin={can("ORGANIZATION_ADMIN")} />
    )
  } else if (selected === "people") {
    content = <PeopleWorkspace token={token} canAdmin={can("WORKFORCE_ADMIN")} />
  } else if (selected === "historical-roster") {
    // Requirement: D-102 — 历史花名册是独立列表页，挂在人员中心之后。
    content = <HistoricalRosterWorkspace token={token} />
  } else if (selected === "positions") {
    content = <PositionWorkspace token={token} canAdmin={can("WORKFORCE_ADMIN")} />
  } else if (selected === "reporting") {
    content = <ReportingWorkspace token={token} canAdmin={can("WORKFORCE_ADMIN")} />
  } else if (selected === "audit") {
    content = <AuditLogWorkspace token={token} canAdmin={can("DATA_GOVERNANCE_ADMIN")} />
  } else if (selected === "headcount") {
    content = <HeadcountWorkspace token={token} canAdmin={can("WORKFORCE_ADMIN")} />
  } else if (selected === "recruitment") {
    content = <RecruitmentWorkspace token={token} canAdmin={can("LIFECYCLE_ADMIN")} />
  } else if (selected === "lifecycle") {
    // Requirement: D-108 — 受授权管理的模块在未授权时写操作禁用，读操作保留。
    content = (
      <LifecycleWorkspace
        token={token}
        canAdmin={can("LIFECYCLE_ADMIN") && moduleWriteAllowed(license, "lifecycle")}
      />
    )
  } else if (selected === "attendance") {
    content = (
      <AttendanceWorkspace
        token={token}
        canAdmin={can("ATTENDANCE_ADMIN") && moduleWriteAllowed(license, "attendance")}
      />
    )
  } else if (selected === "governance") {
    content = (
      <GovernanceWorkspace
        token={token}
        canAdmin={can("DATA_GOVERNANCE_ADMIN") && moduleWriteAllowed(license, "governance")}
      />
    )
  } else if (selected === "accounts") {
    content = <AccountWorkspace token={token} currentUserId={user.id} />
  } else if (selected === "license") {
    content = <LicenseWorkspace token={token} onLicenseChanged={() => void loadLicense()} />
  } else if (selected === "dashboard") {
    content = <DashboardWorkspace token={token} onNavigate={navigate} />
  } else {
    content = <PendingWorkspace label={workspaces.find((item) => item.key === selected)?.label ?? "工作区"} />
  }

  // Requirement: D-108 — 被锁模块进入后显示授权说明面板，而不是空白页或假表单。
  const lockedModules = (selectedWorkspace?.licensedModules ?? []).filter((module) => isModuleLocked(module))
  const licenseNotice = lockedModules.length > 0
    ? (
      <LicenseBanner
        modules={lockedModules}
        state={license}
        onOpenLicense={can("*") ? () => navigate("license") : undefined}
      />
    )
    : null

  return (
    <Layout className="business-shell">
      <Sider width={224} theme="dark" breakpoint="lg" collapsedWidth={0}>
        <div className="business-brand" aria-label="coreHR">
          <span>C</span>
          <strong>coreHR</strong>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          openKeys={[...openMenuKeys]}
          onOpenChange={setOpenMenuKeys}
          selectedKeys={[selected]}
          items={menuItems}
          onClick={({ key }) => {
            if (isWorkspaceKey(key)) navigate(key)
          }}
        />
      </Sider>
      <Layout>
        <Header className="business-header">
          <nav className="business-breadcrumb" aria-label="当前位置">
            {breadcrumbGroup && (
              <>
                <Typography.Text className="business-breadcrumb-group" type="secondary">{breadcrumbGroup}</Typography.Text>
                <Typography.Text type="secondary">/</Typography.Text>
              </>
            )}
            <Typography.Text strong>{selectedWorkspace?.label ?? "工作台"}</Typography.Text>
            {organizationDetailRoute && (
              <>
                <Typography.Text type="secondary">/</Typography.Text>
                <Typography.Text strong>部门详情</Typography.Text>
              </>
            )}
          </nav>
          <Space>
            {/* Requirement: D-100 — 顶栏消息铃铛展示未读数，承载站内信入口。 */}
            <MessageBell token={token} />
            <div className="user-summary">
              <Typography.Text strong>{user.display_name}</Typography.Text>
              <Typography.Text type="secondary">{user.roles.join("、")}</Typography.Text>
            </div>
            <Button loading={signingOut} onClick={() => void signOut()}>退出</Button>
            {/* Requirement: D-108 — 授权徽标固定在顶栏最右端，一眼可见。 */}
            {licenseLoaded && <LicenseBadge state={license} />}
          </Space>
        </Header>
        <Content className="business-content">
          {/* Requirement: D-108 — 内容区水印层：斜向重复、低透明度，且不拦截任何交互。 */}
          {licenseLoaded && (
            <div className="corehr-watermark" aria-hidden="true">
              {Array.from({ length: 24 }, (_, index) => (
                <span className="corehr-watermark-text" key={index}>
                  {bakedWatermarkText() || licenseWatermarkText(license)}
                </span>
              ))}
            </div>
          )}
          <div className="business-content-body">
            {licenseNotice}
            {content}
          </div>
        </Content>
      </Layout>
    </Layout>
  )
}
