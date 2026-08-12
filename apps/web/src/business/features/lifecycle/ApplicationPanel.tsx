import { Alert, Button, Checkbox, Empty, Form, Input, Modal, Select, Space, Table, Tag, Typography } from "antd"
import { useCallback, useEffect, useMemo, useState } from "react"

import { workforceApi } from "../workforce/api"
import type { LegalEntity, Person, RecruitmentRequest } from "../workforce/types"
import { lifecycleApi } from "./api"
import type { Candidate, JobApplication } from "./types"


interface ApplicationPanelProps {
  readonly token: string
  readonly canAdmin: boolean
}


interface HireFormValues {
  readonly planned_start_date: string
  readonly employee_type_code: string
  readonly contract_legal_entity_id: string
  readonly same_legal_entities: boolean
  readonly payroll_legal_entity_id?: string
  readonly social_insurance_legal_entity_id?: string
  readonly tax_legal_entity_id?: string
  readonly existing_person_id?: string
  readonly use_existing_primary_document?: boolean
  readonly probation_end_date?: string
  readonly primary_document_type_code?: string
  readonly primary_document_number?: string
  readonly primary_document_issuing_country_code?: string
  readonly primary_document_issue_date?: string
  readonly primary_document_expiry_date?: string
  readonly reason: string
}


const nextStatuses: Record<string, readonly string[]> = {
  active: ["screening", "rejected", "withdrawn"],
  screening: ["interview", "rejected", "withdrawn"],
  interview: ["offer", "rejected", "withdrawn"],
  offer: ["rejected", "withdrawn"],
}


