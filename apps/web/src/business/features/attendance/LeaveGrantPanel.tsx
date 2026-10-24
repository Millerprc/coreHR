// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { Alert, Button, Drawer, Form, Input, InputNumber, Select, Space, Table, Tag, Typography } from "antd"
import { useCallback, useEffect, useMemo, useState } from "react"

import { attendanceApi } from "./api"
import type {
  AttendanceEmploymentOption,
  LeaveGrantBatch,
  LeaveGrantBatchDetail,
  LeaveGrantItem,
  LeaveGrantRule,
  LeaveType,
} from "./types"


interface LeaveGrantPanelProps {
  readonly token: string
  readonly canAdmin: boolean
}


interface GrantItemValues {
  readonly employment_id: string
  readonly leave_type_id: string
  readonly grant_days: number
}


interface GrantBatchValues {
  readonly period_code: string
  readonly grant_date: string
  readonly items: readonly GrantItemValues[]
}


const today = new Date().toISOString().slice(0, 10)
const currentMonth = today.slice(0, 7)


const batchStatusLabels: Record<string, string> = {
  draft: "草稿",
  issued: "已发放",
  void: "已作废",
}


const itemStatusLabels: Record<string, string> = {
  pending: "待发放",
  issued: "已发放",
}


/** D-107：规则字段未配置时统一显示「规则待配置」，不显示臆测取值。 */
function rulePending(value: string | number | null): string {
  return value === null || value === "" ? "规则待配置" : String(value)
}


