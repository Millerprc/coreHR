import { Alert, Card, Col, List, Row, Skeleton, Space, Tag, Typography } from "antd"
import { useEffect, useState } from "react"

import { getModuleRegistry } from "../../api/client"
import type { ModuleStatus } from "../../api/types"

const { Paragraph, Text, Title } = Typography

const statusLabels: Record<ModuleStatus["status"], string> = {
  foundation: "基础建设",
  slice_available: "首批切片可用",
  planned: "待建设",
}

function PhaseCard({ module }: { readonly module: ModuleStatus }): React.JSX.Element {
  return (
    <Card
      className="phase-card"
      title={
        <Space>
          <span className="phase-number">{module.phase}</span>
          <span>{module.name}</span>
        </Space>
      }
      extra={<Tag color="blue">{statusLabels[module.status]}</Tag>}
    >
      <Text type="secondary">{module.code}</Text>
      <Title level={5}>当前可用接口</Title>
      <List
        size="small"
        dataSource={[...module.available_endpoints]}
        locale={{ emptyText: "尚无可用接口" }}
        renderItem={(endpoint) => (
          <List.Item>
            <code>{endpoint}</code>
          </List.Item>
        )}
      />
      <Title level={5}>等待业务资料</Title>
      <List
        size="small"
        dataSource={[...module.pending_inputs]}
        locale={{ emptyText: "当前无阻塞资料" }}
        renderItem={(item) => <List.Item>{item}</List.Item>}
      />
    </Card>
  )
}

export function ModuleOverview(): React.JSX.Element {
  const [modules, setModules] = useState<readonly ModuleStatus[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()

    getModuleRegistry(controller.signal)
      .then((response) => setModules(response.items))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return
        setErrorMessage(error instanceof Error ? error.message : "无法读取模块状态")
      })
      .finally(() => setIsLoading(false))

    return () => controller.abort()
  }, [])

  if (isLoading) {
    return <Skeleton active paragraph={{ rows: 8 }} />
  }

  return (
    <>
      {errorMessage && (
        <Alert
          type="error"
          showIcon
          message="API尚未连接"
          description={errorMessage}
          className="status-alert"
        />
      )}
      <Paragraph type="secondary">
        当前页面展示业务一至三阶段首批可运行切片。未提供的流程图和考勤规则不会被系统猜测。
      </Paragraph>
      <Row gutter={[20, 20]}>
        {modules.map((module) => (
          <Col key={module.code} xs={24} xl={8}>
            <PhaseCard module={module} />
          </Col>
        ))}
      </Row>
    </>
  )
}

