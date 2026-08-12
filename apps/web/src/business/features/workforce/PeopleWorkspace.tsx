import {
  Alert,
  Button,
  Descriptions,
  Drawer,
  Empty,
  Form,
  Input,
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
import { PersonnelSubrecordsPanel } from "./PersonnelSubrecordsPanel"
import type { LegalEntity, OrganizationOption, Person, PersonArchive } from "./types"


type Action = "person" | "edit" | "employment" | "legalEntityRelation" | "assignment" | "agreement" | "legal" | null


interface PeopleWorkspaceProps {
  readonly token: string
  readonly canAdmin: boolean
}


const today = new Date().toISOString().slice(0, 10)


export function PeopleWorkspace({ token, canAdmin }: PeopleWorkspaceProps) {
  const [people, setPeople] = useState<readonly Person[]>([])
  const [legalEntities, setLegalEntities] = useState<readonly LegalEntity[]>([])
  const [organizations, setOrganizations] = useState<readonly OrganizationOption[]>([])
  const [jobs, setJobs] = useState<readonly { id: string; code: string; name: string }[]>([])
  const [archive, setArchive] = useState<PersonArchive | null>(null)
  const [search, setSearch] = useState("")
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [action, setAction] = useState<Action>(null)
  const [form] = Form.useForm()

  const load = useCallback(async (query: string) => {
    setLoading(true)
    setError(null)
    try {
      const [personPage, legalPage, jobPage, organizationItems] = await Promise.all([
        workforceApi.persons(token, query),
        workforceApi.legalEntities(token),
        workforceApi.jobs(token),
        workforceApi.organizations(token),
      ])
      setPeople(personPage.items)
      setLegalEntities(legalPage.items)
      setJobs(jobPage.items)
      setOrganizations(organizationItems)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "人员中心加载失败")
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { void load("") }, [load])

  async function openArchive(personId: string): Promise<void> {
    setError(null)
    try {
      setArchive(await workforceApi.personArchive(token, personId))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "人员档案加载失败")
    }
  }

  function openAction(nextAction: Exclude<Action, null>): void {
    setAction(nextAction)
    form.resetFields()
    if (nextAction === "edit" && archive) {
      form.setFieldsValue({
        legal_name: archive.person.legal_name,
        display_name: archive.person.display_name,
        former_name: archive.person.former_name,
        gender_code: archive.person.gender_code,
        birth_date: archive.person.birth_date,
        ethnicity_code: archive.person.ethnicity_code,
        country_code: archive.person.country_code,
        nationality_code: archive.person.nationality_code,
        marital_status_code: archive.person.marital_status_code,
        political_status_code: archive.person.political_status_code,
      })
    }
  }

  async function save(values: Record<string, unknown>): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      if (action === "person") {
        const personValues = { ...values }
        if (!personValues.display_name) delete personValues.display_name
        const created = await workforceApi.createPerson(token, {
          ...personValues,
          reserve_employee_number: true,
          change_reason: values.change_reason,
        })
        await load("")
        await openArchive(created.id)
      } else if (action === "edit" && archive) {
        await workforceApi.updatePerson(token, archive.person.id, values)
        await openArchive(archive.person.id)
        await load(search)
      } else if (action === "employment" && archive) {
        await workforceApi.createEmployment(token, { ...values, person_id: archive.person.id })
        await openArchive(archive.person.id)
      } else if (action === "legalEntityRelation" && archive) {
        const { employment_id, ...command } = values
        await workforceApi.createLegalEntityRelationVersion(token, String(employment_id), command)
        await openArchive(archive.person.id)
      } else if (action === "assignment" && archive) {
        await workforceApi.createAssignment(token, values)
        await openArchive(archive.person.id)
      } else if (action === "agreement" && archive) {
        await workforceApi.createAgreement(token, { ...values, person_id: archive.person.id })
        await openArchive(archive.person.id)
      } else if (action === "legal") {
        await workforceApi.createLegalEntity(token, values)
        await load(search)
      }
      setAction(null)
      form.resetFields()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "人员档案保存失败")
    } finally {
      setSaving(false)
    }
  }

  const legalOptions = useMemo(
    () => legalEntities.map((item) => ({ label: `${item.name} (${item.code})`, value: item.id })),
    [legalEntities],
  )
  const organizationOptions = useMemo(
    () => organizations.map((item) => ({ label: `${item.name} (${item.code})`, value: item.id })),
    [organizations],
  )
  const jobOptions = useMemo(
    () => jobs.map((item) => ({ label: `${item.name} (${item.code})`, value: item.id })),
    [jobs],
  )

  const modalTitle: Record<Exclude<Action, null>, string> = {
    legalEntityRelation: "调整四类法人主体",
    person: "新建人员档案",
    edit: "更正基础档案",
    employment: "建立劳动关系",
    assignment: "新增组织职务关系",
    agreement: "登记协议关系",
    legal: "新建法人主体",
  }

  return (
    <section className="workspace-section" aria-labelledby="people-title">
      <div className="workspace-heading">
        <div>
          <Typography.Title id="people-title" level={2}>人员中心</Typography.Title>
          <Typography.Paragraph type="secondary">自然人、雇佣经历、主组织职务和协议关系分层保存。</Typography.Paragraph>
        </div>
        {canAdmin && <Space wrap><Button onClick={() => openAction("legal")}>新建法人</Button><Button type="primary" onClick={() => openAction("person")}>新建人员</Button></Space>}
      </div>
      {error && <Alert closable onClose={() => setError(null)} type="error" showIcon title={error} />}
      <div className="detail-toolbar">
        <Input.Search
          allowClear
          aria-label="搜索人员"
          placeholder="按姓名或工号搜索"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          onSearch={(value) => void load(value)}
        />
        <Typography.Text type="secondary">共 {people.length} 条</Typography.Text>
      </div>
      <Table
        loading={loading}
        rowKey="id"
        dataSource={[...people]}
        locale={{ emptyText: <Empty description="暂无人员档案" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
        onRow={(row) => ({ onClick: () => void openArchive(row.id) })}
        columns={[
          { title: "工号", dataIndex: "employee_number", width: 120, render: (value) => value || "待分配" },
          { title: "姓名", dataIndex: "display_name" },
          { title: "曾用名", dataIndex: "former_name", render: (value) => value || "—" },
          { title: "国家/地区", dataIndex: "country_code", width: 120, render: (value) => value || "—" },
          { title: "状态", dataIndex: "status", width: 110, render: (value) => <Tag color="blue">{value}</Tag> },
          { title: "操作", width: 100, render: (_value, row) => <Button type="link" onClick={(event) => { event.stopPropagation(); void openArchive(row.id) }}>查看</Button> },
        ]}
      />

      <Drawer
        size="large"
        title={archive ? `${archive.person.display_name} · ${archive.person.employee_number ?? "待分配"}` : "人员档案"}
        open={Boolean(archive)}
        onClose={() => setArchive(null)}
        extra={archive && canAdmin ? <Button onClick={() => openAction("edit")}>更正基础信息</Button> : null}
      >
        {archive && (
          <Tabs items={[
            {
              key: "basic",
              label: "基础信息",
              children: <Descriptions bordered size="small" column={2}>
                <Descriptions.Item label="法定姓名">{archive.person.legal_name}</Descriptions.Item>
                <Descriptions.Item label="姓名">{archive.person.display_name}</Descriptions.Item>
                <Descriptions.Item label="曾用名">{archive.person.former_name || "—"}</Descriptions.Item>
                <Descriptions.Item label="性别">{archive.person.gender_code || "—"}</Descriptions.Item>
                <Descriptions.Item label="出生日期">{archive.person.birth_date || "—"}</Descriptions.Item>
                <Descriptions.Item label="国籍">{archive.person.nationality_code || "—"}</Descriptions.Item>
                <Descriptions.Item label="国家/地区">{archive.person.country_code || "—"}</Descriptions.Item>
                <Descriptions.Item label="民族代码">{archive.person.ethnicity_code || "—"}</Descriptions.Item>
                <Descriptions.Item label="婚姻状况代码">{archive.person.marital_status_code || "—"}</Descriptions.Item>
                <Descriptions.Item label="政治面貌代码">{archive.person.political_status_code || "—"}</Descriptions.Item>
              </Descriptions>,
            },
            {
              key: "personnel-subrecords",
              label: "敏感与经历档案",
              children: <PersonnelSubrecordsPanel token={token} personId={archive.person.id} canAdmin={canAdmin} />,
            },
            {
              key: "employment",
              label: `劳动关系 ${archive.employments.length}`,
              children: <><Space className="tab-actions">{canAdmin && <Button type="primary" onClick={() => openAction("employment")}>建立劳动关系</Button>}</Space><Table rowKey="id" pagination={false} dataSource={[...archive.employments]} columns={[
                { title: "人员类型", dataIndex: "employee_type_code" },
                { title: "状态", dataIndex: "status", render: (value) => <Tag>{value}</Tag> },
                { title: "计划入职", dataIndex: "planned_start_date" },
                { title: "实际入职", dataIndex: "actual_start_date", render: (value) => value || "—" },
                { title: "结束日期", dataIndex: "end_date", render: (value) => value || "—" },
              ]} /></>,
            },
            {
              key: "legal-entity-history",
              label: `四类主体版本 ${archive.legal_entity_relations.length}`,
              children: <><Space className="tab-actions">{canAdmin && <Button type="primary" disabled={!archive.employments.length} onClick={() => openAction("legalEntityRelation")}>新增主体版本</Button>}</Space><Table rowKey="id" pagination={false} dataSource={[...archive.legal_entity_relations]} columns={[
                { title: "关系类型", dataIndex: "relation_kind" },
                { title: "法人主体", dataIndex: "legal_entity_id", render: (value) => legalEntities.find((item) => item.id === value)?.name ?? value },
                { title: "生效日期", dataIndex: "effective_from" },
                { title: "失效日期", dataIndex: "effective_to", render: (value) => value || "—" },
                { title: "版本", dataIndex: "version" },
                { title: "变更原因", dataIndex: "change_reason" },
              ]} /></>,
            },
            {
              key: "assignments",
              label: `组织职务 ${archive.assignments.length}`,
              children: <><Space className="tab-actions">{canAdmin && <Button type="primary" disabled={!archive.employments.length} onClick={() => openAction("assignment")}>新增关系</Button>}</Space><Table rowKey="id" pagination={false} dataSource={[...archive.assignments]} columns={[
                { title: "关系类型", dataIndex: "relation_type" },
                { title: "组织", dataIndex: "organization_id", render: (value) => organizations.find((item) => item.id === value)?.name ?? value },
                { title: "职务", dataIndex: "job_id", render: (value) => jobs.find((item) => item.id === value)?.name ?? value ?? "—" },
                { title: "生效日期", dataIndex: "effective_from" },
                { title: "失效日期", dataIndex: "effective_to", render: (value) => value || "—" },
              ]} /></>,
            },
            {
              key: "agreements",
              label: `协议关系 ${archive.agreements.length}`,
              children: <><Space className="tab-actions">{canAdmin && <Button type="primary" onClick={() => openAction("agreement")}>登记协议关系</Button>}</Space><Table rowKey="id" pagination={false} dataSource={[...archive.agreements]} columns={[
                { title: "协议类型", dataIndex: "agreement_type_code" },
                { title: "法人主体", dataIndex: "legal_entity_id", render: (value) => legalEntities.find((item) => item.id === value)?.name ?? value ?? "—" },
                { title: "合作方", dataIndex: "counterparty_name", render: (value) => value || "—" },
                { title: "生效日期", dataIndex: "effective_from" },
                { title: "失效日期", dataIndex: "effective_to", render: (value) => value || "—" },
              ]} /></>,
            },
          ]} />
        )}
      </Drawer>

      <Modal
        destroyOnHidden
        title={action ? modalTitle[action] : ""}
        open={Boolean(action)}
        okText="保存"
        confirmLoading={saving}
        onOk={() => form.submit()}
        onCancel={() => setAction(null)}
      >
        <Form
          form={form}
          layout="vertical"
          requiredMark={false}
          onValuesChange={(changedValues) => {
            if (action === "person" && changedValues.legal_name && !form.getFieldValue("display_name")) {
              form.setFieldValue("display_name", changedValues.legal_name)
            }
          }}
          onFinish={(values) => void save(values)}
        >
          {(action === "person" || action === "edit") && <>
            <Form.Item label="法定姓名" name="legal_name" rules={[{ required: true }]}><Input /></Form.Item>
            <Form.Item label="显示姓名（留空则同法定姓名）" name="display_name"><Input /></Form.Item>
            <Form.Item label="曾用名" name="former_name"><Input /></Form.Item>
            <Form.Item label="性别代码" name="gender_code"><Input /></Form.Item>
            <Form.Item label="出生日期" name="birth_date"><Input type="date" /></Form.Item>
            <Form.Item label="国籍代码" name="nationality_code"><Input maxLength={3} /></Form.Item>
            <Form.Item label="国家/地区代码" name="country_code"><Input maxLength={3} /></Form.Item>
            <Form.Item label="民族代码" name="ethnicity_code"><Input /></Form.Item>
            <Form.Item label="婚姻状况代码" name="marital_status_code"><Input /></Form.Item>
            <Form.Item label="政治面貌代码" name="political_status_code"><Input /></Form.Item>
          </>}
          {action === "employment" && <>
            <Form.Item label="人员类型" name="employee_type_code" rules={[{ required: true }]}><Input placeholder="例如 REGULAR、CAMPUS" /></Form.Item>
            <Form.Item label="计划入职日期" name="planned_start_date" initialValue={today} rules={[{ required: true }]}><Input type="date" /></Form.Item>
            <Form.Item label="劳动合同主体" name="contract_legal_entity_id" rules={[{ required: true }]}><Select showSearch optionFilterProp="label" options={legalOptions} /></Form.Item>
            <Form.Item label="发薪主体（留空则同合同主体）" name="payroll_legal_entity_id"><Select allowClear showSearch optionFilterProp="label" options={legalOptions} /></Form.Item>
            <Form.Item label="社保主体（留空则同合同主体）" name="social_insurance_legal_entity_id"><Select allowClear showSearch optionFilterProp="label" options={legalOptions} /></Form.Item>
            <Form.Item label="个税主体（留空则同合同主体）" name="tax_legal_entity_id"><Select allowClear showSearch optionFilterProp="label" options={legalOptions} /></Form.Item>
          </>}
          {action === "legalEntityRelation" && <>
            <Form.Item label="劳动关系" name="employment_id" rules={[{ required: true }]}><Select options={archive?.employments.map((item) => ({ label: `${item.employee_type_code} · ${item.planned_start_date}`, value: item.id }))} /></Form.Item>
            <Form.Item label="主体类型" name="relation_kind" rules={[{ required: true }]}><Select options={[
              { value: "contract", label: "劳动合同主体" }, { value: "payroll", label: "发薪主体" }, { value: "social_insurance", label: "社保主体" }, { value: "tax", label: "个税主体" },
            ]} /></Form.Item>
            <Form.Item label="法人主体" name="legal_entity_id" rules={[{ required: true }]}><Select showSearch optionFilterProp="label" options={legalOptions} /></Form.Item>
            <Form.Item label="生效日期" name="effective_from" initialValue={today} rules={[{ required: true }]}><Input type="date" /></Form.Item>
          </>}
          {action === "assignment" && <>
            <Form.Item label="劳动关系" name="employment_id" rules={[{ required: true }]}><Select options={archive?.employments.map((item) => ({ label: `${item.employee_type_code} · ${item.planned_start_date}`, value: item.id }))} /></Form.Item>
            <Form.Item label="关系类型" name="relation_type" initialValue="primary" rules={[{ required: true }]}><Select options={[
              { value: "primary", label: "主组织/主职务" }, { value: "concurrent", label: "兼岗" }, { value: "secondment", label: "借调" }, { value: "project", label: "项目" }, { value: "virtual", label: "虚拟组织" },
            ]} /></Form.Item>
            <Form.Item label="组织" name="organization_id" rules={[{ required: true }]}><Select showSearch optionFilterProp="label" options={organizationOptions} /></Form.Item>
            <Form.Item label="职务" name="job_id"><Select allowClear showSearch optionFilterProp="label" options={jobOptions} /></Form.Item>
            <Form.Item label="生效日期" name="effective_from" initialValue={today} rules={[{ required: true }]}><Input type="date" /></Form.Item>
            <Form.Item label="失效日期" name="effective_to"><Input type="date" /></Form.Item>
          </>}
          {action === "agreement" && <>
            <Form.Item label="协议关系类型" name="agreement_type_code" rules={[{ required: true }]}><Input placeholder="例如 COOPERATION、DISPATCH" /></Form.Item>
            <Form.Item label="关联法人" name="legal_entity_id"><Select allowClear showSearch optionFilterProp="label" options={legalOptions} /></Form.Item>
            <Form.Item label="合作方名称" name="counterparty_name"><Input /></Form.Item>
            <Form.Item label="生效日期" name="effective_from" initialValue={today} rules={[{ required: true }]}><Input type="date" /></Form.Item>
            <Form.Item label="失效日期" name="effective_to"><Input type="date" /></Form.Item>
          </>}
          {action === "legal" && <>
            <Form.Item label="法人编码" name="code" rules={[{ required: true }]}><Input /></Form.Item>
            <Form.Item label="法人名称" name="name" rules={[{ required: true }]}><Input /></Form.Item>
            <Form.Item label="注册名称" name="registered_name"><Input /></Form.Item>
            <Form.Item label="国家/地区代码" name="country_code" initialValue="CN" rules={[{ required: true }]}><Input maxLength={3} /></Form.Item>
            <Form.Item label="注册号" name="registration_number"><Input /></Form.Item>
            <Form.Item label="生效日期" name="effective_from" initialValue={today} rules={[{ required: true }]}><Input type="date" /></Form.Item>
          </>}
          {action && <Form.Item label="变更原因" name="change_reason" rules={[{ required: true }]}><Input.TextArea rows={2} /></Form.Item>}
        </Form>
      </Modal>
    </section>
  )
}
