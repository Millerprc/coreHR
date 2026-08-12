import { Alert, Button, Divider, Form, Input, Modal, Select, Space, Table, Tabs, Tag, Typography } from "antd"
import { useCallback, useEffect, useState } from "react"

import { workforceApi } from "./api"
import type { PersonnelSubrecords } from "./types"


type CreateAction = "document" | "contact" | "address" | "emergency" | "education" | "work" | "family" | null

interface RevealTarget {
  readonly recordType: string
  readonly recordId: string
  readonly fieldCode: string
  readonly label: string
}

interface RecordActionTarget {
  readonly recordType: string
  readonly resourcePath: string
  readonly recordId: string
  readonly label: string
  readonly currentEffectiveTo: string | null
  readonly initialValues: Readonly<Record<string, unknown>>
}

interface PersonnelSubrecordsPanelProps {
  readonly token: string
  readonly personId: string
  readonly canAdmin: boolean
}


function localDate(): string {
  const now = new Date()
  const offset = now.getTimezoneOffset() * 60_000
  return new Date(now.getTime() - offset).toISOString().slice(0, 10)
}


const today = localDate()
const emptyData: PersonnelSubrecords = {
  documents: [],
  contacts: [],
  addresses: [],
  emergencyContacts: [],
  educationRecords: [],
  workExperiences: [],
  familyMembers: [],
}


