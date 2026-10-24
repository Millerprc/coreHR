// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import {
  Alert,
  Button,
  DatePicker,
  Divider,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Tag,
  Typography,
} from "antd"
import dayjs from "dayjs"
import type { Dayjs } from "dayjs"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import type { JSX } from "react"

import { ApiClientError, apiRequest } from "../../client"
import { DataTable } from "../../components/DataTable"
import { EffectiveDatePicker } from "../../components/EffectiveDatePicker"
import { FilterBar } from "../../components/FilterBar"
import { FilterField } from "../../components/FilterField"
import { workforceApi } from "./api"


// Requirement: D-104 — 兼岗以人员级组织关系为唯一权威载体，
// 前端只读人员级兼岗接口，不再读取 employment 级任职作为兼岗来源。
const CONCURRENT_POSITIONS_PATH = "/api/v1/workforce/concurrent-positions"
const PAGE_SIZE = 20
const PERSON_SEARCH_DELAY_MS = 250


export interface ConcurrentPosition {
  readonly id: string
  readonly personId: string
  readonly personName: string
  readonly organizationId: string
  readonly organizationName: string
  readonly jobId: string | null
  readonly jobName: string | null
  readonly relationType: string
  readonly effectiveFrom: string
  readonly effectiveTo: string | null
  readonly changeReason: string | null
}


interface ConcurrentPositionPage {
  readonly items: readonly ConcurrentPosition[]
  readonly total: number
  readonly page: number
  readonly pageSize: number
}


interface ConcurrentPositionPayload {
  readonly id?: string
  readonly person_id?: string
  readonly person_name?: string | null
  readonly organization_id?: string
  readonly organization_name?: string | null
  readonly job_id?: string | null
  readonly job_name?: string | null
  readonly relation_type?: string | null
  readonly effective_from?: string | null
  readonly effective_to?: string | null
  readonly change_reason?: string | null
}


interface ConcurrentPositionPagePayload {
  readonly items?: readonly ConcurrentPositionPayload[]
  readonly total?: number
  readonly page?: number
  readonly page_size?: number
}


export interface ConcurrentPositionQuery {
  readonly effectiveAt?: string
  readonly personId?: string
  readonly organizationId?: string
  readonly page?: number
  readonly pageSize?: number
}


export interface CreateConcurrentPositionInput {
  readonly personId: string
  readonly organizationId: string
  readonly jobId?: string
  readonly effectiveFrom: string
  readonly effectiveTo?: string
  readonly changeReason: string
}


interface PersonOption {
  readonly id: string
  readonly displayName: string
}


interface OrganizationOption {
  readonly id: string
  readonly name: string
}


interface JobOption {
  readonly id: string
  readonly name: string
}


function mapConcurrentPosition(payload: ConcurrentPositionPayload): ConcurrentPosition {
  return {
    id: payload.id ?? "",
    personId: payload.person_id ?? "",
    personName: payload.person_name ?? "",
    organizationId: payload.organization_id ?? "",
    organizationName: payload.organization_name ?? "",
    jobId: payload.job_id ?? null,
    jobName: payload.job_name ?? null,
    relationType: payload.relation_type ?? "concurrent",
    effectiveFrom: payload.effective_from ?? "",
    effectiveTo: payload.effective_to ?? null,
    changeReason: payload.change_reason ?? null,
  }
}


function mapConcurrentPositionPage(payload: ConcurrentPositionPagePayload): ConcurrentPositionPage {
  const items = (payload.items ?? []).map(mapConcurrentPosition)
  return {
    items,
    total: payload.total ?? items.length,
    page: payload.page ?? 1,
    pageSize: payload.page_size ?? items.length,
  }
}


function buildQueryString(query: ConcurrentPositionQuery): string {
  const params = new URLSearchParams()
  if (query.effectiveAt) params.set("effective_at", query.effectiveAt)
  if (query.personId) params.set("person_id", query.personId)
  if (query.organizationId) params.set("organization_id", query.organizationId)
  params.set("page", String(query.page ?? 1))
  params.set("page_size", String(query.pageSize ?? PAGE_SIZE))
  return params.toString()
}


