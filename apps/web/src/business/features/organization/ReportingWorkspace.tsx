// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import {
  Alert,
  Button,
  DatePicker,
  Form,
  Modal,
  Popconfirm,
  Select,
  Space,
  Tabs,
  Tag,
  Tree,
  Typography,
} from "antd"
import type { DataNode } from "antd/es/tree"
import dayjs from "dayjs"
import type { Dayjs } from "dayjs"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import type { JSX } from "react"

import { ApiClientError } from "../../client"
import { DataTable } from "../../components/DataTable"
import { EmptyState } from "../../components/EmptyState"
import { FilterBar } from "../../components/FilterBar"
import { FilterField } from "../../components/FilterField"
import { WorkspaceDenied, WorkspaceShell } from "../../components/WorkspaceShell"
import { reportingApi } from "./reporting-api"
import type {
  PersonOption,
  ReportingRelation,
  ReportingRelationPage,
  ReportingRelationType,
} from "./reporting-api"


export interface ReportingWorkspaceProps {
  readonly token: string
  readonly canAdmin: boolean
}


interface RelationFormValues {
  readonly manager_person_id: string
  readonly subordinate_person_id: string
  readonly relation_type: ReportingRelationType
  readonly effective_from: Dayjs
  readonly effective_to?: Dayjs
}


interface ReportingFilterDraft {
  readonly effectiveAt?: string
  readonly managerPersonId?: string
  readonly subordinatePersonId?: string
}


interface PersonSelectProps {
  readonly token: string
  readonly id?: string
  readonly value?: string
  readonly onChange: (value: string | undefined) => void
  readonly placeholder: string
  readonly ariaLabel: string
  readonly allowClear?: boolean
  readonly disabled?: boolean
}


interface ReportingGraphNode {
  readonly key: string
  readonly personId: string
  readonly name: string
  readonly relationType: ReportingRelationType | null
  readonly children: readonly ReportingGraphNode[]
}


const RELATION_TYPE_LABELS: Record<ReportingRelationType, string> = {
  direct: "直属",
  dotted: "虚线",
}
// Requirement: D-093 — 汇报关系双态必须一眼可辨：
// 直属用蓝色标签（底 #E6F4FF、字 #0958D9、描边 #91CAFF），虚线用紫色标签（底 #F9F0FF、字 #531DAB、描边 #D3ADF7）。
// antd 6 的 preset 调色板与画板一致，outlined 变体额外带上描边色。
const RELATION_TYPE_COLORS: Record<ReportingRelationType, string> = {
  direct: "blue",
  dotted: "purple",
}
const RELATION_TYPE_OPTIONS = [
  { label: "直属（实线汇报）", value: "direct" },
  { label: "虚线（兼岗、项目、专业或协同）", value: "dotted" },
]
const PAGE_SIZE = 20
// 后端 reporting-relations 的 page_size 上限是 200，关系图按该上限拉取。
const GRAPH_PAGE_SIZE = 200
const PERSON_SEARCH_DELAY_MS = 250


function localDate(): string {
  const now = new Date()
  const offset = now.getTimezoneOffset() * 60_000
  return new Date(now.getTime() - offset).toISOString().slice(0, 10)
}


function errorMessage(caught: unknown, fallback: string): string {
  return caught instanceof Error ? caught.message : fallback
}


function isRelationEffective(relation: ReportingRelation, today: string): boolean {
  // Requirement: ORG-REPORT-007 — 有效期区间为 [effective_from, effective_to)，
  // effective_to 为空表示当前有效。
  if (relation.effectiveFrom && relation.effectiveFrom > today) return false
  if (relation.effectiveTo && relation.effectiveTo <= today) return false
  return true
}


// Requirement: ORG-REPORT-006 — 同一上级、下级和类型可以存在多段有效期，
// 关系图只保留生效日期最新的一条，避免历史关系重复成节点。
function dedupeRelations(relations: readonly ReportingRelation[]): readonly ReportingRelation[] {
  const latest = new Map<string, ReportingRelation>()
  for (const relation of relations) {
    const key = `${relation.managerPersonId}|${relation.subordinatePersonId}|${relation.relationType}`
    const current = latest.get(key)
    if (!current || relation.effectiveFrom > current.effectiveFrom) latest.set(key, relation)
  }
  return Array.from(latest.values())
}


