// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { Button, DatePicker, Input, Select, Tag, Tooltip, Typography } from "antd"
import type { TableColumnsType } from "antd"
import type { Dayjs } from "dayjs"
import { useCallback, useEffect, useMemo, useState } from "react"
import type { JSX } from "react"

import { DataTable } from "../../components/DataTable"
import { FilterBar } from "../../components/FilterBar"
import { FilterField } from "../../components/FilterField"
import { WorkspaceShell } from "../../components/WorkspaceShell"
import { auditApi } from "./audit-api"
import type { AuditActionCount, AuditActor, AuditLogEntry, AuditLogFilters } from "./audit-api"


export interface AuditLogWorkspaceProps {
  readonly token: string
  readonly canAdmin: boolean
}


type AuditRange = [Dayjs | null, Dayjs | null] | null


interface AuditFilterDraft {
  readonly range: AuditRange
  readonly action: string | null
  readonly objectType: string
  readonly traceId: string
  readonly actorId: string | null
}


const DEFAULT_PAGE_SIZE = 20
const PAGE_SIZE_OPTIONS = ["20", "50", "100"]
const EMPTY_DRAFT: AuditFilterDraft = {
  range: null,
  action: null,
  objectType: "",
  traceId: "",
  actorId: null,
}


function formatLocalDateTime(value: string): string {
  if (!value) return "—"
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  const pad = (part: number): string => String(part).padStart(2, "0")
  return `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())} `
    + `${pad(parsed.getHours())}:${pad(parsed.getMinutes())}:${pad(parsed.getSeconds())}`
}


function toFilters(draft: AuditFilterDraft): AuditLogFilters {
  const [start, end] = draft.range ?? []
  return {
    occurredFrom: start ? start.startOf("day").toISOString() : undefined,
    occurredTo: end ? end.endOf("day").toISOString() : undefined,
    actorId: draft.actorId ?? undefined,
    action: draft.action ?? undefined,
    objectType: draft.objectType.trim() || undefined,
    traceId: draft.traceId.trim() || undefined,
  }
}


/**
 * Requirement: D-091 — 审计列按画板固定语义着色：
 * 操作列统一用 processing 蓝、来源列统一用 warning 橙；
 * action / object_type / source 一律保留后端原始代码，前端不做中文映射。
 */
const auditColumns: TableColumnsType<AuditLogEntry> = [
  {
    title: "时间",
    dataIndex: "occurredAt",
    width: 180,
    render: (value: string) => formatLocalDateTime(value),
  },
  {
    title: "操作人",
    dataIndex: "actorName",
    width: 180,
    render: (_value: string | null, entry: AuditLogEntry) => entry.actorName ?? entry.actorId ?? "—",
  },
  {
    title: "操作",
    dataIndex: "action",
    width: 200,
    render: (value: string) => (
      <Tag color="processing" variant="outlined">{value || "—"}</Tag>
    ),
  },
  {
    title: "对象类型",
    dataIndex: "objectType",
    width: 140,
    render: (value: string | null) => value ?? "—",
  },
  {
    title: "对象 ID",
    dataIndex: "objectId",
    width: 220,
    render: (value: string | null) => value ?? "—",
  },
  {
    title: "追踪 ID",
    dataIndex: "traceId",
    width: 220,
    render: (value: string | null) => value ?? "—",
  },
  {
    title: "来源",
    dataIndex: "source",
    width: 140,
    render: (value: string | null) => (
      value ? <Tag color="warning" variant="outlined">{value}</Tag> : "—"
    ),
  },
  {
    title: "原因",
    dataIndex: "reason",
    width: 260,
    render: (value: string | null) => (
      value
        ? (
          <Tooltip title={value}>
            <Typography.Text ellipsis style={{ maxWidth: 220, display: "inline-block" }}>{value}</Typography.Text>
          </Tooltip>
        )
        : "—"
    ),
  },
]


/**
 * 审计日志是只读宿主页：筛选、分页与导出都在当前标签页内完成，
 * 不引入 Modal / Drawer / 新标签页等额外载体（见 docs/design/antd-page-interaction-standard.md）。
 */
