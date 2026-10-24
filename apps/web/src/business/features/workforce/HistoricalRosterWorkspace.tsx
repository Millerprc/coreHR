// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { Alert, Button, Descriptions, Drawer, Input, Select, Space, Tag } from "antd"
import { useCallback, useEffect, useMemo, useState } from "react"

import { workforceApi } from "./api"
import { personFieldLabel } from "./types"
import { apiRequest } from "../../client"
import { DataTable } from "../../components/DataTable"
import { EffectiveDatePicker } from "../../components/EffectiveDatePicker"
import { FilterBar } from "../../components/FilterBar"
import { FilterField } from "../../components/FilterField"
import { WorkspaceShell } from "../../components/WorkspaceShell"


// Requirement: D-102 — 历史花名册：按任意历史时点回看当时的员工名册与当时的信息。
// 时点口径：时点的人员字段值 = 登记值 + 生效日期不晚于该时点的最后一条修正；
// 未被修正过的字段等于当前值。因此本页面不是「某年某月的完整档案快照」。
const FIELD_HISTORY_NOTE =
  "时点的人员字段值 = 登记值 + 生效日期不晚于该时点的最后一条修正；未被修正过的字段等于当前值。"

const ROSTER_PAGE_SIZE = 20

const EMPLOYMENT_STATUS_OPTIONS = [
  { value: "active", label: "在职" },
  { value: "pending_start", label: "待入职" },
]


export interface HistoricalRosterRow {
  readonly person_id: string
  readonly employee_number: string | null
  readonly display_name: string | null
  readonly legal_name: string | null
  readonly organization_id: string | null
  readonly organization_code: string | null
  readonly organization_name: string | null
  readonly job_id: string | null
  readonly job_code: string | null
  readonly job_name: string | null
  readonly employment_status: string | null
  readonly hire_date: string | null
  /** 该行的字段值是否有时点修正历史支撑。 */
  readonly field_history_available: boolean
  readonly corrected_fields: readonly string[]
}


interface HistoricalRosterResponse {
  readonly as_of: string
  readonly items: readonly HistoricalRosterRow[]
  readonly total: number
  readonly limit: number
  readonly offset: number
  readonly field_history_note: string
}


interface HistoricalRosterFilters {
  readonly asOf: string
  readonly organizationId?: string
  readonly employmentStatus?: string
  readonly search: string
}


interface HistoricalRosterWorkspaceProps {
  readonly token: string
}


function localDate(): string {
  const now = new Date()
  const offset = now.getTimezoneOffset() * 60_000
  return new Date(now.getTime() - offset).toISOString().slice(0, 10)
}


function defaultFilters(): HistoricalRosterFilters {
  return { asOf: localDate(), search: "" }
}


