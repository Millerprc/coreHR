// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import {
  Alert,
  Button,
  Divider,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Tabs,
  Tag,
  Typography,
} from "antd"
import type { ColumnsType } from "antd/es/table"
import { useCallback, useEffect, useMemo, useState } from "react"

import { ApiClientError } from "../../client"
import { DataTable } from "../../components/DataTable"
import { EffectiveDatePicker } from "../../components/EffectiveDatePicker"
import { FilterBar } from "../../components/FilterBar"
import { FilterField } from "../../components/FilterField"
import { MetricStrip } from "../../components/MetricStrip"
import { WorkspaceDenied, WorkspaceShell } from "../../components/WorkspaceShell"
import { positionApi } from "./position-api"
import type {
  Position,
  PositionCreatePayload,
  PositionDimension,
  PositionDimensionCreatePayload,
  PositionDimensionType,
  PositionDimensionVersionPayload,
  PositionVersionPayload,
} from "./position-api"


// Requirement: ORG-PROT-001 / D-087 — 职位管理是组织管理分组下的独立宿主页，
// 显性化后端既有的职务体系，并保留后端“生效日期化版本”这一数据模型优势。

const POSITION_PAGE_SIZE = 20
const DIMENSION_PAGE_SIZE = 20
const DIMENSION_FETCH_LIMIT = 500
const CODE_PATTERN = /^[A-Z0-9][A-Z0-9_.-]{0,49}$/

const dimensionTypeLabels: Readonly<Record<PositionDimensionType, string>> = {
  LEVEL: "职级",
  GRADE: "职等",
  CLASS: "职类",
  SEQUENCE: "序列",
}

const dimensionTypeOptions = (Object.entries(dimensionTypeLabels) as readonly [
  PositionDimensionType,
  string,
][]).map(([value, label]) => ({ value, label }))

const statusOptions = [
  { value: "active", label: "启用" },
  { value: "inactive", label: "停用" },
]


export interface PositionWorkspaceProps {
  readonly token: string
  readonly canAdmin: boolean
}


type PositionEditor =
  | { readonly kind: "position"; readonly record?: Position }
  | { readonly kind: "dimension"; readonly record?: PositionDimension }
  | null


function today(): string {
  const value = new Date()
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, "0")
  const day = String(value.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}


