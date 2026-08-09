import { Alert, Button, Empty, Form, Input, Modal, Select, Space, Table, Tag, Typography } from "antd"
import { useCallback, useEffect, useMemo, useState } from "react"

import { workforceApi } from "../workforce/api"
import type { Employment, LegalEntity, Person } from "../workforce/types"
import { lifecycleApi } from "./api"
import type { ContractRecord } from "./types"


interface ContractPanelProps {
  readonly token: string
  readonly canAdmin: boolean
}


const today = new Date().toISOString().slice(0, 10)


export function ContractPanel({ token, canAdmin }: ContractPanelProps) {
  const [contracts, setContracts] = useState<readonly ContractRecord[]>([])
  const [persons, setPersons] = useState<readonly Person[]>([])
  const [legalEntities, setLegalEntities] = useState<readonly LegalEntity[]>([])
  const [employments, setEmployments] = useState<readonly Employment[]>([])
  const [createOpen, setCreateOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [form] = Form.useForm()

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [contractPage, personPage, legalPage] = await Promise.all([
        lifecycleApi.contracts(token),
        workforceApi.persons(token),
        workforceApi.legalEntities(token),
      ])
      setContracts(contractPage.items)
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
    form.setFieldValue("employment_id", undefined)
    try {
      const archive = await workforceApi.personArchive(token, personId)
      setEmployments(archive.employments)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "劳动关系加载失败")
    }
  }

  async function createContract(values: Record<string, string>): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      await lifecycleApi.createContract(token, {
        person_id: values.person_id,
        employment_id: values.employment_id || null,
        contract_type_code: values.contract_type_code,
        contract_number: values.contract_number,
        legal_entity_id: values.legal_entity_id || null,
        effective_from: values.effective_from,
        effective_to: values.effective_to || null,
        metadata_payload: { note: values.note || null },
      })
      form.resetFields()
      setEmployments([])
      setCreateOpen(false)
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "合同创建失败")
    } finally {
      setSaving(false)
    }
  }

  async function closeContract(contract: ContractRecord): Promise<void> {
    const reason = window.prompt("请输入终止合同的原因")?.trim()
    if (!reason) return
    setSaving(true)
    setError(null)
    try {
      await lifecycleApi.updateContract(token, contract.id, {
        status: "terminated",
        effective_to: today,
        change_reason: reason,
      })
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "合同终止失败")
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

  return <div className="lifecycle-panel-stack">
    {error && <Alert closable onClose={() => setError(null)} type="error" showIcon message={error} />}
    <div className="panel-heading">
      <div>
        <Typography.Title level={4}>合同与协议</Typography.Title>
        <Typography.Text type="secondary">合同记录可关联人员、劳动关系和法人主体；协议关系仍在人员档案独立维护。</Typography.Text>
      </div>
      {canAdmin && <Button type="primary" onClick={() => setCreateOpen(true)}>新建合同</Button>}
    </div>
    <Table
      size="small"
      loading={loading}
      rowKey="id"
      dataSource={[...contracts]}
      locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无合同记录" /> }}
      columns={[
        { title: "合同编号", dataIndex: "contract_number", width: 180 },
        { title: "人员", dataIndex: "person_id", render: (value) => persons.find((item) => item.id === value)?.display_name ?? value },
        { title: "类型", dataIndex: "contract_type_code", width: 120 },
        { title: "法人主体", dataIndex: "legal_entity_id", render: (value) => legalEntities.find((item) => item.id === value)?.name ?? value ?? "—" },
        { title: "开始", dataIndex: "effective_from", width: 110 },
        { title: "结束", dataIndex: "effective_to", width: 110, render: (value) => value ?? "—" },
        { title: "状态", dataIndex: "status", width: 100, render: (value) => <Tag color={value === "active" ? "success" : "default"}>{value}</Tag> },
        { title: "操作", width: 100, render: (_value, row) => canAdmin && row.status === "active" ? <Button type="link" danger loading={saving} onClick={() => void closeContract(row)}>终止</Button> : null },
      ]}
    />

    <Modal title="新建合同" open={createOpen} okText="保存" confirmLoading={saving} onOk={() => form.submit()} onCancel={() => setCreateOpen(false)}>
      <Form form={form} layout="vertical" requiredMark={false} onFinish={(values) => void createContract(values)}>
        <Form.Item label="人员" name="person_id" rules={[{ required: true }]}><Select showSearch optionFilterProp="label" options={personOptions} onChange={(value) => void selectPerson(value)} /></Form.Item>
        <Form.Item label="劳动关系（可选）" name="employment_id"><Select allowClear options={employmentOptions} /></Form.Item>
        <Form.Item label="合同类型" name="contract_type_code" initialValue="LABOR" rules={[{ required: true }]}><Input /></Form.Item>
        <Form.Item label="合同编号" name="contract_number" rules={[{ required: true }]}><Input /></Form.Item>
        <Form.Item label="法人主体" name="legal_entity_id"><Select allowClear showSearch optionFilterProp="label" options={legalOptions} /></Form.Item>
        <Space align="start" size="large">
          <Form.Item label="生效日期" name="effective_from" initialValue={today} rules={[{ required: true }]}><Input type="date" /></Form.Item>
          <Form.Item label="结束日期" name="effective_to"><Input type="date" /></Form.Item>
        </Space>
        <Form.Item label="备注" name="note"><Input.TextArea rows={2} /></Form.Item>
      </Form>
    </Modal>
  </div>
}
