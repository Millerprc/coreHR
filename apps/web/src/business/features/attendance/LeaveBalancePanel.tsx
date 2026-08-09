import { Alert, Button, Drawer, Form, Input, InputNumber, Modal, Select, Space, Table, Tag, Typography } from "antd"
import { useCallback, useEffect, useMemo, useState } from "react"

import { attendanceApi } from "./api"
import type { AttendanceEmploymentOption, LeaveBalanceAccount, LeaveBalanceTransaction, LeaveType } from "./types"


interface LeaveBalancePanelProps {
  readonly token: string
  readonly canAdmin: boolean
}


interface AdjustmentValues {
  readonly employment_id: string
  readonly leave_type_id: string
  readonly period_year: number
  readonly transaction_type: "grant" | "adjustment" | "carryover" | "accrual"
  readonly amount: number
  readonly effective_date: string
  readonly reason: string
}


const today = new Date().toISOString().slice(0, 10)
const currentYear = new Date().getFullYear()


const transactionLabels: Record<string, string> = {
  grant: "发放",
  adjustment: "调整",
  carryover: "结转",
  accrual: "计提",
  usage: "请假扣减",
  reversal: "销假冲回",
}


export function LeaveBalancePanel({ token, canAdmin }: LeaveBalancePanelProps) {
  const [employments, setEmployments] = useState<readonly AttendanceEmploymentOption[]>([])
  const [leaveTypes, setLeaveTypes] = useState<readonly LeaveType[]>([])
  const [accounts, setAccounts] = useState<readonly LeaveBalanceAccount[]>([])
  const [transactions, setTransactions] = useState<readonly LeaveBalanceTransaction[]>([])
  const [ledgerTarget, setLedgerTarget] = useState<LeaveBalanceAccount | null>(null)
  const [adjustmentOpen, setAdjustmentOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [ledgerLoading, setLedgerLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [form] = Form.useForm<AdjustmentValues>()

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [employmentPage, typePage, accountPage] = await Promise.all([
        attendanceApi.employmentOptions(token),
        attendanceApi.leaveTypes(token),
        attendanceApi.leaveBalances(token),
      ])
      setEmployments(employmentPage.items)
      setLeaveTypes(typePage.items)
      setAccounts(accountPage.items)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "假期余额加载失败")
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { void load() }, [load])

  const employmentOptions = useMemo(() => employments.map((item) => ({
    label: `${item.display_name} (${item.employee_number ?? "无工号"})`,
    value: item.id,
  })), [employments])
  const leaveTypeOptions = useMemo(() => leaveTypes.filter((item) => (
    item.status === "active" && (item.rules.balance_mode ?? "none") !== "none"
  )).map((item) => ({ label: item.name, value: item.id })), [leaveTypes])
  const employmentName = (id: string) => employments.find((item) => item.id === id)?.display_name ?? id
  const leaveTypeName = (id: string) => leaveTypes.find((item) => item.id === id)?.name ?? id

  function openAdjustment(): void {
    form.resetFields()
    form.setFieldsValue({
      period_year: currentYear,
      transaction_type: "grant",
      amount: 1,
      effective_date: today,
    })
    setAdjustmentOpen(true)
  }

  async function submitAdjustment(values: AdjustmentValues): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      await attendanceApi.createLeaveBalanceTransaction(token, {
        ...values,
        amount: String(values.amount),
        idempotency_key: crypto.randomUUID(),
      })
      setAdjustmentOpen(false)
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "假期额度调整失败")
    } finally {
      setSaving(false)
    }
  }

  async function openLedger(account: LeaveBalanceAccount): Promise<void> {
    setLedgerTarget(account)
    setLedgerLoading(true)
    setError(null)
    try {
      setTransactions((await attendanceApi.leaveBalanceTransactions(token, account.id)).items)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "假期余额流水加载失败")
      setTransactions([])
    } finally {
      setLedgerLoading(false)
    }
  }

  return <div className="lifecycle-panel-stack">
    <Alert
      type="info"
      showIcon
      title="余额由不可变流水汇总"
      description="批准请假自动扣减，批准销假或直接取消自动冲回。人工发放、调整、结转和计提都必须填写原因；自动计提与跨年结转规则待企业规则确认后再配置。"
    />
    {error && <Alert closable onClose={() => setError(null)} type="error" showIcon title={error} />}
    <div className="panel-heading">
      <div>
        <Typography.Title level={4}>假期余额账户</Typography.Title>
        <Typography.Text type="secondary">账户按员工劳动关系、假期类型和自然年度分别保存。</Typography.Text>
      </div>
      {canAdmin && <Button type="primary" onClick={openAdjustment}>调整额度</Button>}
    </div>
    <Table<LeaveBalanceAccount>
      size="small"
      loading={loading}
      rowKey="id"
      dataSource={[...accounts]}
      locale={{ emptyText: "暂无余额账户" }}
      columns={[
        { title: "员工", dataIndex: "employment_id", render: (value) => employmentName(value) },
        { title: "假期类型", dataIndex: "leave_type_id", render: (value) => leaveTypeName(value) },
        { title: "年度", dataIndex: "period_year", width: 90 },
        { title: "当前余额", dataIndex: "current_balance", width: 120, render: (value, item) => `${value} ${item.unit === "day" ? "天" : "小时"}` },
        { title: "版本", dataIndex: "version", width: 80, render: (value) => `v${value}` },
        { title: "状态", dataIndex: "status", width: 90, render: (value) => <Tag color={value === "active" ? "success" : "default"}>{value === "active" ? "有效" : "已关闭"}</Tag> },
        { title: "操作", width: 100, render: (_value, item) => <Button type="link" onClick={() => void openLedger(item)}>查看流水</Button> },
      ]}
    />

    <Modal
      title="调整假期额度"
      open={adjustmentOpen}
      okText="确认入账"
      confirmLoading={saving}
      onOk={() => form.submit()}
      onCancel={() => setAdjustmentOpen(false)}
    >
      <Form form={form} layout="vertical" requiredMark={false} onFinish={(values) => void submitAdjustment(values)}>
        <Form.Item label="员工劳动关系" name="employment_id" rules={[{ required: true }]}><Select showSearch optionFilterProp="label" options={employmentOptions} /></Form.Item>
        <Form.Item label="假期类型" name="leave_type_id" rules={[{ required: true }]}><Select options={leaveTypeOptions} /></Form.Item>
        <Space size="large">
          <Form.Item label="所属年度" name="period_year" rules={[{ required: true }]}><InputNumber min={2000} max={2200} precision={0} /></Form.Item>
          <Form.Item label="生效日期" name="effective_date" rules={[{ required: true }]}><Input type="date" /></Form.Item>
        </Space>
        <Form.Item label="入账类型" name="transaction_type" rules={[{ required: true }]}>
          <Select options={[
            { label: "额度发放", value: "grant" },
            { label: "人工调整（可为负）", value: "adjustment" },
            { label: "上年结转", value: "carryover" },
            { label: "周期计提", value: "accrual" },
          ]} />
        </Form.Item>
        <Form.Item label="变动数量" name="amount" rules={[{ required: true }]}><InputNumber precision={2} step={0.5} /></Form.Item>
        <Form.Item label="入账原因" name="reason" rules={[{ required: true }]}><Input.TextArea rows={3} maxLength={500} showCount /></Form.Item>
      </Form>
    </Modal>

    <Drawer
      title={ledgerTarget ? `${employmentName(ledgerTarget.employment_id)} · ${leaveTypeName(ledgerTarget.leave_type_id)} · ${ledgerTarget.period_year}` : "假期余额流水"}
      size="large"
      open={Boolean(ledgerTarget)}
      onClose={() => setLedgerTarget(null)}
    >
      <Table<LeaveBalanceTransaction>
        size="small"
        loading={ledgerLoading}
        rowKey="id"
        dataSource={[...transactions]}
        pagination={false}
        locale={{ emptyText: "暂无流水" }}
        columns={[
          { title: "版本", dataIndex: "account_version", width: 75, render: (value) => `v${value}` },
          { title: "日期", dataIndex: "effective_date", width: 110 },
          { title: "类型", dataIndex: "transaction_type", width: 100, render: (value) => transactionLabels[value] ?? value },
          { title: "变动", dataIndex: "amount", width: 90 },
          { title: "变动后", dataIndex: "balance_after", width: 90 },
          { title: "原因", dataIndex: "reason" },
        ]}
      />
    </Drawer>
  </div>
}
