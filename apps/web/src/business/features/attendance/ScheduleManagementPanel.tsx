// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { Alert, Button, Drawer, Form, Input, InputNumber, Modal, Select, Space, Table, Tag, Typography } from "antd"
import { useCallback, useEffect, useMemo, useState } from "react"

import { attendanceApi } from "./api"
import type {
  AttendanceEmploymentOption,
  FlexibleWindow,
  ScheduleDraftResult,
  SchedulePublishBatch,
  ScheduleSwap,
  ScheduleType,
  Shift,
  ShiftCycle,
} from "./types"


interface ScheduleManagementPanelProps {
  readonly token: string
  readonly canAdmin: boolean
}


interface DraftLineValues {
  readonly employment_id: string
  readonly work_date: string
  readonly shift_id: string
}


interface DraftFormValues {
  readonly period_code: string
  readonly lines: readonly DraftLineValues[]
}


type DrawerMode = "cycle" | "window" | "draft" | null
type ModalMode = "type" | "publish" | "swap" | null


const today = new Date().toISOString().slice(0, 10)
const currentMonth = today.slice(0, 7)


export function ScheduleManagementPanel({ token, canAdmin }: ScheduleManagementPanelProps) {
  const [employments, setEmployments] = useState<readonly AttendanceEmploymentOption[]>([])
  const [shifts, setShifts] = useState<readonly Shift[]>([])
  const [scheduleTypes, setScheduleTypes] = useState<readonly ScheduleType[]>([])
  const [shiftCycles, setShiftCycles] = useState<readonly ShiftCycle[]>([])
  const [flexibleWindows, setFlexibleWindows] = useState<readonly FlexibleWindow[]>([])
  const [publishBatches, setPublishBatches] = useState<readonly SchedulePublishBatch[]>([])
  const [swaps, setSwaps] = useState<readonly ScheduleSwap[]>([])
  const [drawerMode, setDrawerMode] = useState<DrawerMode>(null)
  const [modalMode, setModalMode] = useState<ModalMode>(null)
  const [draftResult, setDraftResult] = useState<ScheduleDraftResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [draftForm] = Form.useForm<DraftFormValues>()
  const [cycleForm] = Form.useForm()
  const [windowForm] = Form.useForm()
  const [typeForm] = Form.useForm()
  const [publishForm] = Form.useForm()
  const [swapForm] = Form.useForm()

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [employmentPage, shiftPage, typePage, cyclePage, windowPage, publishPage, swapPage] = await Promise.all([
        attendanceApi.employmentOptions(token),
        attendanceApi.shifts(token),
        attendanceApi.scheduleTypes(token),
        attendanceApi.shiftCycles(token),
        attendanceApi.flexibleWindows(token),
        attendanceApi.schedulePublishBatches(token),
        attendanceApi.scheduleSwaps(token),
      ])
      setEmployments(employmentPage.items)
      setShifts(shiftPage.items)
      setScheduleTypes(typePage.items)
      setShiftCycles(cyclePage.items)
      setFlexibleWindows(windowPage.items)
      setPublishBatches(publishPage.items)
      setSwaps(swapPage.items)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "排班管理数据加载失败")
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
  const shiftOptions = useMemo(
    () => shifts.filter((item) => item.status === "active").map((item) => ({
      label: `${item.name} ${item.start_time.slice(0, 5)}-${item.end_time.slice(0, 5)}`,
      value: item.id,
    })),
    [shifts],
  )
  const scheduleTypeOptions = useMemo(
    () => scheduleTypes.map((item) => ({ label: `${item.name}（${item.code}）`, value: item.id })),
    [scheduleTypes],
  )
  const employmentName = (id: string) => employments.find((item) => item.id === id)?.display_name ?? id
  const shiftName = (id: string | null) => {
    if (!id) return "—"
    return shifts.find((item) => item.id === id)?.name ?? id
  }

  function openDrawer(mode: Exclude<DrawerMode, null>): void {
    setModalMode(null)
    setDrawerMode(mode)
    setError(null)
    if (mode === "draft") {
      draftForm.resetFields()
      draftForm.setFieldsValue({
        period_code: currentMonth,
        lines: [{ employment_id: undefined, work_date: today, shift_id: undefined }],
      })
      setDraftResult(null)
    }
  }

  function openModal(mode: Exclude<ModalMode, null>): void {
    setDrawerMode(null)
    setModalMode(mode)
    setError(null)
    if (mode === "type") {
      typeForm.resetFields()
      typeForm.setFieldsValue({
        requires_shift_cycle: false,
        requires_flexible_window: false,
        allows_multiple_shifts_per_day: false,
        requires_publish: true,
      })
    }
    if (mode === "publish") {
      publishForm.resetFields()
      publishForm.setFieldsValue({ period_code: currentMonth })
    }
    if (mode === "swap") {
      swapForm.resetFields()
      swapForm.setFieldsValue({ work_date: today })
    }
  }

  async function createType(values: Record<string, unknown>): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      await attendanceApi.createScheduleType(token, {
        code: String(values.code ?? "").toUpperCase(),
        name: values.name,
        requires_shift_cycle: Boolean(values.requires_shift_cycle),
        requires_flexible_window: Boolean(values.requires_flexible_window),
        allows_multiple_shifts_per_day: Boolean(values.allows_multiple_shifts_per_day),
        requires_publish: values.requires_publish !== false,
      })
      setModalMode(null)
      setNotice("排班类型已创建。")
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "排班类型创建失败")
    } finally {
      setSaving(false)
    }
  }

  async function createCycle(values: Record<string, unknown>): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      await attendanceApi.createShiftCycle(token, {
        code: values.code,
        name: values.name,
        schedule_type_id: values.schedule_type_id,
        cycle_start_date: values.cycle_start_date,
        cycle_days: Number(values.cycle_days),
        shift_sequence: values.shift_sequence ?? [],
      })
      setDrawerMode(null)
      setNotice("轮班周期已创建。")
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "轮班周期创建失败")
    } finally {
      setSaving(false)
    }
  }

  async function createWindow(values: Record<string, unknown>): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      await attendanceApi.createFlexibleWindow(token, {
        code: values.code,
        name: values.name,
        schedule_type_id: values.schedule_type_id,
        arrival_window_start: values.arrival_window_start ?? null,
        arrival_window_end: values.arrival_window_end ?? null,
        departure_window_start: values.departure_window_start ?? null,
        departure_window_end: values.departure_window_end ?? null,
        standard_daily_minutes: values.standard_daily_minutes === undefined
          ? null
          : Number(values.standard_daily_minutes),
      })
      setDrawerMode(null)
      setNotice("弹性窗口已创建。")
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "弹性窗口创建失败")
    } finally {
      setSaving(false)
    }
  }

  async function submitDraft(values: DraftFormValues): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      const result = await attendanceApi.generateScheduleDrafts(token, {
        period_code: values.period_code,
        source: "batch",
        lines: values.lines.map((line) => ({
          employment_id: line.employment_id,
          work_date: line.work_date,
          shift_id: line.shift_id,
        })),
      })
      setDraftResult(result)
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "批量排班草稿生成失败")
    } finally {
      setSaving(false)
    }
  }

  async function createPublishBatch(values: Record<string, unknown>): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      await attendanceApi.createSchedulePublishBatch(token, {
        period_code: values.period_code,
        schedule_type_id: values.schedule_type_id ?? null,
      })
      setModalMode(null)
      setNotice("发布批次已创建，确认后发布该期间的草稿排班。")
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "发布批次创建失败")
    } finally {
      setSaving(false)
    }
  }

  async function publishBatch(batch: SchedulePublishBatch): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      const published = await attendanceApi.publishScheduleBatch(token, batch.id)
      setNotice(`${published.period_code} 期间已发布 ${published.published_count} 条排班。`)
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "排班发布失败")
    } finally {
      setSaving(false)
    }
  }

  async function createSwap(values: Record<string, unknown>): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      await attendanceApi.createScheduleSwap(token, {
        employment_id_a: values.employment_id_a,
        employment_id_b: values.employment_id_b,
        work_date: values.work_date,
        original_shift_id: values.original_shift_id ?? null,
        new_shift_id: values.new_shift_id ?? null,
        remark: values.remark ?? null,
      })
      setModalMode(null)
      setNotice("换班记录已创建，待批准后生效。")
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "换班记录创建失败")
    } finally {
      setSaving(false)
    }
  }

  async function decideSwap(swap: ScheduleSwap, status: "approved" | "rejected"): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      await attendanceApi.decideScheduleSwap(token, swap.id, { status, remark: status === "approved" ? "换班批准" : "换班驳回" })
      setNotice(status === "approved" ? `换班 ${swap.request_number} 已批准并生效。` : `换班 ${swap.request_number} 已驳回。`)
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "换班处理失败")
    } finally {
      setSaving(false)
    }
  }

  return <div className="lifecycle-panel-stack">
    <Alert
      type="info"
      showIcon
      title="轮班周期与弹性窗口规则待企业输入"
      description="轮班周期天数与班次序列、弹性窗口的浮动范围与标准工时、同日多班次规则由企业确认后配置；未确认前只保留字段容器，不参与考勤计算。"
    />
    {error && <Alert closable={{ onClose: () => setError(null) }} type="error" showIcon title={error} />}
    {notice && <Alert closable={{ onClose: () => setNotice(null) }} type="success" showIcon title={notice} />}

    <div className="panel-heading">
      <div>
        <Typography.Title level={4}>排班类型</Typography.Title>
        <Typography.Text type="secondary">固定班、轮班、弹性、自由班；类型只声明需要哪些规则容器。</Typography.Text>
      </div>
      {canAdmin && <Button type="primary" onClick={() => openModal("type")}>新建排班类型</Button>}
    </div>
    <Table<ScheduleType>
      size="small"
      loading={loading}
      rowKey="id"
      dataSource={[...scheduleTypes]}
      locale={{ emptyText: "暂无排班类型" }}
      columns={[
        { title: "代码", dataIndex: "code", width: 140 },
        { title: "名称", dataIndex: "name" },
        { title: "轮班周期", dataIndex: "requires_shift_cycle", width: 110, render: (value) => value ? "需要" : "不需要" },
        { title: "弹性窗口", dataIndex: "requires_flexible_window", width: 110, render: (value) => value ? "需要" : "不需要" },
        { title: "同日多班次", dataIndex: "allows_multiple_shifts_per_day", width: 130, render: (value) => value ? "允许" : "不允许" },
        { title: "需要发布", dataIndex: "requires_publish", width: 100, render: (value) => value ? "是" : "否" },
        { title: "状态", dataIndex: "status", width: 90, render: (value) => <Tag color={value === "active" ? "success" : "default"}>{value === "active" ? "有效" : value}</Tag> },
      ]}
    />

    <div className="panel-heading">
      <div>
        <Typography.Title level={4}>轮班周期</Typography.Title>
        <Typography.Text type="secondary">周期起始日、周期天数与班次序列；序列长度须与周期天数一致。</Typography.Text>
      </div>
      {canAdmin && <Button onClick={() => openDrawer("cycle")}>新建轮班周期</Button>}
    </div>
    <Table<ShiftCycle>
      size="small"
      loading={loading}
      rowKey="id"
      dataSource={[...shiftCycles]}
      locale={{ emptyText: "暂无轮班周期" }}
      columns={[
        { title: "代码", dataIndex: "code", width: 150 },
        { title: "名称", dataIndex: "name" },
        { title: "排班类型", dataIndex: "schedule_type_id", width: 160, render: (value) => scheduleTypes.find((item) => item.id === value)?.name ?? value },
        { title: "周期起始", dataIndex: "cycle_start_date", width: 120 },
        { title: "周期天数", dataIndex: "cycle_days", width: 100 },
        { title: "班次序列", dataIndex: "shift_sequence", width: 120, render: (value) => value.length ? `${value.length} 个班次` : "规则待配置" },
        { title: "状态", dataIndex: "status", width: 90, render: (value) => <Tag color={value === "active" ? "success" : "gold"}>{value === "active" ? "已生效" : value === "draft" ? "草稿" : value}</Tag> },
      ]}
    />

    <div className="panel-heading">
      <div>
        <Typography.Title level={4}>弹性窗口</Typography.Title>
        <Typography.Text type="secondary">上下班浮动范围与每日标准工时。</Typography.Text>
      </div>
      {canAdmin && <Button onClick={() => openDrawer("window")}>新建弹性窗口</Button>}
    </div>
    <Table<FlexibleWindow>
      size="small"
      loading={loading}
      rowKey="id"
      dataSource={[...flexibleWindows]}
      locale={{ emptyText: "暂无弹性窗口" }}
      columns={[
        { title: "代码", dataIndex: "code", width: 150 },
        { title: "名称", dataIndex: "name" },
        { title: "排班类型", dataIndex: "schedule_type_id", width: 160, render: (value) => scheduleTypes.find((item) => item.id === value)?.name ?? value },
        { title: "上班浮动", width: 180, render: (_value, row) => row.arrival_window_start && row.arrival_window_end ? `${row.arrival_window_start.slice(0, 5)} - ${row.arrival_window_end.slice(0, 5)}` : "规则待配置" },
        { title: "下班浮动", width: 180, render: (_value, row) => row.departure_window_start && row.departure_window_end ? `${row.departure_window_start.slice(0, 5)} - ${row.departure_window_end.slice(0, 5)}` : "规则待配置" },
        { title: "标准工时", dataIndex: "standard_daily_minutes", width: 110, render: (value) => value ? `${value} 分钟` : "规则待配置" },
        { title: "状态", dataIndex: "status", width: 90, render: (value) => <Tag color={value === "active" ? "success" : "gold"}>{value === "active" ? "已生效" : value === "draft" ? "草稿" : value}</Tag> },
      ]}
    />

    <div className="panel-heading">
      <div>
        <Typography.Title level={4}>批量排班（草稿）</Typography.Title>
        <Typography.Text type="secondary">单次最多 1000 条明细；草稿不参与考勤计算，按期间发布后生效。</Typography.Text>
      </div>
      {canAdmin && <Button type="primary" onClick={() => openDrawer("draft")}>批量生成草稿</Button>}
    </div>

    <div className="panel-heading">
      <div>
        <Typography.Title level={4}>发布批次</Typography.Title>
        <Typography.Text type="secondary">按期间发布该期间的草稿排班。</Typography.Text>
      </div>
      {canAdmin && <Button onClick={() => openModal("publish")}>新建发布批次</Button>}
    </div>
    <Table<SchedulePublishBatch>
      size="small"
      loading={loading}
      rowKey="id"
      dataSource={[...publishBatches]}
      locale={{ emptyText: "暂无发布批次" }}
      columns={[
        { title: "批次号", dataIndex: "batch_number", width: 160 },
        { title: "期间", dataIndex: "period_code", width: 110 },
        { title: "区间", width: 200, render: (_value, row) => `${row.period_start} ~ ${row.period_end}` },
        { title: "状态", dataIndex: "status", width: 100, render: (value) => <Tag color={value === "published" ? "success" : "gold"}>{value === "published" ? "已发布" : value === "draft" ? "草稿" : value}</Tag> },
        { title: "发布条数", dataIndex: "published_count", width: 100 },
        { title: "发布时间", dataIndex: "published_at", width: 200, render: (value) => value ? new Date(value).toLocaleString() : "—" },
        {
          title: "操作",
          width: 100,
          render: (_value, row) => canAdmin && row.status === "draft"
            ? <Button type="link" loading={saving} onClick={() => void publishBatch(row)}>发布</Button>
            : null,
        },
      ]}
    />

    <div className="panel-heading">
      <div>
        <Typography.Title level={4}>换班记录</Typography.Title>
        <Typography.Text type="secondary">批准后双方当日班次互换。</Typography.Text>
      </div>
      {canAdmin && <Button onClick={() => openModal("swap")}>新建换班记录</Button>}
    </div>
    <Table<ScheduleSwap>
      size="small"
      loading={loading}
      rowKey="id"
      dataSource={[...swaps]}
      locale={{ emptyText: "暂无换班记录" }}
      columns={[
        { title: "单号", dataIndex: "request_number", width: 150 },
        { title: "换班人 A", dataIndex: "employment_id_a", render: (value) => employmentName(value) },
        { title: "换班人 B", dataIndex: "employment_id_b", render: (value) => employmentName(value) },
        { title: "日期", dataIndex: "work_date", width: 110 },
        { title: "原班次", dataIndex: "original_shift_id", width: 130, render: (value) => shiftName(value) },
        { title: "新班次", dataIndex: "new_shift_id", width: 130, render: (value) => shiftName(value) },
        { title: "状态", dataIndex: "status", width: 100, render: (value) => <Tag color={value === "approved" ? "success" : value === "rejected" ? "error" : "gold"}>{value === "approved" ? "已批准" : value === "rejected" ? "已驳回" : value === "cancelled" ? "已取消" : "待处理"}</Tag> },
        {
          title: "操作",
          width: 140,
          render: (_value, row) => canAdmin && row.status === "draft"
            ? (
              <Space>
                <Button type="link" loading={saving} onClick={() => void decideSwap(row, "approved")}>批准</Button>
                <Button type="link" danger loading={saving} onClick={() => void decideSwap(row, "rejected")}>驳回</Button>
              </Space>
            )
            : null,
        },
      ]}
    />

    <Modal
      title="新建排班类型"
      open={modalMode === "type"}
      okText="保存"
      confirmLoading={saving}
      onOk={() => typeForm.submit()}
      onCancel={() => setModalMode(null)}
    >
      <Form form={typeForm} layout="vertical" requiredMark={false} onFinish={(values) => void createType(values)}>
        <Form.Item label="类型代码" name="code" rules={[{ required: true }]}><Input /></Form.Item>
        <Form.Item label="类型名称" name="name" rules={[{ required: true }]}><Input /></Form.Item>
        <Form.Item label="需要轮班周期" name="requires_shift_cycle"><Select options={[{ label: "否", value: false }, { label: "是", value: true }]} /></Form.Item>
        <Form.Item label="需要弹性窗口" name="requires_flexible_window"><Select options={[{ label: "否", value: false }, { label: "是", value: true }]} /></Form.Item>
        <Form.Item label="允许同日多班次" name="allows_multiple_shifts_per_day"><Select options={[{ label: "否", value: false }, { label: "是", value: true }]} /></Form.Item>
        <Form.Item label="需要发布后生效" name="requires_publish"><Select options={[{ label: "是", value: true }, { label: "否", value: false }]} /></Form.Item>
      </Form>
    </Modal>

    <Modal
      title="新建发布批次"
      open={modalMode === "publish"}
      okText="保存"
      confirmLoading={saving}
      onOk={() => publishForm.submit()}
      onCancel={() => setModalMode(null)}
    >
      <Form form={publishForm} layout="vertical" requiredMark={false} onFinish={(values) => void createPublishBatch(values)}>
        <Form.Item label="期间（YYYY-MM）" name="period_code" rules={[{ required: true }]}><Input placeholder={currentMonth} /></Form.Item>
        <Form.Item label="排班类型（可选）" name="schedule_type_id"><Select allowClear options={scheduleTypeOptions} /></Form.Item>
      </Form>
    </Modal>

    <Modal
      title="新建换班记录"
      open={modalMode === "swap"}
      okText="保存"
      confirmLoading={saving}
      onOk={() => swapForm.submit()}
      onCancel={() => setModalMode(null)}
    >
      <Form form={swapForm} layout="vertical" requiredMark={false} onFinish={(values) => void createSwap(values)}>
        <Form.Item label="换班人 A" name="employment_id_a" rules={[{ required: true, message: "请选择换班人 A" }]}><Select showSearch optionFilterProp="label" options={employmentOptions} /></Form.Item>
        <Form.Item label="换班人 B" name="employment_id_b" rules={[{ required: true, message: "请选择换班人 B" }]}><Select showSearch optionFilterProp="label" options={employmentOptions} /></Form.Item>
        <Form.Item label="换班日期" name="work_date" rules={[{ required: true }]}><Input type="date" /></Form.Item>
        <Form.Item label="原班次" name="original_shift_id"><Select allowClear options={shiftOptions} /></Form.Item>
        <Form.Item label="新班次" name="new_shift_id"><Select allowClear options={shiftOptions} /></Form.Item>
        <Form.Item label="备注" name="remark"><Input.TextArea rows={3} maxLength={500} showCount /></Form.Item>
      </Form>
    </Modal>

    <Drawer
      title="新建轮班周期"
      size="large"
      open={drawerMode === "cycle"}
      onClose={() => setDrawerMode(null)}
      footer={(
        <Space>
          <Button onClick={() => setDrawerMode(null)}>取消</Button>
          <Button type="primary" loading={saving} onClick={() => cycleForm.submit()}>保存</Button>
        </Space>
      )}
    >
      <Form form={cycleForm} layout="vertical" requiredMark={false} onFinish={(values) => void createCycle(values)}>
        <Form.Item label="周期代码" name="code" rules={[{ required: true }]}><Input /></Form.Item>
        <Form.Item label="周期名称" name="name" rules={[{ required: true }]}><Input /></Form.Item>
        <Form.Item label="排班类型" name="schedule_type_id" rules={[{ required: true }]}><Select options={scheduleTypeOptions} /></Form.Item>
        <Form.Item label="周期起始日期" name="cycle_start_date" rules={[{ required: true }]}><Input type="date" /></Form.Item>
        <Form.Item label="周期天数" name="cycle_days" rules={[{ required: true }]}><InputNumber min={1} precision={0} /></Form.Item>
        <Form.Item label="班次序列（按周期顺序选择班次）" name="shift_sequence">
          <Select mode="multiple" allowClear options={shiftOptions} />
        </Form.Item>
      </Form>
    </Drawer>

    <Drawer
      title="新建弹性窗口"
      size="large"
      open={drawerMode === "window"}
      onClose={() => setDrawerMode(null)}
      footer={(
        <Space>
          <Button onClick={() => setDrawerMode(null)}>取消</Button>
          <Button type="primary" loading={saving} onClick={() => windowForm.submit()}>保存</Button>
        </Space>
      )}
    >
      <Form form={windowForm} layout="vertical" requiredMark={false} onFinish={(values) => void createWindow(values)}>
        <Form.Item label="窗口代码" name="code" rules={[{ required: true }]}><Input /></Form.Item>
        <Form.Item label="窗口名称" name="name" rules={[{ required: true }]}><Input /></Form.Item>
        <Form.Item label="排班类型" name="schedule_type_id" rules={[{ required: true }]}><Select options={scheduleTypeOptions} /></Form.Item>
        <Space size="large">
          <Form.Item label="上班浮动开始" name="arrival_window_start"><Input type="time" /></Form.Item>
          <Form.Item label="上班浮动结束" name="arrival_window_end"><Input type="time" /></Form.Item>
        </Space>
        <Space size="large">
          <Form.Item label="下班浮动开始" name="departure_window_start"><Input type="time" /></Form.Item>
          <Form.Item label="下班浮动结束" name="departure_window_end"><Input type="time" /></Form.Item>
        </Space>
        <Form.Item label="每日标准工时（分钟）" name="standard_daily_minutes"><InputNumber min={1} precision={0} /></Form.Item>
      </Form>
    </Drawer>

    <Drawer
      title="批量生成排班草稿"
      size="large"
      open={drawerMode === "draft"}
      onClose={() => setDrawerMode(null)}
      footer={(
        <Space>
          <Button onClick={() => setDrawerMode(null)}>关闭</Button>
          <Button type="primary" loading={saving} onClick={() => draftForm.submit()}>生成草稿</Button>
        </Space>
      )}
    >
      <Form form={draftForm} layout="vertical" requiredMark={false} onFinish={(values) => void submitDraft(values)}>
        <Form.Item label="期间（YYYY-MM）" name="period_code" rules={[{ required: true }]}><Input placeholder={currentMonth} /></Form.Item>
        <Form.List name="lines">
          {(fields, { add, remove }) => (
            <>
              {fields.map((field) => (
                <Space key={field.key} align="start" size="small">
                  <Form.Item name={[field.name, "employment_id"]} rules={[{ required: true, message: "请选择员工" }]}>
                    <Select showSearch optionFilterProp="label" options={employmentOptions} placeholder="员工" style={{ width: 200 }} />
                  </Form.Item>
                  <Form.Item name={[field.name, "work_date"]} rules={[{ required: true, message: "请选择日期" }]}>
                    <Input type="date" style={{ width: 160 }} />
                  </Form.Item>
                  <Form.Item name={[field.name, "shift_id"]} rules={[{ required: true, message: "请选择班次" }]}>
                    <Select options={shiftOptions} placeholder="班次" style={{ width: 190 }} />
                  </Form.Item>
                  <Button type="link" danger onClick={() => remove(field.name)}>删除</Button>
                </Space>
              ))}
              <Button type="dashed" onClick={() => add({ work_date: today })}>添加明细</Button>
            </>
          )}
        </Form.List>
      </Form>
      {draftResult ? (
        <Alert
          type={draftResult.failed.length ? "warning" : "success"}
          showIcon
          title={`草稿生成完成：成功 ${draftResult.created} 条，失败 ${draftResult.failed.length} 条`}
          description={draftResult.failed.length ? (
            <ul>
              {draftResult.failed.map((item) => (
                <li key={`${item.line_index}-${item.work_date}`}>
                  {item.work_date} · {item.message}
                </li>
              ))}
            </ul>
          ) : "全部明细已生成草稿，按期间发布后生效。"}
        />
      ) : null}
    </Drawer>
  </div>
}
