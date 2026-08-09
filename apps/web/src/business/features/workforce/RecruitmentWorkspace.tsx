import {
  Alert,
  Button,
  Descriptions,
  Drawer,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from "antd"
import { useCallback, useEffect, useMemo, useState } from "react"

import { workforceApi } from "./api"
import type {
  HeadcountResultLine,
  Job,
  OrganizationOption,
  RecruitmentRequest,
} from "./types"


interface RecruitmentWorkspaceProps {
  readonly token: string
  readonly canAdmin: boolean
}


interface RequestContext {
  readonly request: RecruitmentRequest
  readonly headcount: HeadcountResultLine | null
}


const currentMonth = new Date().toISOString().slice(0, 7)
const today = new Date().toISOString().slice(0, 10)


export function RecruitmentWorkspace({ token, canAdmin }: RecruitmentWorkspaceProps) {
  const [requests, setRequests] = useState<readonly RecruitmentRequest[]>([])
  const [organizations, setOrganizations] = useState<readonly OrganizationOption[]>([])
  const [jobs, setJobs] = useState<readonly Job[]>([])
  const [context, setContext] = useState<RequestContext | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [form] = Form.useForm()

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [requestPage, organizationItems, jobPage] = await Promise.all([
        workforceApi.recruitmentRequests(token),
        workforceApi.organizations(token),
        workforceApi.jobs(token),
      ])
      setRequests(requestPage.items)
      setOrganizations(organizationItems)
      setJobs(jobPage.items)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "招聘需求加载失败")
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { void load() }, [load])

  async function createRequest(values: Record<string, unknown>): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      await workforceApi.createRecruitmentRequest(token, {
        ...values,
        target_month: values.target_month ? `${String(values.target_month)}-01` : null,
      })
      setCreateOpen(false)
      form.resetFields()
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "招聘需求创建失败")
    } finally {
      setSaving(false)
    }
  }

  async function changeStatus(item: RecruitmentRequest, status: RecruitmentRequest["status"]): Promise<void> {
    const reason = window.prompt("请输入状态变更原因")?.trim()
    if (!reason) return
    setSaving(true)
    setError(null)
    try {
      await workforceApi.updateRecruitmentRequest(token, item.id, {
        status,
        change_reason: reason,
      })
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "招聘需求状态变更失败")
    } finally {
      setSaving(false)
    }
  }

  async function showContext(item: RecruitmentRequest): Promise<void> {
    setError(null)
    try {
      const periodMonth = item.target_month ?? `${currentMonth}-01`
      const result = await workforceApi.headcountResults(
        token,
        periodMonth,
        today,
        item.organization_id,
        item.job_id,
      )
      setContext({ request: item, headcount: result.items[0] ?? null })
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "关联编制信息加载失败")
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

  return (
    <section className="workspace-section" aria-labelledby="recruitment-title">
      <div className="workspace-heading">
        <div>
          <Typography.Title id="recruitment-title" level={2}>招聘需求</Typography.Title>
          <Typography.Paragraph type="secondary">关联编制和人数只作参考；冻结、无空编或超编均不阻断招聘需求。</Typography.Paragraph>
        </div>
        {canAdmin && <Button type="primary" onClick={() => setCreateOpen(true)}>新建招聘需求</Button>}
      </div>
      {error && <Alert closable onClose={() => setError(null)} type="error" showIcon title={error} />}
      <Table
        loading={loading}
        rowKey="id"
        dataSource={[...requests]}
        locale={{ emptyText: <Empty description="暂无招聘需求" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
        columns={[
          { title: "需求编号", dataIndex: "request_number", width: 150 },
          { title: "组织", dataIndex: "organization_id", render: (value) => organizations.find((item) => item.id === value)?.name ?? value },
          { title: "职务", dataIndex: "job_id", render: (value) => jobs.find((item) => item.id === value)?.name ?? value },
          { title: "需求人数", dataIndex: "requested_count", width: 100 },
          { title: "目标月份", dataIndex: "target_month", width: 110, render: (value) => value?.slice(0, 7) || "—" },
          { title: "状态", dataIndex: "status", width: 110, render: (value) => <Tag color={value === "submitted" ? "processing" : value === "closed" ? "success" : value === "cancelled" ? "default" : "gold"}>{value}</Tag> },
          { title: "需求原因", dataIndex: "reason", ellipsis: true },
          {
            title: "操作",
            width: 260,
            render: (_value, row) => <Space wrap>
              <Button type="link" onClick={() => void showContext(row)}>查看编制</Button>
              {canAdmin && row.status === "draft" && <Button type="link" loading={saving} onClick={() => void changeStatus(row, "submitted")}>提交</Button>}
              {canAdmin && !["closed", "cancelled"].includes(row.status) && <Button type="link" loading={saving} onClick={() => void changeStatus(row, "closed")}>关闭</Button>}
              {canAdmin && !["closed", "cancelled"].includes(row.status) && <Button type="link" danger loading={saving} onClick={() => void changeStatus(row, "cancelled")}>取消</Button>}
            </Space>,
          },
        ]}
      />

      <Modal title="新建招聘需求" open={createOpen} okText="保存草稿" confirmLoading={saving} onOk={() => form.submit()} onCancel={() => setCreateOpen(false)}>
        <Form form={form} layout="vertical" requiredMark={false} onFinish={(values) => void createRequest(values)}>
          <Form.Item label="组织" name="organization_id" rules={[{ required: true }]}><Select showSearch optionFilterProp="label" options={organizationOptions} /></Form.Item>
          <Form.Item label="职务" name="job_id" rules={[{ required: true }]}><Select showSearch optionFilterProp="label" options={jobOptions} /></Form.Item>
          <Form.Item label="需求人数" name="requested_count" rules={[{ required: true }]}><InputNumber min={1} precision={0} /></Form.Item>
          <Form.Item label="目标月份" name="target_month" initialValue={currentMonth}><Input type="month" /></Form.Item>
          <Form.Item label="需求原因" name="reason" rules={[{ required: true }]}><Input.TextArea rows={3} /></Form.Item>
        </Form>
      </Modal>

      <Drawer size="large" title={context ? `${context.request.request_number} · 编制参考` : "编制参考"} open={Boolean(context)} onClose={() => setContext(null)}>
        {context && <>
          <Alert type="info" showIcon title="参考信息不会阻断招聘" description="招聘人数不会预占编制，需求状态变化也不会修改编制。" />
          {context.headcount ? <Descriptions bordered column={2} className="drawer-descriptions">
            <Descriptions.Item label="月度编制">{context.headcount.planned_count}</Descriptions.Item>
            <Descriptions.Item label="当前人数">{context.headcount.current_count}</Descriptions.Item>
            <Descriptions.Item label="差额">{context.headcount.variance}</Descriptions.Item>
            <Descriptions.Item label="需求人数">{context.request.requested_count}</Descriptions.Item>
            <Descriptions.Item label="冻结状态"><Tag color={context.headcount.frozen ? "red" : "default"}>{context.headcount.frozen ? "已冻结" : "未冻结"}</Tag></Descriptions.Item>
            <Descriptions.Item label="编制版本">v{context.headcount.plan_version}</Descriptions.Item>
          </Descriptions> : <Empty description="相同组织、职务和月份暂无编制记录；仍可继续招聘" />}
        </>}
      </Drawer>
    </section>
  )
}