export function LeaveGrantPanel({ token, canAdmin }: LeaveGrantPanelProps) {
  const [employments, setEmployments] = useState<readonly AttendanceEmploymentOption[]>([])
  const [leaveTypes, setLeaveTypes] = useState<readonly LeaveType[]>([])
  const [batches, setBatches] = useState<readonly LeaveGrantBatch[]>([])
  const [rules, setRules] = useState<readonly LeaveGrantRule[]>([])
  const [detail, setDetail] = useState<LeaveGrantBatchDetail | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [detailLoading, setDetailLoading] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [batchForm] = Form.useForm<GrantBatchValues>()

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [employmentPage, typePage, batchPage, rulePage] = await Promise.all([
        attendanceApi.employmentOptions(token),
        attendanceApi.leaveTypes(token),
        attendanceApi.leaveGrantBatches(token),
        attendanceApi.leaveGrantRules(token),
      ])
      setEmployments(employmentPage.items)
      setLeaveTypes(typePage.items)
      setBatches(batchPage.items)
      setRules(rulePage.items)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "发假明细加载失败")
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { void load() }, [load])

  const employmentOptions = useMemo(
    () => employments.map((item) => ({
      label: `${item.display_name} (${item.employee_number ?? "无工号"})`,
      value: item.id,
    })),
    [employments],
  )
  const leaveTypeOptions = useMemo(
    () => leaveTypes.map((item) => ({ label: item.name, value: item.id })),
    [leaveTypes],
  )
  const employmentName = (id: string) => employments.find((item) => item.id === id)?.display_name ?? id
  const leaveTypeName = (id: string) => leaveTypes.find((item) => item.id === id)?.name ?? id

  function openCreate(): void {
    setDetail(null)
    batchForm.resetFields()
    batchForm.setFieldsValue({
      period_code: currentMonth,
      grant_date: today,
      items: [{ employment_id: undefined, leave_type_id: undefined, grant_days: 1 }],
    })
    setDrawerOpen(true)
  }

  async function openDetail(batch: LeaveGrantBatch): Promise<void> {
    setDrawerOpen(true)
    setDetailLoading(true)
    setError(null)
    try {
      setDetail(await attendanceApi.leaveGrantBatch(token, batch.id))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "发假批次明细加载失败")
      setDetail(null)
    } finally {
      setDetailLoading(false)
    }
  }

  async function submitBatch(values: GrantBatchValues): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      await attendanceApi.createLeaveGrantBatch(token, {
        period_code: values.period_code,
        period_type: "month",
        grant_date: values.grant_date,
        source: "manual",
        items: values.items.map((item) => ({
          employment_id: item.employment_id,
          leave_type_id: item.leave_type_id,
          grant_days: String(item.grant_days),
        })),
      })
      setDrawerOpen(false)
      setNotice("发假批次已创建为草稿，确认无误后再发放。")
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "发假批次创建失败")
    } finally {
      setSaving(false)
    }
  }

  async function issueBatch(batch: LeaveGrantBatch): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      await attendanceApi.issueLeaveGrantBatch(token, batch.id)
      setNotice(`批次 ${batch.batch_number} 已发放，额度已写入假期余额流水。`)
      await load()
      if (detail?.id === batch.id) {
        setDetail(await attendanceApi.leaveGrantBatch(token, batch.id))
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "发假批次发放失败")
    } finally {
      setSaving(false)
    }
  }

  async function voidBatch(batch: LeaveGrantBatch): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      await attendanceApi.voidLeaveGrantBatch(token, batch.id, { reason: "发假明细作废" })
      setNotice(`批次 ${batch.batch_number} 已作废。`)
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "发假批次作废失败")
    } finally {
      setSaving(false)
    }
  }

  return <div className="lifecycle-panel-stack">
    <Alert
      type="info"
      showIcon
      title="发假额度规则待企业输入"
      description="计提频率、工龄折算、封顶、清零、结转上限、有效期与离职处理由企业规则确认后配置；未配置的规则不会参与自动计提，计提任务会跳过并记录原因。"
    />
    {error && <Alert closable={{ onClose: () => setError(null) }} type="error" showIcon title={error} />}
    {notice && <Alert closable={{ onClose: () => setNotice(null) }} type="success" showIcon title={notice} />}

    <div className="panel-heading">
      <div>
        <Typography.Title level={4}>发假批次</Typography.Title>
        <Typography.Text type="secondary">批次先建草稿，确认后发放；发放会写入假期余额流水。</Typography.Text>
      </div>
      {canAdmin && <Button type="primary" onClick={openCreate}>新建发放批次</Button>}
    </div>
    <Table<LeaveGrantBatch>
      size="small"
      loading={loading}
      rowKey="id"
      dataSource={[...batches]}
      locale={{ emptyText: "暂无发假批次" }}
      columns={[
        { title: "批次号", dataIndex: "batch_number", width: 160 },
        { title: "期间", dataIndex: "period_code", width: 110 },
        { title: "发放日", dataIndex: "grant_date", width: 110 },
        { title: "来源", dataIndex: "source", width: 110, render: (value) => value === "rule_accrual" ? "规则计提" : "手工发放" },
        { title: "状态", dataIndex: "status", width: 100, render: (value) => <Tag color={value === "issued" ? "success" : value === "draft" ? "gold" : "default"}>{batchStatusLabels[value] ?? value}</Tag> },
        { title: "发放时间", dataIndex: "issued_at", width: 200, render: (value) => value ? new Date(value).toLocaleString() : "—" },
        {
          title: "操作",
          width: 180,
          render: (_value, row) => (
            <Space>
              <Button type="link" onClick={() => void openDetail(row)}>明细</Button>
              {canAdmin && row.status === "draft" ? (
                <>
                  <Button type="link" loading={saving} onClick={() => void issueBatch(row)}>发放</Button>
                  <Button type="link" danger loading={saving} onClick={() => void voidBatch(row)}>作废</Button>
                </>
              ) : null}
            </Space>
          ),
        },
      ]}
    />

    <div className="panel-heading">
      <div>
        <Typography.Title level={4}>发假额度规则</Typography.Title>
        <Typography.Text type="secondary">规则按生效起止日期版本化；空字段表示规则待配置。</Typography.Text>
      </div>
    </div>
    <Table<LeaveGrantRule>
      size="small"
      loading={loading}
      rowKey="id"
      dataSource={[...rules]}
      locale={{ emptyText: "暂无发假额度规则" }}
      columns={[
        { title: "代码", dataIndex: "code", width: 180 },
        { title: "名称", dataIndex: "name" },
        { title: "版本", dataIndex: "version", width: 70, render: (value) => `v${value}` },
        { title: "假期类型", dataIndex: "leave_type_id", width: 140, render: (value) => leaveTypeName(value) },
        { title: "额度天数", dataIndex: "entitlement_days", width: 120, render: (value) => rulePending(value) },
        { title: "计提频率", dataIndex: "accrual_frequency", width: 130, render: (value) => rulePending(value) },
        { title: "工龄下限", dataIndex: "seniority_min_years", width: 110, render: (value) => rulePending(value) },
        { title: "工龄上限", dataIndex: "seniority_max_years", width: 110, render: (value) => rulePending(value) },
        { title: "折算方式", dataIndex: "proration_method", width: 120, render: (value) => rulePending(value) },
        { title: "封顶", dataIndex: "cap_days", width: 100, render: (value) => rulePending(value) },
        { title: "结转上限", dataIndex: "carryover_cap_days", width: 110, render: (value) => rulePending(value) },
        {
          title: "有效期",
          width: 190,
          render: (_value, row) => row.valid_from || row.valid_to
            ? `${row.valid_from ?? "—"} ~ ${row.valid_to ?? "—"}`
            : "规则待配置",
        },
        { title: "清零策略", dataIndex: "reset_policy", width: 110, render: (value) => rulePending(value) },
        { title: "离职处理", dataIndex: "termination_policy", width: 110, render: (value) => rulePending(value) },
        {
          title: "生效期间",
          width: 190,
          render: (_value, row) => `${row.effective_from} ~ ${row.effective_to ?? "长期"}`,
        },
        { title: "状态", dataIndex: "status", width: 100, render: (value) => <Tag color={value === "active" ? "success" : value === "draft" ? "gold" : "default"}>{value === "active" ? "已生效" : value === "draft" ? "草稿" : value}</Tag> },
      ]}
    />

    <Drawer
      title={detail ? `发假批次 ${detail.batch_number}` : "新建发放批次"}
      size="large"
      open={drawerOpen}
      onClose={() => { setDrawerOpen(false); setDetail(null) }}
      footer={detail ? (
        <Space>
          <Button onClick={() => { setDrawerOpen(false); setDetail(null) }}>关闭</Button>
          {canAdmin && detail.status === "draft" ? (
            <Button type="primary" loading={saving} onClick={() => void issueBatch(detail)}>确认发放</Button>
          ) : null}
        </Space>
      ) : (
        <Space>
          <Button onClick={() => setDrawerOpen(false)}>取消</Button>
          <Button type="primary" loading={saving} onClick={() => batchForm.submit()}>保存草稿</Button>
        </Space>
      )}
    >
      {detail ? (
        <>
          <Typography.Paragraph type="secondary">
            期间 {detail.period_code} · 发放日 {detail.grant_date} · 状态 {batchStatusLabels[detail.status] ?? detail.status}
          </Typography.Paragraph>
          <Table<LeaveGrantItem>
            size="small"
            loading={detailLoading}
            rowKey="id"
            dataSource={[...detail.items]}
            pagination={false}
            locale={{ emptyText: "暂无明细" }}
            columns={[
              { title: "员工", dataIndex: "employment_id", render: (value) => employmentName(value) },
              { title: "假期类型", dataIndex: "leave_type_id", render: (value) => leaveTypeName(value) },
              { title: "发放天数", dataIndex: "grant_days", width: 100 },
              {
                title: "有效期",
                width: 190,
                render: (_value, row) => row.valid_from || row.valid_to ? `${row.valid_from ?? "—"} ~ ${row.valid_to ?? "—"}` : "规则待配置",
              },
              { title: "来源", dataIndex: "source", width: 110, render: (value) => value === "rule_accrual" ? "规则计提" : "手工发放" },
              { title: "状态", dataIndex: "status", width: 100, render: (value) => <Tag color={value === "issued" ? "success" : "gold"}>{itemStatusLabels[value] ?? value}</Tag> },
              { title: "余额流水", dataIndex: "transaction_id", width: 120, render: (value) => value ? "已写入" : "未写入" },
            ]}
          />
        </>
      ) : (
        <Form form={batchForm} layout="vertical" requiredMark={false} onFinish={(values) => void submitBatch(values)}>
          <Space size="large">
            <Form.Item label="发放期间（YYYY-MM）" name="period_code" rules={[{ required: true }]}>
              <Input placeholder={currentMonth} />
            </Form.Item>
            <Form.Item label="发放日" name="grant_date" rules={[{ required: true }]}>
              <Input type="date" />
            </Form.Item>
          </Space>
          <Typography.Title level={5}>发放明细</Typography.Title>
          <Form.List name="items">
            {(fields, { add, remove }) => (
              <>
                {fields.map((field) => (
                  <Space key={field.key} align="start" size="small">
                    <Form.Item
                      name={[field.name, "employment_id"]}
                      rules={[{ required: true, message: "请选择员工" }]}
                    >
                      <Select showSearch optionFilterProp="label" options={employmentOptions} placeholder="员工" style={{ width: 220 }} />
                    </Form.Item>
                    <Form.Item
                      name={[field.name, "leave_type_id"]}
                      rules={[{ required: true, message: "请选择假期类型" }]}
                    >
                      <Select options={leaveTypeOptions} placeholder="假期类型" style={{ width: 180 }} />
                    </Form.Item>
                    <Form.Item
                      name={[field.name, "grant_days"]}
                      label="发放天数"
                      rules={[{ required: true, message: "请填写天数" }]}
                    >
                      <InputNumber min={0.5} step={0.5} precision={2} style={{ width: 120 }} />
                    </Form.Item>
                    <Button type="link" danger onClick={() => remove(field.name)}>删除</Button>
                  </Space>
                ))}
                <Button type="dashed" onClick={() => add({ grant_days: 1 })}>添加明细</Button>
              </>
            )}
          </Form.List>
        </Form>
      )}
    </Drawer>
  </div>
}
