import { Alert, Button, Empty, Form, Input, Modal, Select, Space, Table, Tag, Typography } from "antd"
import { useCallback, useEffect, useMemo, useState } from "react"

import { workforceApi } from "../workforce/api"
import type { RecruitmentRequest } from "../workforce/types"
import { lifecycleApi } from "./api"
import type { Candidate, JobApplication } from "./types"


interface ApplicationPanelProps {
  readonly token: string
  readonly canAdmin: boolean
}


const nextStatuses: Record<string, readonly string[]> = {
  active: ["screening", "rejected", "withdrawn"],
  screening: ["interview", "rejected", "withdrawn"],
  interview: ["offer", "rejected", "withdrawn"],
  offer: ["hired", "rejected", "withdrawn"],
}


export function ApplicationPanel({ token, canAdmin }: ApplicationPanelProps) {
  const [candidates, setCandidates] = useState<readonly Candidate[]>([])
  const [applications, setApplications] = useState<readonly JobApplication[]>([])
  const [requests, setRequests] = useState<readonly RecruitmentRequest[]>([])
  const [candidateOpen, setCandidateOpen] = useState(false)
  const [applicationOpen, setApplicationOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [candidateForm] = Form.useForm()
  const [applicationForm] = Form.useForm()

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [candidatePage, applicationPage, requestPage] = await Promise.all([
        lifecycleApi.candidates(token),
        lifecycleApi.applications(token),
        workforceApi.recruitmentRequests(token),
      ])
      setCandidates(candidatePage.items)
      setApplications(applicationPage.items)
      setRequests(requestPage.items)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "应聘数据加载失败")
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { void load() }, [load])

  async function createCandidate(values: Record<string, string>): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      await lifecycleApi.createCandidate(token, {
        display_name: values.display_name,
        contact_payload: { mobile: values.mobile || null, email: values.email || null },
      })
      candidateForm.resetFields()
      setCandidateOpen(false)
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "候选人创建失败")
    } finally {
      setSaving(false)
    }
  }

  async function createApplication(values: Record<string, string>): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      await lifecycleApi.createApplication(token, {
        candidate_id: values.candidate_id,
        recruitment_request_id: values.recruitment_request_id,
        current_stage: "screening",
      })
      applicationForm.resetFields()
      setApplicationOpen(false)
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "应聘记录创建失败")
    } finally {
      setSaving(false)
    }
  }

  async function changeStatus(application: JobApplication, status: string): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      await lifecycleApi.updateApplication(token, application.id, {
        status,
        current_stage: status,
        change_reason: `主管理员推进至 ${status}`,
      })
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "应聘状态变更失败")
    } finally {
      setSaving(false)
    }
  }

  async function deactivateCandidate(candidate: Candidate): Promise<void> {
    const reason = window.prompt("请输入停用候选人的原因")?.trim()
    if (!reason) return
    setSaving(true)
    try {
      await lifecycleApi.updateCandidate(token, candidate.id, { status: "inactive", change_reason: reason })
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "候选人停用失败")
    } finally {
      setSaving(false)
    }
  }

  const candidateOptions = useMemo(() => candidates
    .filter((item) => item.status === "active")
    .map((item) => ({ label: `${item.display_name} (${item.candidate_number})`, value: item.id })), [candidates])
  const requestOptions = useMemo(() => requests
    .filter((item) => !["closed", "cancelled"].includes(item.status))
    .map((item) => ({ label: `${item.request_number} · ${item.requested_count}人`, value: item.id })), [requests])

  return <div className="lifecycle-panel-stack">
    {error && <Alert closable onClose={() => setError(null)} type="error" showIcon message={error} />}
    <div className="panel-heading">
      <div>
        <Typography.Title level={4}>候选人</Typography.Title>
        <Typography.Text type="secondary">候选人是招聘过程记录；录用后可关联人员档案。</Typography.Text>
      </div>
      {canAdmin && <Space>
        <Button onClick={() => setCandidateOpen(true)}>新建候选人</Button>
        <Button type="primary" onClick={() => setApplicationOpen(true)}>登记应聘</Button>
      </Space>}
    </div>
    <Table
      size="small"
      loading={loading}
      rowKey="id"
      dataSource={[...candidates]}
      locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无候选人" /> }}
      columns={[
        { title: "候选人编号", dataIndex: "candidate_number", width: 160 },
        { title: "姓名", dataIndex: "display_name" },
        { title: "手机", render: (_value, row) => String(row.contact_payload.mobile ?? "—") },
        { title: "邮箱", render: (_value, row) => String(row.contact_payload.email ?? "—") },
        { title: "状态", dataIndex: "status", width: 100, render: (value) => <Tag color={value === "active" ? "processing" : value === "converted" ? "success" : "default"}>{value}</Tag> },
        { title: "人员档案", dataIndex: "linked_person_id", ellipsis: true, render: (value) => value ?? "—" },
        { title: "操作", width: 100, render: (_value, row) => canAdmin && row.status === "active" ? <Button type="link" danger loading={saving} onClick={() => void deactivateCandidate(row)}>停用</Button> : null },
      ]}
    />

    <Typography.Title level={4}>应聘记录</Typography.Title>
    <Table
      size="small"
      loading={loading}
      rowKey="id"
      dataSource={[...applications]}
      columns={[
        { title: "候选人", dataIndex: "candidate_id", render: (value) => candidates.find((item) => item.id === value)?.display_name ?? value },
        { title: "招聘需求", dataIndex: "recruitment_request_id", render: (value) => requests.find((item) => item.id === value)?.request_number ?? value },
        { title: "当前阶段", dataIndex: "current_stage", width: 130, render: (value) => value ?? "—" },
        { title: "状态", dataIndex: "status", width: 110, render: (value) => <Tag color={value === "hired" ? "success" : ["rejected", "withdrawn"].includes(value) ? "default" : "processing"}>{value}</Tag> },
        {
          title: "推进",
          width: 260,
          render: (_value, row) => canAdmin ? <Space wrap>{(nextStatuses[row.status] ?? []).map((status) =>
            <Button key={status} size="small" loading={saving} danger={["rejected", "withdrawn"].includes(status)} onClick={() => void changeStatus(row, status)}>{status}</Button>,
          )}</Space> : null,
        },
      ]}
    />

    <Modal title="新建候选人" open={candidateOpen} okText="保存" confirmLoading={saving} onOk={() => candidateForm.submit()} onCancel={() => setCandidateOpen(false)}>
      <Form form={candidateForm} layout="vertical" requiredMark={false} onFinish={(values) => void createCandidate(values)}>
        <Form.Item label="姓名" name="display_name" rules={[{ required: true }]}><Input /></Form.Item>
        <Form.Item label="手机" name="mobile"><Input /></Form.Item>
        <Form.Item label="邮箱" name="email" rules={[{ type: "email" }]}><Input /></Form.Item>
      </Form>
    </Modal>
    <Modal title="登记应聘" open={applicationOpen} okText="保存" confirmLoading={saving} onOk={() => applicationForm.submit()} onCancel={() => setApplicationOpen(false)}>
      <Form form={applicationForm} layout="vertical" requiredMark={false} onFinish={(values) => void createApplication(values)}>
        <Form.Item label="候选人" name="candidate_id" rules={[{ required: true }]}><Select showSearch optionFilterProp="label" options={candidateOptions} /></Form.Item>
        <Form.Item label="招聘需求" name="recruitment_request_id" rules={[{ required: true }]}><Select showSearch optionFilterProp="label" options={requestOptions} /></Form.Item>
      </Form>
    </Modal>
  </div>
}
