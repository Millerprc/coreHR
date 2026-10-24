// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import {
  Alert,
  Button,
  DatePicker,
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
} from "antd"
import dayjs from "dayjs"
import type { Dayjs } from "dayjs"
import { useCallback, useEffect, useMemo, useState } from "react"

import { workforceApi } from "./api"
import { PersonnelSubrecordsPanel } from "./PersonnelSubrecordsPanel"
import { PersonLabelPanel } from "../people/PersonLabelPanel"
import { DataTable } from "../../components/DataTable"
import { EmptyState } from "../../components/EmptyState"
import { FilterBar } from "../../components/FilterBar"
import { FilterField } from "../../components/FilterField"
import { WorkspaceShell } from "../../components/WorkspaceShell"
import {
  PERSON_CORRECTABLE_FIELDS,
  personFieldLabel,
  type LegalEntity,
  type OrganizationOption,
  type Person,
  type PersonArchive,
} from "./types"


// Requirement: D-095 — 「编辑」与「修正」是两个语义不同的操作，拆成两个入口：
// 编辑直接覆盖主档（立即生效），修正登记带生效日期的修正记录（不覆盖主档）。
// 按 AntD 页面交互规范 §4.3，两层业务容器禁止嵌套，因此编辑态与修正态都由
// 员工档案 Drawer 自身切换承载，不在 Drawer 之上再开 Modal。
type Action = "person" | "employment" | "legalEntityRelation" | "assignment" | "agreement" | "legal" | null
type DrawerMode = "view" | "edit" | "correction"


interface PeopleWorkspaceProps {
  readonly token: string
  readonly canAdmin: boolean
}


interface PeopleFilterDraft {
  readonly search: string
  readonly status?: string
}


const today = new Date().toISOString().slice(0, 10)
const PEOPLE_PAGE_SIZE = 20


// Requirement: D-095 — 修正入口只允许选择可修正的基础信息字段，
// 取值与后端 PERSON_CORRECTABLE_FIELD_CODES 一致。
const CORRECTABLE_FIELD_OPTIONS = PERSON_CORRECTABLE_FIELDS.map((code) => ({
  value: code,
  label: personFieldLabel(code),
}))


// 表单取值归一：空串与 undefined 都按「未填写」处理，便于比较「是否真的改过」。
function normalizeFieldValue(value: unknown): unknown {
  return value === undefined || value === "" ? null : value
}


// Requirement: D-093 — 在职状态沿用后端 persons.status 的启停取值，
// 展示层按画板翻译为「在职 / 停用」，前端不新增后端字段。
const EMPLOYMENT_STATUS_OPTIONS = [
  { value: "active", label: "在职" },
  { value: "inactive", label: "停用" },
]


