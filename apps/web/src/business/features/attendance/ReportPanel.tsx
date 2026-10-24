// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { Alert, Button, Descriptions, Drawer, Form, Input, Modal, Space, Table, Tag, Typography } from "antd"
import { useCallback, useEffect, useState } from "react"

import { ActionErrorAlert, describeActionError } from "../../components/ActionErrorAlert"
import type { ActionErrorInfo } from "../../components/ActionErrorAlert"
import { attendanceApi } from "./api"
import type {
  AttendanceCalculationKind,
  AttendanceCalculationScope,
  AttendanceCalculationTaskRequest,
  AttendanceCalculationTaskResult,
} from "./api"
import { AttendanceScopePicker } from "./AttendanceScopePicker"
import type { AttendanceDailyResult, AttendanceEmploymentOption, AttendanceMonthlyResult } from "./types"


interface ReportPanelProps {
  readonly token: string
  readonly canAdmin: boolean
}


/** 页面上的计算任务条目：提交时已知的信息 + 轮询回来的状态。 */
interface CalculationTaskView {
  readonly id: string
  readonly kind: AttendanceCalculationKind
  readonly scope: AttendanceCalculationScope
  /** 指定 / 排除语义下的人数。 */
  readonly scopeCount: number
  /** 提交时的计算日期（日报）或账期（月初）。 */
  readonly submittedPeriod: string
  readonly status: string
  readonly result: AttendanceCalculationTaskResult | null
  readonly errorCode: string | null
}


const today = new Date().toISOString().slice(0, 10)
const currentMonth = `${today.slice(0, 7)}-01`

/** 计算任务状态轮询间隔（毫秒）。 */
const TASK_POLL_INTERVAL_MS = 2000


function statusColor(status: string): string {
  if (status === "normal" || status === "calculated") return "success"
  if (status === "leave" || status === "leave_with_punch") return "processing"
  if (status === "absent" || status === "exception") return "error"
  return "default"
}


function taskStatusColor(status: string): string {
  if (status === "running") return "processing"
  if (status === "succeeded") return "success"
  if (status === "failed") return "error"
  if (status === "canceled") return "warning"
  return "default"
}


function taskStatusText(status: string): string {
  if (status === "pending") return "排队中"
  if (status === "running") return "处理中"
  if (status === "succeeded") return "成功"
  if (status === "failed") return "失败"
  if (status === "canceled") return "已取消"
  return status
}


function scopeText(scope: AttendanceCalculationScope, count: number): string {
  if (scope === "all") return "全员"
  if (scope === "selected") return `指定人员（${count} 人）`
  return `排除人员（${count} 人）`
}


/** 任务覆盖的日期（日报）或账期（月报）。 */
function periodText(task: CalculationTaskView): string {
  const period = task.result?.work_date ?? task.result?.period_month ?? task.submittedPeriod
  if (!period) return ""
  return task.kind === "monthly" ? period.slice(0, 7) : period
}


/** 失败错误码的中文解释。 */
const FAILURE_CODE_TEXT: Readonly<Record<string, string>> = {
  ATTENDANCE_PERIOD_FROZEN: "账期冻结",
  PERMISSION_DENIED: "没有操作权限",
}


function failureCodeText(code: string): string {
  return FAILURE_CODE_TEXT[code] ?? code
}


/** 任务级失败：说明原因 + 下一步动作。 */
function taskErrorText(code: string): string {
  if (code === "ATTENDANCE_PERIOD_FROZEN") return "账期冻结：请先在「期间冻结」中解冻对应账期，再重新发起计算。"
  if (code === "PERMISSION_DENIED") return "没有操作权限：请联系主管理员开通考勤计算权限后重试。"
  return `计算失败（${code}）：请稍后重试，或联系主管理员查看任务记录。`
}