const concurrentPositionsApi = {
  list: async (
    token: string,
    query: ConcurrentPositionQuery = {},
  ): Promise<ConcurrentPositionPage> => {
    const payload = await apiRequest<ConcurrentPositionPagePayload>(
      `${CONCURRENT_POSITIONS_PATH}?${buildQueryString(query)}`,
      token,
    )
    return mapConcurrentPositionPage(payload)
  },
  forPerson: async (token: string, personId: string): Promise<readonly ConcurrentPosition[]> => {
    const payload = await apiRequest<readonly ConcurrentPositionPayload[]>(
      `/api/v1/workforce/persons/${personId}/concurrent-positions`,
      token,
    )
    return (payload ?? []).map(mapConcurrentPosition)
  },
  create: async (
    token: string,
    input: CreateConcurrentPositionInput,
  ): Promise<ConcurrentPosition> => {
    const payload = await apiRequest<ConcurrentPositionPayload>(CONCURRENT_POSITIONS_PATH, token, {
      method: "POST",
      body: {
        person_id: input.personId,
        organization_id: input.organizationId,
        ...(input.jobId ? { job_id: input.jobId } : {}),
        effective_from: input.effectiveFrom,
        ...(input.effectiveTo ? { effective_to: input.effectiveTo } : {}),
        change_reason: input.changeReason,
      },
    })
    return mapConcurrentPosition(payload)
  },
  end: (token: string, relationId: string): Promise<void> =>
    apiRequest<void>(`${CONCURRENT_POSITIONS_PATH}/${relationId}`, token, { method: "DELETE" }),
}


function errorMessage(caught: unknown, fallback: string): string {
  return caught instanceof Error ? caught.message : fallback
}


function localDate(): string {
  const now = new Date()
  const offset = now.getTimezoneOffset() * 60_000
  return new Date(now.getTime() - offset).toISOString().slice(0, 10)
}


interface PersonSelectProps {
  readonly token: string
  readonly value?: string
  readonly onChange: (value: string | undefined) => void
  readonly placeholder: string
  readonly ariaLabel: string
  readonly allowClear?: boolean
  readonly disabled?: boolean
}


/**
 * 人员远程搜索选择器。
 *
 * Requirement: D-104 — 兼岗表单按人员远程搜索选择，
 * 写法与汇报关系页的人员选择器保持一致（防抖 250ms + 远程检索）。
 */
function PersonSelect({
  token,
  value,
  onChange,
  placeholder,
  ariaLabel,
  allowClear = false,
  disabled = false,
}: PersonSelectProps): JSX.Element {
  const [results, setResults] = useState<readonly PersonOption[]>([])
  const [known, setKnown] = useState<Readonly<Record<string, PersonOption>>>({})
  const [loading, setLoading] = useState(false)
  const requestSequence = useRef(0)
  const searchTimer = useRef<number | null>(null)

  const load = useCallback(async (search: string) => {
    const sequence = ++requestSequence.current
    setLoading(true)
    try {
      const page = await workforceApi.persons(token, search)
      if (sequence !== requestSequence.current) return
      const people = page.items.map((person) => ({
        id: person.id,
        displayName: person.display_name || person.employee_number || person.id,
      }))
      setResults(people)
      setKnown((current) => {
        const next: Record<string, PersonOption> = { ...current }
        for (const person of people) {
          next[person.id] = person
        }
        return next
      })
    } catch {
      if (sequence === requestSequence.current) setResults([])
    } finally {
      if (sequence === requestSequence.current) setLoading(false)
    }
  }, [token])

  useEffect(() => {
    void load("")
    return () => {
      if (searchTimer.current !== null) window.clearTimeout(searchTimer.current)
    }
  }, [load])

  const options = useMemo(() => {
    const list = results.map((person) => ({ label: person.displayName, value: person.id }))
    const selected = value ? known[value] : undefined
    if (selected && !results.some((person) => person.id === selected.id)) {
      return [{ label: selected.displayName, value: selected.id }, ...list]
    }
    return list
  }, [known, results, value])

  return (
    <Select
      aria-label={ariaLabel}
      allowClear={allowClear}
      showSearch
      filterOption={false}
      loading={loading}
      disabled={disabled}
      placeholder={placeholder}
      value={value ?? null}
      options={options}
      notFoundContent={loading ? "搜索中" : "未找到匹配人员"}
      onSearch={(term) => {
        if (searchTimer.current !== null) window.clearTimeout(searchTimer.current)
        searchTimer.current = window.setTimeout(() => {
          searchTimer.current = null
          void load(term)
        }, PERSON_SEARCH_DELAY_MS)
      }}
      onChange={(next) => onChange(next ?? undefined)}
    />
  )
}