export function HistoricalRosterWorkspace({ token }: HistoricalRosterWorkspaceProps): React.JSX.Element {
  const [rows, setRows] = useState<readonly HistoricalRosterRow[]>([])
  const [total, setTotal] = useState(0)
  // 计数行与页头用的时点以服务端回显的 as_of 为准，避免与列表口径漂移。
  const [asOf, setAsOf] = useState(localDate())
  const [organizations, setOrganizations] = useState<
    readonly { id: string; code: string; name: string }[]
  >([])
  // Requirement: D-091 — 筛选为草稿式：改值不立即查询，点「查询」才生效。
  const [filterDraft, setFilterDraft] = useState<HistoricalRosterFilters>(defaultFilters)
  const [filters, setFilters] = useState<HistoricalRosterFilters>(defaultFilters)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [detail, setDetail] = useState<HistoricalRosterRow | null>(null)

  const load = useCallback(async (next: HistoricalRosterFilters, nextPage: number) => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams({
        as_of: next.asOf,
        limit: String(ROSTER_PAGE_SIZE),
        offset: String((nextPage - 1) * ROSTER_PAGE_SIZE),
      })
      if (next.organizationId) params.set("organization_id", next.organizationId)
      if (next.employmentStatus) params.set("employment_status", next.employmentStatus)
      if (next.search.trim()) params.set("search", next.search.trim())
      const result = await apiRequest<HistoricalRosterResponse>(
        `/api/v1/workforce/people/roster-history?${params.toString()}`,
        token,
      )
      setRows(result.items)
      setTotal(result.total)
      setAsOf(result.as_of)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "历史花名册加载失败")
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    void load(defaultFilters(), 1)
  }, [load])

  useEffect(() => {
    void workforceApi
      .organizations(token)
      .then((items) => setOrganizations(items.map((item) => ({ id: item.id, code: item.code, name: item.name }))))
      .catch(() => setOrganizations([]))
  }, [token])

  // Requirement: D-091 — 「查询」提交草稿筛选并回到第一页。
  function applyFilters(): void {
    const next = { ...filterDraft }
    setFilters(next)
    setPage(1)
    void load(next, 1)
  }

  // Requirement: D-091 — 「重置」清空全部筛选条件，查看日期回到今天。
  function resetFilters(): void {
    const next = defaultFilters()
    setFilterDraft(next)
    setFilters(next)
    setPage(1)
    void load(next, 1)
  }

  function changePage(nextPage: number): void {
    setPage(nextPage)
    void load(filters, nextPage)
  }

  const organizationOptions = useMemo(
    () => organizations.map((item) => ({ label: `${item.name} (${item.code})`, value: item.id })),
    [organizations],
  )

  // 计数行与分页器取同一个 total，口径一致。
  const summaryText = `共 ${total} 人（截至 ${asOf}）`

  return (
    <WorkspaceShell
      titleId="historical-roster-title"
      title="历史花名册"
      subtitle="按生效日期回看任意时点的员工名册与当时信息。"
      error={error}
      onErrorClose={() => setError(null)}
    >
      {/* Requirement: D-102 — 提示条写明字段级历史的边界，
          避免被读成「某年某月的完整档案快照」。 */}
      <Alert type="info" showIcon title={FIELD_HISTORY_NOTE} />
      <FilterBar
        layout="flat"
        ariaLabel="历史花名册筛选"
        actions={(
          <>
            <Button onClick={resetFilters}>重置</Button>
            <Button type="primary" onClick={applyFilters}>查询</Button>
          </>
        )}
      >
        <EffectiveDatePicker
          value={filterDraft.asOf}
          onChange={(value) => setFilterDraft((previous) => ({ ...previous, asOf: value }))}
        />
        <FilterField label="主组织">
          <Select
            aria-label="主组织"
            allowClear
            placeholder="全部组织"
            value={filterDraft.organizationId}
            options={organizationOptions}
            onChange={(value: string | undefined) =>
              setFilterDraft((previous) => ({ ...previous, organizationId: value }))
            }
          />
        </FilterField>
        <FilterField label="在职状态">
          <Select
            aria-label="在职状态"
            allowClear
            placeholder="全部状态"
            value={filterDraft.employmentStatus}
            options={EMPLOYMENT_STATUS_OPTIONS}
            onChange={(value: string | undefined) =>
              setFilterDraft((previous) => ({ ...previous, employmentStatus: value }))
            }
          />
        </FilterField>
        <FilterField label="搜索姓名或工号">
          <Input.Search
            allowClear
            aria-label="搜索姓名或工号"
            placeholder="搜索姓名或工号"
            value={filterDraft.search}
            onChange={(event) =>
              setFilterDraft((previous) => ({ ...previous, search: event.target.value }))
            }
          />
        </FilterField>
      </FilterBar>
      <DataTable<HistoricalRosterRow>
        rowKey="person_id"
        loading={loading}
        dataSource={[...rows]}
        columns={[
          {
            title: "工号",
            dataIndex: "employee_number",
            width: 120,
            render: (value: string | null) => value || "待分配",
          },
          { title: "姓名（时点）", dataIndex: "display_name", width: 160 },
          {
            title: "主组织（时点）",
            key: "organization",
            width: 200,
            render: (_value, row) => row.organization_name || "—",
          },
          {
            title: "职位（时点）",
            key: "job",
            width: 180,
            render: (_value, row) => row.job_name || "—",
          },
          {
            title: "在职状态（时点）",
            dataIndex: "employment_status",
            width: 130,
            render: (value: string | null) => (
              value === "active"
                ? <Tag color="success" variant="outlined">在职</Tag>
                : value === "pending_start"
                  ? <Tag variant="outlined">待入职</Tag>
                  : <Tag variant="outlined">—</Tag>
            ),
          },
          {
            title: "入职日期（时点）",
            dataIndex: "hire_date",
            width: 140,
            render: (value: string | null) => value || "—",
          },
          {
            title: "操作",
            key: "action",
            width: 140,
            render: (_value, row) => (
              <Button type="link" onClick={(event) => { event.stopPropagation(); setDetail(row) }}>
                查看时点信息
              </Button>
            ),
          },
        ]}
        emptyText="该时点没有在册员工"
        summaryText={summaryText}
        pagination={{
          current: page,
          pageSize: ROSTER_PAGE_SIZE,
          total,
          showSizeChanger: false,
          showTotalLabel: "人",
          onChange: (nextPage) => changePage(nextPage),
        }}
      />
      <Drawer
        title={detail ? `${detail.display_name || "未命名人员"} · ${detail.employee_number || "待分配"}` : "时点信息"}
        open={Boolean(detail)}
        onClose={() => setDetail(null)}
      >
        {detail && (
          <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
            <Descriptions bordered size="small" column={1}>
              <Descriptions.Item label="查看时点">{asOf}</Descriptions.Item>
              <Descriptions.Item label="姓名（时点）">{detail.display_name || "—"}</Descriptions.Item>
              <Descriptions.Item label="主组织（时点）">
                {detail.organization_name
                  ? `${detail.organization_name} (${detail.organization_code})`
                  : "—"}
              </Descriptions.Item>
              <Descriptions.Item label="职位（时点）">
                {detail.job_name ? `${detail.job_name} (${detail.job_code})` : "—"}
              </Descriptions.Item>
              <Descriptions.Item label="在职状态（时点）">{detail.employment_status || "—"}</Descriptions.Item>
              <Descriptions.Item label="入职日期（时点）">{detail.hire_date || "—"}</Descriptions.Item>
              <Descriptions.Item label="修正过的字段">
                {detail.corrected_fields.length > 0
                  ? detail.corrected_fields.map((field) => personFieldLabel(field)).join("、")
                  : "无（该时点字段值等于当前登记值）"}
              </Descriptions.Item>
            </Descriptions>
            <Alert type="info" showIcon title={FIELD_HISTORY_NOTE} />
          </Space>
        )}
      </Drawer>
    </WorkspaceShell>
  )
}