function failureSummary(result: AttendanceCalculationTaskResult): string {
  const codes = result.failure_codes ?? {}
  return Object.entries(codes).map(([code, count]) => `${failureCodeText(code)} ${count} 人`).join("，")
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
  const [tasks, setTasks] = useState<readonly CalculationTaskView[]>([])
  const [dailyActionError, setDailyActionError] = useState<ActionErrorInfo | null>(null)
  const [monthlyActionError, setMonthlyActionError] = useState<ActionErrorInfo | null>(null)
  const [dailyScope, setDailyScope] = useState<AttendanceCalculationScope>("all")
  const [dailyScopeIds, setDailyScopeIds] = useState<readonly string[]>([])
  const [monthlyScope, setMonthlyScope] = useState<AttendanceCalculationScope>("all")
  const [monthlyScopeIds, setMonthlyScopeIds] = useState<readonly string[]>([])
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

  /**
   * 轮询未结束的计算任务：任务到达成功 / 失败 / 已取消时停止轮询，
   * 并自动刷新下面的日报、月报结果表。组件卸载时清理定时器。
   */
  useEffect(() => {
    const active = tasks.filter((task) => task.status === "pending" || task.status === "running")
    if (active.length === 0) return
    const timer = setInterval(() => {
      for (const task of active) {
        void attendanceApi.getCalculationTask(token, task.id).then((detail) => {
          setTasks((current) => current.map((item) => (item.id === detail.id
            ? { ...item, status: detail.status, result: detail.result, errorCode: detail.error_code }
            : item)))
          if (detail.status === "succeeded" || detail.status === "failed" || detail.status === "canceled") {
            void load()
          }
        }).catch((caught) => {
          setError(caught instanceof Error ? caught.message : "计算任务状态查询失败，请稍后重试")
        })
      }
    }, TASK_POLL_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [tasks, token, load])

  function appendTask(task: CalculationTaskView): void {
    setTasks((current) => [...current, task])
  }

  async function calculateDaily(values: Record<string, string>): Promise<void> {
    if (dailyScope !== "all" && dailyScopeIds.length === 0) {
      setDailyActionError({ tone: "error", title: "请至少选择 1 名要计算的人员，或把人员范围改为「全员」。" })
      return
    }
    setSaving(true)
    setError(null)
    setDailyActionError(null)
    try {
      const body: AttendanceCalculationTaskRequest = {
        kind: "daily",
        scope: dailyScope,
        employment_ids: dailyScope === "all" ? [] : [...dailyScopeIds],
        work_date: values.work_date,
        reason: values.reason,
      }
      const created = await attendanceApi.submitCalculationTask(token, body)
      appendTask({
        id: created.id,
        kind: "daily",
        scope: dailyScope,
        scopeCount: dailyScope === "all" ? 0 : dailyScopeIds.length,
        submittedPeriod: values.work_date,
        status: created.status,
        result: null,
        errorCode: null,
      })
      dailyForm.resetFields()
      setDailyScope("all")
      setDailyScopeIds([])
      setDailyOpen(false)
    } catch (caught) {
      // 提交阶段就被拒（账期冻结 409、权限 403、校验 422）都在弹窗内提示。
      setDailyActionError(describeActionError(caught, "日报计算任务提交失败，请稍后重试"))
    } finally {
      setSaving(false)
    }
  }

  async function calculateMonthly(values: Record<string, string>): Promise<void> {
    if (monthlyScope !== "all" && monthlyScopeIds.length === 0) {
      setMonthlyActionError({ tone: "error", title: "请至少选择 1 名要计算的人员，或把人员范围改为「全员」。" })
      return
    }
    setSaving(true)
    setError(null)
    setMonthlyActionError(null)
    try {
      const body: AttendanceCalculationTaskRequest = {
        kind: "monthly",
        scope: monthlyScope,
        employment_ids: monthlyScope === "all" ? [] : [...monthlyScopeIds],
        period_month: `${values.period_month}-01`,
        reason: values.reason,
      }
      const created = await attendanceApi.submitCalculationTask(token, body)
      appendTask({
        id: created.id,
        kind: "monthly",
        scope: monthlyScope,
        scopeCount: monthlyScope === "all" ? 0 : monthlyScopeIds.length,
        submittedPeriod: `${values.period_month}-01`,
        status: created.status,
        result: null,
        errorCode: null,
      })
      monthlyForm.resetFields()
      setMonthlyScope("all")
      setMonthlyScopeIds([])
      setMonthlyOpen(false)
    } catch (caught) {
      setMonthlyActionError(describeActionError(caught, "月报计算任务提交失败，请稍后重试"))
    } finally {
      setSaving(false)
    }
  }

  const employmentName = (id: string) => employments.find((item) => item.id === id)?.display_name ?? id

  return <div className="lifecycle-panel-stack">
    {error && <Alert closable={{ onClose: () => setError(null) }} type="error" showIcon title={error} />}
    {tasks.length > 0 && <div style={{ display: "grid", gap: 8 }}>
      <Typography.Text strong>计算任务</Typography.Text>
      {tasks.map((task) => <div key={task.id} style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 12 }}>
        <Tag>{task.kind === "daily" ? "日报" : "月报"}</Tag>
        <Typography.Text>{scopeText(task.scope, task.scopeCount)}</Typography.Text>
        <Typography.Text type="secondary">{periodText(task)}</Typography.Text>
        <Tag color={taskStatusColor(task.status)}>{taskStatusText(task.status)}</Tag>
        {task.result && <Typography.Text>目标 {task.result.target_count} 人 · 成功 {task.result.succeeded_count} 人 · 失败 {task.result.failed_count} 人</Typography.Text>}
        {task.result && Object.keys(task.result.failure_codes ?? {}).length > 0 && <Typography.Text type="secondary">{failureSummary(task.result)}</Typography.Text>}
        {task.errorCode && <Typography.Text type="danger">{taskErrorText(task.errorCode)}</Typography.Text>}
      </div>)}
    </div>}
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

    <Modal title="计算考勤日报" open={dailyOpen} okText="计算" confirmLoading={saving} okButtonProps={{ disabled: dailyScope !== "all" && dailyScopeIds.length === 0 }} onOk={() => dailyForm.submit()} onCancel={() => { setDailyOpen(false); setDailyActionError(null) }}>
      <ActionErrorAlert info={dailyActionError} onClose={() => setDailyActionError(null)} />
      <Form form={dailyForm} layout="vertical" requiredMark={false} onFinish={(values) => void calculateDaily(values)}>
        <AttendanceScopePicker
          id="daily_scope_employment_ids"
          token={token}
          scope={dailyScope}
          employmentIds={dailyScopeIds}
          onChange={(scope, employmentIds) => { setDailyScope(scope); setDailyScopeIds(employmentIds) }}
        />
        <Form.Item label="工作日期" name="work_date" initialValue={today} rules={[{ required: true }]}><Input type="date" /></Form.Item>
        <Form.Item label="计算原因" name="reason" initialValue="主管理员手工计算" rules={[{ required: true }]}><Input /></Form.Item>
      </Form>
    </Modal>
    <Modal title="计算考勤月报" open={monthlyOpen} okText="计算" confirmLoading={saving} okButtonProps={{ disabled: monthlyScope !== "all" && monthlyScopeIds.length === 0 }} onOk={() => monthlyForm.submit()} onCancel={() => { setMonthlyOpen(false); setMonthlyActionError(null) }}>
      <ActionErrorAlert info={monthlyActionError} onClose={() => setMonthlyActionError(null)} />
      <Form form={monthlyForm} layout="vertical" requiredMark={false} onFinish={(values) => void calculateMonthly(values)}>
        <AttendanceScopePicker
          id="monthly_scope_employment_ids"
          token={token}
          scope={monthlyScope}
          employmentIds={monthlyScopeIds}
          onChange={(scope, employmentIds) => { setMonthlyScope(scope); setMonthlyScopeIds(employmentIds) }}
        />
        <Form.Item label="月份" name="period_month" initialValue={currentMonth.slice(0, 7)} rules={[{ required: true }]}><Input type="month" /></Form.Item>
        <Form.Item label="计算原因" name="reason" initialValue="主管理员手工汇总" rules={[{ required: true }]}><Input /></Form.Item>
      </Form>
    </Modal>
    <Drawer size="large" title={detail ? `${employmentName(detail.employment_id)} · ${detail.work_date}` : "日报证据"} open={Boolean(detail)} onClose={() => setDetail(null)}>
      {detail && <><Descriptions bordered column={2}><Descriptions.Item label="状态">{detail.status}</Descriptions.Item><Descriptions.Item label="版本">v{detail.version}</Descriptions.Item><Descriptions.Item label="应出勤">{detail.scheduled_minutes} 分钟</Descriptions.Item><Descriptions.Item label="实出勤">{detail.worked_minutes} 分钟</Descriptions.Item></Descriptions><Typography.Title level={5}>计算证据</Typography.Title><pre className="payload-preview">{JSON.stringify(detail.evidence, null, 2)}</pre></>}
    </Drawer>
  </div>
}