interface ConcurrentPositionFormValues {
  readonly person_id: string
  readonly organization_id: string
  readonly job_id: string
  readonly effective_from: Dayjs
  readonly effective_to?: Dayjs
  readonly change_reason: string
}


export interface ConcurrentPositionCreateModalProps {
  readonly token: string
  readonly open: boolean
  /** 不传时组件自行取数，供宿主页页头单独挂载本 Modal 的场景使用。 */
  readonly organizations?: readonly OrganizationOption[]
  readonly jobs?: readonly JobOption[]
  readonly onClose: () => void
  readonly onCreated?: () => void
}


/**
 * 新建兼岗表单（Modal）。
 *
 * Requirement: D-104 — 兼岗是人员级组织关系，表单字段为人员、组织、职务、生效日期、失效日期与变更原因。
 * 表单生命周期：每次打开都是空白表单，生效日期默认今天。
 */
export function ConcurrentPositionCreateModal({
  token,
  open,
  organizations,
  jobs,
  onClose,
  onCreated,
}: ConcurrentPositionCreateModalProps): JSX.Element {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loadedOrganizations, setLoadedOrganizations] = useState<readonly OrganizationOption[]>([])
  const [loadedJobs, setLoadedJobs] = useState<readonly JobOption[]>([])
  const [form] = Form.useForm<ConcurrentPositionFormValues>()

  useEffect(() => {
    if (organizations !== undefined && jobs !== undefined) return
    let cancelled = false
    async function loadOptions(): Promise<void> {
      try {
        const [organizationItems, jobPage] = await Promise.all([
          workforceApi.organizations(token),
          workforceApi.jobs(token),
        ])
        if (cancelled) return
        setLoadedOrganizations(organizationItems.map((item) => ({ id: item.id, name: item.name })))
        setLoadedJobs(jobPage.items.map((item) => ({ id: item.id, name: item.name })))
      } catch {
        if (!cancelled) {
          setLoadedOrganizations([])
          setLoadedJobs([])
        }
      }
    }
    void loadOptions()
    return () => {
      cancelled = true
    }
  }, [jobs, organizations, token])

  const organizationOptions = organizations ?? loadedOrganizations
  const jobOptions = jobs ?? loadedJobs

  useEffect(() => {
    if (!open) return
    // 表单生命周期：每次打开都是空白表单，默认生效日期为今天。
    form.resetFields()
    form.setFieldsValue({ effective_from: dayjs() })
  }, [form, open])

  async function submit(): Promise<void> {
    let values: ConcurrentPositionFormValues
    try {
      values = await form.validateFields()
    } catch {
      return
    }
    setSaving(true)
    setError(null)
    try {
      await concurrentPositionsApi.create(token, {
        personId: values.person_id,
        organizationId: values.organization_id,
        jobId: values.job_id,
        effectiveFrom: values.effective_from.format("YYYY-MM-DD"),
        effectiveTo: values.effective_to ? values.effective_to.format("YYYY-MM-DD") : undefined,
        changeReason: values.change_reason,
      })
      onClose()
      onCreated?.()
    } catch (caught) {
      setError(errorMessage(caught, "兼岗保存失败"))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      title="新建兼岗"
      open={open}
      destroyOnHidden
      mask={{ closable: false }}
      confirmLoading={saving}
      okText="保存"
      cancelText="取消"
      onCancel={onClose}
      onOk={() => void submit()}
    >
      {error && <Alert closable={{ onClose: () => setError(null) }} type="error" showIcon title={error} />}
      <Form form={form} layout="vertical" requiredMark="optional">
        <Form.Item
          name="person_id"
          label="人员"
          rules={[{ required: true, message: "请选择人员" }]}
        >
          <PersonSelect
            token={token}
            ariaLabel="选择人员"
            placeholder="搜索并选择人员"
            onChange={() => undefined}
          />
        </Form.Item>
        <Form.Item
          name="organization_id"
          label="组织"
          rules={[{ required: true, message: "请选择组织" }]}
        >
          <Select
            aria-label="选择组织"
            showSearch
            allowClear
            placeholder="搜索并选择组织"
            optionFilterProp="label"
            options={organizationOptions.map((organization) => ({
              label: organization.name,
              value: organization.id,
            }))}
          />
        </Form.Item>
        <Form.Item
          name="job_id"
          label="职务"
          rules={[{ required: true, message: "请选择职务" }]}
        >
          <Select
            aria-label="选择职务"
            showSearch
            allowClear
            placeholder="搜索并选择职务"
            optionFilterProp="label"
            options={jobOptions.map((job) => ({ label: job.name, value: job.id }))}
          />
        </Form.Item>
        <Form.Item
          name="effective_from"
          label="生效日期"
          rules={[{ required: true, message: "请选择生效日期" }]}
        >
          <DatePicker aria-label="选择生效日期" style={{ width: "100%" }} />
        </Form.Item>
        <Form.Item
          name="effective_to"
          label="失效日期"
          extra="留空表示长期有效"
          dependencies={["effective_from"]}
          rules={[
            {
              validator: (_rule, value: Dayjs | undefined) => {
                const start = form.getFieldValue("effective_from") as Dayjs | undefined
                if (value && start && value.isBefore(start, "day")) {
                  return Promise.reject(new Error("失效日期不能早于生效日期"))
                }
                return Promise.resolve()
              },
            },
          ]}
        >
          <DatePicker aria-label="选择失效日期" style={{ width: "100%" }} />
        </Form.Item>
        <Form.Item
          name="change_reason"
          label="变更原因"
          rules={[{ required: true, message: "请填写变更原因" }]}
        >
          <Input.TextArea rows={2} maxLength={100} showCount aria-label="填写变更原因" />
        </Form.Item>
      </Form>
    </Modal>
  )
}