export function AuditLogWorkspace({ token, canAdmin }: AuditLogWorkspaceProps): JSX.Element {
  const [entries, setEntries] = useState<readonly AuditLogEntry[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE)
  const [filters, setFilters] = useState<AuditLogFilters>({})
  const [draft, setDraft] = useState<AuditFilterDraft>(EMPTY_DRAFT)
  const [actionCounts, setActionCounts] = useState<readonly AuditActionCount[]>([])
  const [actors, setActors] = useState<readonly AuditActor[]>([])
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await auditApi.list(token, filters, { page, pageSize })
      setEntries(result.items)
      setTotal(result.total)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "操作日志加载失败")
    } finally {
      setLoading(false)
    }
  }, [token, filters, page, pageSize])

  useEffect(() => { void load() }, [load])

  useEffect(() => {
    let active = true
    void auditApi.actions(token)
      .then((items) => { if (active) setActionCounts(items) })
      .catch(() => { if (active) setActionCounts([]) })
    void auditApi.actors(token)
      .then((items) => { if (active) setActors(items) })
      .catch(() => { if (active) setActors([]) })
    return () => { active = false }
  }, [token])

  const actionOptions = useMemo(
    () => actionCounts.map((item) => ({ value: item.code, label: `${item.code} (${item.count})` })),
    [actionCounts],
  )

  const actorOptions = useMemo(
    () => actors.map((actor) => ({ value: actor.id, label: actor.name })),
    [actors],
  )

  function applyFilters(): void {
    setPage(1)
    setFilters(toFilters(draft))
  }

  function resetFilters(): void {
    setDraft(EMPTY_DRAFT)
    setPage(1)
    setFilters({})
  }

  async function exportCsv(): Promise<void> {
    setExporting(true)
    setError(null)
    try {
      const download = await auditApi.exportCsv(token, filters)
      const url = URL.createObjectURL(download.blob)
      const anchor = document.createElement("a")
      anchor.href = url
      anchor.download = download.filename
      anchor.click()
      URL.revokeObjectURL(url)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "操作日志导出失败")
    } finally {
      setExporting(false)
    }
  }

  return (
    <WorkspaceShell
      titleId="audit-log-title"
      title="操作日志"
      subtitle="记录平台内的关键写操作，供合规核查与问题追溯使用。日志只读，不提供修改或删除入口。"
      actions={canAdmin ? (
        <Button loading={exporting} onClick={() => void exportCsv()}>导出CSV</Button>
      ) : null}
      error={error}
      onErrorClose={() => setError(null)}
    >
      <FilterBar
        layout="flat"
        ariaLabel="操作日志筛选"
        actions={(
          <>
            <Button onClick={resetFilters}>重置</Button>
            <Button type="primary" onClick={applyFilters}>查询</Button>
          </>
        )}
      >
        <FilterField label="时间范围">
          <DatePicker.RangePicker
            value={draft.range}
            format="YYYY-MM-DD"
            placeholder={["开始日期", "结束日期"]}
            onChange={(value) => setDraft((previous) => ({ ...previous, range: value }))}
          />
        </FilterField>
        <FilterField label="操作类型" htmlFor="audit-action">
          <Select
            id="audit-action"
            aria-label="操作类型"
            allowClear
            showSearch
            optionFilterProp="label"
            virtual={false}
            placeholder="全部操作"
            value={draft.action}
            options={actionOptions}
            onChange={(value: string | null) => setDraft((previous) => ({ ...previous, action: value ?? null }))}
          />
        </FilterField>
        <FilterField label="对象类型">
          <Input
            aria-label="对象类型"
            allowClear
            placeholder="例如 user"
            value={draft.objectType}
            onChange={(event) => setDraft((previous) => ({ ...previous, objectType: event.target.value }))}
          />
        </FilterField>
        <FilterField label="追踪 ID">
          <Input
            aria-label="追踪 ID"
            allowClear
            placeholder="例如 trace-0001"
            value={draft.traceId}
            onChange={(event) => setDraft((previous) => ({ ...previous, traceId: event.target.value }))}
          />
        </FilterField>
        <FilterField label="操作人" htmlFor="audit-actor">
          <Select
            id="audit-actor"
            aria-label="操作人"
            allowClear
            showSearch
            optionFilterProp="label"
            virtual={false}
            placeholder="全部操作人"
            value={draft.actorId}
            options={actorOptions}
            onChange={(value: string | null) => setDraft((previous) => ({ ...previous, actorId: value ?? null }))}
          />
        </FilterField>
      </FilterBar>
      <DataTable<AuditLogEntry>
        rowKey="id"
        loading={loading}
        size="small"
        dataSource={[...entries]}
        columns={auditColumns}
        scroll={{ x: 1400 }}
        emptyText="暂无符合条件的操作日志"
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          pageSizeOptions: PAGE_SIZE_OPTIONS,
          showTotalLabel: "条操作日志",
          onChange: (nextPage, nextPageSize) => {
            if (nextPageSize !== pageSize) {
              setPageSize(nextPageSize)
              setPage(1)
              return
            }
            setPage(nextPage)
          },
        }}
      />
    </WorkspaceShell>
  )
}
