import { Alert, Button, Empty, Form, Input, Modal, Select, Space, Table, Tag, Typography } from "antd"
import { useCallback, useEffect, useMemo, useState } from "react"

import { attendanceApi } from "./api"
import type { AttendanceEmploymentOption, AttendancePunch, ScheduleAssignment, Shift } from "./types"


interface SchedulePunchPanelProps {
  readonly token: string
  readonly canAdmin: boolean
}


const today = new Date().toISOString().slice(0, 10)


export function SchedulePunchPanel({ token, canAdmin }: SchedulePunchPanelProps) {
  const [employments, setEmployments] = useState<readonly AttendanceEmploymentOption[]>([])
  const [shifts, setShifts] = useState<readonly Shift[]>([])
  const [schedules, setSchedules] = useState<readonly ScheduleAssignment[]>([])
  const [punches, setPunches] = useState<readonly AttendancePunch[]>([])
  const [scheduleOpen, setScheduleOpen] = useState(false)
  const [punchOpen, setPunchOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [scheduleForm] = Form.useForm()
  const [punchForm] = Form.useForm()

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [employmentPage, shiftPage, schedulePage, punchPage] = await Promise.all([
        attendanceApi.employmentOptions(token),
        attendanceApi.shifts(token),
        attendanceApi.schedules(token),
        attendanceApi.punches(token),
      ])
      setEmployments(employmentPage.items)
      setShifts(shiftPage.items)
      setSchedules(schedulePage.items)
      setPunches(punchPage.items)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "排班与打卡数据加载失败")
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { void load() }, [load])

  async function createSchedule(values: Record<string, string>): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      await attendanceApi.createSchedule(token, { ...values, source: "manual" })
      scheduleForm.resetFields()
      setScheduleOpen(false)
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "排班创建失败")
    } finally {
      setSaving(false)
    }
  }

  async function cancelSchedule(item: ScheduleAssignment): Promise<void> {
    setSaving(true)
    try {
      await attendanceApi.updateSchedule(token, item.id, { status: "cancelled" })
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "排班取消失败")
    } finally {
      setSaving(false)
    }
  }

  async function createPunch(values: Record<string, string>): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      const punchedAt = `${values.punched_at}:00${values.utc_offset}`
      await attendanceApi.createPunch(token, {
        employment_id: values.employment_id,
        punched_at: punchedAt,
        punch_type: values.punch_type,
        source: "manual",
        source_record_id: `manual-${values.employment_id}-${punchedAt}-${values.punch_type}`,
        raw_payload: { entered_by: "attendance_admin" },
      })
      punchForm.resetFields()
      setPunchOpen(false)
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "打卡记录创建失败")
    } finally {
      setSaving(false)
    }
  }

  const employmentOptions = useMemo(() => employments.map((item) => ({ label: `${item.display_name} (${item.employee_number ?? "无工号"}) · ${item.employee_type_code}`, value: item.id })), [employments])
  const shiftOptions = useMemo(() => shifts.filter((item) => item.status === "active").map((item) => ({ label: `${item.name} ${item.start_time.slice(0, 5)}-${item.end_time.slice(0, 5)}`, value: item.id })), [shifts])
  const employmentName = (id: string) => employments.find((item) => item.id === id)?.display_name ?? id

  return <div className="lifecycle-panel-stack">
    {error && <Alert closable onClose={() => setError(null)} type="error" showIcon message={error} />}
    <div className="panel-heading"><div><Typography.Title level={4}>排班</Typography.Title><Typography.Text type="secondary">每个劳动关系每天最多一个有效班次。</Typography.Text></div>{canAdmin && <Button type="primary" onClick={() => setScheduleOpen(true)}>新增排班</Button>}</div>
    <Table size="small" loading={loading} rowKey="id" dataSource={[...schedules]} locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无排班" /> }} columns={[
      { title: "员工", dataIndex: "employment_id", render: (value) => employmentName(value) },
      { title: "日期", dataIndex: "work_date", width: 110 },
      { title: "班次", dataIndex: "shift_id", render: (value) => shifts.find((item) => item.id === value)?.name ?? value },
      { title: "来源", dataIndex: "source", width: 100 },
      { title: "状态", dataIndex: "status", width: 100, render: (value) => <Tag color={value === "active" ? "success" : "default"}>{value}</Tag> },
      { title: "操作", width: 100, render: (_value, row) => canAdmin && row.status === "active" ? <Button type="link" danger loading={saving} onClick={() => void cancelSchedule(row)}>取消</Button> : null },
    ]} />

    <div className="panel-heading"><div><Typography.Title level={4}>打卡记录</Typography.Title><Typography.Text type="secondary">来源记录号保证幂等；手工补录必须携带明确 UTC 偏移。</Typography.Text></div>{canAdmin && <Button onClick={() => setPunchOpen(true)}>手工补录</Button>}</div>
    <Table size="small" loading={loading} rowKey="id" dataSource={[...punches]} columns={[
      { title: "员工", dataIndex: "employment_id", render: (value) => employmentName(value) },
      { title: "打卡时间", dataIndex: "punched_at", width: 210, render: (value) => new Date(value).toLocaleString() },
      { title: "类型", dataIndex: "punch_type", width: 90, render: (value) => value === "in" ? "上班" : value === "out" ? "下班" : "未指定" },
      { title: "来源", dataIndex: "source", width: 100 },
      { title: "来源记录号", dataIndex: "source_record_id", ellipsis: true },
    ]} />

    <Modal title="新增排班" open={scheduleOpen} okText="保存" confirmLoading={saving} onOk={() => scheduleForm.submit()} onCancel={() => setScheduleOpen(false)}>
      <Form form={scheduleForm} layout="vertical" requiredMark={false} onFinish={(values) => void createSchedule(values)}>
        <Form.Item label="员工劳动关系" name="employment_id" rules={[{ required: true }]}><Select showSearch optionFilterProp="label" options={employmentOptions} /></Form.Item>
        <Form.Item label="日期" name="work_date" initialValue={today} rules={[{ required: true }]}><Input type="date" /></Form.Item>
        <Form.Item label="班次" name="shift_id" rules={[{ required: true }]}><Select options={shiftOptions} /></Form.Item>
      </Form>
    </Modal>
    <Modal title="手工补录打卡" open={punchOpen} okText="保存" confirmLoading={saving} onOk={() => punchForm.submit()} onCancel={() => setPunchOpen(false)}>
      <Form form={punchForm} layout="vertical" requiredMark={false} onFinish={(values) => void createPunch(values)}>
        <Form.Item label="员工劳动关系" name="employment_id" rules={[{ required: true }]}><Select showSearch optionFilterProp="label" options={employmentOptions} /></Form.Item>
        <Form.Item label="本地时间" name="punched_at" rules={[{ required: true }]}><Input type="datetime-local" /></Form.Item>
        <Space size="large"><Form.Item label="UTC 偏移" name="utc_offset" initialValue="+08:00" rules={[{ required: true }]}><Select style={{ width: 150 }} options={[{ label: "UTC+08:00", value: "+08:00" }, { label: "UTC+00:00", value: "+00:00" }]} /></Form.Item><Form.Item label="打卡类型" name="punch_type" rules={[{ required: true }]}><Select style={{ width: 150 }} options={[{ label: "上班", value: "in" }, { label: "下班", value: "out" }]} /></Form.Item></Space>
      </Form>
    </Modal>
  </div>
}
