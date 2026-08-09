import {
  Alert,
  Button,
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

import { workforceApi } from "../workforce/api"
import type {
  AgreementRelationship,
  Employment,
  LegalEntity,
  Person,
} from "../workforce/types"
import { lifecycleApi } from "./api"
import type { ContractExpiryAlert, ContractRecord } from "./types"


interface ContractPanelProps {
  readonly token: string
  readonly canAdmin: boolean
}


interface CreateContractValues {
  readonly person_id: string
  readonly relation_type: "employment" | "agreement" | "none"
  readonly employment_id?: string
  readonly agreement_relationship_id?: string
  readonly contract_type_code: string
  readonly contract_number: string
  readonly legal_entity_id?: string
  readonly signed_on?: string
  readonly effective_from: string
  readonly effective_to?: string
  readonly expiry_notice_days: number
  readonly note?: string
  readonly change_reason: string
}


interface ContractActionValues {
  readonly action_type: "amendment" | "renewal" | "termination" | "cancellation"
  readonly effective_date: string
  readonly reason: string
  readonly signed_on?: string
  readonly effective_to?: string
  readonly expiry_notice_days?: number
  readonly contract_number?: string
  readonly note?: string
}


function localToday(): string {
  const now = new Date()
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000)
    .toISOString()
    .slice(0, 10)
}


const today = localToday()


const statusLabels: Record<string, string> = {
  active: "有效",
  expired: "已到期",
  renewed: "已续签",
  terminated: "已解除",
  cancelled: "已取消",
}


