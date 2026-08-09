import { Alert, Button, Empty, Form, Input, Modal, Select, Space, Table, Tag, Typography } from "antd"
import { useCallback, useEffect, useState } from "react"

import { lifecycleApi } from "./api"
import type { WorkflowDefinition, WorkflowInstance, WorkflowTask } from "./types"


interface WorkflowPanelProps {
  readonly token: string
  readonly canAdmin: boolean
}


export function WorkflowPanel({ token, canAdmin }: WorkflowPanelProps) {
  const [definitions, setDefinitions] = useState<readonly WorkflowDefinition[]>([])
  const [instances, setInstances] = useState<readonly WorkflowInstance[]>([])
  const [tasks, setTasks] = useState<readonly WorkflowTask[]>([])
  const [createOpen, setCreateOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [form] = Form.useForm()

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [definitionPage, instancePage, taskPage] = await Promise.all([
        lifecycleApi.definitions(token),
        lifecycleApi.instances(token),
        lifecycleApi.tasks(token),
      ])
      setDefinitions(definitionPage.items)
      setInstances(instancePage.items)
      setTasks(taskPage.items)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "流程数据加载失败")
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { void load() }, [load])

  async function createDefinition(values: Record<string, string>): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      const assignees = values.assignees.split(",").map((value) => value.trim()).filter(Boolean)
      await lifecycleApi.createDefinition(token, {
        code: values.code.toUpperCase(),
        name: values.name,
        category: values.category,
        description: values.description || null,
        nodes: [
          { code: "START", name: "开始", node_type: "start" },
          {
            code: "APPROVE",
            name: "主管理员审批",
            node_type: "approval",
            sign_mode: values.sign_mode,
            assignees: assignees.map((assignee_ref) => ({ assignee_type: "role", assignee_ref })),
          },
          { code: "END", name: "结束", node_type: "end" },
        ],
        edges: [
          { source: "START", target: "APPROVE" },
          { source: "APPROVE", target: "END" },
        ],
        change_reason: values.change_reason,
      })
      setCreateOpen(false)
      form.resetFields()
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "流程模板创建失败")
    } finally {
      setSaving(false)
    }
  }

  async function publish(item: WorkflowDefinition): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      await lifecycleApi.publishDefinition(token, item.id)
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "流程发布失败")
    } finally {
      setSaving(false)
    }
  }

  async function decide(task: WorkflowTask, decision: "approve" | "reject"): Promise<void> {
    const comment = window.prompt(decision === "approve" ? "请输入审批意见" : "请输入驳回原因")?.trim()
    if (!comment) return
    setSaving(true)
    setError(null)
    try {
      await lifecycleApi.decideTask(token, task.id, { decision, comment })
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "审批处理失败")
    } finally {
      setSaving(false)
    }
  }

  return <div className="lifecycle-panel-stack">
    {error && <Alert closable onClose={() => setError(null)} type="error" showIcon message={error} />}
    <div className="panel-heading">
      <div>
        <Typography.Title level={4}>流程模板</Typography.Title>
        <Typography.Text type="secondary">当前先提供线性审批模板；节点支持会签或或签，后续可继续扩展条件路由。</Typography.Text>
      </div>
      {canAdmin && <Button type="primary" onClick={() => setCreateOpen(true)}>新建流程模板</Button>}
    </div>
    <Table
      size="small"
      loading={loading}
      rowKey="id"
      dataSource={[...definitions]}
      locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无流程模板" /> }}
      columns={[
        { title: "代码", dataIndex: "code", width: 180 },
        { title: "名称", dataIndex: "name" },
        { title: "类别", dataIndex: "category", width: 140 },
        { title: "状态", dataIndex: "status", width: 100, render: (value) => <Tag color={value === "active" ? "success" : "gold"}>{value}</Tag> },
        { title: "版本", dataIndex: "active_version", width: 80, render: (value) => value ? `v${value}` : "—" },
        { title: "操作", width: 100, render: (_value, row) => canAdmin && row.status !== "active" ? <Button type="link" loading={saving} onClick={() => void publish(row)}>发布</Button> : null },
      ]}
    />

    <Typography.Title level={4}>审批待办</Typography.Title>
    <Table
      size="small"
      loading={loading}
      rowKey="id"
      dataSource={[...tasks]}
      columns={[
        { title: "流程实例", dataIndex: "workflow_instance_id", ellipsis: true },
        { title: "节点", dataIndex: "node_code", width: 130 },
        { title: "办理对象", width: 190, render: (_value, row) => `${row.assignee_type}: ${row.assignee_ref}` },
        { title: "签署方式", dataIndex: "sign_mode", width: 100, render: (value) => value === "all" ? "会签" : "或签" },
        { title: "状态", dataIndex: "status", width: 100, render: (value) => <Tag color={value === "pending" ? "processing" : "default"}>{value}</Tag> },
        {
          title: "操作",
          width: 150,
          render: (_value, row) => row.status === "pending" && canAdmin ? <Space>
            <Button size="small" type="primary" loading={saving} onClick={() => void decide(row, "approve")}>通过</Button>
            <Button size="small" danger loading={saving} onClick={() => void decide(row, "reject")}>驳回</Button>
          </Space> : row.decision ?? "—",
        },
      ]}
    />

    <Typography.Title level={4}>流程实例</Typography.Title>
    <Table
      size="small"
      loading={loading}
      rowKey="id"
      dataSource={[...instances]}
      columns={[
        { title: "实例编号", dataIndex: "instance_number", width: 170 },
        { title: "业务类型", dataIndex: "business_object_type", width: 130 },
        { title: "业务对象", dataIndex: "business_object_id", ellipsis: true },
        { title: "当前节点", dataIndex: "current_node_code", width: 130, render: (value) => value ?? "—" },
        { title: "状态", dataIndex: "status", width: 110, render: (value) => <Tag color={value === "completed" ? "success" : value === "rejected" ? "error" : "processing"}>{value}</Tag> },
        { title: "发起时间", dataIndex: "started_at", width: 180, render: (value) => new Date(value).toLocaleString() },
      ]}
    />

    <Modal
      title="新建线性审批模板"
      open={createOpen}
      okText="创建草稿"
      confirmLoading={saving}
      onOk={() => form.submit()}
      onCancel={() => setCreateOpen(false)}
    >
      <Form form={form} layout="vertical" requiredMark={false} onFinish={(values) => void createDefinition(values)}>
        <Form.Item label="流程代码" name="code" rules={[{ required: true }, { pattern: /^[A-Za-z0-9_]+$/, message: "仅支持字母、数字和下划线" }]}><Input placeholder="例如 TRANSFER_APPROVAL" /></Form.Item>
        <Form.Item label="流程名称" name="name" rules={[{ required: true }]}><Input /></Form.Item>
        <Form.Item label="业务类别" name="category" initialValue="hr_event" rules={[{ required: true }]}><Input /></Form.Item>
        <Form.Item label="签署方式" name="sign_mode" initialValue="any" rules={[{ required: true }]}><Select options={[{ label: "或签：任一人通过", value: "any" }, { label: "会签：全部人通过", value: "all" }]} /></Form.Item>
        <Form.Item label="办理角色" name="assignees" initialValue="HR_ADMIN" rules={[{ required: true }]}><Input placeholder="多个角色用英文逗号分隔" /></Form.Item>
        <Form.Item label="说明" name="description"><Input.TextArea rows={2} /></Form.Item>
        <Form.Item label="创建原因" name="change_reason" rules={[{ required: true }]}><Input.TextArea rows={2} /></Form.Item>
      </Form>
    </Modal>
  </div>
}