export function PeopleWorkspace({ token, canAdmin }: PeopleWorkspaceProps) {
  const [people, setPeople] = useState<readonly Person[]>([])
  const [legalEntities, setLegalEntities] = useState<readonly LegalEntity[]>([])
  const [organizations, setOrganizations] = useState<readonly OrganizationOption[]>([])
  const [jobs, setJobs] = useState<readonly { id: string; code: string; name: string }[]>([])
  const [archive, setArchive] = useState<PersonArchive | null>(null)
  // Requirement: D-091 — 筛选为草稿式：改值不立即查询，点「查询」才生效。
  const [filterDraft, setFilterDraft] = useState<PeopleFilterDraft>({ search: "" })
  const [filters, setFilters] = useState<PeopleFilterDraft>({ search: "" })
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [action, setAction] = useState<Action>(null)
  const [drawerMode, setDrawerMode] = useState<DrawerMode>("view")
  const [form] = Form.useForm()
  const [editForm] = Form.useForm()
  const [correctionForm] = Form.useForm()
  // Requirement: D-091 — 修正态需要按所选字段展示「登记值 / 当前生效值」对照，
  // 因此监听待修正字段的当前取值。
  const correctionField = Form.useWatch("field_code", correctionForm) as string | undefined

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

  // 在职状态在后端人员列表里没有对应过滤参数，按已加载结果在前端筛选。
  const visiblePeople = useMemo(
    () => (filters.status ? people.filter((person) => person.status === filters.status) : people),
    [filters.status, people],
  )

  const pagedPeople = useMemo(
    () => visiblePeople.slice((page - 1) * PEOPLE_PAGE_SIZE, page * PEOPLE_PAGE_SIZE),
    [page, visiblePeople],
  )

  async function openArchive(personId: string): Promise<void> {
    setError(null)
    try {
      setArchive(await workforceApi.personArchive(token, personId))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "人员档案加载失败")
    }
  }

  // Requirement: D-091 — 「查询」提交草稿筛选并回到第一页。
  function applyFilters(): void {
    setPage(1)
    setFilters(filterDraft)
    void load(filterDraft.search)
  }

  // Requirement: D-091 — 「重置」清空全部筛选条件。
  function resetFilters(): void {
    setFilterDraft({ search: "" })
    setFilters({ search: "" })
    setPage(1)
    void load("")
  }

  function openAction(nextAction: Exclude<Action, null>): void {
    setAction(nextAction)
    form.resetFields()
  }

  // Requirement: D-095 — 编辑态与修正态都在员工档案 Drawer 内切换，
  // 表单生命周期：每次进入都是当前档案值的草稿。
  useEffect(() => {
    if (drawerMode !== "edit" || !archive) return
    editForm.resetFields()
    editForm.setFieldsValue({
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
  }, [drawerMode, archive, editForm])

  useEffect(() => {
    if (drawerMode !== "correction" || !archive) return
    correctionForm.resetFields()
    correctionForm.setFieldsValue({ effective_from: dayjs(today) })
  }, [drawerMode, archive, correctionForm])

  function closeDrawerMode(): void {
    setDrawerMode("view")
    editForm.resetFields()
    correctionForm.resetFields()
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
        await load(filters.search)
        await openArchive(created.id)
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
        await load(filters.search)
      }
      setAction(null)
      form.resetFields()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "人员档案保存失败")
    } finally {
      setSaving(false)
    }
  }

  // Requirement: D-095 — 编辑态直接覆盖主档；只提交用户实际改动的字段，
  // 未改动的字段不回传，避免把没动过的值重新写一遍。
  async function saveEdit(values: Record<string, unknown>): Promise<void> {
    if (!archive) return
    const changes: Record<string, unknown> = {}
    for (const field of PERSON_CORRECTABLE_FIELDS) {
      const next = values[field]
      const current = (archive.person as unknown as Record<string, unknown>)[field]
      if (normalizeFieldValue(next) !== normalizeFieldValue(current)) {
        changes[field] = next === "" ? null : next
      }
    }
    if (Object.keys(changes).length === 0) {
      setError("没有需要保存的基础信息变更")
      return
    }
    setSaving(true)
    setError(null)
    try {
      await workforceApi.updatePerson(token, archive.person.id, {
        ...changes,
        change_reason: values.change_reason,
      })
      await openArchive(archive.person.id)
      await load(filters.search)
      setDrawerMode("view")
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "基础信息保存失败")
    } finally {
      setSaving(false)
    }
  }

  // Requirement: D-095 — 修正态不写主档，只登记带生效日期的修正记录。
  async function saveCorrection(values: Record<string, unknown>): Promise<void> {
    if (!archive) return
    const fieldCode = String(values.field_code ?? "")
    const effectiveFrom = values.effective_from as Dayjs | undefined
    setSaving(true)
    setError(null)
    try {
      await workforceApi.createPersonCorrection(token, archive.person.id, {
        field_code: fieldCode,
        new_value: values.new_value === "" ? null : values.new_value,
        effective_from: effectiveFrom ? effectiveFrom.format("YYYY-MM-DD") : "",
        change_reason: values.change_reason ? String(values.change_reason) : null,
      })
      await openArchive(archive.person.id)
      setDrawerMode("view")
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "修正记录提交失败")
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

  // Requirement: D-095 — 修正态要区分「登记值」（主档）与「当前生效值」
  // （主档 + 已生效修正），让用户知道改的是哪一层的值。
  const registeredPerson = archive?.registered_person ?? archive?.person
  const registeredValue = correctionField
    ? String((registeredPerson as unknown as Record<string, unknown> | undefined)?.[correctionField] ?? "")
    : ""
  const effectiveValue = correctionField
    ? String((archive?.person as unknown as Record<string, unknown> | undefined)?.[correctionField] ?? "")
    : ""

  const modalTitle: Record<Exclude<Action, null>, string> = {
    legalEntityRelation: "调整四类法人主体",
    person: "新建人员档案",
    employment: "建立劳动关系",
    assignment: "新增组织职务关系",
    agreement: "登记协议关系",
    legal: "新建法人主体",
  }

  return (
    <WorkspaceShell
      titleId="people-title"
      title="人员中心"
      subtitle="自然人、雇佣经历、主组织职务和协议关系分层保存。"
      actions={canAdmin ? (
        <Space wrap><Button onClick={() => openAction("legal")}>新建法人</Button><Button type="primary" onClick={() => openAction("person")}>新建人员</Button></Space>
      ) : null}
      error={error}
      onErrorClose={() => setError(null)}
    >
      <FilterBar
        layout="flat"
        ariaLabel="人员筛选"
        actions={(
          <>
            <Button onClick={resetFilters}>重置</Button>
            <Button type="primary" onClick={applyFilters}>查询</Button>
          </>
        )}
      >
        <FilterField label="姓名或工号">
          <Input.Search
            allowClear
            aria-label="搜索姓名或工号"
            placeholder="搜索姓名或工号"
            value={filterDraft.search}
            onChange={(event) => setFilterDraft((previous) => ({ ...previous, search: event.target.value }))}
          />
        </FilterField>
        <FilterField label="在职状态">
          <Select
            aria-label="在职状态"
            allowClear
            placeholder="全部状态"
            value={filterDraft.status}
            options={EMPLOYMENT_STATUS_OPTIONS}
            onChange={(value: string | undefined) => setFilterDraft((previous) => ({ ...previous, status: value }))}
          />
        </FilterField>
      </FilterBar>
      {/* Requirement: D-093 / ORG-PROT-001 — 人员列表按画板的七列呈现：
          主组织、职位、入职日期属于人员档案数据（组织职务与劳动关系），
          人员列表接口当前不返回，这三列显示为空占位，档案数据在员工档案 Drawer 中可见。 */}
      <DataTable<Person>
        rowKey="id"
        loading={loading}
        dataSource={[...pagedPeople]}
        columns={[
          { title: "姓名", dataIndex: "display_name", width: 160 },
          { title: "工号", dataIndex: "employee_number", width: 140, render: (value) => value || "待分配" },
          { title: "主组织", key: "organization", width: 160, render: () => "—" },
          { title: "职位", key: "job", width: 180, render: () => "—" },
          {
            title: "在职状态",
            dataIndex: "status",
            width: 110,
            render: (value: string) => (
              value === "active"
                ? <Tag color="success" variant="outlined">在职</Tag>
                : <Tag variant="outlined">停用</Tag>
            ),
          },
          { title: "入职日期", key: "hire_date", width: 140, render: () => "—" },
          {
            title: "操作",
            key: "action",
            width: 120,
            render: (_value, row) => (
              <Button type="link" onClick={(event) => { event.stopPropagation(); void openArchive(row.id) }}>
                查看档案
              </Button>
            ),
          },
        ]}
        emptyText="暂无人员档案"
        pagination={{
          current: page,
          pageSize: PEOPLE_PAGE_SIZE,
          total: visiblePeople.length,
          showSizeChanger: false,
          showTotalLabel: "名员工",
          onChange: (nextPage) => setPage(nextPage),
        }}
        onRow={(row) => ({ onClick: () => void openArchive(row.id) })}
      />

      <Drawer
        size="large"
        title={(
          <div className="drawer-heading">
            <div className="drawer-heading-title">
              {archive ? `${archive.person.display_name} · ${archive.person.employee_number ?? "待分配"}` : "人员档案"}
            </div>
            <div className="drawer-heading-subtitle">
              {drawerMode === "edit"
                ? "员工档案 · 编辑基础信息"
                : drawerMode === "correction"
                  ? "员工档案 · 修正基础信息"
                  : "员工档案 · 人员中心"}
            </div>
          </div>
        )}
        open={Boolean(archive)}
        onClose={() => { setArchive(null); closeDrawerMode() }}
        // Requirement: D-095 — 抽屉头提供两个语义不同的入口：编辑（主路径，立即生效）
        // 与修正（版本化写操作，需要生效日期）。
        extra={archive && canAdmin && drawerMode === "view" ? (
          <Space>
            <Button type="primary" onClick={() => setDrawerMode("edit")}>编辑</Button>
            <Button onClick={() => setDrawerMode("correction")}>修正</Button>
          </Space>
        ) : null}
        // 编辑态与修正态的操作条放在抽屉底部，取消后回到预览态。
        footer={drawerMode === "edit" ? (
          <Space className="drawer-footer">
            <Button onClick={closeDrawerMode}>取消</Button>
            <Button type="primary" loading={saving} onClick={() => editForm.submit()}>保存</Button>
          </Space>
        ) : drawerMode === "correction" ? (
          <Space className="drawer-footer">
            <Button onClick={closeDrawerMode}>取消</Button>
            <Button type="primary" loading={saving} onClick={() => correctionForm.submit()}>提交修正</Button>
          </Space>
        ) : null}
      >
        {archive && drawerMode === "view" && (
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
              // Requirement: D-095 — 修正记录是只读的历史清单，
              // 与「基础信息」的当前生效结果分开呈现。
              key: "corrections",
              label: `修正记录 ${archive.corrections?.length ?? 0}`,
              children: (archive.corrections?.length ?? 0) > 0 ? (
                <Table rowKey="id" pagination={false} dataSource={[...(archive.corrections ?? [])]} columns={[
                  { title: "字段", dataIndex: "field_code", render: (value: string) => personFieldLabel(value) },
                  { title: "修正后值", dataIndex: "new_value", render: (value: string | null) => value || "（清空）" },
                  { title: "生效日期", dataIndex: "effective_from" },
                  { title: "原因", dataIndex: "change_reason", render: (value: string | null) => value || "—" },
                  { title: "记录时间", dataIndex: "created_at", render: (value: string) => new Date(value).toLocaleString("zh-CN") },
                ]} />
              ) : <EmptyState description="暂无修正记录" />,
            },
            {
              key: "personnel-subrecords",
              label: "敏感与经历档案",
              children: <PersonnelSubrecordsPanel token={token} personId={archive.person.id} canAdmin={canAdmin} />,
            },
            ...(canAdmin
              ? [{
                // Requirement: HR-LABEL-016 — 员工标签的读写在后端都要求 WORKFORCE_ADMIN，
                // 因此该 Tab 只对具备该权限的用户展示，避免给出必然 403 的入口。
                key: "person-labels",
                label: "员工标签",
                children: <PersonLabelPanel token={token} personId={archive.person.id} canAdmin={canAdmin} />,
              }]
              : []),
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
        {archive && drawerMode === "edit" && (
          // Requirement: D-095 — 编辑态直接覆盖主档，改完立即生效，不产生版本。
          <Form
            form={editForm}
            layout="vertical"
            requiredMark={false}
            onFinish={(values) => void saveEdit(values)}
          >
            <Form.Item label="法定姓名" name="legal_name" rules={[{ required: true }]}><Input /></Form.Item>
            <Form.Item label="显示姓名" name="display_name" rules={[{ required: true }]}><Input /></Form.Item>
            <Form.Item label="曾用名" name="former_name"><Input /></Form.Item>
            <Form.Item label="性别代码" name="gender_code"><Input /></Form.Item>
            <Form.Item label="出生日期" name="birth_date"><Input type="date" /></Form.Item>
            <Form.Item label="国籍代码" name="nationality_code"><Input maxLength={3} /></Form.Item>
            <Form.Item label="国家/地区代码" name="country_code"><Input maxLength={3} /></Form.Item>
            <Form.Item label="民族代码" name="ethnicity_code"><Input /></Form.Item>
            <Form.Item label="婚姻状况代码" name="marital_status_code"><Input /></Form.Item>
            <Form.Item label="政治面貌代码" name="political_status_code"><Input /></Form.Item>
            <Form.Item label="变更原因" name="change_reason" rules={[{ required: true, message: "请填写变更原因" }]}>
              <Input.TextArea rows={2} />
            </Form.Item>
          </Form>
        )}
        {archive && drawerMode === "correction" && (
          // Requirement: D-095 — 修正态不改主档，只登记带生效日期的修正记录。
          <Form
            form={correctionForm}
            layout="vertical"
            requiredMark={false}
            onFinish={(values) => void saveCorrection(values)}
          >
            <Form.Item label="待修正字段" name="field_code" rules={[{ required: true, message: "请选择待修正字段" }]}>
              <Select aria-label="待修正字段" options={CORRECTABLE_FIELD_OPTIONS} />
            </Form.Item>
            {correctionField ? (
              <Descriptions bordered size="small" column={1} items={[
                { key: "registered", label: "登记值", children: registeredValue || "—" },
                { key: "effective", label: "当前生效值", children: effectiveValue || "—" },
              ]} />
            ) : null}
            <Form.Item label="修正后值" name="new_value">
              <Input type={correctionField === "birth_date" ? "date" : "text"} />
            </Form.Item>
            <Form.Item label="生效日期" name="effective_from" rules={[{ required: true, message: "请选择生效日期" }]}>
              <DatePicker aria-label="选择生效日期" style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item label="修正原因" name="change_reason">
              <Input.TextArea rows={2} />
            </Form.Item>
          </Form>
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
          {action === "person" && <>
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
    </WorkspaceShell>
  )
}
