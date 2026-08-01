import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Form,
  Input,
  Layout,
  Menu,
  Row,
  Skeleton,
  Space,
  Statistic,
  Tag,
  Typography,
} from "antd"
import { useCallback, useEffect, useState } from "react"

import {
  clearToken,
  getModules,
  getPageCount,
  getProfile,
  login,
  logout,
  storedToken,
  storeToken,
} from "./client"
import type { ModuleStatus, UserProfile } from "./types"
import "./business.css"

const { Content, Header, Sider } = Layout
const { Paragraph, Text, Title } = Typography

interface DashboardState {
  readonly user: UserProfile
  readonly modules: readonly ModuleStatus[]
  readonly counts: {
    readonly organizations: number
    readonly persons: number
    readonly jobs: number
    readonly legalEntities: number
    readonly headcountPlans: number
  }
}

function LoginPanel({ onLoggedIn }: { readonly onLoggedIn: (token: string) => void }) {
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(values: { username: string; password: string }): Promise<void> {
    setSubmitting(true)
    setError(null)
    try {
      const result = await login(values.username, values.password)
      storeToken(result.access_token)
      onLoggedIn(result.access_token)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "登录失败")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="login-page">
      <Card className="login-card" bordered={false}>
        <div className="login-brand">C</div>
        <Title level={2}>coreHR 管理员工作台</Title>
        <Paragraph type="secondary">第一批仅向 HR 系统主管理员开放</Paragraph>
        {error && <Alert type="error" showIcon message={error} />}
        <Form layout="vertical" onFinish={submit} requiredMark={false}>
          <Form.Item label="账号" name="username" rules={[{ required: true, message: "请输入账号" }]}>
            <Input autoComplete="username" size="large" />
          </Form.Item>
          <Form.Item label="密码" name="password" rules={[{ required: true, message: "请输入密码" }]}>
            <Input.Password autoComplete="current-password" size="large" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={submitting} block size="large">
            登录
          </Button>
        </Form>
      </Card>
    </main>
  )
}

function PhaseCard({ module }: { readonly module: ModuleStatus }) {
  return (
    <Card className="business-phase-card" title={`${module.phase} 阶段 · ${module.name}`}>
      <Space wrap>
        <Tag color="processing">首批切片可用</Tag>
        <Text code>{module.code}</Text>
      </Space>
      <Title level={5}>已开放接口</Title>
      <ul className="compact-list">
        {module.available_endpoints.map((endpoint) => (
          <li key={endpoint}><code>{endpoint}</code></li>
        ))}
      </ul>
      <Title level={5}>等待企业资料</Title>
      <ul className="compact-list muted-list">
        {module.pending_inputs.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </Card>
  )
}

function Dashboard({ token, onSignedOut }: { readonly token: string; readonly onSignedOut: () => void }) {
  const [state, setState] = useState<DashboardState | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const [user, moduleRegistry, organizations, persons, jobs, legalEntities, headcountPlans] =
        await Promise.all([
          getProfile(token),
          getModules(token),
          getPageCount("/api/v1/workforce/organizations", token),
          getPageCount("/api/v1/workforce/persons", token),
          getPageCount("/api/v1/workforce/jobs", token),
          getPageCount("/api/v1/workforce/legal-entities", token),
          getPageCount("/api/v1/workforce/headcount-plans", token),
        ])
      setState({
        user,
        modules: moduleRegistry.items,
        counts: { organizations, persons, jobs, legalEntities, headcountPlans },
      })
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "加载工作台失败")
    }
  }, [token])

  useEffect(() => { void load() }, [load])

  async function signOut(): Promise<void> {
    await logout(token).catch(() => undefined)
    clearToken()
    onSignedOut()
  }

  return (
    <Layout className="business-shell">
      <Sider width={232} theme="dark">
        <div className="business-brand"><span>C</span><strong>coreHR</strong></div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={["dashboard"]}
          items={[
            { key: "dashboard", label: "建设与数据总览" },
            { key: "phase1", label: "组织、人事与编制" },
            { key: "phase2", label: "流程与人员生命周期" },
            { key: "phase3", label: "考勤" },
          ]}
        />
      </Sider>
      <Layout>
        <Header className="business-header">
          <div><Text type="secondary">产品化自用 · 主管理员工作台</Text><Title level={3}>业务一至三阶段</Title></div>
          <Space>
            <Text>{state?.user.display_name ?? "加载中"}</Text>
            <Button onClick={() => void signOut()}>退出</Button>
          </Space>
        </Header>
        <Content className="business-content">
          {error && <Alert type="error" showIcon message="工作台加载失败" description={error} />}
          {!state ? <Skeleton active paragraph={{ rows: 10 }} /> : (
            <>
              <Row gutter={[16, 16]}>
                <Col xs={12} lg={4}><Card><Statistic title="有效组织" value={state.counts.organizations} /></Card></Col>
                <Col xs={12} lg={5}><Card><Statistic title="人员档案" value={state.counts.persons} /></Card></Col>
                <Col xs={12} lg={5}><Card><Statistic title="职务" value={state.counts.jobs} /></Card></Col>
                <Col xs={12} lg={5}><Card><Statistic title="法人主体" value={state.counts.legalEntities} /></Card></Col>
                <Col xs={12} lg={5}><Card><Statistic title="编制月度版本" value={state.counts.headcountPlans} /></Card></Col>
              </Row>
              <Card className="identity-card" title="当前权限">
                <Descriptions column={{ xs: 1, md: 3 }}>
                  <Descriptions.Item label="账号">{state.user.username}</Descriptions.Item>
                  <Descriptions.Item label="角色">{state.user.roles.join("、")}</Descriptions.Item>
                  <Descriptions.Item label="数据范围">主管理员全量</Descriptions.Item>
                </Descriptions>
              </Card>
              <Row gutter={[18, 18]}>
                {state.modules.map((module) => (
                  <Col key={module.code} xs={24} xl={8}><PhaseCard module={module} /></Col>
                ))}
              </Row>
              <Alert
                className="api-hint"
                type="info"
                showIcon
                message="当前为首批可运行切片"
                description={<>真实业务表单继续按原子任务补齐；当前接口契约可在 <a href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">API 文档</a> 验收。</>}
              />
            </>
          )}
        </Content>
      </Layout>
    </Layout>
  )
}

export default function BusinessApp() {
  const [token, setToken] = useState<string | null>(() => storedToken())
  return token
    ? <Dashboard token={token} onSignedOut={() => setToken(null)} />
    : <LoginPanel onLoggedIn={setToken} />
}
