// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { Button, Radio, Select, Typography } from "antd"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"

import { attendanceApi } from "./api"
import type { AttendanceCalculationScope } from "./api"
import type { AttendanceEmploymentOption } from "./types"


const SCOPE_OPTIONS = [
  { label: "全员", value: "all" },
  { label: "指定人员", value: "selected" },
  { label: "排除人员", value: "excluded" },
]

/** 人员搜索的防抖间隔（毫秒）。 */
const SEARCH_DEBOUNCE_MS = 300


export interface AttendanceScopePickerProps {
  readonly token: string
  /** 多选框的表单 id：用于定位控件与自动化测试。 */
  readonly id: string
  readonly scope: AttendanceCalculationScope
  /** scope=selected 时表示「要计算的人」，scope=excluded 时表示「要排除的人」。 */
  readonly employmentIds: readonly string[]
  readonly onChange: (scope: AttendanceCalculationScope, employmentIds: readonly string[]) => void
}


interface EmploymentChoice {
  readonly value: string
  readonly label: string
}


/** 人员选项文案：姓名 (工号)，沿用考勤面板既有写法。 */
function toChoice(item: AttendanceEmploymentOption): EmploymentChoice {
  return { value: item.id, label: `${item.display_name} (${item.employee_number ?? "无工号"})` }
}


/**
 * 人员范围选择器：全员 / 指定人员 / 排除人员。
 *
 * 默认「全员」——200 人规模下不应该让人逐个点名。
 * 「指定人员」与「排除人员」共用一份已选人员列表，由 scope 决定这些人
 * 是「要算的人」还是「要排除的人」；切回「全员」时清空列表，
 * 因为 scope=all 要求 employment_ids 为空数组。
 *
 * 人员下拉走**服务端搜索**（`employmentOptions(token, search)`，防抖 300ms）：
 * 该接口单页上限 200 人，只在前端过滤已加载的这一页会选不到后面的人。
 * 接口不按在职状态过滤（与「全员」口径同源），补算历史月份时要能算到离职人员。
 */
export function AttendanceScopePicker({ token, id, scope, employmentIds, onChange }: AttendanceScopePickerProps) {
  const [search, setSearch] = useState("")
  const [choices, setChoices] = useState<readonly EmploymentChoice[]>([])
  const [knownLabels, setKnownLabels] = useState<Readonly<Record<string, string>>>({})
  const [headcount, setHeadcount] = useState<number | null>(null)
  const [total, setTotal] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const firstLoadRef = useRef(true)

  const loadChoices = useCallback(async (keyword: string) => {
    setLoading(true)
    setLoadError(null)
    try {
      const page = await attendanceApi.employmentOptions(token, keyword)
      const loaded = page.items.map(toChoice)
      setChoices(loaded)
      setTotal(page.total)
      setKnownLabels((current) => {
        const next: Record<string, string> = { ...current }
        for (const choice of loaded) next[choice.value] = choice.label
        return next
      })
      if (!keyword) setHeadcount(page.total)
    } catch (caught) {
      setLoadError(caught instanceof Error ? caught.message : "人员列表加载失败，请稍后重试")
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    if (firstLoadRef.current) {
      firstLoadRef.current = false
      void loadChoices("")
      return
    }
    const timer = setTimeout(() => { void loadChoices(search) }, SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [search, loadChoices])

  /** 已加载人员 + 已选人员的缓存，保证换搜索词后仍能显示已选人员的姓名。 */
  const options = useMemo<EmploymentChoice[]>(() => {
    const merged = new Map<string, EmploymentChoice>()
    for (const [value, label] of Object.entries(knownLabels)) merged.set(value, { value, label })
    for (const choice of choices) merged.set(choice.value, choice)
    return [...merged.values()]
  }, [knownLabels, choices])

  function handleScopeChange(next: AttendanceCalculationScope): void {
    onChange(next, next === "all" ? [] : employmentIds)
  }

  function handleIdsChange(next: readonly string[]): void {
    onChange(scope, [...next])
  }

  /** 把当前已加载的人员全部加入列表（已选的人员保留）。 */
  function selectAll(): void {
    onChange(scope, [...new Set([...employmentIds, ...choices.map((choice) => choice.value)])])
  }

  function clearAll(): void {
    onChange(scope, [])
  }

  const selectedCount = employmentIds.length
  const totalLabel = search.trim() ? `匹配 ${total ?? 0} 人` : `共 ${total ?? 0} 人`
  const hint = scope === "all"
    ? `全员：本次计算覆盖全部 ${headcount ?? 0} 人。`
    : scope === "selected"
      ? selectedCount === 0
        ? "指定人员：还没有选择人员，请至少选择 1 个人。"
        : `指定人员：只计算选中的 ${selectedCount} 个人，未选中的人员不会重算。`
      : selectedCount === 0
        ? "排除人员：计算全员，当前不排除任何人。"
        : `排除人员：计算全员，但排除选中的 ${selectedCount} 个人。`

  return <div style={{ display: "grid", gap: 8 }}>
    <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 12 }}>
      <Typography.Text strong>人员范围</Typography.Text>
      <Radio.Group
        optionType="button"
        buttonStyle="solid"
        options={SCOPE_OPTIONS}
        value={scope}
        onChange={(event) => handleScopeChange(event.target.value as AttendanceCalculationScope)}
      />
      {scope === "all" && <Typography.Text type="secondary">{hint}</Typography.Text>}
    </div>
    {scope !== "all" && <>
      <Typography.Text type="secondary">{hint}</Typography.Text>
      <Typography.Text type="secondary">输入姓名或工号可搜索定位人员。</Typography.Text>
      <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 8 }}>
        <Button size="small" onClick={selectAll}>{scope === "excluded" ? `排除已加载的 ${choices.length} 人` : `选中已加载的 ${choices.length} 人`}</Button>
        <Button size="small" onClick={clearAll}>清空</Button>
        <Typography.Text type="secondary">已选 {selectedCount} 人 · 已加载 {choices.length} 人 · {totalLabel}</Typography.Text>
      </div>
      {total !== null && total > choices.length && <Typography.Text type="warning">
        {scope === "excluded"
          ? `共 ${total} 人，当前只加载了前 ${choices.length} 人。「排除已加载的 ${choices.length} 人」只排除这 ${choices.length} 人，其余人员仍会参与计算；需要排除的人请用姓名或工号搜索添加。`
          : `共 ${total} 人，当前只加载了前 ${choices.length} 人；其余人员请用姓名或工号搜索添加。`}
      </Typography.Text>}
      <Select
        id={id}
        mode="multiple"
        showSearch
        filterOption={false}
        allowClear
        value={[...employmentIds]}
        options={options}
        onChange={(next) => handleIdsChange(Array.isArray(next) ? next.map((item) => String(item)) : [])}
        onSearch={setSearch}
        placeholder={scope === "selected" ? "选择要计算的人员" : "选择要排除的人员"}
        loading={loading}
        notFoundContent={loading ? "人员加载中" : "没有匹配的人员"}
        style={{ width: "100%" }}
      />
    </>}
    {loadError && <Typography.Text type="danger">{loadError}</Typography.Text>}
  </div>
}