export interface ConcurrentPositionPanelProps {
  readonly token: string
  readonly personId: string
}


/**
 * 员工档案 Drawer「组织职务」页签里的兼岗只读预览。
 *
 * Requirement: D-104 — 兼岗来源是人员级组织关系；
 * 按 AntD 页面交互规范 §4.3，Drawer 内不再叠加业务 Modal，这里只做只读展示。
 */
export function ConcurrentPositionPanel({ token, personId }: ConcurrentPositionPanelProps): JSX.Element {
  const [items, setItems] = useState<readonly ConcurrentPosition[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setItems(await concurrentPositionsApi.forPerson(token, personId))
    } catch (caught) {
      if (caught instanceof ApiClientError && caught.status === 403) {
        setError("无权查看兼岗信息")
      } else {
        setError(errorMessage(caught, "兼岗加载失败"))
      }
    } finally {
      setLoading(false)
    }
  }, [personId, token])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <div>
      {error && (
        <Alert closable={{ onClose: () => setError(null) }} type="error" showIcon title={error} />
      )}
      <DataTable<ConcurrentPosition>
        rowKey="id"
        loading={loading}
        dataSource={items}
        emptyText="该员工暂无兼岗记录"
        summaryText={`共 ${items.length} 条兼岗`}
        columns={[
          {
            title: "组织",
            dataIndex: "organizationName",
            width: 180,
            render: (value: string) => value || "—",
          },
          {
            title: "职务",
            dataIndex: "jobName",
            width: 160,
            render: (value: string | null) => value || "—",
          },
          {
            title: "关系类型",
            dataIndex: "relationType",
            width: 110,
            render: () => (
              <Tag color="blue" variant="outlined">兼岗</Tag>
            ),
          },
          {
            title: "生效日期",
            dataIndex: "effectiveFrom",
            width: 130,
            render: (value: string) => value || "—",
          },
          {
            title: "失效日期",
            dataIndex: "effectiveTo",
            width: 130,
            render: (value: string | null) => value ?? "长期有效",
          },
        ]}
      />
    </div>
  )
}


