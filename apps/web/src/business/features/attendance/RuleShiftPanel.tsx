import { Alert, Button, Empty, Form, Input, InputNumber, Modal, Select, Space, Table, Tag, Typography } from "antd"
import { useCallback, useEffect, useMemo, useState } from "react"

import { attendanceApi } from "./api"
import type { AttendanceRuleSet, Shift } from "./types"


interface RuleShiftPanelProps {
  readonly token: string
  readonly canAdmin: boolean
}


const today = new Date().toISOString().slice(0, 10)


export function RuleShiftPanel({ token, canAdmin }: RuleShiftPanelProps) {
  const [ruleSets, setRuleSets] = useState<readonly AttendanceRuleSet[]>([])
  const [shifts, setShifts] = useState<readonly Shift[]>([])
  const [ruleOpen, setRuleOpen] = useState(false)
  const [shiftOpen, setShiftOpen] = useState(false)
  const [versionSource, setVersionSource] = useState<AttendanceRuleSet | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [ruleForm] = Form.useForm()
  const [shiftForm] = Form.useForm()
  const [versionForm] = Form.useForm()

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [rulePage, shiftPage] = await Promise.all([
        attendanceApi.ruleSets(token),
        attendanceApi.shifts(token),
      ])
      setRuleSets(rulePage.items)
      setShifts(shiftPage.items)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "考勤规则加载失败")
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { void load() }, [load])

  function rules(values: Record<string, unknown>): Record<string, unknown> {
    return {
      late_grace_minutes: Number(values.late_grace_minutes ?? 0),
      early_leave_grace_minutes: Number(values.early_leave_grace_minutes ?? 0),
    }
  }

  async function createRule(values: Record<string, unknown>): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      await attendanceApi.createRuleSet(token, {
        code: String(values.code).toUpperCase(),
        name: values.name,
        timezone: values.timezone,
        effective_from: values.effective_from,
        rules: rules(values),
      })
      ruleForm.resetFields()
      setRuleOpen(false)
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "考勤规则创建失败")
    } finally {
      setSaving(false)
    }
  }

  async function createVersion(values: Record<string, unknown>): Promise<void> {
    if (!versionSource) return
    setSaving(true)
    setError(null)
    try {
      await attendanceApi.createRuleVersion(token, versionSource.id, {
        name: values.name,
        timezone: values.timezone,
        effective_from: values.effective_from,
        rules: rules(values),
      })
      setVersionSource(null)
      versionForm.resetFields()
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "规则新版本创建失败")
    } finally {
      setSaving(false)
    }
  }

  function openVersion(item: AttendanceRuleSet): void {
    setVersionSource(item)
    versionForm.setFieldsValue({
      name: item.name,
      timezone: item.timezone,
      effective_from: today,
      late_grace_minutes: Number(item.rules.late_grace_minutes ?? 0),
      early_leave_grace_minutes: Number(item.rules.early_leave_grace_minutes ?? 0),
    })
  }

  async function publish(item: AttendanceRuleSet): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      await attendanceApi.publishRuleSet(token, item.id)
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "规则发布失败")
    } finally {
      setSaving(false)
    }
  }

  async function createShift(values: Record<string, unknown>): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      await attendanceApi.createShift(token, values)
      shiftForm.resetFields()
      setShiftOpen(false)
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "班次创建失败")
    } finally {
      setSaving(false)
    }
  }

  async function deactivateShift(item: Shift): Promise<void> {
    setSaving(true)
    try {
      await attendanceApi.updateShift(token, item.id, { status: "inactive" })
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "班次停用失败")
    } finally {
      setSaving(false)
    }
  }

  const ruleOptions = useMemo(() => ruleSets.filter((item) => item.status === "active").map((item) => ({ label: `${item.name} v${item.version}`, value: item.id })), [ruleSets])

  const ruleFields = <>
    <Form.Item label="规则名称" name="name" rules={[{ required: true }]}><Input /></Form.Item>
    <Form.Item label="时区" name="timezone" initialValue="Asia/Shanghai" rules={[{ required: true }]}><Select showSearch options={[{ label: "中国标准时间（Asia/Shanghai）", value: "Asia/Shanghai" }, { label: "UTC", value: "UTC" }]} /></Form.Item>
    <Form.Item label="生效日期" name="effective_from" initialValue={today} rules={[{ required: true }]}><Input type="date" /></Form.Item>
    <Space size="large">
      <Form.Item label="迟到宽限（分钟）" name="late_grace_minutes" initialValue={0}><InputNumber min={0} precision={0} /></Form.Item>
      <Form.Item label="早退宽限（分钟）" name="early_leave_grace_minutes" initialValue={0}><InputNumber min={0} precision={0} /></Form.Item>
    </Space>
  </>

  return <div className="lifecycle-panel-stack">
    {error && <Alert closable onClose={() => setError(null)} type="error" showIcon message={error} />}
    <div className="panel-heading">
      <div><Typography.Title level={4}>考勤规则</Typography.Title><Typography.Text type="secondary">规则按版本和生效日期管理，班次引用明确版本。</Typography.Text></div>
      {canAdmin && <Button type="primary" onClick={() => setRuleOpen(true)}>新建规则</Button>}
    </div>
    <Table size="small" loading={loading} rowKey="id" dataSource={[...ruleSets]} locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无考勤规则" /> }} columns={[
      { title: "代码", dataIndex: "code", width: 180 },
      { title: "名称", dataIndex: "name" },
      { title: "时区", dataIndex: "timezone", width: 160 },
      { title: "版本", dataIndex: "version", width: 80, render: (value) => `v${value}` },
      { title: "生效日期", dataIndex: "effective_from", width: 110 },
      { title: "状态", dataIndex: "status", width: 100, render: (value) => <Tag color={value === "active" ? "success" : value === "draft" ? "gold" : "default"}>{value}</Tag> },
      { title: "操作", width: 180, render: (_value, row) => canAdmin ? <Space>{row.status === "draft" && <Button type="link" loading={saving} onClick={() => void publish(row)}>发布</Button>}<Button type="link" onClick={() => openVersion(row)}>新版本</Button></Space> : null },
    ]} />

    <div className="panel-heading"><Typography.Title level={4}>班次</Typography.Title>{canAdmin && <Button onClick={() => setShiftOpen(true)}>新建班次</Button>}</div>
    <Table size="small" loading={loading} rowKey="id" dataSource={[...shifts]} columns={[
      { title: "代码", dataIndex: "code", width: 130 },
      { title: "名称", dataIndex: "name" },
      { title: "开始", dataIndex: "start_time", width: 110 },
      { title: "结束", dataIndex: "end_time", width: 110 },
      { title: "跨日", dataIndex: "crosses_midnight", width: 80, render: (value) => value ? "是" : "否" },
      { title: "规则", dataIndex: "rule_set_id", render: (value) => { const item = ruleSets.find((rule) => rule.id === value); return item ? `${item.name} v${item.version}` : value } },
      { title: "状态", dataIndex: "status", width: 100, render: (value) => <Tag color={value === "active" ? "success" : "default"}>{value}</Tag> },
      { title: "操作", width: 100, render: (_value, row) => canAdmin && row.status === "active" ? <Button type="link" danger loading={saving} onClick={() => void deactivateShift(row)}>停用</Button> : null },
    ]} />

    <Modal title="新建考勤规则" open={ruleOpen} okText="创建草稿" confirmLoading={saving} onOk={() => ruleForm.submit()} onCancel={() => setRuleOpen(false)}>
      <Form form={ruleForm} layout="vertical" requiredMark={false} onFinish={(values) => void createRule(values)}>
        <Form.Item label="规则代码" name="code" rules={[{ required: true }, { pattern: /^[A-Za-z0-9_]+$/ }]}><Input /></Form.Item>{ruleFields}
      </Form>
    </Modal>
    <Modal title={`新建版本 · ${versionSource?.code ?? ""}`} open={Boolean(versionSource)} okText="创建草稿" confirmLoading={saving} onOk={() => versionForm.submit()} onCancel={() => setVersionSource(null)}>
      <Form form={versionForm} layout="vertical" requiredMark={false} onFinish={(values) => void createVersion(values)}>{ruleFields}</Form>
    </Modal>
    <Modal title="新建班次" open={shiftOpen} okText="保存" confirmLoading={saving} onOk={() => shiftForm.submit()} onCancel={() => setShiftOpen(false)}>
      <Form form={shiftForm} layout="vertical" requiredMark={false} onFinish={(values) => void createShift(values)}>
        <Form.Item label="班次代码" name="code" rules={[{ required: true }]}><Input /></Form.Item>
        <Form.Item label="班次名称" name="name" rules={[{ required: true }]}><Input /></Form.Item>
        <Space size="large"><Form.Item label="开始时间" name="start_time" rules={[{ required: true }]}><Input type="time" /></Form.Item><Form.Item label="结束时间" name="end_time" rules={[{ required: true }]}><Input type="time" /></Form.Item></Space>
        <Form.Item label="跨午夜" name="crosses_midnight" initialValue={false}><Select options={[{ label: "否", value: false }, { label: "是", value: true }]} /></Form.Item>
        <Form.Item label="考勤规则" name="rule_set_id" rules={[{ required: true }]}><Select options={ruleOptions} /></Form.Item>
      </Form>
    </Modal>
  </div>
}
