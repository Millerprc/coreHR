import { Alert, Button, Empty, Form, Input, InputNumber, Modal, Select, Space, Table, Tag, Typography } from "antd"
import { useCallback, useEffect, useMemo, useState } from "react"

import { attendanceApi } from "./api"
import type { AttendanceEmploymentOption, LeaveRequest, LeaveType } from "./types"


interface LeavePanelProps {
  readonly token: string
  readonly canAdmin: boolean
}


const today = new Date().toISOString().slice(0, 10)


export function LeavePanel({ token, canAdmin }: LeavePanelProps) {
  const [employments, setEmployments] = useState<readonly AttendanceEmploymentOption[]>([])
  const [leaveTypes, setLeaveTypes] = useState<readonly LeaveType[]>([])
  const [requests, setRequests] = useState<readonly LeaveRequest[]>([])
  const [typeOpen, setTypeOpen] = useState(false)
  const [balanceRuleTarget, setBalanceRuleTarget] = useState<LeaveType | null>(null)
  const [requestOpen, setRequestOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [typeForm] = Form.useForm()
  const [balanceRuleForm] = Form.useForm<{ balance_mode: "none" | "tracked" | "enforced" }>()
  const [requestForm] = Form.useForm()

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [employmentPage, typePage, requestPage] = await Promise.all([
        attendanceApi.employmentOptions(token),
        attendanceApi.leaveTypes(token),
        attendanceApi.leaveRequests(token),
      ])
      setEmployments(employmentPage.items)
      setLeaveTypes(typePage.items)
      setRequests(requestPage.items)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "假期数据加载失败")
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { void load() }, [load])

  async function createType(values: Record<string, unknown>): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      const { balance_mode, ...fields } = values
      await attendanceApi.createLeaveType(token, {
        ...fields,
        code: String(values.code).toUpperCase(),
        rules: { balance_mode: balance_mode ?? "none" },
      })
      typeForm.resetFields()
      setTypeOpen(false)
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "假期类型创建失败")
    } finally {
      setSaving(false)
    }
  }

  async function createRequest(values: Record<string, unknown>): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      await attendanceApi.createLeaveRequest(token, values)
      requestForm.resetFields()
      setRequestOpen(false)
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "请假记录创建失败")
    } finally {
      setSaving(false)
    }
  }

  function openBalanceRule(item: LeaveType): void {
    balanceRuleForm.setFieldsValue({ balance_mode: (item.rules.balance_mode as "none" | "tracked" | "enforced" | undefined) ?? "none" })
    setBalanceRuleTarget(item)
  }

  async function updateBalanceRule(values: { balance_mode: "none" | "tracked" | "enforced" }): Promise<void> {
    if (!balanceRuleTarget) return
    setSaving(true)
    setError(null)
    try {
      await attendanceApi.updateLeaveType(token, balanceRuleTarget.id, {
        rules: { ...balanceRuleTarget.rules, balance_mode: values.balance_mode },
      })
      setBalanceRuleTarget(null)
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "余额规则更新失败")
    } finally {
      setSaving(false)
    }
  }

  async function changeStatus(item: LeaveRequest, status: "approved" | "rejected" | "cancelled"): Promise<void> {
    const reason = window.prompt(status === "approved" ? "请输入批准意见" : "请输入处理原因")?.trim()
    if (!reason) return
    setSaving(true)
    try {
      await attendanceApi.updateLeaveRequest(token, item.id, { status, change_reason: reason })
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "请假状态变更失败")
    } finally {
      setSaving(false)
    }
  }

  async function requestCancellation(item: LeaveRequest): Promise<void> {
    const reason = window.prompt("请输入销假原因")?.trim()
    if (!reason) return
    setSaving(true)
    try {
      await attendanceApi.cancelLeaveRequest(token, item.id, { reason })
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "销假申请创建失败")
    } finally {
      setSaving(false)
    }
  }

  const employmentOptions = useMemo(() => employments.map((item) => ({ label: `${item.display_name} (${item.employee_number ?? "无工号"})`, value: item.id })), [employments])
  const typeOptions = useMemo(() => leaveTypes.filter((item) => item.status === "active").map((item) => ({ label: `${item.name} (${item.unit === "day" ? "天" : "小时"})`, value: item.id })), [leaveTypes])
  const employmentName = (id: string) => employments.find((item) => item.id === id)?.display_name ?? id

  return <div className="lifecycle-panel-stack">
    {error && <Alert closable onClose={() => setError(null)} type="error" showIcon message={error} />}
    <div className="panel-heading"><div><Typography.Title level={4}>假期规则</Typography.Title><Typography.Text type="secondary">每类假期可选择不跟踪余额、允许负余额或余额不足时阻止批准。</Typography.Text></div>{canAdmin && <Button onClick={() => setTypeOpen(true)}>新建假期类型</Button>}</div>
    <Table size="small" loading={loading} rowKey="id" dataSource={[...leaveTypes]} locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无假期类型" /> }} columns={[
      { title: "代码", dataIndex: "code", width: 160 },
      { title: "名称", dataIndex: "name" },
      { title: "单位", dataIndex: "unit", width: 100, render: (value) => value === "day" ? "天" : "小时" },
      { title: "余额规则", width: 180, render: (_value, row) => ({ none: "不跟踪", tracked: "记录，可为负", enforced: "余额不足不批准" }[String(row.rules.balance_mode ?? "none")] ?? "不跟踪") },
      { title: "状态", dataIndex: "status", width: 100, render: (value) => <Tag color={value === "active" ? "success" : "default"}>{value}</Tag> },
      { title: "操作", width: 110, render: (_value, row) => canAdmin ? <Button type="link" onClick={() => openBalanceRule(row)}>设置余额规则</Button> : null },
    ]} />

    <div className="panel-heading"><div><Typography.Title level={4}>请假与销假</Typography.Title><Typography.Text type="secondary">主管理员可直接批准；销假以关联记录呈现并保留原申请。</Typography.Text></div>{canAdmin && <Button type="primary" onClick={() => setRequestOpen(true)}>登记请假</Button>}</div>
    <Table size="small" loading={loading} rowKey="id" dataSource={[...requests]} columns={[
      { title: "单号", dataIndex: "request_number", width: 170 },
      { title: "员工", dataIndex: "employment_id", render: (value) => employmentName(value) },
      { title: "假期类型", dataIndex: "leave_type_id", render: (value) => leaveTypes.find((item) => item.id === value)?.name ?? value },
      { title: "期间", width: 220, render: (_value, row) => `${row.start_date} 至 ${row.end_date}` },
      { title: "数量", dataIndex: "amount", width: 90 },
      { title: "类型", width: 90, render: (_value, row) => row.cancellation_of_id ? "销假" : "请假" },
      { title: "状态", dataIndex: "status", width: 140, render: (value) => <Tag color={value === "approved" ? "success" : value === "rejected" || value === "cancelled" ? "default" : "processing"}>{value}</Tag> },
      {
        title: "操作",
        width: 240,
        render: (_value, row) => canAdmin ? <Space wrap>
          {["draft", "pending_approval", "draft_cancellation"].includes(row.status) && <><Button size="small" type="primary" loading={saving} onClick={() => void changeStatus(row, "approved")}>批准</Button><Button size="small" danger loading={saving} onClick={() => void changeStatus(row, "rejected")}>拒绝</Button></>}
          {row.status === "approved" && !row.cancellation_of_id && <Button size="small" loading={saving} onClick={() => void requestCancellation(row)}>发起销假</Button>}
        </Space> : null,
      },
    ]} />

    <Modal title="新建假期类型" open={typeOpen} okText="保存" confirmLoading={saving} onOk={() => typeForm.submit()} onCancel={() => setTypeOpen(false)}>
      <Form form={typeForm} layout="vertical" requiredMark={false} onFinish={(values) => void createType(values)}>
        <Form.Item label="类型代码" name="code" rules={[{ required: true }]}><Input /></Form.Item>
        <Form.Item label="类型名称" name="name" rules={[{ required: true }]}><Input /></Form.Item>
        <Form.Item label="计量单位" name="unit" initialValue="day" rules={[{ required: true }]}><Select options={[{ label: "天", value: "day" }, { label: "小时", value: "hour" }]} /></Form.Item>
        <Form.Item label="余额规则" name="balance_mode" initialValue="none" rules={[{ required: true }]}>
          <Select options={[
            { label: "不跟踪余额", value: "none" },
            { label: "记录余额，允许为负", value: "tracked" },
            { label: "余额不足时不允许批准", value: "enforced" },
          ]} />
        </Form.Item>
      </Form>
    </Modal>
    <Modal
      title={balanceRuleTarget ? `设置 ${balanceRuleTarget.name} 的余额规则` : "设置余额规则"}
      open={Boolean(balanceRuleTarget)}
      okText="保存"
      confirmLoading={saving}
      onOk={() => balanceRuleForm.submit()}
      onCancel={() => setBalanceRuleTarget(null)}
    >
      <Alert type="info" showIcon title="规则只影响后续批准和入账，历史流水不会重算" />
      <Form form={balanceRuleForm} layout="vertical" requiredMark={false} onFinish={(values) => void updateBalanceRule(values)}>
        <Form.Item label="余额规则" name="balance_mode" rules={[{ required: true }]}>
          <Select options={[
            { label: "不跟踪余额", value: "none" },
            { label: "记录余额，允许为负", value: "tracked" },
            { label: "余额不足时不允许批准", value: "enforced" },
          ]} />
        </Form.Item>
      </Form>
    </Modal>
    <Modal title="登记请假" open={requestOpen} okText="保存草稿" confirmLoading={saving} onOk={() => requestForm.submit()} onCancel={() => setRequestOpen(false)}>
      <Form form={requestForm} layout="vertical" requiredMark={false} onFinish={(values) => void createRequest(values)}>
        <Form.Item label="员工劳动关系" name="employment_id" rules={[{ required: true }]}><Select showSearch optionFilterProp="label" options={employmentOptions} /></Form.Item>
        <Form.Item label="假期类型" name="leave_type_id" rules={[{ required: true }]}><Select options={typeOptions} /></Form.Item>
        <Space size="large"><Form.Item label="开始日期" name="start_date" initialValue={today} rules={[{ required: true }]}><Input type="date" /></Form.Item><Form.Item label="结束日期" name="end_date" initialValue={today} rules={[{ required: true }]}><Input type="date" /></Form.Item></Space>
        <Form.Item label="请假数量" name="amount" initialValue={1} rules={[{ required: true }]}><InputNumber min={0.01} precision={2} /></Form.Item>
        <Form.Item label="请假原因" name="reason" rules={[{ required: true }]}><Input.TextArea rows={3} /></Form.Item>
      </Form>
    </Modal>
  </div>
}
