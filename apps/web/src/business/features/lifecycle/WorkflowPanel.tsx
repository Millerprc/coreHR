import { Alert, Button, Empty, Form, Input, Modal, Radio, Select, Space, Table, Tag, Typography } from "antd"
import { useCallback, useEffect, useState } from "react"

import { lifecycleApi } from "./api"
import type { WorkflowDefinition, WorkflowInstance, WorkflowTask } from "./types"
import { buildWorkflowDefinition } from "./workflowDefinition"
import type { WorkflowTemplateValues } from "./workflowDefinition"


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
  const [routingMode, setRoutingMode] = useState<"linear" | "conditional">("linear")
  const [conditionOperator, setConditionOperator] = useState("eq")
  const [form] = Form.useForm()
  const conditionNeedsValue = conditionOperator !== "exists" && conditionOperator !== "not_exists"
  const conditionUsesList = conditionOperator === "in" || conditionOperator === "not_in"

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

  async function createDefinition(values: WorkflowTemplateValues): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      await lifecycleApi.createDefinition(token, buildWorkflowDefinition(values))
      setCreateOpen(false)
      form.resetFields()
      setRoutingMode("linear")
      setConditionOperator("eq")
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
        <Typography.Text type="secondary">支持统一审批和按业务数据自动分流；节点可选择会签或或签。</Typography.Text>
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
      title="新建审批流程模板"
      open={createOpen}
      okText="创建草稿"
      confirmLoading={saving}
      onOk={() => form.submit()}
      onCancel={() => {
        setCreateOpen(false)
        form.resetFields()
        setRoutingMode("linear")
        setConditionOperator("eq")
      }}
    >
      <Form
        form={form}
        layout="vertical"
        requiredMark={false}
        initialValues={{
          category: "hr_event",
          routing_mode: "linear",
          sign_mode: "any",
          assignees: "HR_ADMIN",
          default_assignees: "SSC_ADMIN",
          condition_operator: "eq",
          condition_value_type: "text",
        }}
        onFinish={(values) => void createDefinition(values as WorkflowTemplateValues)}
      >
        <Form.Item label="流程代码" name="code" rules={[{ required: true }, { pattern: /^[A-Za-z0-9_]+$/, message: "仅支持字母、数字和下划线" }]}><Input placeholder="例如 TRANSFER_APPROVAL" /></Form.Item>
        <Form.Item label="流程名称" name="name" rules={[{ required: true }]}><Input /></Form.Item>
        <Form.Item label="业务类别" name="category" rules={[{ required: true }]}><Input /></Form.Item>
        <Form.Item label="审批路径" name="routing_mode" rules={[{ required: true }]}>
          <Radio.Group
            optionType="button"
            buttonStyle="solid"
            onChange={(event) => setRoutingMode(event.target.value as "linear" | "conditional")}
            options={[{ label: "统一审批", value: "linear" }, { label: "按条件分流", value: "conditional" }]}
          />
        </Form.Item>
        <Form.Item label="签署方式" name="sign_mode" rules={[{ required: true }]}><Select options={[{ label: "或签：任一人通过", value: "any" }, { label: "会签：全部人通过", value: "all" }]} /></Form.Item>
        <Form.Item label={routingMode === "conditional" ? "符合条件时的办理角色" : "办理角色"} name="assignees" rules={[{ required: true }]}><Input placeholder="多个角色用英文逗号分隔" /></Form.Item>
        {routingMode === "conditional" && <>
          <Form.Item
            label="判断字段"
            name="condition_path"
            extra="读取发起流程时提交的业务数据，例如 amount、event_type 或 organization.level"
            rules={[
              { required: true },
              { pattern: /^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*){0,7}$/, message: "使用字段名或点分层级，最多8级" },
            ]}
          ><Input placeholder="例如 amount" /></Form.Item>
          <Form.Item label="判断方式" name="condition_operator" rules={[{ required: true }]}>
            <Select onChange={(value: string) => setConditionOperator(value)} options={[
              { label: "等于", value: "eq" },
              { label: "不等于", value: "ne" },
              { label: "大于", value: "gt" },
              { label: "大于等于", value: "gte" },
              { label: "小于", value: "lt" },
              { label: "小于等于", value: "lte" },
              { label: "属于列表", value: "in" },
              { label: "不属于列表", value: "not_in" },
              { label: "字段存在", value: "exists" },
              { label: "字段不存在", value: "not_exists" },
            ]} />
          </Form.Item>
          {conditionNeedsValue && <>
            <Form.Item label="比较值类型" name="condition_value_type" rules={[{ required: true }]}>
              <Select options={[{ label: "文本", value: "text" }, { label: "数字", value: "number" }, { label: "是/否", value: "boolean" }]} />
            </Form.Item>
            <Form.Item
              label="比较值"
              name="condition_value"
              extra={conditionUsesList ? "多个值使用英文逗号分隔" : undefined}
              rules={[{ required: true }]}
            ><Input placeholder={conditionUsesList ? "例如 CN, SG" : "例如 10000"} /></Form.Item>
          </>}
          <Form.Item label="不符合条件时的办理角色" name="default_assignees" rules={[{ required: true }]}><Input placeholder="多个角色用英文逗号分隔" /></Form.Item>
        </>}
        <Form.Item label="说明" name="description"><Input.TextArea rows={2} /></Form.Item>
        <Form.Item label="创建原因" name="change_reason" rules={[{ required: true }]}><Input.TextArea rows={2} /></Form.Item>
      </Form>
    </Modal>
  </div>
}
