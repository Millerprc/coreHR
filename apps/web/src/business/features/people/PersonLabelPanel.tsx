// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import {
  Button,
  Divider,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Tag,
  Tooltip,
  Typography,
} from "antd"
import { useCallback, useEffect, useMemo, useState } from "react"
import type { JSX, ReactNode } from "react"

import { EmptyState } from "../../components/EmptyState"
import { WorkspaceError } from "../../components/WorkspaceShell"
import { labelApi } from "./label-api"
import type { LabelLibraryType, LabelTypeOption, PersonLabel } from "./label-api"


export interface PersonLabelPanelProps {
  readonly token: string
  readonly canAdmin: boolean
  readonly personId: string
}


const SOURCE_MANUAL = "MANUAL"
const SOURCE_AI = "AI"
const AI_TAG_COLOR = "purple"
const MANUAL_TAG_COLOR = "blue"
const TYPE_FILTER_FIELD = "label_type_filter"


function localDate(): string {
  const now = new Date()
  const offset = now.getTimezoneOffset() * 60_000
  return new Date(now.getTime() - offset).toISOString().slice(0, 10)
}


export function PersonLabelPanel({ token, canAdmin, personId }: PersonLabelPanelProps): JSX.Element {
  const [labels, setLabels] = useState<readonly PersonLabel[]>([])
  const [labelTypes, setLabelTypes] = useState<readonly LabelTypeOption[]>([])
  const [library, setLibrary] = useState<readonly LabelLibraryType[]>([])
  const [typeFilter, setTypeFilter] = useState<string | undefined>(undefined)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [endingId, setEndingId] = useState<string | null>(null)
  const [panelError, setPanelError] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [form] = Form.useForm()

  const load = useCallback(async () => {
    setLoading(true)
    setPanelError(null)
    const [labelResult, typeResult, libraryResult] = await Promise.allSettled([
      labelApi.personLabels(token, personId),
      labelApi.labelTypes(token),
      labelApi.labelLibrary(token),
    ])
    if (labelResult.status === "fulfilled") {
      setLabels(labelResult.value.items)
    } else {
      setPanelError(labelResult.reason instanceof Error ? labelResult.reason.message : "员工标签加载失败")
    }
    if (typeResult.status === "fulfilled") {
      setLabelTypes(typeResult.value)
    } else {
      // 标签类型清单取不到时退回显示编码，不阻断标签列表展示。
      setLabelTypes([])
    }
    if (libraryResult.status === "fulfilled") {
      setLibrary(libraryResult.value)
    } else {
      setLibrary([])
    }
    setLoading(false)
  }, [personId, token])

  useEffect(() => { void load() }, [load])

  // 表单生命周期：每次打开新增标签都是一份空表单，生效日期默认当天，来源默认人工标记。
  useEffect(() => {
    if (!creating) return
    setTypeFilter(undefined)
    form.setFieldsValue({
      [TYPE_FILTER_FIELD]: undefined,
      labels: [],
      source: SOURCE_MANUAL,
      effective_from: localDate(),
    })
  }, [creating, form])

  const typeNames = useMemo(
    () => new Map(labelTypes.map((item) => [item.code, item.name])),
    [labelTypes],
  )

  // 标签库索引：选择器的值用标签项编码，取回所属标签类型以组装批量请求。
  const libraryItems = useMemo(() => {
    const items = new Map<string, { readonly typeCode: string; readonly code: string; readonly name: string }>()
    for (const type of library) {
      for (const item of type.items) {
        if (!items.has(item.code)) {
          items.set(item.code, { typeCode: type.typeCode, code: item.code, name: item.name })
        }
      }
    }
    return items
  }, [library])

  const groups = useMemo(() => {
    const grouped = new Map<string, PersonLabel[]>()
    for (const label of labels) {
      const bucket = grouped.get(label.labelType)
      if (bucket) bucket.push(label)
      else grouped.set(label.labelType, [label])
    }
    return [...grouped.entries()]
      .sort((left, right) => left[0].localeCompare(right[0]))
      .map(([code, items]) => ({ code, name: typeNames.get(code) || code, items }))
  }, [labels, typeNames])

  const labelTypeOptions = useMemo(
    () => labelTypes.map((item) => ({
      value: item.code,
      label: item.name && item.name !== item.code ? `${item.name}（${item.code}）` : item.code,
    })),
    [labelTypes],
  )

  const libraryOptions = useMemo(
    () => library
      .filter((type) => !typeFilter || type.typeCode === typeFilter)
      .map((type) => ({
        label: typeNames.get(type.typeCode) || type.typeName || type.typeCode,
        options: type.items.map((item) => ({ value: item.code, label: item.name || item.code })),
      }))
      .filter((group) => group.options.length > 0),
    [library, typeFilter, typeNames],
  )

  function applyTypeFilter(next: string | undefined): void {
    setTypeFilter(next)
    const allowed = new Set(
      library
        .filter((type) => !next || type.typeCode === next)
        .flatMap((type) => type.items.map((item) => item.code)),
    )
    const selected = form.getFieldValue("labels")
    if (!Array.isArray(selected)) return
    const kept = selected.filter((code: unknown) => allowed.has(String(code)))
    if (kept.length !== selected.length) form.setFieldValue("labels", kept)
  }

  function openCreate(): void {
    setFormError(null)
    setCreating(true)
  }

  async function save(values: Record<string, unknown>): Promise<void> {
    setSaving(true)
    setFormError(null)
    try {
      const selected = Array.isArray(values.labels) ? values.labels.map((code) => String(code)) : []
      const entries = selected
        .map((code) => libraryItems.get(code))
        .filter((item): item is { readonly typeCode: string; readonly code: string; readonly name: string } => Boolean(item))
      if (entries.length !== selected.length) {
        throw new Error("选中的标签已不在标签库中，请重新选择")
      }
      await labelApi.createPersonLabelsBatch(token, personId, {
        effectiveFrom: String(values.effective_from ?? ""),
        source: String(values.source ?? SOURCE_MANUAL),
        labels: entries.map((item) => ({ labelTypeCode: item.typeCode, labelCode: item.code })),
      })
      setCreating(false)
      await load()
    } catch (caught) {
      // 失败时保留用户输入，错误落在新增标签弹窗内；批量接口整批原子，不会产生部分结果。
      setFormError(caught instanceof Error ? caught.message : "标签保存失败")
    } finally {
      setSaving(false)
    }
  }

  async function endLabel(labelId: string): Promise<void> {
    setEndingId(labelId)
    setPanelError(null)
    try {
      await labelApi.endPersonLabel(token, labelId)
      await load()
    } catch (caught) {
      setPanelError(caught instanceof Error ? caught.message : "标签结束失败")
    } finally {
      setEndingId(null)
    }
  }

  function renderLabel(label: PersonLabel) {
    const isAi = label.isAiGenerated || label.source.toUpperCase() === SOURCE_AI
    const sourceText = isAi ? "AI 生成" : "人工标记"
    const typeText = typeNames.get(label.labelType) || label.labelType
    const displayName = libraryItems.get(label.labelName)?.name || label.labelName
    const periodText = label.effectiveTo
      ? `${label.effectiveFrom} 至 ${label.effectiveTo}`
      : `${label.effectiveFrom} 起`
    const validityText = label.effectiveTo ? "已结束" : "当前有效"
    // Requirement: D-091 — 单个标签两行结构：上行是标签本体（人工蓝 / AI 紫并带 🤖），
    // 下行是来源、有效期与有效性，结束操作只在标签仍然生效时出现。
    return (
      <div className="label-item" key={label.id}>
        <div className="label-item-tag">
          <Tooltip title={`标签类型：${typeText} · 来源：${sourceText} · 有效期：${label.effectiveFrom} 至 ${label.effectiveTo ?? "当前有效"}`}>
            <Tag color={isAi ? AI_TAG_COLOR : MANUAL_TAG_COLOR} variant="outlined">
              {isAi ? `🤖 ${displayName}` : displayName}
            </Tag>
          </Tooltip>
        </div>
        <div className="label-item-meta">
          <span>{sourceText}</span>
          <span>{periodText}</span>
          <span>{validityText}</span>
          {!label.effectiveTo && (
            <Popconfirm
              title={`结束标签「${displayName}」`}
              description="结束为软失效：标签记录保留，仅不再生效，可由管理员重新维护。"
              okText="确认结束"
              cancelText="取消"
              onConfirm={() => void endLabel(label.id)}
            >
              <Button type="link" size="small" danger disabled={!canAdmin} loading={endingId === label.id}>结束</Button>
            </Popconfirm>
          )}
        </div>
      </div>
    )
  }

  let content: ReactNode
  if (loading && labels.length === 0) {
    content = <Typography.Text type="secondary">加载中…</Typography.Text>
  } else if (groups.length === 0) {
    // 加载失败时由上方错误提示说明原因，不再给出“暂无标签”的空态误导。
    content = panelError ? null : <EmptyState description="暂无标签" />
  } else {
    content = (
      <div>
        {groups.map((group) => (
          <div key={group.code}>
            <Divider titlePlacement="left">{group.name}</Divider>
            <div className="label-group-body">
              {group.items.map((label) => renderLabel(label))}
            </div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <>
      <WorkspaceError message={panelError} onClose={() => setPanelError(null)} />
      {/* Requirement: D-091 — 工具条左侧是标签总数，右侧是主操作按钮。 */}
      <div className="tab-actions split">
        <Typography.Text type="secondary">共 {labels.length} 个标签</Typography.Text>
        <Button type="primary" disabled={!canAdmin} onClick={openCreate}>新增标签</Button>
      </div>
      {content}

      {/* Requirement: D-068 / D-069 — 人员档案为宿主页，新增标签属于轻量表单子任务，使用 MODAL 载体并保留宿主页状态。 */}
      <Modal
        destroyOnHidden
        width={520}
        title="批量新增标签"
        open={creating}
        okText="保存"
        cancelText="取消"
        confirmLoading={saving}
        onOk={() => form.submit()}
        onCancel={() => { setFormError(null); setCreating(false) }}
      >
        {formError && (
          <WorkspaceError
            message={formError}
            onClose={() => setFormError(null)}
            style={{ marginBottom: 16 }}
          />
        )}
        <Form
          form={form}
          layout="vertical"
          requiredMark={false}
          onValuesChange={(changed) => {
            if (TYPE_FILTER_FIELD in changed) applyTypeFilter(changed[TYPE_FILTER_FIELD] as string | undefined)
          }}
          onFinish={(values) => void save(values)}
        >
          <Divider titlePlacement="left" plain>从标签库选择</Divider>
          <Form.Item label="标签类型" name={TYPE_FILTER_FIELD}>
            <Select
              allowClear
              showSearch
              optionFilterProp="label"
              placeholder="全部标签类型"
              options={labelTypeOptions}
            />
          </Form.Item>
          <Form.Item label="标签" name="labels" rules={[{ required: true, message: "请至少选择一个标签" }]}>
            <Select
              mode="multiple"
              showSearch
              optionFilterProp="label"
              placeholder="从标签库选择标签"
              options={libraryOptions}
            />
          </Form.Item>
          <Divider titlePlacement="left" plain>生效与来源</Divider>
          <Form.Item label="生效日期" name="effective_from" rules={[{ required: true, message: "请选择生效日期" }]}>
            <Input type="date" />
          </Form.Item>
          <Form.Item label="来源" name="source" rules={[{ required: true }]}>
            <Select options={[
              { value: SOURCE_MANUAL, label: "人工标记" },
              { value: SOURCE_AI, label: "AI 生成" },
            ]} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
