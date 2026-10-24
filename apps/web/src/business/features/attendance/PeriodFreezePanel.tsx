// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { Alert, Button, Form, Input, Modal, Select, Space, Table, Tag, Typography } from "antd"
import { useCallback, useEffect, useState } from "react"

import { attendanceApi } from "./api"
import type { AttendancePeriodFreeze } from "./types"
import { ActionErrorAlert, describeActionError } from "../../components/ActionErrorAlert"
import type { ActionErrorInfo } from "../../components/ActionErrorAlert"


interface PeriodFreezePanelProps {
  readonly token: string
  readonly canAdmin: boolean
}


interface FreezeFormValues {
  readonly freeze_type: "monthly" | "special"
  readonly period_month?: string
  readonly date_from?: string
  readonly date_to?: string
  readonly reason: string
}


const currentMonth = new Date().toISOString().slice(0, 7)


function monthEnd(month: string): string {
  const [year, monthNumber] = month.split("-").map(Number)
  return new Date(Date.UTC(year, monthNumber, 0)).toISOString().slice(0, 10)
}


export function PeriodFreezePanel({ token, canAdmin }: PeriodFreezePanelProps) {
  const [items, setItems] = useState<readonly AttendancePeriodFreeze[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Requirement: D-113 —— 弹窗内操作失败必须渲染在弹窗内部（弹窗带遮罩，外部 Alert 看不见）。
  const [createError, setCreateError] = useState<ActionErrorInfo | null>(null)
  const [releaseError, setReleaseError] = useState<ActionErrorInfo | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [releaseTarget, setReleaseTarget] = useState<AttendancePeriodFreeze | null>(null)
  const [freezeType, setFreezeType] = useState<"monthly" | "special">("monthly")
  const [form] = Form.useForm<FreezeFormValues>()
  const [releaseForm] = Form.useForm<{ reason: string }>()

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setItems((await attendanceApi.periodFreezes(token)).items)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "考勤冻结记录加载失败")
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { void load() }, [load])

  function openCreate(): void {
    form.resetFields()
    form.setFieldsValue({
      freeze_type: "monthly",
      period_month: currentMonth,
      reason: "月结确认后冻结考勤结果",
    })
    setFreezeType("monthly")
    setCreateError(null)
    setCreateOpen(true)
  }

  async function create(values: FreezeFormValues): Promise<void> {
    setSaving(true)
    setCreateError(null)
    try {
      const dates = values.freeze_type === "monthly"
        ? {
            date_from: `${values.period_month}-01`,
            date_to: monthEnd(String(values.period_month)),
          }
        : { date_from: values.date_from, date_to: values.date_to }
      await attendanceApi.createPeriodFreeze(token, {
        freeze_type: values.freeze_type,
        ...dates,
        reason: values.reason,
      })
      setCreateOpen(false)
      await load()
    } catch (caught) {
      setCreateError(describeActionError(caught, "考勤期间冻结失败"))
    } finally {
      setSaving(false)
    }
  }

  async function release(values: { reason: string }): Promise<void> {
    if (!releaseTarget) return
    setSaving(true)
    setReleaseError(null)
    try {
      await attendanceApi.releasePeriodFreeze(token, releaseTarget.id, values)
      setReleaseTarget(null)
      releaseForm.resetFields()
      await load()
    } catch (caught) {
      setReleaseError(describeActionError(caught, "考勤期间解冻失败"))
    } finally {
      setSaving(false)
    }
  }

  return <div className="lifecycle-panel-stack">
    <Alert
      type="info"
      showIcon
      title="冻结锁定日报和月报结果"
      description="存在任一有效冻结时，对应日期范围不能重算，也不能补录打卡 —— 已月结的账期不再接受新的考勤事实。需要更正时先填写原因解冻，补录并完成重算后可再次冻结。"
    />
    {error && <Alert closable={{ onClose: () => setError(null) }} type="error" showIcon title={error} />}
    <div className="panel-heading">
      <div>
        <Typography.Title level={4}>考勤期间冻结</Typography.Title>
        <Typography.Text type="secondary">支持完整自然月的月结冻结，也支持任意日期段的特殊业务冻结。</Typography.Text>
      </div>
      {canAdmin && <Button type="primary" onClick={openCreate}>新增冻结</Button>}
    </div>
    <Table<AttendancePeriodFreeze>
      size="small"
      loading={loading}
      rowKey="id"
      dataSource={[...items]}
      locale={{ emptyText: "暂无冻结记录" }}
      columns={[
        { title: "类型", dataIndex: "freeze_type", width: 110, render: (value) => value === "monthly" ? "月结冻结" : "特殊冻结" },
        { title: "开始日期", dataIndex: "date_from", width: 120 },
        { title: "结束日期", dataIndex: "date_to", width: 120 },
        { title: "原因", dataIndex: "reason" },
        { title: "冻结时间", dataIndex: "frozen_at", width: 180, render: (value) => new Date(value).toLocaleString("zh-CN") },
        { title: "状态", dataIndex: "status", width: 100, render: (value) => <Tag color={value === "active" ? "error" : "default"}>{value === "active" ? "冻结中" : "已解冻"}</Tag> },
        {
          title: "操作",
          width: 100,
          render: (_value, item) => canAdmin && item.status === "active"
            ? <Button type="link" onClick={() => { releaseForm.resetFields(); setReleaseError(null); setReleaseTarget(item) }}>解冻</Button>
            : "—",
        },
      ]}
    />

    <Modal
      title="新增考勤冻结"
      open={createOpen}
      okText="确认冻结"
      confirmLoading={saving}
      onOk={() => form.submit()}
      onCancel={() => setCreateOpen(false)}
    >
      <ActionErrorAlert info={createError} onClose={() => setCreateError(null)} />
      <Form form={form} layout="vertical" requiredMark={false} onFinish={(values) => void create(values)}>
        <Form.Item label="冻结类型" name="freeze_type" rules={[{ required: true }]}>
          <Select
            options={[{ label: "月结冻结", value: "monthly" }, { label: "特殊业务冻结", value: "special" }]}
            onChange={(value: "monthly" | "special") => setFreezeType(value)}
          />
        </Form.Item>
        {freezeType === "monthly" ? (
          <Form.Item label="冻结月份" name="period_month" rules={[{ required: true }]}><Input type="month" /></Form.Item>
        ) : (
          <Space size="large">
            <Form.Item label="开始日期" name="date_from" rules={[{ required: true }]}><Input type="date" /></Form.Item>
            <Form.Item label="结束日期" name="date_to" rules={[{ required: true }]}><Input type="date" /></Form.Item>
          </Space>
        )}
        <Form.Item label="冻结原因" name="reason" rules={[{ required: true }]}><Input.TextArea rows={3} maxLength={500} showCount /></Form.Item>
      </Form>
    </Modal>

    <Modal
      title="解冻考勤期间"
      open={Boolean(releaseTarget)}
      okText="确认解冻"
      confirmLoading={saving}
      onOk={() => releaseForm.submit()}
      onCancel={() => setReleaseTarget(null)}
    >
      <Alert type="warning" showIcon title="解冻后允许重新生成对应日期的日报和月报" />
      <ActionErrorAlert info={releaseError} onClose={() => setReleaseError(null)} />
      <Form form={releaseForm} layout="vertical" requiredMark={false} onFinish={(values) => void release(values)}>
        <Form.Item label="解冻原因" name="reason" rules={[{ required: true }]}><Input.TextArea rows={3} maxLength={500} showCount /></Form.Item>
      </Form>
    </Modal>
  </div>
}