function addDays(date: string, days: number): string {
  const parsed = new Date(`${date}T00:00:00`)
  parsed.setDate(parsed.getDate() + days)
  const year = parsed.getFullYear()
  const month = String(parsed.getMonth() + 1).padStart(2, "0")
  const day = String(parsed.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}


// 后端要求新版本生效日期晚于最新版本，前端默认值同样落在最新版本之后。
function nextEffectiveFrom(currentEffectiveFrom: string): string {
  const candidate = addDays(currentEffectiveFrom, 1)
  return candidate > today() ? candidate : today()
}


function readString(values: Record<string, unknown>, key: string): string {
  const value = values[key]
  return typeof value === "string" ? value.trim() : ""
}


function readOptionalString(values: Record<string, unknown>, key: string): string | undefined {
  const value = readString(values, key)
  return value ? value : undefined
}


function readNumber(values: Record<string, unknown>, key: string): number {
  const value = values[key]
  return typeof value === "number" ? value : 0
}


function readDimensionType(
  values: Record<string, unknown>,
  key: string,
): PositionDimensionType | undefined {
  const value = values[key]
  if (typeof value !== "string") return undefined
  return value in dimensionTypeLabels ? (value as PositionDimensionType) : undefined
}


function readStatus(values: Record<string, unknown>): string {
  const value = readString(values, "status")
  return value === "inactive" ? "inactive" : "active"
}


function buildPositionPayload(values: Record<string, unknown>): PositionCreatePayload {
  return {
    code: readString(values, "code"),
    name: readString(values, "name"),
    level_code: readString(values, "level_code"),
    grade_code: readString(values, "grade_code"),
    class_code: readString(values, "class_code"),
    sequence_code: readString(values, "sequence_code"),
    status: readStatus(values),
    effective_from: readString(values, "effective_from"),
    effective_to: readOptionalString(values, "effective_to"),
    source_job_id: readOptionalString(values, "source_job_id"),
    notes: readOptionalString(values, "notes"),
    attributes: {},
    change_reason: readString(values, "change_reason"),
  }
}


function buildPositionVersionPayload(
  values: Record<string, unknown>,
  record: Position,
): PositionVersionPayload {
  return {
    name: readString(values, "name"),
    level_code: readString(values, "level_code"),
    grade_code: readString(values, "grade_code"),
    class_code: readString(values, "class_code"),
    sequence_code: readString(values, "sequence_code"),
    status: readStatus(values),
    effective_from: readString(values, "effective_from"),
    effective_to: readOptionalString(values, "effective_to"),
    source_job_id: readOptionalString(values, "source_job_id") ?? record.source_job_id ?? undefined,
    notes: readOptionalString(values, "notes"),
    attributes: { ...record.attributes },
    change_reason: readString(values, "change_reason"),
  }
}


function buildDimensionPayload(
  values: Record<string, unknown>,
): PositionDimensionCreatePayload {
  return {
    dimension_type: readDimensionType(values, "dimension_type") ?? "LEVEL",
    code: readString(values, "code"),
    name: readString(values, "name"),
    parent_dimension_type: readDimensionType(values, "parent_dimension_type"),
    parent_dimension_code: readOptionalString(values, "parent_dimension_code"),
    sort_order: readNumber(values, "sort_order"),
    status: readStatus(values),
    effective_from: readString(values, "effective_from"),
    effective_to: readOptionalString(values, "effective_to"),
    notes: readOptionalString(values, "notes"),
    change_reason: readString(values, "change_reason"),
  }
}


function buildDimensionVersionPayload(
  values: Record<string, unknown>,
): PositionDimensionVersionPayload {
  return {
    name: readString(values, "name"),
    parent_dimension_type: readDimensionType(values, "parent_dimension_type"),
    parent_dimension_code: readOptionalString(values, "parent_dimension_code"),
    sort_order: readNumber(values, "sort_order"),
    status: readStatus(values),
    effective_from: readString(values, "effective_from"),
    effective_to: readOptionalString(values, "effective_to"),
    notes: readOptionalString(values, "notes"),
    change_reason: readString(values, "change_reason"),
  }
}


export function PositionWorkspace({ token, canAdmin }: PositionWorkspaceProps): React.JSX.Element {
  const [activeTab, setActiveTab] = useState<"positions" | "dimensions">("positions")
  const [effectiveAt, setEffectiveAt] = useState(today)
  const [searchText, setSearchText] = useState("")
  const [page, setPage] = useState(1)
  const [positions, setPositions] = useState<readonly Position[]>([])
  const [positionTotal, setPositionTotal] = useState(0)
  const [dimensions, setDimensions] = useState<readonly PositionDimension[]>([])
  const [loading, setLoading] = useState(true)
  const [dimensionLoading, setDimensionLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [editorError, setEditorError] = useState<string | null>(null)
  const [forbidden, setForbidden] = useState(false)
  const [editor, setEditor] = useState<PositionEditor>(null)
  const [editorValues, setEditorValues] = useState<Record<string, unknown>>({})
  const [form] = Form.useForm()

  const loadPositions = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await positionApi.positions(token, {
        effectiveAt,
        limit: POSITION_PAGE_SIZE,
        offset: (page - 1) * POSITION_PAGE_SIZE,
      })
      setPositions(result.items)
      setPositionTotal(result.total)
    } catch (caught) {
      if (caught instanceof ApiClientError && caught.status === 403) setForbidden(true)
      else setError(caught instanceof Error ? caught.message : "职位列表加载失败")
    } finally {
      setLoading(false)
    }
  }, [effectiveAt, page, token])

  const loadDimensions = useCallback(async () => {
    setDimensionLoading(true)
    setError(null)
    try {
      const result = await positionApi.dimensions(token, {
        effectiveAt,
        limit: DIMENSION_FETCH_LIMIT,
        offset: 0,
      })
      setDimensions(result.items)
    } catch (caught) {
      if (caught instanceof ApiClientError && caught.status === 403) setForbidden(true)
      else setError(caught instanceof Error ? caught.message : "职务维度加载失败")
    } finally {
      setDimensionLoading(false)
    }
  }, [effectiveAt, token])

  useEffect(() => {
    void loadPositions()
  }, [loadPositions])

  useEffect(() => {
    void loadDimensions()
  }, [loadDimensions])

  const visiblePositions = useMemo(() => {
    const query = searchText.trim().toLocaleLowerCase()
    if (!query) return positions
    return positions.filter((item) => (
      item.name.toLocaleLowerCase().includes(query)
      || item.code.toLocaleLowerCase().includes(query)
    ))
  }, [positions, searchText])

  const visibleDimensions = useMemo(() => {
    const query = searchText.trim().toLocaleLowerCase()
    if (!query) return dimensions
    return dimensions.filter((item) => (
      item.name.toLocaleLowerCase().includes(query)
      || item.code.toLocaleLowerCase().includes(query)
    ))
  }, [dimensions, searchText])

  const dimensionCounts = useMemo(() => {
    const counts: Record<PositionDimensionType, number> = {
      LEVEL: 0,
      GRADE: 0,
      CLASS: 0,
      SEQUENCE: 0,
    }
    for (const item of dimensions) counts[item.dimension_type] += 1
    return counts
  }, [dimensions])

  // 职位只能引用生效日期上有效的启用维度，后端对停用维度直接返回 422。
  const dimensionOptions = useMemo(() => {
    const options: Record<PositionDimensionType, { label: string; value: string }[]> = {
      LEVEL: [],
      GRADE: [],
      CLASS: [],
      SEQUENCE: [],
    }
    for (const item of dimensions) {
      if (item.status !== "active") continue
      options[item.dimension_type].push({ label: `${item.name} (${item.code})`, value: item.code })
    }
    return options
  }, [dimensions])

  const parentOptions = useMemo(() => dimensions.map((item) => ({
    label: `${dimensionTypeLabels[item.dimension_type]} · ${item.name} (${item.code})`,
    value: `${item.dimension_type}:${item.code}`,
  })), [dimensions])

  const parentReference = Form.useWatch("parent_reference", form) as string | undefined

  useEffect(() => {
    if (!parentReference) {
      form.setFieldsValue({ parent_dimension_type: undefined, parent_dimension_code: undefined })
      return
    }
    const [parentType, ...codeParts] = parentReference.split(":")
    form.setFieldsValue({
      parent_dimension_type: parentType,
      parent_dimension_code: codeParts.join(":"),
    })
  }, [form, parentReference])

  const editorRecord = editor?.kind === "position" ? editor.record : undefined
  const editorDimension = editor?.kind === "dimension" ? editor.record : undefined

  function openPositionEditor(record?: Position): void {
    setEditorError(null)
    setEditorValues(record
      ? {
        name: record.name,
        level_code: record.level_code,
        grade_code: record.grade_code,
        class_code: record.class_code,
        sequence_code: record.sequence_code,
        status: record.status,
        effective_from: nextEffectiveFrom(record.effective_from),
        effective_to: record.effective_to ?? undefined,
        notes: record.notes ?? undefined,
      }
      : { status: "active", effective_from: today() })
    setEditor({ kind: "position", record })
  }

  function openDimensionEditor(record?: PositionDimension): void {
    setEditorError(null)
    setEditorValues(record
      ? {
        name: record.name,
        parent_reference: record.parent_dimension_type && record.parent_dimension_code
          ? `${record.parent_dimension_type}:${record.parent_dimension_code}`
          : undefined,
        parent_dimension_type: record.parent_dimension_type ?? undefined,
        parent_dimension_code: record.parent_dimension_code ?? undefined,
        sort_order: record.sort_order,
        status: record.status,
        effective_from: nextEffectiveFrom(record.effective_from),
        effective_to: record.effective_to ?? undefined,
        notes: record.notes ?? undefined,
      }
      : {
        dimension_type: "LEVEL",
        sort_order: 0,
        status: "active",
        effective_from: today(),
      })
    setEditor({ kind: "dimension", record })
  }

  function closeEditor(): void {
    setEditor(null)
    setEditorError(null)
  }

  function changeEffectiveAt(value: string): void {
    setPage(1)
    setEffectiveAt(value || today())
  }

  async function save(values: Record<string, unknown>): Promise<void> {
    if (!editor) return
    setSaving(true)
    setEditorError(null)
    try {
      if (editor.kind === "position") {
        if (editor.record) {
          await positionApi.createPositionVersion(
            token,
            editor.record.id,
            buildPositionVersionPayload(values, editor.record),
          )
        } else {
          await positionApi.createPosition(token, buildPositionPayload(values))
        }
      } else if (editor.record) {
        await positionApi.createDimensionVersion(
          token,
          editor.record.id,
          buildDimensionVersionPayload(values),
        )
      } else {
        await positionApi.createDimension(token, buildDimensionPayload(values))
      }
      closeEditor()
      await Promise.all([loadPositions(), loadDimensions()])
    } catch (caught) {
      setEditorError(caught instanceof Error ? caught.message : "保存失败")
    } finally {
      setSaving(false)
    }
  }

  const positionColumns: ColumnsType<Position> = [
    { title: "职位编码", dataIndex: "code", width: 160 },
    { title: "职位名称", dataIndex: "name", width: 220 },
    { title: "职级", dataIndex: "level_code", width: 130 },
    { title: "职等", dataIndex: "grade_code", width: 130 },
    { title: "职类", dataIndex: "class_code", width: 130 },
    { title: "序列", dataIndex: "sequence_code", width: 130 },
    {
      title: "生效日期",
      key: "effective_period",
      width: 200,
      render: (_value, record) => `${record.effective_from} 至 ${record.effective_to ?? "长期"}`,
    },
    { title: "版本", dataIndex: "version", width: 90 },
    {
      title: "状态",
      dataIndex: "status",
      width: 100,
      render: (value: string) => (
        <Tag color={value === "active" ? "success" : "default"} variant="outlined">
          {value === "active" ? "启用" : "停用"}
        </Tag>
      ),
    },
    {
      title: "操作",
      key: "action",
      width: 120,
      render: (_value, record) => (
        <Button type="link" disabled={!canAdmin} onClick={() => openPositionEditor(record)}>
          新增版本
        </Button>
      ),
    },
  ]

  const dimensionColumns: ColumnsType<PositionDimension> = [
    {
      title: "维度类型",
      dataIndex: "dimension_type",
      width: 120,
      render: (value: PositionDimensionType) => (
        <Tag color="processing" variant="outlined">{dimensionTypeLabels[value]}</Tag>
      ),
    },
    { title: "维度代码", dataIndex: "code", width: 180 },
    { title: "维度名称", dataIndex: "name", width: 200 },
    {
      title: "上级维度",
      key: "parent",
      width: 200,
      render: (_value, record) => (
        record.parent_dimension_type && record.parent_dimension_code
          ? `${dimensionTypeLabels[record.parent_dimension_type]} · ${record.parent_dimension_code}`
          : "—"
      ),
    },
    { title: "显示顺序", dataIndex: "sort_order", width: 110 },
    {
      title: "生效日期",
      key: "effective_period",
      width: 200,
      render: (_value, record) => `${record.effective_from} 至 ${record.effective_to ?? "长期"}`,
    },
    { title: "版本", dataIndex: "version", width: 90 },
    {
      title: "状态",
      dataIndex: "status",
      width: 100,
      render: (value: string) => (
        <Tag color={value === "active" ? "success" : "default"} variant="outlined">
          {value === "active" ? "启用" : "停用"}
        </Tag>
      ),
    },
    {
      title: "操作",
      key: "action",
      width: 120,
      render: (_value, record) => (
        <Button type="link" disabled={!canAdmin} onClick={() => openDimensionEditor(record)}>
          新增版本
        </Button>
      ),
    },
  ]

  // Requirement: ORG-PROT-001 / D-091 — 筛选区放在页签内容之内并采用扁平样式；
  // 职位页「重置」只清空搜索词，生效日期按画板保留。
  const renderFilters = (placeholder: string) => (
    <FilterBar
      layout="flat"
      ariaLabel="职位筛选"
      actions={(
        <Button onClick={() => {
          setSearchText("")
          setPage(1)
        }}>重置</Button>
      )}
    >
      <EffectiveDatePicker label="生效日期" value={effectiveAt} onChange={changeEffectiveAt} />
      <FilterField label="搜索">
        <Input.Search
          allowClear
          aria-label="搜索职位或职务维度"
          placeholder={placeholder}
          value={searchText}
          onChange={(event) => setSearchText(event.target.value)}
        />
      </FilterField>
    </FilterBar>
  )

  if (forbidden) {
    return (
      <WorkspaceDenied
        titleId="position-title"
        title="职位管理"
        message="无权查看职位管理"
        description="请联系主管理员分配职务体系维护权限。"
      />
    )
  }

  return (
    <WorkspaceShell
      titleId="position-title"
      title="职位管理"
      subtitle="维护职位目录及其生效版本。职位引用职级、职等、职类和序列四类职务维度，每次调整都会按生效日期形成新版本，历史版本不被覆盖。"
      error={error}
      onErrorClose={() => setError(null)}
    >
      {/* Requirement: D-091 / ORG-PROT-001 — 指标条位于页头之下、页签之上。 */}
      <MetricStrip items={[
        { label: "有效职位", value: positionTotal },
        { label: "职级", value: dimensionCounts.LEVEL },
        { label: "职等", value: dimensionCounts.GRADE },
        { label: "职类", value: dimensionCounts.CLASS },
        { label: "序列", value: dimensionCounts.SEQUENCE },
      ]} />
      <Tabs
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as "positions" | "dimensions")}
        items={[
          {
            key: "positions",
            label: "职位列表",
            children: (
              <>
                {renderFilters("搜索职位名称或编码")}
                <div className="tab-actions">
                  <Button
                    type="primary"
                    disabled={!canAdmin}
                    onClick={() => openPositionEditor()}
                  >
                    新建职位
                  </Button>
                </div>
                <DataTable<Position>
                  rowKey="id"
                  loading={loading}
                  dataSource={[...visiblePositions]}
                  scroll={{ x: 1180 }}
                  columns={positionColumns}
                  emptyText="没有符合条件的职位"
                  pagination={{
                    current: page,
                    pageSize: POSITION_PAGE_SIZE,
                    total: positionTotal,
                    showSizeChanger: false,
                    showTotalLabel: "个职位",
                    onChange: (next) => setPage(next),
                  }}
                />
              </>
            ),
          },
          {
            key: "dimensions",
            label: "职务维度",
            children: (
              <>
                {renderFilters("搜索维度名称或代码")}
                <div className="tab-actions">
                  <Button
                    type="primary"
                    disabled={!canAdmin}
                    onClick={() => openDimensionEditor()}
                  >
                    新建职务维度
                  </Button>
                </div>
                <DataTable<PositionDimension>
                  rowKey="id"
                  loading={dimensionLoading}
                  dataSource={[...visibleDimensions]}
                  scroll={{ x: 1180 }}
                  columns={dimensionColumns}
                  emptyText="没有符合条件的职务维度"
                  pagination={{
                    pageSize: DIMENSION_PAGE_SIZE,
                    showSizeChanger: false,
                    showTotalLabel: "个职务维度",
                  }}
                />
              </>
            ),
          },
        ]}
      />

      <Modal
        destroyOnHidden
        width={760}
        title={editor?.kind === "dimension"
          ? (editor.record ? "新增职务维度版本" : "新建职务维度")
          : (editor?.record ? "新增职位版本" : "新建职位")}
        open={editor !== null}
        okText="保存"
        confirmLoading={saving}
        onOk={() => form.submit()}
        onCancel={closeEditor}
      >
        {editorError && (
          <Alert closable={{ onClose: () => setEditorError(null) }} type="error" showIcon title={editorError} />
        )}
        <Form
          form={form}
          layout="vertical"
          requiredMark={false}
          initialValues={editorValues}
          onFinish={(values) => void save(values)}
        >
          {editor?.kind === "position" && (
            <>
              <Divider titlePlacement="left" plain>职位标识</Divider>
              {editor.record ? (
                <Typography.Paragraph type="secondary">
                  稳定编码：{editor.record.code}（版本不修改编码）
                </Typography.Paragraph>
              ) : (
                <Form.Item
                  label="职位编码"
                  name="code"
                  rules={[
                    { required: true, message: "请输入职位编码" },
                    { pattern: CODE_PATTERN, message: "使用大写字母、数字、点、下划线或短横线，最多 50 位" },
                  ]}
                >
                  <Input placeholder="例如 JOB_001" />
                </Form.Item>
              )}
              <Form.Item label="职位名称" name="name" rules={[{ required: true, message: "请输入职位名称" }]}>
                <Input placeholder="例如 高级后端工程师" />
              </Form.Item>
              <Divider titlePlacement="left" plain>所属维度</Divider>
              <Form.Item label="职级" name="level_code" rules={[{ required: true, message: "请选择职级" }]}>
                <Select
                  showSearch
                  optionFilterProp="label"
                  placeholder="选择职级"
                  options={dimensionOptions.LEVEL}
                />
              </Form.Item>
              <Form.Item label="职等" name="grade_code" rules={[{ required: true, message: "请选择职等" }]}>
                <Select
                  showSearch
                  optionFilterProp="label"
                  placeholder="选择职等"
                  options={dimensionOptions.GRADE}
                />
              </Form.Item>
              <Form.Item label="职类" name="class_code" rules={[{ required: true, message: "请选择职类" }]}>
                <Select
                  showSearch
                  optionFilterProp="label"
                  placeholder="选择职类"
                  options={dimensionOptions.CLASS}
                />
              </Form.Item>
              <Form.Item label="序列" name="sequence_code" rules={[{ required: true, message: "请选择序列" }]}>
                <Select
                  showSearch
                  optionFilterProp="label"
                  placeholder="选择序列"
                  options={dimensionOptions.SEQUENCE}
                />
              </Form.Item>
              <Divider titlePlacement="left" plain>生效与变更</Divider>
              <Form.Item label="状态" name="status" rules={[{ required: true, message: "请选择状态" }]}>
                <Select options={statusOptions} />
              </Form.Item>
              <Form.Item
                label="生效日期"
                name="effective_from"
                rules={[
                  { required: true, message: "请选择生效日期" },
                  ...(editorRecord ? [{
                    validator: (_rule: unknown, value: string | undefined) => (
                      value && value <= editorRecord.effective_from
                        ? Promise.reject(new Error(`新版本生效日期必须晚于 ${editorRecord.effective_from}`))
                        : Promise.resolve()
                    ),
                  }] : []),
                ]}
              >
                <Input type="date" />
              </Form.Item>
              <Form.Item
                label="失效日期"
                name="effective_to"
                dependencies={["effective_from"]}
                rules={[{
                  validator: (_rule: unknown, value: string | undefined) => {
                    const effectiveFrom = readString(
                      { effective_from: form.getFieldValue("effective_from") },
                      "effective_from",
                    )
                    return value && effectiveFrom && value < effectiveFrom
                      ? Promise.reject(new Error("失效日期不能早于生效日期"))
                      : Promise.resolve()
                  },
                }]}
              >
                <Input type="date" />
              </Form.Item>
              <Form.Item label="变更原因" name="change_reason" rules={[{ required: true, message: "请填写变更原因" }]}>
                <Input.TextArea rows={2} placeholder="说明本次调整原因，后端按此记录版本审计" />
              </Form.Item>
              <Form.Item label="备注" name="notes">
                <Input.TextArea rows={2} />
              </Form.Item>
            </>
          )}
          {editor?.kind === "dimension" && (
            <>
              <Divider titlePlacement="left" plain>维度标识</Divider>
              {editor.record ? (
                <Typography.Paragraph type="secondary">
                  稳定编码：{dimensionTypeLabels[editor.record.dimension_type]} · {editor.record.code}
                  （版本不修改编码）
                </Typography.Paragraph>
              ) : (
                <>
                  <Form.Item label="维度类型" name="dimension_type" rules={[{ required: true, message: "请选择维度类型" }]}>
                    <Select options={dimensionTypeOptions} />
                  </Form.Item>
                  <Form.Item
                    label="维度代码"
                    name="code"
                    rules={[
                      { required: true, message: "请输入维度代码" },
                      { pattern: CODE_PATTERN, message: "使用大写字母、数字、点、下划线或短横线，最多 50 位" },
                    ]}
                  >
                    <Input placeholder="例如 LEVEL_06" />
                  </Form.Item>
                </>
              )}
              <Form.Item label="维度名称" name="name" rules={[{ required: true, message: "请输入维度名称" }]}>
                <Input placeholder="例如 六级" />
              </Form.Item>
              <Divider titlePlacement="left" plain>层级与顺序</Divider>
              <Form.Item label="上级维度" name="parent_reference">
                <Select
                  allowClear
                  showSearch
                  optionFilterProp="label"
                  placeholder="选择上级维度（可选）"
                  options={parentOptions.filter((option) => (
                    !editorDimension
                    || option.value !== `${editorDimension.dimension_type}:${editorDimension.code}`
                  ))}
                />
              </Form.Item>
              <Form.Item name="parent_dimension_type" hidden><Input /></Form.Item>
              <Form.Item name="parent_dimension_code" hidden><Input /></Form.Item>
              <Form.Item label="显示顺序" name="sort_order" rules={[{ required: true, message: "请输入显示顺序" }]}>
                <InputNumber min={0} precision={0} style={{ width: "100%" }} />
              </Form.Item>
              <Divider titlePlacement="left" plain>生效与变更</Divider>
              <Form.Item label="状态" name="status" rules={[{ required: true, message: "请选择状态" }]}>
                <Select options={statusOptions} />
              </Form.Item>
              <Form.Item
                label="生效日期"
                name="effective_from"
                rules={[
                  { required: true, message: "请选择生效日期" },
                  ...(editorDimension ? [{
                    validator: (_rule: unknown, value: string | undefined) => (
                      value && value <= editorDimension.effective_from
                        ? Promise.reject(new Error(`新版本生效日期必须晚于 ${editorDimension.effective_from}`))
                        : Promise.resolve()
                    ),
                  }] : []),
                ]}
              >
                <Input type="date" />
              </Form.Item>
              <Form.Item
                label="失效日期"
                name="effective_to"
                dependencies={["effective_from"]}
                rules={[{
                  validator: (_rule: unknown, value: string | undefined) => {
                    const effectiveFrom = readString(
                      { effective_from: form.getFieldValue("effective_from") },
                      "effective_from",
                    )
                    return value && effectiveFrom && value < effectiveFrom
                      ? Promise.reject(new Error("失效日期不能早于生效日期"))
                      : Promise.resolve()
                  },
                }]}
              >
                <Input type="date" />
              </Form.Item>
              <Form.Item label="变更原因" name="change_reason" rules={[{ required: true, message: "请填写变更原因" }]}>
                <Input.TextArea rows={2} placeholder="说明本次调整原因，后端按此记录版本审计" />
              </Form.Item>
              <Form.Item label="备注" name="notes">
                <Input.TextArea rows={2} />
              </Form.Item>
            </>
          )}
        </Form>
      </Modal>
    </WorkspaceShell>
  )
}