interface ConcurrentPositionFilterDraft {
  readonly effectiveAt?: string
  readonly personId?: string
  readonly organizationId?: string
}


export interface ConcurrentPositionSectionProps {
  readonly token: string
  readonly canAdmin: boolean
  /** 宿主页在别处新建兼岗后递增该值，列表随即重新取数。 */
  readonly refreshSignal?: number
  /** 宿主页页头已提供「新建兼岗」入口时置 true，避免出现两个入口。 */
  readonly hideCreateAction?: boolean
}


/**
 * 宿主页（人员中心）上的兼岗管理区块。
 *
 * Requirement: D-104 — 列表读人员级兼岗；
 * 按 AntD 页面交互规范 §4.3，新建兼岗的 Modal 覆盖宿主页，不叠加在员工档案 Drawer 之上。
 */
export function ConcurrentPositionSection({
  token,
  canAdmin,
  refreshSignal,
  hideCreateAction = false,
}: ConcurrentPositionSectionProps): JSX.Element {
  const [filterDraft, setFilterDraft] = useState<ConcurrentPositionFilterDraft>({})
  const [filters, setFilters] = useState<ConcurrentPositionFilterDraft>({})
  const [page, setPage] = useState(1)
  const [result, setResult] = useState<ConcurrentPositionPage>({
    items: [],
    total: 0,
    page: 1,
    pageSize: PAGE_SIZE,
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [organizations, setOrganizations] = useState<readonly OrganizationOption[]>([])
  const [jobs, setJobs] = useState<readonly JobOption[]>([])
  const firstRefresh = useRef(true)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const payload = await concurrentPositionsApi.list(token, {
        effectiveAt: filters.effectiveAt,
        personId: filters.personId,
        organizationId: filters.organizationId,
        page,
        pageSize: PAGE_SIZE,
      })
      setResult(payload)
    } catch (caught) {
      if (caught instanceof ApiClientError && caught.status === 403) {
        setError("无权查看兼岗信息")
      } else {
        setError(errorMessage(caught, "兼岗加载失败"))
      }
    } finally {
      setLoading(false)
    }
  }, [filters, page, token])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (refreshSignal === undefined) return
    // 首帧不重复取数：列表已经在挂载时加载过一次。
    if (firstRefresh.current) {
      firstRefresh.current = false
      return
    }
    void load()
  }, [load, refreshSignal])

  useEffect(() => {
    let cancelled = false
    async function loadOptions(): Promise<void> {
      try {
        const [organizationItems, jobPage] = await Promise.all([
          workforceApi.organizations(token),
          workforceApi.jobs(token),
        ])
        if (cancelled) return
        setOrganizations(organizationItems.map((item) => ({ id: item.id, name: item.name })))
        setJobs(jobPage.items.map((item) => ({ id: item.id, name: item.name })))
      } catch {
        if (!cancelled) {
          setOrganizations([])
          setJobs([])
        }
      }
    }
    void loadOptions()
    return () => {
      cancelled = true
    }
  }, [token])

  // Requirement: D-091 — 草稿式筛选：点「查询」才提交筛选条件并回到第一页。
  function applyFilters(): void {
    setPage(1)
    setFilters(filterDraft)
  }

  // Requirement: D-091 — 「重置」清空全部筛选条件。
  function resetFilters(): void {
    setFilterDraft({})
    setPage(1)
    setFilters({})
  }

  async function endPosition(relationId: string): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      await concurrentPositionsApi.end(token, relationId)
      await load()
    } catch (caught) {
      setError(errorMessage(caught, "结束兼岗失败"))
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="concurrent-position-section">
      <Divider />
      <div className="panel-heading">
        <div>
          <Typography.Title level={4}>兼岗管理</Typography.Title>
          <Typography.Text type="secondary">
            兼岗是人员在组织中的第二个岗位，以人员级组织关系保存；结束兼岗只关闭生效区间，历史记录保留。
          </Typography.Text>
        </div>
        <Space size="middle" align="end">
          {!hideCreateAction && (
            <Button
              type="primary"
              disabled={!canAdmin}
              onClick={() => setFormOpen(true)}
            >新建兼岗</Button>
          )}
        </Space>
      </div>
      {error && (
        <Alert closable={{ onClose: () => setError(null) }} type="error" showIcon title={error} />
      )}
      {/* Requirement: D-091 — 筛选区扁平样式；生效日期复用共享的 EffectiveDatePicker。 */}
      <FilterBar
        layout="flat"
        ariaLabel="兼岗筛选"
        actions={(
          <>
            <Button onClick={resetFilters}>重置</Button>
            <Button type="primary" onClick={applyFilters}>查询</Button>
          </>
        )}
      >
        <FilterField label="人员">
          <PersonSelect
            token={token}
            ariaLabel="按人员筛选"
            placeholder="全部人员"
            allowClear
            value={filterDraft.personId}
            onChange={(next) => setFilterDraft((previous) => ({
              ...previous,
              personId: next,
            }))}
          />
        </FilterField>
        <FilterField label="组织">
          <Select
            aria-label="按组织筛选"
            allowClear
            showSearch
            optionFilterProp="label"
            placeholder="全部组织"
            value={filterDraft.organizationId ?? null}
            options={organizations.map((organization) => ({
              label: organization.name,
              value: organization.id,
            }))}
            onChange={(next) => setFilterDraft((previous) => ({
              ...previous,
              organizationId: next ?? undefined,
            }))}
          />
        </FilterField>
        <EffectiveDatePicker
          value={filterDraft.effectiveAt ?? ""}
          label="按生效日期查看"
          onChange={(value) => setFilterDraft((previous) => ({
            ...previous,
            effectiveAt: value || undefined,
          }))}
        />
      </FilterBar>
      <DataTable<ConcurrentPosition>
        rowKey="id"
        loading={loading}
        dataSource={result.items}
        emptyText="没有符合条件的兼岗"
        summaryText={`共 ${result.total} 条兼岗`}
        pagination={{
          current: page,
          pageSize: PAGE_SIZE,
          total: result.total,
          showSizeChanger: false,
          showTotalLabel: "条兼岗",
          onChange: (nextPage) => setPage(nextPage),
        }}
        columns={[
          {
            title: "人员",
            dataIndex: "personName",
            width: 160,
            render: (value: string) => value || "—",
          },
          {
            title: "组织",
            dataIndex: "organizationName",
            width: 180,
            render: (value: string) => value || "—",
          },
          {
            title: "职务",
            dataIndex: "jobName",
            width: 160,
            render: (value: string | null) => value || "—",
          },
          {
            title: "关系类型",
            dataIndex: "relationType",
            width: 110,
            render: () => (
              <Tag color="blue" variant="outlined">兼岗</Tag>
            ),
          },
          {
            title: "生效日期",
            dataIndex: "effectiveFrom",
            width: 130,
            render: (value: string) => value || "—",
          },
          {
            title: "失效日期",
            dataIndex: "effectiveTo",
            width: 130,
            render: (value: string | null) => value ?? "长期有效",
          },
          {
            title: "操作",
            key: "action",
            width: 110,
            render: (_, position) => (
              <Popconfirm
                title="确认结束这条兼岗？"
                description="结束后保留历史记录，不再计入当前兼岗。"
                okText="确认结束"
                cancelText="取消"
                onConfirm={() => void endPosition(position.id)}
              >
                <Button type="link" danger disabled={!canAdmin} loading={saving}>结束</Button>
              </Popconfirm>
            ),
          },
        ]}
      />
      <ConcurrentPositionCreateModal
        token={token}
        open={formOpen}
        organizations={organizations}
        jobs={jobs}
        onClose={() => setFormOpen(false)}
        onCreated={() => void load()}
      />
    </section>
  )
}
