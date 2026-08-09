import { Alert, Button, Descriptions, Drawer, Form, Input, Modal, Select, Space, Table, Tag, Typography } from "antd"
import { useCallback, useEffect, useMemo, useState } from "react"

import { attendanceApi } from "./api"
import type { AttendanceDailyResult, AttendanceEmploymentOption, AttendanceMonthlyResult } from "./types"


interface ReportPanelProps {
  readonly token: string
  readonly canAdmin: boolean
}


const today = new Date().toISOString().slice(0, 10)
const currentMonth = `${today.slice(0, 7)}-01`


function statusColor(status: string): string {
  if (status === "normal" || status === "calculated") return "success"
  if (status === "leave" || status === "leave_with_punch") return "processing"
  if (status === "absent" || status === "exception") return "error"
  return "default"
}


export function ReportPanel({ token, canAdmin }: ReportPanelProps) {
  const [employments, setEmployments] = useState<readonly AttendanceEmploymentOption[]>([])
  const [dailyResults, setDailyResults] = useState<readonly AttendanceDailyResult[]>([])
  const [monthlyResults, setMonthlyResults] = useState<readonly AttendanceMonthlyResult[]>([])
  const [detail, setDetail] = useState<AttendanceDailyResult | null>(null)
  const [dailyOpen, setDailyOpen] = useState(false)
  const [monthlyOpen, setMonthlyOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dailyForm] = Form.useForm()
  const [monthlyForm] = Form.useForm()

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [employmentPage, dailyPage, monthlyPage] = await Promise.all([
        attendanceApi.employmentOptions(token),
        attendanceApi.dailyResults(token),
        attendanceApi.monthlyResults(token),
      ])
      setEmployments(employmentPage.items)
      setDailyResults(dailyPage.items)
      setMonthlyResults(monthlyPage.items)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "考勤报表加载失败")
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { void load() }, [load])

  async function calculateDaily(values: Record<string, string>): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      await attendanceApi.calculateDaily(token, values)
      dailyForm.resetFields()
      setDailyOpen(false)
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "日报计算失败")
    } finally {
      setSaving(false)
    }
  }

  async function calculateMonthly(values: Record<string, string>): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      await attendanceApi.calculateMonthly(token, { ...values, period_month: `${values.period_month}-01` })
      monthlyForm.resetFields()
      setMonthlyOpen(false)
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "月报计算失败")
    } finally {
      setSaving(false)
    }
  }

  const employmentOptions = useMemo(() => employments.map((item) => ({ label: `${item.display_name} (${item.employee_number ?? "无工号"})`, value: item.id })), [employments])
  const employmentName = (id: string) => employments.find((item) => item.id === id)?.display_name ?? id

  return <div className="lifecycle-panel-stack">
    {error && <Alert closable onClose={() => setError(null)} type="error" showIcon message={error} />}
    <div className="panel-heading"><div><Typography.Title level={4}>考勤日报</Typography.Title><Typography.Text type="secondary">每次重算生成新版本，旧版本保留但不再作为当前结果。</Typography.Text></div>{canAdmin && <Button type="primary" onClick={() => setDailyOpen(true)}>计算日报</Button>}</div>
    <Table size="small" loading={loading} rowKey="id" dataSource={[...dailyResults]} columns={[
      { title: "员工", dataIndex: "employment_id", render: (value) => employmentName(value) },
      { title: "日期", dataIndex: "work_date", width: 110 },
      { title: "状态", dataIndex: "status", width: 130, render: (value) => <Tag color={statusColor(value)}>{value}</Tag> },
      { title: "应出勤", dataIndex: "scheduled_minutes", width: 90, render: (value) => `${value}分` },
      { title: "实出勤", dataIndex: "worked_minutes", width: 90, render: (value) => `${value}分` },
      { title: "迟到", dataIndex: "late_minutes", width: 80, render: (value) => `${value}分` },
      { title: "早退", dataIndex: "early_leave_minutes", width: 80, render: (value) => `${value}分` },
      { title: "异常", dataIndex: "exception_codes", render: (values: readonly string[]) => values.length ? <Space wrap>{values.map((value) => <Tag color="error" key={value}>{value}</Tag>)}</Space> : "—" },
      { title: "版本", dataIndex: "version", width: 70, render: (value) => `v${value}` },
      { title: "操作", width: 80, render: (_value, row) => <Button type="link" onClick={() => setDetail(row)}>证据</Button> },
    ]} />

    <div className="panel-heading"><div><Typography.Title level={4}>考勤月报</Typography.Title><Typography.Text type="secondary">月报由当前日报聚合；缺失日报的有效排班会先自动计算。</Typography.Text></div>{canAdmin && <Button onClick={() => setMonthlyOpen(true)}>计算月报</Button>}</div>
    <Table size="small" loading={loading} rowKey="id" dataSource={[...monthlyResults]} columns={[
      { title: "员工", dataIndex: "employment_id", render: (value) => employmentName(value) },
      { title: "月份", dataIndex: "period_month", width: 110, render: (value) => value.slice(0, 7) },
      { title: "应出勤天", dataIndex: "scheduled_days", width: 100 },
      { title: "实出勤天", dataIndex: "worked_days", width: 100 },
      { title: "请假天", dataIndex: "leave_days", width: 90 },
      { title: "缺勤天", dataIndex: "absent_days", width: 90 },
      { title: "迟到分钟", dataIndex: "late_minutes", width: 100 },
      { title: "早退分钟", dataIndex: "early_leave_minutes", width: 100 },
      { title: "版本", dataIndex: "version", width: 70, render: (value) => `v${value}` },
      { title: "状态", dataIndex: "status", width: 110, render: (value) => <Tag color={statusColor(value)}>{value}</Tag> },
    ]} />

    <Modal title="计算考勤日报" open={dailyOpen} okText="计算" confirmLoading={saving} onOk={() => dailyForm.submit()} onCancel={() => setDailyOpen(false)}>
      <Form form={dailyForm} layout="vertical" requiredMark={false} onFinish={(values) => void calculateDaily(values)}>
        <Form.Item label="员工劳动关系" name="employment_id" rules={[{ required: true }]}><Select showSearch optionFilterProp="label" options={employmentOptions} /></Form.Item>
        <Form.Item label="工作日期" name="work_date" initialValue={today} rules={[{ required: true }]}><Input type="date" /></Form.Item>
        <Form.Item label="计算原因" name="reason" initialValue="主管理员手工计算" rules={[{ required: true }]}><Input /></Form.Item>
      </Form>
    </Modal>
    <Modal title="计算考勤月报" open={monthlyOpen} okText="计算" confirmLoading={saving} onOk={() => monthlyForm.submit()} onCancel={() => setMonthlyOpen(false)}>
      <Form form={monthlyForm} layout="vertical" requiredMark={false} onFinish={(values) => void calculateMonthly(values)}>
        <Form.Item label="员工劳动关系" name="employment_id" rules={[{ required: true }]}><Select showSearch optionFilterProp="label" options={employmentOptions} /></Form.Item>
        <Form.Item label="月份" name="period_month" initialValue={currentMonth.slice(0, 7)} rules={[{ required: true }]}><Input type="month" /></Form.Item>
        <Form.Item label="计算原因" name="reason" initialValue="主管理员手工汇总" rules={[{ required: true }]}><Input /></Form.Item>
      </Form>
    </Modal>
    <Drawer size="large" title={detail ? `${employmentName(detail.employment_id)} · ${detail.work_date}` : "日报证据"} open={Boolean(detail)} onClose={() => setDetail(null)}>
      {detail && <><Descriptions bordered column={2}><Descriptions.Item label="状态">{detail.status}</Descriptions.Item><Descriptions.Item label="版本">v{detail.version}</Descriptions.Item><Descriptions.Item label="应出勤">{detail.scheduled_minutes} 分钟</Descriptions.Item><Descriptions.Item label="实出勤">{detail.worked_minutes} 分钟</Descriptions.Item></Descriptions><Typography.Title level={5}>计算证据</Typography.Title><pre className="payload-preview">{JSON.stringify(detail.evidence, null, 2)}</pre></>}
    </Drawer>
  </div>
}
