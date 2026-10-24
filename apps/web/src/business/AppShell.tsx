import {
  Alert,
  Button,
  Card,
  Col,
  Layout,
  Menu,
  Row,
  Skeleton,
  Space,
  Statistic,
  Tag,
  Typography,
} from "antd"
import { useCallback, useEffect, useMemo, useState } from "react"

import { getPageCount, logout } from "./client"
import { DictionaryWorkspace } from "./features/configuration/DictionaryWorkspace"
import { GovernanceWorkspace } from "./features/governance/GovernanceWorkspace"
import { AccountWorkspace } from "./features/platform/AccountWorkspace"
import { AttendanceWorkspace } from "./features/attendance/AttendanceWorkspace"
import { LifecycleWorkspace } from "./features/lifecycle/LifecycleWorkspace"
import { OrganizationDetailWorkspace } from "./features/organization/OrganizationDetailWorkspace"
import { OrganizationWorkspace } from "./features/organization/OrganizationWorkspace"
import { HeadcountWorkspace } from "./features/workforce/HeadcountWorkspace"
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
import type { OrganizationDetailRoute } from "./navigation"
import type { WorkspaceKey } from "./navigation"
import type { UserProfile } from "./types"


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
      {error && <Alert type="error" showIcon message={error} />}
      {!counts ? <Skeleton active paragraph={{ rows: 6 }} /> : (
        <Row gutter={[16, 16]} className="metric-strip">
          <Col xs={12} xl={4}><Statistic title="有效组织" value={counts.organizations} /></Col>
          <Col xs={12} xl={5}><Statistic title="人员档案" value={counts.persons} /></Col>
          <Col xs={12} xl={5}><Statistic title="职务" value={counts.jobs} /></Col>
          <Col xs={12} xl={5}><Statistic title="法人主体" value={counts.legalEntities} /></Col>
          <Col xs={12} xl={5}><Statistic title="编制月度版本" value={counts.headcountPlans} /></Col>
        </Row>
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
      </div>
    </section>
  )
}


function PendingWorkspace({ label }: { readonly label: string }) {
  return (
    <section className="workspace-section">
      <Typography.Title level={2}>{label}</Typography.Title>
      <Alert type="info" showIcon message="该工作区将在第一阶段后续批次开放" description="当前不会显示假功能或占位业务表单。" />
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

  const can = useCallback(
    (permission: string) => user.permissions.includes("*") || user.permissions.includes(permission),
    [user.permissions],
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
    const item = (key: WorkspaceKey) => {
      const workspace = visibleWorkspaces.find((candidate) => candidate.key === key)
      return workspace ? {
        key: workspace.key,
        label: workspace.label,
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
        label: workspace.label,
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
  }, [visibleWorkspaces])

  const selectedWorkspace = workspaces.find((workspace) => workspace.key === selected)
  const selectedInOrganization = organizationWorkspaceKeys.includes(selected)

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
  } else if (selected === "headcount") {
    content = <HeadcountWorkspace token={token} canAdmin={can("WORKFORCE_ADMIN")} />
  } else if (selected === "recruitment") {
    content = <RecruitmentWorkspace token={token} canAdmin={can("LIFECYCLE_ADMIN")} />
  } else if (selected === "lifecycle") {
    content = <LifecycleWorkspace token={token} canAdmin={can("LIFECYCLE_ADMIN")} />
  } else if (selected === "attendance") {
    content = <AttendanceWorkspace token={token} canAdmin={can("ATTENDANCE_ADMIN")} />
  } else if (selected === "governance") {
    content = <GovernanceWorkspace token={token} canAdmin={can("DATA_GOVERNANCE_ADMIN")} />
  } else if (selected === "accounts") {
    content = <AccountWorkspace token={token} currentUserId={user.id} />
  } else if (selected === "dashboard") {
    content = <DashboardWorkspace token={token} onNavigate={navigate} />
  } else {
    content = <PendingWorkspace label={workspaces.find((item) => item.key === selected)?.label ?? "工作区"} />
  }

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
            {selectedInOrganization && (
              <>
                <Typography.Text className="business-breadcrumb-group" type="secondary">组织管理</Typography.Text>
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
            <div className="user-summary">
              <Typography.Text strong>{user.display_name}</Typography.Text>
              <Typography.Text type="secondary">{user.roles.join("、")}</Typography.Text>
            </div>
            <Button loading={signingOut} onClick={() => void signOut()}>退出</Button>
          </Space>
        </Header>
        <Content className="business-content">{content}</Content>
      </Layout>
    </Layout>
  )
}