export function PersonnelSubrecordsPanel({ token, personId, canAdmin }: PersonnelSubrecordsPanelProps) {
  const [data, setData] = useState<PersonnelSubrecords>(emptyData)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [action, setAction] = useState<CreateAction>(null)
  const [revealTarget, setRevealTarget] = useState<RevealTarget | null>(null)
  const [revealedValue, setRevealedValue] = useState<string | null>(null)
  const [recordActionTarget, setRecordActionTarget] = useState<RecordActionTarget | null>(null)
  const [recordAction, setRecordAction] = useState<"correct" | "expire" | null>(null)
  const [form] = Form.useForm()
  const [revealForm] = Form.useForm()
  const [recordActionForm] = Form.useForm()

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [documents, contacts, addresses, emergencyContacts, educationRecords, workExperiences, familyMembers] = await Promise.all([
        workforceApi.personDocuments(token, personId),
        workforceApi.personContacts(token, personId),
        workforceApi.personAddresses(token, personId),
        workforceApi.emergencyContacts(token, personId),
        workforceApi.educationRecords(token, personId),
        workforceApi.workExperiences(token, personId),
        workforceApi.familyMembers(token, personId),
      ])
      setData({ documents, contacts, addresses, emergencyContacts, educationRecords, workExperiences, familyMembers })
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "人员子档案加载失败")
    } finally {
      setLoading(false)
    }
  }, [personId, token])

  useEffect(() => { void load() }, [load])

  function openCreate(nextAction: Exclude<CreateAction, null>): void {
    form.resetFields()
    setAction(nextAction)
  }

  async function save(values: Record<string, unknown>): Promise<void> {
    if (!action) return
    setSaving(true)
    setError(null)
    try {
      const commands = {
        document: workforceApi.createPersonDocument,
        contact: workforceApi.createPersonContact,
        address: workforceApi.createPersonAddress,
        emergency: workforceApi.createEmergencyContact,
        education: workforceApi.createEducationRecord,
        work: workforceApi.createWorkExperience,
        family: workforceApi.createFamilyMember,
      }
      await commands[action](token, personId, values)
      setAction(null)
      form.resetFields()
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "人员子档案保存失败")
    } finally {
      setSaving(false)
    }
  }

  async function reveal(values: { reason: string }): Promise<void> {
    if (!revealTarget) return
    setSaving(true)
    setError(null)
    try {
      const response = await workforceApi.revealSensitiveValue(
        token,
        personId,
        revealTarget.recordType,
        revealTarget.recordId,
        revealTarget.fieldCode,
        values.reason,
      )
      setRevealedValue(response.value)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "敏感字段读取失败")
    } finally {
      setSaving(false)
    }
  }

  function closeReveal(): void {
    setRevealedValue(null)
    setRevealTarget(null)
    revealForm.resetFields()
  }

  function openRecordAction(target: RecordActionTarget, actionType: "correct" | "expire"): void {
    recordActionForm.resetFields()
    recordActionForm.setFieldsValue({
      ...target.initialValues,
      effective_to: target.currentEffectiveTo ?? undefined,
    })
    setRecordActionTarget(target)
    setRecordAction(actionType)
  }

  async function saveRecordAction(values: Record<string, unknown>): Promise<void> {
    if (!recordActionTarget || !recordAction) return
    setSaving(true)
    setError(null)
    try {
      if (recordAction === "expire") {
        await workforceApi.expireSensitiveRecord(
          token,
          personId,
          recordActionTarget.recordType,
          recordActionTarget.recordId,
          String(values.effective_to),
          String(values.reason),
        )
      } else {
        const changes: Record<string, unknown> = {}
        for (const [field, value] of Object.entries(values)) {
          if (field === "reason" || value === undefined) continue
          const initialValue = field === "effective_to"
            ? recordActionTarget.currentEffectiveTo
            : recordActionTarget.initialValues[field]
          if (value === initialValue || (value === "" && initialValue == null)) continue
          changes[field] = value === "" ? null : value
        }
        if (Object.keys(changes).length === 0) {
          throw new Error("请至少修改一项档案内容")
        }
        await workforceApi.updateSensitiveRecord(
          token,
          personId,
          recordActionTarget.resourcePath,
          recordActionTarget.recordId,
          {
            ...changes,
            change_reason: String(values.reason),
          },
        )
      }
      setRecordAction(null)
      setRecordActionTarget(null)
      recordActionForm.resetFields()
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "档案记录维护失败")
    } finally {
      setSaving(false)
    }
  }

  const actionCell = (target: RecordActionTarget) => canAdmin ? <Space>
    <Button size="small" onClick={() => openRecordAction(target, "correct")}>更正</Button>
    <Button size="small" danger disabled={Boolean(target.currentEffectiveTo)} onClick={() => openRecordAction(target, "expire")}>失效</Button>
  </Space> : null

  const revealCell = (
    masked: string | null,
    target: RevealTarget,
  ) => <Space><Typography.Text>{masked || "—"}</Typography.Text>{masked && canAdmin && <Button size="small" onClick={() => setRevealTarget(target)}>查看明文</Button>}</Space>

  const createTitles: Record<Exclude<CreateAction, null>, string> = {
    document: "新增证件",
    contact: "新增联系方式",
    address: "新增地址",
    emergency: "新增紧急联系人",
    education: "新增教育经历",
    work: "新增工作经历",
    family: "新增家庭成员",
  }

  return <>
    {error && <Alert closable onClose={() => setError(null)} type="error" showIcon title={error} />}
    <Tabs items={[
      {
        key: "documents",
        label: `证件 ${data.documents.length}`,
        children: <><Space className="tab-actions">{canAdmin && <Button type="primary" onClick={() => openCreate("document")}>新增证件</Button>}</Space><Table loading={loading} rowKey="id" pagination={false} dataSource={[...data.documents]} columns={[
          { title: "证件类型", dataIndex: "document_type_code" },
          { title: "证件号码", dataIndex: "masked_document_number", render: (value, row) => revealCell(value, { recordType: "document", recordId: row.id, fieldCode: "document_number", label: "证件号码" }) },
          { title: "签发国家/地区", dataIndex: "issuing_country_code" },
          { title: "有效期", render: (_value, row) => `${row.issue_date || "—"} 至 ${row.expiry_date || "长期"}` },
          { title: "主要证件", dataIndex: "is_primary", render: (value) => value ? <Tag color="blue">是</Tag> : "否" },
          { title: "校验状态", dataIndex: "verification_status" },
          { title: "维护", render: (_value, row) => actionCell({
            recordType: "document",
            resourcePath: "documents",
            recordId: row.id,
            label: "证件",
            currentEffectiveTo: row.effective_to,
            initialValues: {
              document_type_code: row.document_type_code,
              issuing_country_code: row.issuing_country_code,
              issue_date: row.issue_date,
              expiry_date: row.expiry_date,
              is_primary: row.is_primary,
              verification_status: row.verification_status,
              effective_from: row.effective_from,
            },
          }) },
        ]} /></>,
      },
      {
        key: "contacts",
        label: `联系信息 ${data.contacts.length + data.addresses.length + data.emergencyContacts.length}`,
        children: <>
          <Space className="tab-actions">{canAdmin && <><Button onClick={() => openCreate("contact")}>新增联系方式</Button><Button onClick={() => openCreate("address")}>新增地址</Button><Button onClick={() => openCreate("emergency")}>新增紧急联系人</Button></>}</Space>
          <Divider>联系方式</Divider>
          <Table loading={loading} rowKey="id" pagination={false} dataSource={[...data.contacts]} columns={[
            { title: "类型", dataIndex: "contact_type" },
            { title: "内容", dataIndex: "masked_contact_value", render: (value, row) => revealCell(value, { recordType: "contact", recordId: row.id, fieldCode: "contact_value", label: "联系方式" }) },
            { title: "主要", dataIndex: "is_primary", render: (value) => value ? "是" : "否" },
            { title: "生效日期", dataIndex: "effective_from" },
            { title: "维护", render: (_value, row) => actionCell({
              recordType: "contact",
              resourcePath: "contacts",
              recordId: row.id,
              label: "联系方式",
              currentEffectiveTo: row.effective_to,
              initialValues: {
                contact_type: row.contact_type,
                is_primary: row.is_primary,
                effective_from: row.effective_from,
              },
            }) },
          ]} />
          <Divider>地址</Divider>
          <Table loading={loading} rowKey="id" pagination={false} dataSource={[...data.addresses]} columns={[
            { title: "类型", dataIndex: "address_type" },
            { title: "国家/地区", dataIndex: "country_code" },
            { title: "行政区", dataIndex: "region_code", render: (value) => value || "—" },
            { title: "详细地址", dataIndex: "masked_address_detail", render: (value, row) => revealCell(value, { recordType: "address", recordId: row.id, fieldCode: "address_detail", label: "详细地址" }) },
            { title: "维护", render: (_value, row) => actionCell({
              recordType: "address",
              resourcePath: "addresses",
              recordId: row.id,
              label: "地址",
              currentEffectiveTo: row.effective_to,
              initialValues: {
                address_type: row.address_type,
                country_code: row.country_code,
                region_code: row.region_code,
                effective_from: row.effective_from,
              },
            }) },
          ]} />
          <Divider>紧急联系人</Divider>
          <Table loading={loading} rowKey="id" pagination={false} dataSource={[...data.emergencyContacts]} columns={[
            { title: "姓名", dataIndex: "masked_name", render: (value, row) => revealCell(value, { recordType: "emergency_contact", recordId: row.id, fieldCode: "name", label: "紧急联系人姓名" }) },
            { title: "关系", dataIndex: "relationship_code" },
            { title: "电话", dataIndex: "masked_phone", render: (value, row) => revealCell(value, { recordType: "emergency_contact", recordId: row.id, fieldCode: "phone", label: "紧急联系人电话" }) },
            { title: "维护", render: (_value, row) => actionCell({
              recordType: "emergency_contact",
              resourcePath: "emergency-contacts",
              recordId: row.id,
              label: "紧急联系人",
              currentEffectiveTo: row.effective_to,
              initialValues: {
                relationship_code: row.relationship_code,
                effective_from: row.effective_from,
              },
            }) },
          ]} />
        </>,
      },
      {
        key: "education",
        label: `教育经历 ${data.educationRecords.length}`,
        children: <><Space className="tab-actions">{canAdmin && <Button type="primary" onClick={() => openCreate("education")}>新增教育经历</Button>}</Space><Table loading={loading} rowKey="id" pagination={false} dataSource={[...data.educationRecords]} columns={[
          { title: "院校", dataIndex: "masked_institution_name", render: (value, row) => revealCell(value, { recordType: "education", recordId: row.id, fieldCode: "institution_name", label: "院校名称" }) },
          { title: "学历", dataIndex: "education_level_code" },
          { title: "专业", dataIndex: "masked_major_name", render: (value, row) => revealCell(value, { recordType: "education", recordId: row.id, fieldCode: "major_name", label: "专业名称" }) },
          { title: "起止日期", render: (_value, row) => `${row.study_start_date} 至 ${row.study_end_date || "至今"}` },
          { title: "维护", render: (_value, row) => actionCell({
            recordType: "education",
            resourcePath: "education-records",
            recordId: row.id,
            label: "教育经历",
            currentEffectiveTo: row.effective_to,
            initialValues: {
              education_level_code: row.education_level_code,
              study_start_date: row.study_start_date,
              study_end_date: row.study_end_date,
              effective_from: row.effective_from,
            },
          }) },
        ]} /></>,
      },
      {
        key: "work",
        label: `工作经历 ${data.workExperiences.length}`,
        children: <><Space className="tab-actions">{canAdmin && <Button type="primary" onClick={() => openCreate("work")}>新增工作经历</Button>}</Space><Table loading={loading} rowKey="id" pagination={false} dataSource={[...data.workExperiences]} columns={[
          { title: "单位", dataIndex: "masked_employer_name", render: (value, row) => revealCell(value, { recordType: "work_experience", recordId: row.id, fieldCode: "employer_name", label: "工作单位" }) },
          { title: "职务", dataIndex: "masked_job_title", render: (value, row) => revealCell(value, { recordType: "work_experience", recordId: row.id, fieldCode: "job_title", label: "原职务" }) },
          { title: "起止日期", render: (_value, row) => `${row.work_start_date} 至 ${row.work_end_date || "至今"}` },
          { title: "维护", render: (_value, row) => actionCell({
            recordType: "work_experience",
            resourcePath: "work-experiences",
            recordId: row.id,
            label: "工作经历",
            currentEffectiveTo: row.effective_to,
            initialValues: {
              work_start_date: row.work_start_date,
              work_end_date: row.work_end_date,
              effective_from: row.effective_from,
            },
          }) },
        ]} /></>,
      },
      {
        key: "family",
        label: `家庭成员 ${data.familyMembers.length}`,
        children: <><Space className="tab-actions">{canAdmin && <Button type="primary" onClick={() => openCreate("family")}>新增家庭成员</Button>}</Space><Table loading={loading} rowKey="id" pagination={false} dataSource={[...data.familyMembers]} columns={[
          { title: "姓名", dataIndex: "masked_name", render: (value, row) => revealCell(value, { recordType: "family_member", recordId: row.id, fieldCode: "name", label: "家庭成员姓名" }) },
          { title: "关系", dataIndex: "relationship_code" },
          { title: "生效日期", dataIndex: "effective_from" },
          { title: "维护", render: (_value, row) => actionCell({
            recordType: "family_member",
            resourcePath: "family-members",
            recordId: row.id,
            label: "家庭成员",
            currentEffectiveTo: row.effective_to,
            initialValues: {
              relationship_code: row.relationship_code,
              effective_from: row.effective_from,
            },
          }) },
        ]} /></>,
      },
    ]} />

    <Modal destroyOnHidden title={action ? createTitles[action] : ""} open={Boolean(action)} okText="保存" confirmLoading={saving} onOk={() => form.submit()} onCancel={() => setAction(null)}>
      <Form form={form} layout="vertical" requiredMark={false} onFinish={(values) => void save(values)}>
        {action === "document" && <>
          <Form.Item label="证件类型" name="document_type_code" rules={[{ required: true }]}><Input placeholder="例如 NATIONAL_ID、PASSPORT" /></Form.Item>
          <Form.Item label="证件号码" name="document_number" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item label="签发国家/地区" name="issuing_country_code" initialValue="CN" rules={[{ required: true }]}><Input maxLength={3} /></Form.Item>
          <Form.Item label="签发日期" name="issue_date"><Input type="date" /></Form.Item>
          <Form.Item label="到期日期" name="expiry_date"><Input type="date" /></Form.Item>
          <Form.Item label="是否主要证件" name="is_primary" initialValue={true}><Select options={[{ value: true, label: "是" }, { value: false, label: "否" }]} /></Form.Item>
        </>}
        {action === "contact" && <>
          <Form.Item label="联系方式类型" name="contact_type" rules={[{ required: true }]}><Select options={[
            { value: "personal_phone", label: "个人手机" }, { value: "work_phone", label: "工作电话" }, { value: "personal_email", label: "个人邮箱" }, { value: "work_email", label: "工作邮箱" },
          ]} /></Form.Item>
          <Form.Item label="联系方式" name="contact_value" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item label="是否主要联系方式" name="is_primary" initialValue={false}><Select options={[{ value: true, label: "是" }, { value: false, label: "否" }]} /></Form.Item>
        </>}
        {action === "address" && <>
          <Form.Item label="地址类型" name="address_type" rules={[{ required: true }]}><Select options={[{ value: "residential", label: "常住地址" }, { value: "mailing", label: "通讯地址" }]} /></Form.Item>
          <Form.Item label="国家/地区" name="country_code" initialValue="CN" rules={[{ required: true }]}><Input maxLength={3} /></Form.Item>
          <Form.Item label="行政区代码" name="region_code"><Input /></Form.Item>
          <Form.Item label="详细地址" name="address_detail" rules={[{ required: true }]}><Input.TextArea rows={2} /></Form.Item>
        </>}
        {action === "emergency" && <>
          <Form.Item label="姓名" name="name" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item label="与本人关系" name="relationship_code" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item label="电话" name="phone" rules={[{ required: true }]}><Input /></Form.Item>
        </>}
        {action === "education" && <>
          <Form.Item label="院校名称" name="institution_name" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item label="学历代码" name="education_level_code" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item label="专业名称" name="major_name"><Input /></Form.Item>
          <Form.Item label="入学日期" name="study_start_date" rules={[{ required: true }]}><Input type="date" /></Form.Item>
          <Form.Item label="毕业日期" name="study_end_date"><Input type="date" /></Form.Item>
        </>}
        {action === "work" && <>
          <Form.Item label="工作单位" name="employer_name" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item label="职务" name="job_title"><Input /></Form.Item>
          <Form.Item label="开始日期" name="work_start_date" rules={[{ required: true }]}><Input type="date" /></Form.Item>
          <Form.Item label="结束日期" name="work_end_date"><Input type="date" /></Form.Item>
        </>}
        {action === "family" && <>
          <Form.Item label="姓名" name="name" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item label="与本人关系" name="relationship_code" rules={[{ required: true }]}><Input /></Form.Item>
        </>}
        {action && <>
          <Form.Item label="生效日期" name="effective_from" initialValue={today} rules={[{ required: true }]}><Input type="date" /></Form.Item>
          <Form.Item label="失效日期" name="effective_to"><Input type="date" /></Form.Item>
          <Form.Item label="变更原因" name="change_reason" rules={[{ required: true }]}><Input.TextArea rows={2} /></Form.Item>
        </>}
      </Form>
    </Modal>

    <Modal destroyOnHidden title={revealTarget ? `查看${revealTarget.label}` : "查看敏感字段"} open={Boolean(revealTarget)} okText={revealedValue === null ? "确认查看" : "关闭"} confirmLoading={saving} onOk={() => revealedValue === null ? revealForm.submit() : closeReveal()} onCancel={closeReveal}>
      {revealedValue === null ? <Form form={revealForm} layout="vertical" onFinish={(values) => void reveal(values)}>
        <Alert type="warning" showIcon title="本次查看会记录操作人、原因、人员、字段和时间。" />
        <Form.Item label="查看原因" name="reason" rules={[{ required: true }]}><Input.TextArea rows={3} /></Form.Item>
      </Form> : <Typography.Text copyable>{revealedValue}</Typography.Text>}
    </Modal>

    <Modal
      destroyOnHidden
      title={recordActionTarget ? `${recordAction === "expire" ? "失效" : "更正"}${recordActionTarget.label}` : "维护档案记录"}
      open={Boolean(recordActionTarget)}
      okText={recordAction === "expire" ? "确认失效" : "保存更正"}
      confirmLoading={saving}
      onOk={() => recordActionForm.submit()}
      onCancel={() => { setRecordAction(null); setRecordActionTarget(null) }}
    >
      <Alert type="info" showIcon title="记录不会物理删除，本次操作会保留操作者、原因和变更字段。" />
      <Form form={recordActionForm} layout="vertical" onFinish={(values) => void saveRecordAction(values)}>
        {recordAction === "correct" && recordActionTarget?.recordType === "document" && <>
          <Form.Item label="证件类型" name="document_type_code"><Input /></Form.Item>
          <Form.Item label="新证件号码" name="document_number" extra="不修改时留空"><Input autoComplete="off" /></Form.Item>
          <Form.Item label="签发国家/地区" name="issuing_country_code"><Input maxLength={3} /></Form.Item>
          <Form.Item label="签发日期" name="issue_date"><Input type="date" /></Form.Item>
          <Form.Item label="到期日期" name="expiry_date"><Input type="date" /></Form.Item>
          <Form.Item label="是否主要证件" name="is_primary"><Select options={[{ value: true, label: "是" }, { value: false, label: "否" }]} /></Form.Item>
          <Form.Item label="校验状态" name="verification_status"><Select options={[{ value: "unverified", label: "未核验" }, { value: "verified", label: "已核验" }, { value: "rejected", label: "核验不通过" }]} /></Form.Item>
        </>}
        {recordAction === "correct" && recordActionTarget?.recordType === "contact" && <>
          <Form.Item label="联系方式类型" name="contact_type"><Select options={[
            { value: "personal_phone", label: "个人手机" }, { value: "work_phone", label: "工作电话" }, { value: "personal_email", label: "个人邮箱" }, { value: "work_email", label: "工作邮箱" },
          ]} /></Form.Item>
          <Form.Item label="新联系方式" name="contact_value" extra="不修改时留空；更换类型时必须重新输入"><Input autoComplete="off" /></Form.Item>
          <Form.Item label="是否主要联系方式" name="is_primary"><Select options={[{ value: true, label: "是" }, { value: false, label: "否" }]} /></Form.Item>
        </>}
        {recordAction === "correct" && recordActionTarget?.recordType === "address" && <>
          <Form.Item label="地址类型" name="address_type"><Select options={[{ value: "residential", label: "常住地址" }, { value: "mailing", label: "通讯地址" }]} /></Form.Item>
          <Form.Item label="国家/地区" name="country_code"><Input maxLength={3} /></Form.Item>
          <Form.Item label="行政区代码" name="region_code"><Input /></Form.Item>
          <Form.Item label="新详细地址" name="address_detail" extra="不修改时留空"><Input.TextArea rows={2} /></Form.Item>
        </>}
        {recordAction === "correct" && recordActionTarget?.recordType === "emergency_contact" && <>
          <Form.Item label="新姓名" name="name" extra="不修改时留空"><Input autoComplete="off" /></Form.Item>
          <Form.Item label="与本人关系" name="relationship_code"><Input /></Form.Item>
          <Form.Item label="新电话" name="phone" extra="不修改时留空"><Input autoComplete="off" /></Form.Item>
        </>}
        {recordAction === "correct" && recordActionTarget?.recordType === "education" && <>
          <Form.Item label="新院校名称" name="institution_name" extra="不修改时留空"><Input autoComplete="off" /></Form.Item>
          <Form.Item label="学历代码" name="education_level_code"><Input /></Form.Item>
          <Form.Item label="新专业名称" name="major_name" extra="不修改时留空"><Input autoComplete="off" /></Form.Item>
          <Form.Item label="入学日期" name="study_start_date"><Input type="date" /></Form.Item>
          <Form.Item label="毕业日期" name="study_end_date"><Input type="date" /></Form.Item>
        </>}
        {recordAction === "correct" && recordActionTarget?.recordType === "work_experience" && <>
          <Form.Item label="新工作单位" name="employer_name" extra="不修改时留空"><Input autoComplete="off" /></Form.Item>
          <Form.Item label="新职务" name="job_title" extra="不修改时留空"><Input autoComplete="off" /></Form.Item>
          <Form.Item label="开始日期" name="work_start_date"><Input type="date" /></Form.Item>
          <Form.Item label="结束日期" name="work_end_date"><Input type="date" /></Form.Item>
        </>}
        {recordAction === "correct" && recordActionTarget?.recordType === "family_member" && <>
          <Form.Item label="新姓名" name="name" extra="不修改时留空"><Input autoComplete="off" /></Form.Item>
          <Form.Item label="与本人关系" name="relationship_code"><Input /></Form.Item>
        </>}
        {recordAction === "correct" && <Form.Item label="生效日期" name="effective_from"><Input type="date" /></Form.Item>}
        <Form.Item label="失效日期" name="effective_to" rules={[{ required: recordAction === "expire" }]}><Input type="date" /></Form.Item>
        <Form.Item label="操作原因" name="reason" rules={[{ required: true }]}><Input.TextArea rows={3} /></Form.Item>
      </Form>
    </Modal>
  </>
}