export function ApplicationPanel({ token, canAdmin }: ApplicationPanelProps) {
  const [candidates, setCandidates] = useState<readonly Candidate[]>([])
  const [applications, setApplications] = useState<readonly JobApplication[]>([])
  const [requests, setRequests] = useState<readonly RecruitmentRequest[]>([])
  const [legalEntities, setLegalEntities] = useState<readonly LegalEntity[]>([])
  const [persons, setPersons] = useState<readonly Person[]>([])
  const [candidateOpen, setCandidateOpen] = useState(false)
  const [applicationOpen, setApplicationOpen] = useState(false)
  const [hireOpen, setHireOpen] = useState(false)
  const [hireApplicationRecord, setHireApplicationRecord] = useState<JobApplication | null>(null)
  const [hireIdempotencyKey, setHireIdempotencyKey] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [personSearching, setPersonSearching] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hireError, setHireError] = useState<string | null>(null)
  const [candidateForm] = Form.useForm()
  const [applicationForm] = Form.useForm()
  const [hireForm] = Form.useForm<HireFormValues>()
  const sameLegalEntities = Form.useWatch("same_legal_entities", hireForm) ?? true
  const existingPersonId = Form.useWatch("existing_person_id", hireForm)
  const useExistingPrimaryDocumentValue = Form.useWatch(
    "use_existing_primary_document",
    hireForm,
  )
  const useExistingPrimaryDocument = Boolean(
    existingPersonId && useExistingPrimaryDocumentValue,
  )

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [candidatePage, applicationPage, requestPage, legalPage, personPage] = await Promise.all([
        lifecycleApi.candidates(token),
        lifecycleApi.applications(token),
        workforceApi.recruitmentRequests(token),
        workforceApi.legalEntities(token),
        workforceApi.persons(token),
      ])
      setCandidates(candidatePage.items)
      setApplications(applicationPage.items)
      setRequests(requestPage.items)
      setLegalEntities(legalPage.items)
      setPersons(personPage.items)
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

  function openHire(application: JobApplication): void {
    setHireError(null)
    setHireApplicationRecord(application)
    setHireIdempotencyKey(globalThis.crypto.randomUUID())
    hireForm.setFieldsValue({
      employee_type_code: "REGULAR",
      same_legal_entities: true,
      contract_legal_entity_id: legalEntities.length === 1 ? legalEntities[0].id : undefined,
      primary_document_type_code: "NATIONAL_ID",
      primary_document_issuing_country_code: "CN",
    })
    setHireOpen(true)
  }

  function closeHire(): void {
    hireForm.resetFields()
    setHireOpen(false)
    setHireApplicationRecord(null)
    setHireIdempotencyKey(null)
    setHireError(null)
  }

  async function searchPersons(value: string): Promise<void> {
    const search = value.trim()
    if (search.length < 2) return
    setPersonSearching(true)
    setHireError(null)
    try {
      const page = await workforceApi.persons(token, search)
      setPersons(page.items)
    } catch (caught) {
      setHireError(caught instanceof Error ? caught.message : "人员档案搜索失败")
    } finally {
      setPersonSearching(false)
    }
  }

  async function confirmHire(values: HireFormValues): Promise<void> {
    if (!hireApplicationRecord || !hireIdempotencyKey) return
    const reuseDocument = Boolean(
      values.existing_person_id && values.use_existing_primary_document,
    )
    setSaving(true)
    setError(null)
    try {
      await lifecycleApi.hireApplication(token, hireApplicationRecord.id, {
        idempotency_key: hireIdempotencyKey,
        planned_start_date: values.planned_start_date,
        employee_type_code: values.employee_type_code.trim().toUpperCase(),
        contract_legal_entity_id: values.contract_legal_entity_id,
        payroll_legal_entity_id: values.same_legal_entities ? null : values.payroll_legal_entity_id || null,
        social_insurance_legal_entity_id: values.same_legal_entities ? null : values.social_insurance_legal_entity_id || null,
        tax_legal_entity_id: values.same_legal_entities ? null : values.tax_legal_entity_id || null,
        existing_person_id: values.existing_person_id || null,
        probation_end_date: values.probation_end_date || null,
        primary_document_type_code: reuseDocument
          ? null
          : values.primary_document_type_code?.trim().toUpperCase() || null,
        primary_document_number: reuseDocument
          ? null
          : values.primary_document_number?.trim() || null,
        primary_document_issuing_country_code: reuseDocument
          ? null
          : values.primary_document_issuing_country_code?.trim().toUpperCase() || null,
        primary_document_issue_date: reuseDocument ? null : values.primary_document_issue_date || null,
        primary_document_expiry_date: reuseDocument ? null : values.primary_document_expiry_date || null,
        reason: values.reason.trim(),
      })
      closeHire()
      await load()
    } catch (caught) {
      setHireError(caught instanceof Error ? caught.message : "确认录用失败")
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
  const legalEntityOptions = useMemo(() => legalEntities
    .filter((item) => item.status === "active")
    .map((item) => ({ label: `${item.name} (${item.code})`, value: item.id })), [legalEntities])
  const personOptions = useMemo(() => persons
    .map((item) => ({
      label: `${item.display_name}${item.employee_number ? ` (${item.employee_number})` : ""}`,
      value: item.id,
    })), [persons])

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
          width: 340,
          render: (_value, row) => canAdmin ? <Space wrap>
            {row.status === "offer" && <Button type="primary" size="small" loading={saving} onClick={() => openHire(row)}>确认录用</Button>}
            {(nextStatuses[row.status] ?? []).map((status) =>
              <Button key={status} size="small" loading={saving} danger={["rejected", "withdrawn"].includes(status)} onClick={() => void changeStatus(row, status)}>{status}</Button>,
            )}
          </Space> : null,
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
    <Modal
      title="确认录用并创建待入职档案"
      open={hireOpen}
      okText="确认录用"
      confirmLoading={saving}
      onOk={() => hireForm.submit()}
      onCancel={closeHire}
      width={720}
    >
      <Form<HireFormValues> form={hireForm} layout="vertical" requiredMark={false} onFinish={(values) => void confirmHire(values)}>
        {hireError && <Alert type="error" showIcon message={hireError} />}
        <Typography.Paragraph type="secondary">
          确认后将占用工号，并按招聘需求建立主组织和主职务。重复提交不会重复建档。
        </Typography.Paragraph>
        <Form.Item label="计划入职日期" name="planned_start_date" rules={[{ required: true }]}><Input type="date" /></Form.Item>
        <Form.Item label="员工类型代码" name="employee_type_code" rules={[{ required: true }]}><Input placeholder="例如 REGULAR、CAMPUS" /></Form.Item>
        <Form.Item label="合同法人主体" name="contract_legal_entity_id" rules={[{ required: true }]}>
          <Select showSearch optionFilterProp="label" options={legalEntityOptions} />
        </Form.Item>
        <Form.Item name="same_legal_entities" valuePropName="checked"><Checkbox>薪资、社保、个税主体默认与合同主体相同</Checkbox></Form.Item>
        {!sameLegalEntities && <>
          <Form.Item label="薪资法人主体" name="payroll_legal_entity_id"><Select allowClear showSearch optionFilterProp="label" options={legalEntityOptions} /></Form.Item>
          <Form.Item label="社保法人主体" name="social_insurance_legal_entity_id"><Select allowClear showSearch optionFilterProp="label" options={legalEntityOptions} /></Form.Item>
          <Form.Item label="个税法人主体" name="tax_legal_entity_id"><Select allowClear showSearch optionFilterProp="label" options={legalEntityOptions} /></Form.Item>
        </>}
        <Form.Item label="关联已有人员档案" name="existing_person_id" extra="再次入职时选择，系统会沿用原工号">
          <Select
            allowClear
            showSearch
            filterOption={false}
            loading={personSearching}
            onSearch={(value) => void searchPersons(value)}
            onChange={(value) => {
              hireForm.setFieldValue("use_existing_primary_document", Boolean(value))
            }}
            options={personOptions}
            placeholder="输入至少两个字或工号搜索"
          />
        </Form.Item>
        <Form.Item label="试用期结束日期" name="probation_end_date"><Input type="date" /></Form.Item>
        <Typography.Title level={5}>主要证件</Typography.Title>
        <Typography.Paragraph type="secondary">待入职劳动关系生效前必须存在一张已核验的有效主要证件。证件号码将加密保存，普通页面只显示脱敏值。</Typography.Paragraph>
        {existingPersonId && <Form.Item name="use_existing_primary_document" valuePropName="checked">
          <Checkbox>沿用人员档案中计划入职日有效且已核验的主要证件</Checkbox>
        </Form.Item>}
        {!useExistingPrimaryDocument && <>
          <Form.Item label="证件类型代码" name="primary_document_type_code" rules={[{ required: true }]}><Input placeholder="例如 NATIONAL_ID、PASSPORT" /></Form.Item>
          <Form.Item label="证件号码" name="primary_document_number" rules={[{ required: true }]}><Input autoComplete="off" /></Form.Item>
          <Form.Item label="签发国家/地区" name="primary_document_issuing_country_code" rules={[{ required: true }]}><Input maxLength={3} /></Form.Item>
          <Form.Item label="签发日期" name="primary_document_issue_date"><Input type="date" /></Form.Item>
          <Form.Item label="到期日期" name="primary_document_expiry_date"><Input type="date" /></Form.Item>
        </>}
        <Form.Item label="录用原因" name="reason" rules={[{ required: true }]}><Input.TextArea rows={3} /></Form.Item>
      </Form>
    </Modal>
  </div>
}
