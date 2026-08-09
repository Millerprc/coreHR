import { Alert, Button, Descriptions, Drawer, Empty, Form, Input, Modal, Select, Space, Table, Tag, Typography } from "antd"
import { useCallback, useEffect, useMemo, useState } from "react"

import { workforceApi } from "../workforce/api"
import type { Employment, EmploymentAssignment, Job, OrganizationOption, Person } from "../workforce/types"
import { lifecycleApi } from "./api"
import type { HrEvent, WorkflowDefinition } from "./types"


interface HrEventPanelProps {
  readonly token: string
  readonly canAdmin: boolean
}


const today = new Date().toISOString().slice(0, 10)
const assignmentEventTypes = ["TRANSFER", "CONCURRENT_ASSIGNMENT", "SECONDMENT"]


function eventColor(status: string): string {
  if (status === "completed") return "success"
  if (status === "failed" || status === "rejected") return "error"
  if (status === "pending_approval") return "processing"
  return "gold"
}


export function HrEventPanel({ token, canAdmin }: HrEventPanelProps) {
  const [events, setEvents] = useState<readonly HrEvent[]>([])
  const [persons, setPersons] = useState<readonly Person[]>([])
  const [organizations, setOrganizations] = useState<readonly OrganizationOption[]>([])
  const [jobs, setJobs] = useState<readonly Job[]>([])
  const [definitions, setDefinitions] = useState<readonly WorkflowDefinition[]>([])
  const [employments, setEmployments] = useState<readonly Employment[]>([])
  const [assignments, setAssignments] = useState<readonly EmploymentAssignment[]>([])
  const [detail, setDetail] = useState<HrEvent | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [approvalEvent, setApprovalEvent] = useState<HrEvent | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [form] = Form.useForm()
  const [approvalForm] = Form.useForm()
  const eventType = Form.useWatch("event_type", form)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [eventPage, personPage, organizationItems, jobPage, definitionPage] = await Promise.all([
        lifecycleApi.hrEvents(token),
        workforceApi.persons(token),
        workforceApi.organizations(token),
        workforceApi.jobs(token),
        lifecycleApi.definitions(token),
      ])
      setEvents(eventPage.items)
      setPersons(personPage.items)
      setOrganizations(organizationItems)
      setJobs(jobPage.items)
      setDefinitions(definitionPage.items)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "人事事件加载失败")
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { void load() }, [load])

  async function selectPerson(personId: string): Promise<void> {
    form.setFieldsValue({ employment_id: undefined, assignment_id: undefined })
    try {
      const archive = await workforceApi.personArchive(token, personId)
      setEmployments(archive.employments)
      setAssignments(archive.assignments)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "人员关系加载失败")
    }
  }

  function plannedPayload(values: Record<string, string>): Record<string, unknown> {
    if (assignmentEventTypes.includes(values.event_type)) {
      return {
        organization_id: values.organization_id,
        job_id: values.job_id,
        ...(values.effective_to ? { effective_to: values.effective_to } : {}),
      }
    }
    if (values.event_type === "END_ASSIGNMENT") return { assignment_id: values.assignment_id }
    if (values.event_type === "TERMINATION") return { end_reason_code: values.end_reason_code || null }
    if (values.event_type === "EMPLOYMENT_CORRECTION") return { [values.correction_field]: values.correction_value }
    return {}
  }

  async function createEvent(values: Record<string, string>): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      await lifecycleApi.createHrEvent(token, {
        event_type: values.event_type,
        object_type: "employment",
        object_id: values.employment_id,
        effective_date: values.effective_date,
        execution_mode: values.execution_mode,
        reason: values.reason,
        planned_payload: plannedPayload(values),
      })
      form.resetFields()
      setEmployments([])
      setAssignments([])
      setCreateOpen(false)
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "人事事件创建失败")
    } finally {
      setSaving(false)
    }
  }

  async function startApproval(values: { workflow_definition_id: string }): Promise<void> {
    if (!approvalEvent) return
    setSaving(true)
    setError(null)
    try {
      await lifecycleApi.startWorkflow(token, {
        workflow_definition_id: values.workflow_definition_id,
        business_object_type: "hr_event",
        business_object_id: approvalEvent.id,
        context: { event_type: approvalEvent.event_type, event_number: approvalEvent.event_number },
      })
      setApprovalEvent(null)
      approvalForm.resetFields()
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "审批流程发起失败")
    } finally {
      setSaving(false)
    }
  }

  async function processDue(): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      await lifecycleApi.processHrEvents(token, today)
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "到期事件处理失败")
    } finally {
      setSaving(false)
    }
  }

  async function rollback(event: HrEvent): Promise<void> {
    const reason = window.prompt("请输入回退原因")?.trim()
    if (!reason) return
    setSaving(true)
    setError(null)
    try {
      await lifecycleApi.rollbackHrEvent(token, event.id, {
        execution_mode: "direct",
        effective_date: today,
        reason,
      })
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "人事事件回退失败")
    } finally {
      setSaving(false)
    }
  }

  const personOptions = useMemo(() => persons.map((item) => ({ label: `${item.display_name} (${item.employee_number ?? "无工号"})`, value: item.id })), [persons])
  const employmentOptions = useMemo(() => employments.map((item) => ({ label: `${item.employee_type_code} · ${item.status} · ${item.planned_start_date}`, value: item.id })), [employments])
  const assignmentOptions = useMemo(() => assignments.map((item) => ({ label: `${item.relation_type} · ${item.effective_from}`, value: item.id })), [assignments])
  const organizationOptions = useMemo(() => organizations.map((item) => ({ label: `${item.name} (${item.code})`, value: item.id })), [organizations])
  const jobOptions = useMemo(() => jobs.map((item) => ({ label: `${item.name} (${item.code})`, value: item.id })), [jobs])
  const definitionOptions = useMemo(() => definitions.filter((item) => item.status === "active").map((item) => ({ label: `${item.name} (v${item.active_version})`, value: item.id })), [definitions])

  return <div className="lifecycle-panel-stack">
    {error && <Alert closable onClose={() => setError(null)} type="error" showIcon message={error} />}
    <div className="panel-heading">
      <div>
        <Typography.Title level={4}>人事事件</Typography.Title>
        <Typography.Text type="secondary">入职、转正、调动、兼岗、借调、离职和更正统一按事件留痕；未来事件到期后生效。</Typography.Text>
      </div>
      {canAdmin && <Space>
        <Button loading={saving} onClick={() => void processDue()}>处理到期事件</Button>
        <Button type="primary" onClick={() => setCreateOpen(true)}>新建人事事件</Button>
      </Space>}
    </div>
    <Table
      size="small"
      loading={loading}
      rowKey="id"
      dataSource={[...events]}
      locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无人事事件" /> }}
      columns={[
        { title: "事件编号", dataIndex: "event_number", width: 170 },
        { title: "类型", dataIndex: "event_type", width: 190 },
        { title: "生效日期", dataIndex: "effective_date", width: 110 },
        { title: "原因", dataIndex: "reason", ellipsis: true },
        { title: "状态", dataIndex: "status", width: 140, render: (value) => <Tag color={eventColor(value)}>{value}</Tag> },
        { title: "尝试", dataIndex: "attempts", width: 70 },
        {
          title: "操作",
          width: 250,
          render: (_value, row) => <Space wrap>
            <Button type="link" onClick={() => setDetail(row)}>详情</Button>
            {canAdmin && row.status === "pending_approval" && !row.workflow_instance_id && <Button type="link" onClick={() => setApprovalEvent(row)}>发起审批</Button>}
            {canAdmin && row.status === "completed" && !row.event_type.startsWith("ROLLBACK_") && <Button type="link" danger loading={saving} onClick={() => void rollback(row)}>回退</Button>}
          </Space>,
        },
      ]}
    />

    <Modal title="新建人事事件" width={680} open={createOpen} okText="创建" confirmLoading={saving} onOk={() => form.submit()} onCancel={() => setCreateOpen(false)}>
      <Form form={form} layout="vertical" requiredMark={false} onFinish={(values) => void createEvent(values)}>
        <Space align="start" size="large" wrap>
          <Form.Item label="人员" name="person_id" rules={[{ required: true }]}><Select style={{ width: 270 }} showSearch optionFilterProp="label" options={personOptions} onChange={(value) => void selectPerson(value)} /></Form.Item>
          <Form.Item label="劳动关系" name="employment_id" rules={[{ required: true }]}><Select style={{ width: 270 }} options={employmentOptions} /></Form.Item>
        </Space>
        <Space align="start" size="large" wrap>
          <Form.Item label="事件类型" name="event_type" rules={[{ required: true }]}><Select style={{ width: 270 }} options={[
            { label: "入职", value: "ONBOARDING" },
            { label: "转正", value: "CONFIRMATION" },
            { label: "调动", value: "TRANSFER" },
            { label: "兼岗", value: "CONCURRENT_ASSIGNMENT" },
            { label: "借调", value: "SECONDMENT" },
            { label: "结束组织关系", value: "END_ASSIGNMENT" },
            { label: "离职", value: "TERMINATION" },
            { label: "撤回入职", value: "WITHDRAWAL" },
            { label: "劳动关系更正", value: "EMPLOYMENT_CORRECTION" },
          ]} /></Form.Item>
          <Form.Item label="生效日期" name="effective_date" initialValue={today} rules={[{ required: true }]}><Input style={{ width: 270 }} type="date" /></Form.Item>
        </Space>
        {assignmentEventTypes.includes(eventType) && <Space align="start" size="large" wrap>
          <Form.Item label="目标组织" name="organization_id" rules={[{ required: true }]}><Select style={{ width: 270 }} showSearch optionFilterProp="label" options={organizationOptions} /></Form.Item>
          <Form.Item label="目标职务" name="job_id" rules={[{ required: true }]}><Select style={{ width: 270 }} showSearch optionFilterProp="label" options={jobOptions} /></Form.Item>
        </Space>}
        {eventType === "END_ASSIGNMENT" && <Form.Item label="要结束的组织关系" name="assignment_id" rules={[{ required: true }]}><Select options={assignmentOptions} /></Form.Item>}
        {eventType === "TERMINATION" && <Form.Item label="离职原因代码" name="end_reason_code"><Input /></Form.Item>}
        {eventType === "EMPLOYMENT_CORRECTION" && <Space align="start" size="large">
          <Form.Item label="更正字段" name="correction_field" rules={[{ required: true }]}><Select style={{ width: 270 }} options={[
            { label: "员工类型", value: "employee_type_code" },
            { label: "计划入职日期", value: "planned_start_date" },
            { label: "实际入职日期", value: "actual_start_date" },
            { label: "试用期结束日期", value: "probation_end_date" },
          ]} /></Form.Item>
          <Form.Item label="更正值" name="correction_value" rules={[{ required: true }]}><Input style={{ width: 270 }} /></Form.Item>
        </Space>}
        <Form.Item label="执行方式" name="execution_mode" initialValue="approval" rules={[{ required: true }]}><Select options={[{ label: "审批后生效", value: "approval" }, { label: "直接生效", value: "direct" }]} /></Form.Item>
        <Form.Item label="变更原因" name="reason" rules={[{ required: true }]}><Input.TextArea rows={3} /></Form.Item>
      </Form>
    </Modal>

    <Modal title={`发起审批 · ${approvalEvent?.event_number ?? ""}`} open={Boolean(approvalEvent)} okText="发起" confirmLoading={saving} onOk={() => approvalForm.submit()} onCancel={() => setApprovalEvent(null)}>
      <Form form={approvalForm} layout="vertical" onFinish={(values) => void startApproval(values)}>
        <Form.Item label="流程模板" name="workflow_definition_id" rules={[{ required: true }]}><Select options={definitionOptions} placeholder="请选择已发布流程" /></Form.Item>
      </Form>
    </Modal>

    <Drawer size="large" title={detail?.event_number ?? "事件详情"} open={Boolean(detail)} onClose={() => setDetail(null)}>
      {detail && <>
        <Descriptions bordered column={2}>
          <Descriptions.Item label="类型">{detail.event_type}</Descriptions.Item>
          <Descriptions.Item label="状态"><Tag color={eventColor(detail.status)}>{detail.status}</Tag></Descriptions.Item>
          <Descriptions.Item label="生效日期">{detail.effective_date}</Descriptions.Item>
          <Descriptions.Item label="版本">v{detail.version}</Descriptions.Item>
          <Descriptions.Item label="流程实例" span={2}>{detail.workflow_instance_id ?? "—"}</Descriptions.Item>
          <Descriptions.Item label="原因" span={2}>{detail.reason}</Descriptions.Item>
          <Descriptions.Item label="最后错误" span={2}>{detail.last_error ?? "—"}</Descriptions.Item>
        </Descriptions>
        <Typography.Title level={5}>计划数据</Typography.Title>
        <pre className="payload-preview">{JSON.stringify(detail.planned_payload, null, 2)}</pre>
        <Typography.Title level={5}>实际结果</Typography.Title>
        <pre className="payload-preview">{JSON.stringify(detail.actual_payload, null, 2)}</pre>
      </>}
    </Drawer>
  </div>
}