export function ContractPanel({ token, canAdmin }: ContractPanelProps) {
  const [contracts, setContracts] = useState<readonly ContractRecord[]>([])
  const [alerts, setAlerts] = useState<readonly ContractExpiryAlert[]>([])
  const [persons, setPersons] = useState<readonly Person[]>([])
  const [legalEntities, setLegalEntities] = useState<readonly LegalEntity[]>([])
  const [employments, setEmployments] = useState<readonly Employment[]>([])
  const [agreements, setAgreements] = useState<readonly AgreementRelationship[]>([])
  const [selectedContract, setSelectedContract] = useState<ContractRecord | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [actionOpen, setActionOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [form] = Form.useForm<CreateContractValues>()
  const [actionForm] = Form.useForm<ContractActionValues>()
  const relationType = Form.useWatch("relation_type", form) ?? "none"
  const actionType = Form.useWatch("action_type", actionForm) ?? "amendment"

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [contractPage, alertPage, personPage, legalPage] = await Promise.all([
        lifecycleApi.contracts(token),
        lifecycleApi.contractExpiryAlerts(token),
        workforceApi.persons(token),
        workforceApi.legalEntities(token),
      ])
      setContracts(contractPage.items)
      setAlerts(alertPage.items)
      setPersons(personPage.items)
      setLegalEntities(legalPage.items)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "合同数据加载失败")
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { void load() }, [load])

  async function selectPerson(personId: string): Promise<void> {
    form.setFieldsValue({ employment_id: undefined, agreement_relationship_id: undefined })
    try {
      const archive = await workforceApi.personArchive(token, personId)
      setEmployments(archive.employments)
      setAgreements(archive.agreements)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "人员关系加载失败")
    }
  }

  async function createContract(values: CreateContractValues): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      await lifecycleApi.createContract(token, {
        person_id: values.person_id,
        employment_id: values.relation_type === "employment" ? values.employment_id : null,
        agreement_relationship_id: values.relation_type === "agreement"
          ? values.agreement_relationship_id
          : null,
        contract_type_code: values.contract_type_code,
        contract_number: values.contract_number,
        legal_entity_id: values.legal_entity_id || null,
        signed_on: values.signed_on || null,
        effective_from: values.effective_from,
        effective_to: values.effective_to || null,
        expiry_notice_days: values.expiry_notice_days,
        metadata_payload: { note: values.note || null },
        change_reason: values.change_reason,
      })
      form.resetFields()
      setEmployments([])
      setAgreements([])
      setCreateOpen(false)
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "合同创建失败")
    } finally {
      setSaving(false)
    }
  }

  function openAction(contract: ContractRecord): void {
    setSelectedContract(contract)
    actionForm.setFieldsValue({
      action_type: "amendment",
      effective_date: today,
    })
    setActionOpen(true)
  }

  async function submitAction(values: ContractActionValues): Promise<void> {
    if (!selectedContract) return
    const payload: Record<string, unknown> = {
      idempotency_key: crypto.randomUUID(),
      action_type: values.action_type,
      effective_date: values.effective_date,
      execution_mode: "direct",
      reason: values.reason,
    }
    if (values.action_type === "amendment") {
      const amendment = Object.fromEntries(Object.entries({
        signed_on: values.signed_on,
        effective_to: values.effective_to,
        expiry_notice_days: values.expiry_notice_days,
        metadata_payload: values.note ? { note: values.note } : undefined,
      }).filter(([, value]) => value !== undefined && value !== ""))
      if (Object.keys(amendment).length === 0) {
        setError("合同变更至少填写一个新值")
        return
      }
      payload.amendment = amendment
    }
    if (values.action_type === "renewal") {
      payload.renewal = {
        contract_number: values.contract_number,
        signed_on: values.signed_on || null,
        effective_to: values.effective_to || null,
        expiry_notice_days: values.expiry_notice_days ?? 30,
        metadata_payload: { note: values.note || null },
      }
    }
    setSaving(true)
    setError(null)
    try {
      await lifecycleApi.createContractAction(token, selectedContract.id, payload)
      actionForm.resetFields()
      setSelectedContract(null)
      setActionOpen(false)
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "合同动作提交失败")
    } finally {
      setSaving(false)
    }
  }

  async function refreshExpiredStatuses(): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      await lifecycleApi.processContractStatuses(token)
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "到期状态刷新失败")
    } finally {
      setSaving(false)
    }
  }

  const personOptions = useMemo(() => persons.map((item) => ({
    label: `${item.display_name} (${item.employee_number ?? "无工号"})`,
    value: item.id,
  })), [persons])
  const legalOptions = useMemo(() => legalEntities.map((item) => ({
    label: `${item.name} (${item.code})`,
    value: item.id,
  })), [legalEntities])
  const employmentOptions = useMemo(() => employments.map((item) => ({
    label: `${item.employee_type_code} · ${item.status} · ${item.planned_start_date}`,
    value: item.id,
  })), [employments])
  const agreementOptions = useMemo(() => agreements.map((item) => ({
    label: `${item.agreement_type_code} · ${item.effective_from}`,
    value: item.id,
  })), [agreements])

  return <div className="lifecycle-panel-stack">
    {error && <Alert closable onClose={() => setError(null)} type="error" showIcon title={error} />}
    {alerts.length > 0 && <Alert
      type="warning"
      showIcon
      title={`未来 90 天有 ${alerts.length} 份合同进入到期提醒期`}
      description={<Space wrap>{alerts.map((item) => <Tag key={item.contract_id} color="orange">
        {item.contract_number} · 剩余 {item.days_remaining} 天
      </Tag>)}</Space>}
    />}
    <div className="panel-heading">
      <div>
        <Typography.Title level={4}>合同与协议</Typography.Title>
        <Typography.Text type="secondary">统一管理合同创建、变更、续签、解除、取消和到期提醒；未来生效动作进入人事事件待执行队列。</Typography.Text>
      </div>
      {canAdmin && <Space>
        <Button loading={saving} onClick={() => void refreshExpiredStatuses()}>刷新到期状态</Button>
        <Button type="primary" onClick={() => setCreateOpen(true)}>新建合同/协议</Button>
      </Space>}
    </div>
    <Table
      size="small"
      loading={loading}
      rowKey="id"
      scroll={{ x: 1180 }}
      dataSource={[...contracts]}
      locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无合同记录" /> }}
      columns={[
        { title: "合同编号", dataIndex: "contract_number", width: 180 },
        { title: "人员", dataIndex: "person_id", width: 140, render: (value) => persons.find((item) => item.id === value)?.display_name ?? value },
        { title: "类型", dataIndex: "contract_type_code", width: 110 },
        { title: "法人主体", dataIndex: "legal_entity_id", width: 150, render: (value) => legalEntities.find((item) => item.id === value)?.name ?? value ?? "—" },
        { title: "签署日", dataIndex: "signed_on", width: 110, render: (value) => value ?? "—" },
        { title: "生效日", dataIndex: "effective_from", width: 110 },
        { title: "结束日", dataIndex: "effective_to", width: 110, render: (value) => value ?? "长期" },
        { title: "版本", dataIndex: "version", width: 70, render: (value) => `V${value}` },
        { title: "状态", dataIndex: "status", width: 90, render: (value) => <Tag color={value === "active" ? "success" : "default"}>{statusLabels[value] ?? value}</Tag> },
        { title: "操作", fixed: "right", width: 90, render: (_value, row) => canAdmin && ["active", "expired"].includes(row.status) ? <Button type="link" loading={saving} onClick={() => openAction(row)}>处理</Button> : null },
      ]}
    />

    <Modal title="新建合同/协议" open={createOpen} width={680} okText="保存" confirmLoading={saving} onOk={() => form.submit()} onCancel={() => setCreateOpen(false)}>
      <Form<CreateContractValues>
        form={form}
        layout="vertical"
        requiredMark={false}
        initialValues={{ relation_type: "employment", contract_type_code: "LABOR", effective_from: today, expiry_notice_days: 30 }}
        onFinish={(values) => void createContract(values)}
      >
        <Form.Item label="人员" name="person_id" rules={[{ required: true }]}><Select showSearch optionFilterProp="label" options={personOptions} onChange={(value) => void selectPerson(value)} /></Form.Item>
        <Form.Item label="关联关系" name="relation_type" rules={[{ required: true }]}><Select options={[
          { label: "劳动关系", value: "employment" },
          { label: "协议关系", value: "agreement" },
          { label: "仅关联人员", value: "none" },
        ]} /></Form.Item>
        {relationType === "employment" && <Form.Item label="劳动关系" name="employment_id" rules={[{ required: true }]}><Select options={employmentOptions} /></Form.Item>}
        {relationType === "agreement" && <Form.Item label="协议关系" name="agreement_relationship_id" rules={[{ required: true }]}><Select options={agreementOptions} /></Form.Item>}
        <Space align="start" size="large" wrap>
          <Form.Item label="合同/协议类型" name="contract_type_code" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item label="合同/协议编号" name="contract_number" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item label="法人主体" name="legal_entity_id"><Select allowClear showSearch optionFilterProp="label" options={legalOptions} style={{ width: 210 }} /></Form.Item>
        </Space>
        <Space align="start" size="large" wrap>
          <Form.Item label="签署日期" name="signed_on"><Input type="date" /></Form.Item>
          <Form.Item label="生效日期" name="effective_from" rules={[{ required: true }]}><Input type="date" /></Form.Item>
          <Form.Item label="结束日期" name="effective_to"><Input type="date" /></Form.Item>
          <Form.Item label="提前提醒天数" name="expiry_notice_days" rules={[{ required: true }]}><InputNumber min={0} max={3650} /></Form.Item>
        </Space>
        <Form.Item label="备注" name="note"><Input.TextArea rows={2} /></Form.Item>
        <Form.Item label="建档原因" name="change_reason" rules={[{ required: true }]}><Input.TextArea rows={2} /></Form.Item>
      </Form>
    </Modal>

    <Modal
      title={`处理合同：${selectedContract?.contract_number ?? ""}`}
      open={actionOpen}
      width={620}
      okText="提交"
      confirmLoading={saving}
      onOk={() => actionForm.submit()}
      onCancel={() => { setActionOpen(false); setSelectedContract(null); actionForm.resetFields() }}
    >
      <Form<ContractActionValues> form={actionForm} layout="vertical" requiredMark={false} onFinish={(values) => void submitAction(values)}>
        <Form.Item label="处理类型" name="action_type" rules={[{ required: true }]}><Select options={[
          { label: "变更", value: "amendment" },
          { label: "续签", value: "renewal" },
          { label: "解除", value: "termination" },
          { label: "取消", value: "cancellation" },
        ]} /></Form.Item>
        <Form.Item label="生效日期" name="effective_date" rules={[{ required: true }]}><Input type="date" /></Form.Item>
        {actionType === "renewal" && <Form.Item label="新合同编号" name="contract_number" rules={[{ required: true }]}><Input /></Form.Item>}
        {["amendment", "renewal"].includes(actionType) && <Space align="start" size="large" wrap>
          <Form.Item label="签署日期" name="signed_on"><Input type="date" /></Form.Item>
          <Form.Item label={actionType === "renewal" ? "新合同结束日" : "变更后结束日"} name="effective_to"><Input type="date" /></Form.Item>
          <Form.Item label="提前提醒天数" name="expiry_notice_days"><InputNumber min={0} max={3650} /></Form.Item>
        </Space>}
        {["amendment", "renewal"].includes(actionType) && <Form.Item label="备注" name="note"><Input.TextArea rows={2} /></Form.Item>}
        <Form.Item label="处理原因" name="reason" rules={[{ required: true }]}><Input.TextArea rows={2} /></Form.Item>
      </Form>
    </Modal>
  </div>
}
