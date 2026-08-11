import {
  Alert,
  Button,
  Checkbox,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
} from "antd"
import { useCallback, useEffect, useMemo, useState } from "react"

import { workforceApi } from "./api"
import { JobArchitecturePanel } from "./JobArchitecturePanel"
import type {
  HeadcountFreeze,
  HeadcountResultLine,
  Job,
  OccupancyRule,
  OrganizationOption,
} from "./types"


type Action = "plan" | "rule" | "freeze" | "snapshot" | null


interface HeadcountWorkspaceProps {
  readonly token: string
  readonly canAdmin: boolean
}


function currentMonth(): string {
  return new Date().toISOString().slice(0, 7)
}


function localDateTimeValue(): string {
  const date = new Date(Date.now() - new Date().getTimezoneOffset() * 60_000)
  return date.toISOString().slice(0, 16)
}


function lastDayOfMonth(month: string): string {
  const [year, monthNumber] = month.split("-").map(Number)
  return new Date(Date.UTC(year, monthNumber, 0)).toISOString().slice(0, 10)
}


export function HeadcountWorkspace({ token, canAdmin }: HeadcountWorkspaceProps) {
  const [month, setMonth] = useState(currentMonth())
  const [asOf, setAsOf] = useState(new Date().toISOString().slice(0, 10))
  const [organizationId, setOrganizationId] = useState<string | undefined>()
  const [jobId, setJobId] = useState<string | undefined>()
  const [organizations, setOrganizations] = useState<readonly OrganizationOption[]>([])
  const [jobs, setJobs] = useState<readonly Job[]>([])
  const [results, setResults] = useState<readonly HeadcountResultLine[]>([])
  const [rules, setRules] = useState<readonly OccupancyRule[]>([])
  const [freezes, setFreezes] = useState<readonly HeadcountFreeze[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [action, setAction] = useState<Action>(null)
  const [form] = Form.useForm()

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [organizationItems, jobPage, result, rulePage, freezePage] = await Promise.all([
        workforceApi.organizations(token),
        workforceApi.jobs(token),
        workforceApi.headcountResults(token, `${month}-01`, asOf, organizationId, jobId),
        workforceApi.occupancyRules(token),
        workforceApi.freezes(token),
      ])
      setOrganizations(organizationItems)
      setJobs(jobPage.items)
      setResults(result.items)
      setRules(rulePage.items)
      setFreezes(freezePage.items)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "人力与编制加载失败")
    } finally {
      setLoading(false)
    }
  }, [asOf, jobId, month, organizationId, token])

  useEffect(() => { void load() }, [load])

  function openAction(nextAction: Exclude<Action, null>): void {
    setAction(nextAction)
    form.resetFields()
    if (nextAction === "freeze") {
      form.setFieldsValue({ freeze_type: "business", period_month: month, starts_at: localDateTimeValue() })
    }
    if (nextAction === "snapshot") {
      form.setFieldsValue({ snapshot_type: "month_start", timezone: "Asia/Shanghai", rule_version: "v1" })
    }
  }

  async function save(values: Record<string, unknown>): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      if (action === "plan") {
        await workforceApi.createHeadcountPlan(token, {
          ...values,
          period_month: `${String(values.period_month)}-01`,
        })
      } else if (action === "rule") {
        await workforceApi.createOccupancyRule(token, values)
      } else if (action === "freeze") {
        await workforceApi.createFreeze(token, {
          ...values,
          period_month: values.period_month ? `${String(values.period_month)}-01` : null,
          starts_at: new Date(String(values.starts_at)).toISOString(),
          ends_at: values.ends_at ? new Date(String(values.ends_at)).toISOString() : null,
        })
      } else if (action === "snapshot") {
        const snapshotType = String(values.snapshot_type)
        const timezone = String(values.timezone)
        const boundaryDate = snapshotType === "month_start" ? `${month}-01` : lastDayOfMonth(month)
        const suffix = timezone === "UTC" ? "Z" : "+08:00"
        const boundaryTime = snapshotType === "month_start" ? "00:00:00" : "23:59:59"
        if (timezone !== "UTC" && timezone !== "Asia/Shanghai" && !values.boundary_at) {
          throw new Error("使用其他IANA时区时，请填写包含UTC偏移的边界时刻")
        }
        await workforceApi.createSnapshot(token, {
          ...values,
          period_month: `${month}-01`,
          boundary_at: values.boundary_at || `${boundaryDate}T${boundaryTime}${suffix}`,
        })
      }
      setAction(null)
      form.resetFields()
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "人力与编制保存失败")
    } finally {
      setSaving(false)
    }
  }

  async function closeFreeze(item: HeadcountFreeze): Promise<void> {
    const reason = window.prompt("请输入解冻原因")?.trim()
    if (!reason) return
    setSaving(true)
    try {
      await workforceApi.closeFreeze(token, item.id, reason)
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "解冻失败")
    } finally {
      setSaving(false)
    }
  }

  const organizationOptions = useMemo(
    () => organizations.map((item) => ({ label: `${item.name} (${item.code})`, value: item.id })),
    [organizations],
  )
  const jobOptions = useMemo(
    () => jobs.map((item) => ({ label: `${item.name} (${item.code})`, value: item.id })),
    [jobs],
  )
  const actionTitles: Record<Exclude<Action, null>, string> = {
    plan: "维护月度编制",
    rule: "新增占编规则版本",
    freeze: "新增冻结",
    snapshot: "生成月度快照",
  }

  return (
    <section className="workspace-section" aria-labelledby="headcount-title">
      <div className="workspace-heading">
        <div>
          <Typography.Title id="headcount-title" level={2}>人力与编制</Typography.Title>
          <Typography.Paragraph type="secondary">编制仅呈现结果，不预占或阻断招聘；月均人数为（月初＋月末）÷2。</Typography.Paragraph>
        </div>
        {canAdmin && <Button type="primary" onClick={() => openAction("plan")}>维护编制</Button>}
      </div>
      {error && <Alert closable onClose={() => setError(null)} type="error" showIcon title={error} />}
      <div className="filter-grid">
        <label><span className="field-label">年月</span><Input aria-label="编制年月" type="month" value={month} onChange={(event) => setMonth(event.target.value)} /></label>
        <label><span className="field-label">统计日期</span><Input aria-label="统计日期" type="date" value={asOf} onChange={(event) => setAsOf(event.target.value)} /></label>
        <label><span className="field-label">组织</span><Select allowClear showSearch optionFilterProp="label" value={organizationId} options={organizationOptions} onChange={setOrganizationId} /></label>
        <label><span className="field-label">职务</span><Select allowClear showSearch optionFilterProp="label" value={jobId} options={jobOptions} onChange={setJobId} /></label>
      </div>
      <Tabs defaultActiveKey="results" items={[
        {
          key: "job-architecture",
          label: "职务体系",
          children: <JobArchitecturePanel token={token} canAdmin={canAdmin} onJobsChanged={load} />,
        },
        {
          key: "results",
          label: "编制与人数结果",
          children: <Table
            loading={loading}
            rowKey={(row) => `${row.organization_id}-${row.job_id}`}
            dataSource={[...results]}
            scroll={{ x: 1100 }}
            locale={{ emptyText: <Empty description="当前范围暂无编制数据" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
            columns={[
              { title: "组织", dataIndex: "organization_code", fixed: "left", width: 130 },
              { title: "职务", dataIndex: "job_name", width: 180, render: (value, row) => `${value} (${row.job_code})` },
              { title: "编制", dataIndex: "planned_count", width: 100 },
              { title: "当前人数", dataIndex: "current_count", width: 110 },
              { title: "差额", dataIndex: "variance", width: 100 },
              { title: "月初", dataIndex: "month_start_count", width: 90, render: (value) => value ?? "—" },
              { title: "月末", dataIndex: "month_end_count", width: 90, render: (value) => value ?? "—" },
              { title: "月均", dataIndex: "average_count", width: 90, render: (value) => value ?? "—" },
              { title: "版本", dataIndex: "plan_version", width: 80 },
              { title: "冻结", dataIndex: "frozen", width: 90, render: (value) => value ? <Tag color="red">已冻结</Tag> : <Tag>未冻结</Tag> },
            ]}
          />,
        },
        {
          key: "rules",
          label: `占编规则 ${rules.length}`,
          children: <><Space className="tab-actions">{canAdmin && <Button type="primary" onClick={() => openAction("rule")}>新增规则版本</Button>}</Space><Table rowKey="id" pagination={false} dataSource={[...rules]} columns={[
            { title: "人员类型", dataIndex: "employee_type_code" },
            { title: "计入编制", dataIndex: "counts_for_headcount", render: (value) => <Tag color={value ? "green" : "default"}>{value ? "是" : "否"}</Tag> },
            { title: "生效日期", dataIndex: "effective_from" },
            { title: "失效日期", dataIndex: "effective_to", render: (value) => value || "—" },
            { title: "版本", dataIndex: "version" },
          ]} /></>,
        },
        {
          key: "freezes",
          label: `冻结 ${freezes.filter((item) => item.status === "active").length}`,
          children: <><Space className="tab-actions">{canAdmin && <Button type="primary" onClick={() => openAction("freeze")}>新增冻结</Button>}</Space><Table rowKey="id" pagination={false} dataSource={[...freezes]} columns={[
            { title: "类型", dataIndex: "freeze_type", render: (value) => value === "month_close" ? "月结冻结" : "业务冻结" },
            { title: "月份", dataIndex: "period_month", render: (value) => value?.slice(0, 7) || "全部" },
            { title: "组织", dataIndex: "organization_id", render: (value) => organizations.find((item) => item.id === value)?.name ?? "全部" },
            { title: "职务", dataIndex: "job_id", render: (value) => jobs.find((item) => item.id === value)?.name ?? "全部" },
            { title: "状态", dataIndex: "status", render: (value) => <Tag color={value === "active" ? "red" : "default"}>{value}</Tag> },
            { title: "原因", dataIndex: "reason" },
            { title: "操作", render: (_value, row) => row.status === "active" && canAdmin ? <Button type="link" loading={saving} onClick={() => void closeFreeze(row)}>解冻</Button> : "—" },
          ]} /></>,
        },
        {
          key: "snapshots",
          label: "月度快照",
          children: <div className="empty-guidance"><Typography.Paragraph>快照按所选月份固化编制版本和人数。重复请求幂等；修订必须填写原批次ID。</Typography.Paragraph>{canAdmin && <Button type="primary" onClick={() => openAction("snapshot")}>生成快照</Button>}</div>,
        },
      ]} />

      <Modal destroyOnHidden title={action ? actionTitles[action] : ""} open={Boolean(action)} okText="保存" confirmLoading={saving} onOk={() => form.submit()} onCancel={() => setAction(null)}>
        <Form form={form} layout="vertical" requiredMark={false} onFinish={(values) => void save(values)}>
          {action === "plan" && <>
            <Form.Item label="年月" name="period_month" initialValue={month} rules={[{ required: true }]}><Input type="month" /></Form.Item>
            <Form.Item label="组织" name="organization_id" initialValue={organizationId} rules={[{ required: true }]}><Select showSearch optionFilterProp="label" options={organizationOptions} /></Form.Item>
            <Form.Item label="职务" name="job_id" initialValue={jobId} rules={[{ required: true }]}><Select showSearch optionFilterProp="label" options={jobOptions} /></Form.Item>
            <Form.Item label="编制数" name="planned_count" rules={[{ required: true }]}><InputNumber min={0} precision={2} stringMode /></Form.Item>
            <Form.Item name="override_freeze" valuePropName="checked"><Checkbox>授权绕过冻结（仍记录日志）</Checkbox></Form.Item>
          </>}
          {action === "rule" && <>
            <Form.Item label="人员类型代码" name="employee_type_code" rules={[{ required: true }]}><Input /></Form.Item>
            <Form.Item label="是否计入编制" name="counts_for_headcount" valuePropName="checked"><Checkbox>计入</Checkbox></Form.Item>
            <Form.Item label="生效日期" name="effective_from" initialValue={`${month}-01`} rules={[{ required: true }]}><Input type="date" /></Form.Item>
          </>}
          {action === "freeze" && <>
            <Form.Item label="冻结类型" name="freeze_type" rules={[{ required: true }]}><Select options={[{ value: "month_close", label: "月结冻结" }, { value: "business", label: "业务冻结" }]} /></Form.Item>
            <Form.Item label="月份（留空表示全部）" name="period_month"><Input type="month" /></Form.Item>
            <Form.Item label="组织（留空表示全部；选择后包含下级）" name="organization_id"><Select allowClear showSearch optionFilterProp="label" options={organizationOptions} /></Form.Item>
            <Form.Item label="职务（留空表示全部）" name="job_id"><Select allowClear showSearch optionFilterProp="label" options={jobOptions} /></Form.Item>
            <Form.Item label="开始时间" name="starts_at" rules={[{ required: true }]}><Input type="datetime-local" /></Form.Item>
            <Form.Item label="结束时间" name="ends_at"><Input type="datetime-local" /></Form.Item>
          </>}
          {action === "snapshot" && <>
            <Form.Item label="快照类型" name="snapshot_type" rules={[{ required: true }]}><Select options={[{ value: "month_start", label: "月初" }, { value: "month_end", label: "月末" }]} /></Form.Item>
            <Form.Item label="边界时区（IANA）" name="timezone" rules={[{ required: true }]}><Input placeholder="Asia/Shanghai" /></Form.Item>
            <Form.Item label="边界时刻（其他时区必填）" name="boundary_at"><Input placeholder="2026-08-01T00:00:00+08:00" /></Form.Item>
            <Form.Item label="规则版本" name="rule_version" rules={[{ required: true }]}><Input /></Form.Item>
            <Form.Item label="原批次ID（仅修订时填写）" name="parent_batch_id"><Input /></Form.Item>
          </>}
          {action && <Form.Item label={action === "freeze" ? "冻结原因" : "变更原因"} name={action === "freeze" || action === "snapshot" ? "reason" : "change_reason"} rules={[{ required: true }]}><Input.TextArea rows={2} /></Form.Item>}
        </Form>
      </Modal>
    </section>
  )
}