// Requirement: ORG-REPORT-005 — 同类型汇报关系不得成环，关系图在建树时截断回环边。
function buildReportingGraph(
  relations: readonly ReportingRelation[],
  today: string,
): readonly ReportingGraphNode[] {
  const edges = dedupeRelations(relations.filter((relation) => isRelationEffective(relation, today)))
  if (!edges.length) return []

  const childMap = new Map<string, readonly ReportingRelation[]>()
  const subordinateIds = new Set<string>()
  const nameByPerson = new Map<string, string>()
  for (const relation of edges) {
    childMap.set(relation.managerPersonId, [
      ...(childMap.get(relation.managerPersonId) ?? []),
      relation,
    ])
    subordinateIds.add(relation.subordinatePersonId)
    if (relation.managerName) nameByPerson.set(relation.managerPersonId, relation.managerName)
    if (relation.subordinateName) nameByPerson.set(relation.subordinatePersonId, relation.subordinateName)
  }

  const rootIds: string[] = []
  for (const relation of edges) {
    if (!subordinateIds.has(relation.managerPersonId) && !rootIds.includes(relation.managerPersonId)) {
      rootIds.push(relation.managerPersonId)
    }
  }
  // 关系数据成环时不存在根节点，用第一条关系的上级兜底，避免关系图整体空白。
  if (!rootIds.length) rootIds.push(edges[0].managerPersonId)

  const buildNode = (
    personId: string,
    relationType: ReportingRelationType | null,
    key: string,
    path: ReadonlySet<string>,
  ): ReportingGraphNode => {
    const children = (childMap.get(personId) ?? []).map((relation, index) => {
      const childKey = `${key}-${relation.subordinatePersonId}-${index}`
      if (path.has(relation.subordinatePersonId)) {
        return {
          key: childKey,
          personId: relation.subordinatePersonId,
          name: relation.subordinateName || relation.subordinatePersonId,
          relationType: relation.relationType,
          children: [],
        }
      }
      const nextPath = new Set(path)
      nextPath.add(relation.subordinatePersonId)
      return buildNode(relation.subordinatePersonId, relation.relationType, childKey, nextPath)
    })
    return {
      key,
      personId,
      name: nameByPerson.get(personId) ?? personId,
      relationType,
      children,
    }
  }

  return rootIds.map((rootId, index) => buildNode(rootId, null, `root-${rootId}-${index}`, new Set([rootId])))
}


function toTreeData(nodes: readonly ReportingGraphNode[]): DataNode[] {
  return nodes.map((node) => ({
    key: node.key,
    title: (
      <Space size={6}>
        <span>{node.name}</span>
        {node.relationType && (
          <Tag color={RELATION_TYPE_COLORS[node.relationType]} variant="outlined">
            {RELATION_TYPE_LABELS[node.relationType]}
          </Tag>
        )}
      </Space>
    ),
    children: toTreeData(node.children),
  }))
}


