import { Layout, Menu, Typography } from "antd"

import { ModuleOverview } from "./features/module-overview/ModuleOverview"

const { Content, Header, Sider } = Layout
const { Text, Title } = Typography

const navigationItems = [
  { key: "overview", label: "建设总览" },
  { key: "phase-1", label: "一阶段 · Core HR" },
  { key: "phase-2", label: "二阶段 · 流程" },
  { key: "phase-3", label: "三阶段 · 考勤" },
]

export default function App(): React.JSX.Element {
  return (
    <Layout className="app-shell">
      <Sider width={240} theme="dark">
        <div className="brand">
          <span className="brand-mark">C</span>
          <span>
            <strong>coreHR</strong>
            <Text className="brand-caption">企业人力系统</Text>
          </span>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={["overview"]}
          items={navigationItems}
        />
      </Sider>
      <Layout>
        <Header className="app-header">
          <div>
            <Text type="secondary">产品化自用 · 管理员工作台</Text>
            <Title level={3}>业务一至三阶段建设总览</Title>
          </div>
          <Tagline />
        </Header>
        <Content className="app-content">
          <ModuleOverview />
        </Content>
      </Layout>
    </Layout>
  )
}

function Tagline(): React.JSX.Element {
  return <span className="tagline">PostgreSQL · FastAPI · React</span>
}