function PersonSelect({
  token,
  id,
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
      const people = await reportingApi.persons(token, search)
      if (sequence !== requestSequence.current) return
      setResults(people)
      setKnown((current) => {
        const next: Record<string, PersonOption> = { ...current }
        for (const person of people) {
          if (person.id) next[person.id] = person
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
    const list = results
      .filter((person) => person.id)
      .map((person) => ({ label: person.displayName || person.id, value: person.id }))
    const selected = value ? known[value] : undefined
    if (selected && !results.some((person) => person.id === selected.id)) {
      return [{ label: selected.displayName || selected.id, value: selected.id }, ...list]
    }
    return list
  }, [known, results, value])

  return (
    <Select
      id={id}
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


export function ReportingWorkspace({ token, canAdmin }: ReportingWorkspaceProps): JSX.Element {
  const [activeTab, setActiveTab] = useState<"relations" | "graph">("relations")
  // Requirement: D-091 — 筛选为草稿式：改值不立即查询，点「查询」才生效（与画板一致）。
  const [filterDraft, setFilterDraft] = useState<ReportingFilterDraft>({})
  const [filters, setFilters] = useState<ReportingFilterDraft>({})
  const [page, setPage] = useState(1)
  const [relations, setRelations] = useState<ReportingRelationPage>({
    items: [],
    total: 0,
    page: 1,
    pageSize: PAGE_SIZE,
  })
  const [graphRelations, setGraphRelations] = useState<readonly ReportingRelation[]>([])
  const [loading, setLoading] = useState(true)
  const [graphLoading, setGraphLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [forbidden, setForbidden] = useState(false)
  const [formOpen, setFormOpen] = useState(false)
  const [form] = Form.useForm<RelationFormValues>()

  const loadRelations = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await reportingApi.list(token, {
        effectiveAt: filters.effectiveAt,
        managerPersonId: filters.managerPersonId,
        subordinatePersonId: filters.subordinatePersonId,
        page,
        pageSize: PAGE_SIZE,
      })
      setRelations(result)
    } catch (caught) {
      if (caught instanceof ApiClientError && caught.status === 403) setForbidden(true)
      else setError(errorMessage(caught, "汇报关系加载失败"))
    } finally {
      setLoading(false)
    }
  }, [filters, page, token])

  const loadGraph = useCallback(async () => {
    setGraphLoading(true)
    try {
      const result = await reportingApi.list(token, { page: 1, pageSize: GRAPH_PAGE_SIZE })
      setGraphRelations(result.items)
    } catch (caught) {
      setError(errorMessage(caught, "汇报关系图加载失败"))
    } finally {
      setGraphLoading(false)
    }
  }, [token])

  useEffect(() => {
    void loadRelations()
  }, [loadRelations])

  useEffect(() => {
    if (activeTab === "graph") void loadGraph()
  }, [activeTab, loadGraph])

  useEffect(() => {
    if (!formOpen) return
    // 表单生命周期：每次打开都是空白表单，默认关系类型为直属、生效日期为今天。
    form.resetFields()
    form.setFieldsValue({ relation_type: "direct", effective_from: dayjs() })
  }, [form, formOpen])

  const graphData = useMemo(
    () => toTreeData(buildReportingGraph(graphRelations, localDate())),
    [graphRelations],
  )

  // Requirement: D-091 — 草稿式筛选：点「查询」才提交筛选条件并回到第一页。
  function applyFilters(): void {
    setPage(1)
    setFilters(filterDraft)
  }

  // Requirement: D-091 — 「重置」清空全部筛选条件（含生效日期与人员）。
  function resetFilters(): void {
    setFilterDraft({})
    setPage(1)
    setFilters({})
  }

  async function submitForm(): Promise<void> {
    let values: RelationFormValues
    try {
      values = await form.validateFields()
    } catch {
      return
    }
    setSaving(true)
    setError(null)
    try {
      await reportingApi.create(token, {
        managerPersonId: values.manager_person_id,
        subordinatePersonId: values.subordinate_person_id,
        relationType: values.relation_type,
        effectiveFrom: values.effective_from.format("YYYY-MM-DD"),
        effectiveTo: values.effective_to ? values.effective_to.format("YYYY-MM-DD") : undefined,
      })
      setFormOpen(false)
      await loadRelations()
    } catch (caught) {
      setError(errorMessage(caught, "汇报关系保存失败"))
    } finally {
      setSaving(false)
    }
  }

  async function endRelation(relationId: string): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      await reportingApi.remove(token, relationId)
      await loadRelations()
    } catch (caught) {
      setError(errorMessage(caught, "结束汇报关系失败"))
    } finally {
      setSaving(false)
    }
  }

  if (forbidden) {
    return (
      <WorkspaceDenied
        titleId="reporting-title"
        title="汇报关系"
        message="无权查看汇报关系"
        description="请联系主管理员分配组织查看权限。"
      />
    )
  }

  return (
    <WorkspaceShell
      titleId="reporting-title"
      title="汇报关系"
      subtitle="维护员工的上级与下级汇报关系；实线表示主要业务管理关系，虚线表示兼岗、项目、专业或协同关系。"
      actions={(
        <Space wrap>
          <Button
            type="primary"
            disabled={!canAdmin}
            onClick={() => setFormOpen(true)}
          >新增关系</Button>
        </Space>
      )}
      error={error}
      onErrorClose={() => setError(null)}
    >
      {!canAdmin && (
        <Alert
          type="info"
          showIcon
          title="当前账号为只读权限，不能新增或结束汇报关系。"
        />
      )}
      <Tabs
        activeKey={activeTab}
        onChange={(key) => {
          setActiveTab(key as "relations" | "graph")
          setError(null)
        }}
        items={[
          {
            key: "relations",
            label: "关系管理",
            children: (
              <div>
                {/* Requirement: D-091 — 筛选区在页签内容之内、扁平样式；上级/下级保持远程搜索。 */}
                <FilterBar
                  layout="flat"
                  ariaLabel="汇报关系筛选"
                  actions={(
                    <>
                      <Button onClick={resetFilters}>重置</Button>
                      <Button type="primary" onClick={applyFilters}>查询</Button>
                    </>
                  )}
                >
                  <FilterField label="生效日期">
                    <DatePicker
                      aria-label="按生效日期筛选"
                      value={filterDraft.effectiveAt ? dayjs(filterDraft.effectiveAt) : null}
                      onChange={(value) => setFilterDraft((previous) => ({
                        ...previous,
                        effectiveAt: value ? value.format("YYYY-MM-DD") : undefined,
                      }))}
                    />
                  </FilterField>
                  <FilterField label="上级">
                    <PersonSelect
                      token={token}
                      ariaLabel="按上级筛选"
                      placeholder="全部上级"
                      allowClear
                      value={filterDraft.managerPersonId}
                      onChange={(next) => setFilterDraft((previous) => ({
                        ...previous,
                        managerPersonId: next,
                      }))}
                    />
                  </FilterField>
                  <FilterField label="下级">
                    <PersonSelect
                      token={token}
                      ariaLabel="按下级筛选"
                      placeholder="全部下级"
                      allowClear
                      value={filterDraft.subordinatePersonId}
                      onChange={(next) => setFilterDraft((previous) => ({
                        ...previous,
                        subordinatePersonId: next,
                      }))}
                    />
                  </FilterField>
                </FilterBar>
                <DataTable<ReportingRelation>
                  rowKey="id"
                  loading={loading}
                  dataSource={relations.items}
                  emptyText="没有符合条件的汇报关系"
                  pagination={{
                    current: page,
                    pageSize: PAGE_SIZE,
                    total: relations.total,
                    showSizeChanger: false,
                    showTotalLabel: "条汇报关系",
                    onChange: (nextPage) => setPage(nextPage),
                  }}
                  columns={[
                    {
                      title: "上级",
                      dataIndex: "managerName",
                      width: 200,
                      render: (value: string) => value || "—",
                    },
                    {
                      title: "下级",
                      dataIndex: "subordinateName",
                      width: 200,
                      render: (value: string) => value || "—",
                    },
                    {
                      title: "关系类型",
                      dataIndex: "relationType",
                      width: 120,
                      render: (value: ReportingRelationType) => (
                        <Tag color={RELATION_TYPE_COLORS[value]} variant="outlined">
                          {RELATION_TYPE_LABELS[value]}
                        </Tag>
                      ),
                    },
                    {
                      title: "生效日期",
                      dataIndex: "effectiveFrom",
                      width: 140,
                      render: (value: string) => value || "—",
                    },
                    {
                      title: "失效日期",
                      dataIndex: "effectiveTo",
                      width: 140,
                      render: (value: string | null) => value ?? "长期有效",
                    },
                    {
                      title: "操作",
                      key: "action",
                      width: 120,
                      render: (_, relation) => (
                        <Popconfirm
                          title="确认结束这条汇报关系？"
                          description="结束后保留历史记录，不再计入当前汇报结构。"
                          okText="确认结束"
                          cancelText="取消"
                          onConfirm={() => void endRelation(relation.id)}
                        >
                          <Button type="link" danger disabled={!canAdmin} loading={saving}>结束</Button>
                        </Popconfirm>
                      ),
                    },
                  ]}
                />
              </div>
            ),
          },
          {
            key: "graph",
            label: "关系图",
            children: (
              <div>
                <Typography.Paragraph type="secondary">
                  关系图按今天的生效日期展示当前汇报结构；历史关系请在关系管理中查看。
                </Typography.Paragraph>
                {graphLoading ? (
                  <Typography.Text type="secondary">关系图加载中…</Typography.Text>
                ) : graphData.length ? (
                  <Tree
                    aria-label="汇报关系图"
                    blockNode
                    defaultExpandAll
                    showLine={{ showLeafIcon: false }}
                    treeData={graphData}
                  />
                ) : (
                  <EmptyState description="暂无生效的汇报关系" />
                )}
              </div>
            ),
          },
        ]}
      />

      <Modal
        title="新增汇报关系"
        open={formOpen}
        destroyOnHidden
        mask={{ closable: false }}
        confirmLoading={saving}
        okText="保存"
        cancelText="取消"
        onCancel={() => setFormOpen(false)}
        onOk={() => void submitForm()}
      >
        <Form form={form} layout="vertical" requiredMark="optional">
          <Form.Item
            name="manager_person_id"
            label="上级"
            rules={[{ required: true, message: "请选择上级" }]}
          >
            <PersonSelect
              token={token}
              ariaLabel="选择上级"
              placeholder="搜索并选择上级"
              onChange={() => undefined}
            />
          </Form.Item>
          <Form.Item
            name="subordinate_person_id"
            label="下级"
            dependencies={["manager_person_id"]}
            rules={[
              { required: true, message: "请选择下级" },
              {
                // Requirement: ORG-REPORT-002 — 上级与下级不能是同一个员工。
                validator: (_rule, value: string) => (
                  value && value === form.getFieldValue("manager_person_id")
                    ? Promise.reject(new Error("上级和下级不能是同一人"))
                    : Promise.resolve()
                ),
              },
            ]}
          >
            <PersonSelect
              token={token}
              ariaLabel="选择下级"
              placeholder="搜索并选择下级"
              onChange={() => undefined}
            />
          </Form.Item>
          <Form.Item
            name="relation_type"
            label="关系类型"
            rules={[{ required: true, message: "请选择关系类型" }]}
          >
            <Select aria-label="选择关系类型" options={RELATION_TYPE_OPTIONS} />
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
                // Requirement: ORG-REPORT-004 — 结束日期不得早于开始日期。
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
        </Form>
      </Modal>
    </WorkspaceShell>
  )
}
