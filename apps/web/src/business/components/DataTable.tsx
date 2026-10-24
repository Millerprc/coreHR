// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { Table } from "antd"
import type { TableProps } from "antd"
import type { ColumnsType } from "antd/es/table"
import type { JSX } from "react"

import { EmptyState } from "./EmptyState"


// Requirement: D-091 — 同一能力域不得出现第二套结构写法：
// 列表页的表格外壳统一由本组件承载，rowKey / loading / 空态文案 /
// 横向滚动 / 分页器口径（current、pageSize、total、showSizeChanger、showTotal）只有一套写法。
export interface DataTablePagination {
  readonly current?: number
  readonly pageSize: number
  readonly total?: number
  readonly showSizeChanger?: boolean
  readonly pageSizeOptions?: readonly string[]
  /** 分页器总条数文案的后缀，例如 "个职位" 渲染为「共 N 个职位」。 */
  readonly showTotalLabel?: string
  readonly onChange?: (page: number, pageSize: number) => void
}


export interface DataTableProps<T> {
  readonly rowKey: string
  readonly dataSource: readonly T[]
  readonly columns: ColumnsType<T>
  readonly loading?: boolean
  readonly size?: TableProps<T>["size"]
  readonly scroll?: TableProps<T>["scroll"]
  readonly onRow?: TableProps<T>["onRow"]
  readonly emptyText: string
  readonly pagination?: DataTablePagination
  /** 表格上方的计数行文案；缺省时复用分页器的「共 N xx」口径。 */
  readonly summaryText?: string
}


export function DataTable<T>({
  rowKey,
  dataSource,
  columns,
  loading = false,
  size,
  scroll,
  onRow,
  emptyText,
  pagination,
  summaryText,
}: DataTableProps<T>): JSX.Element {
  // Requirement: D-091 — 列表计数行与分页器共用同一口径，缺省文案只在表格外壳里生成一次。
  const summary = summaryText
    ?? (pagination?.showTotalLabel && pagination.total !== undefined
      ? `共 ${pagination.total} ${pagination.showTotalLabel}`
      : undefined)
  return (
    <>
      {summary ? <div className="list-summary">{summary}</div> : null}
      <Table<T>
        rowKey={rowKey}
        loading={loading}
        size={size}
        dataSource={dataSource}
        columns={columns}
        scroll={scroll}
        onRow={onRow}
        locale={{ emptyText: <EmptyState description={emptyText} /> }}
        pagination={pagination ? {
          current: pagination.current,
          pageSize: pagination.pageSize,
          total: pagination.total,
          showSizeChanger: pagination.showSizeChanger ?? false,
          pageSizeOptions: pagination.pageSizeOptions ? [...pagination.pageSizeOptions] : undefined,
          showTotal: pagination.showTotalLabel
            ? (total: number) => `共 ${total} ${pagination.showTotalLabel}`
            : undefined,
          onChange: pagination.onChange,
        } : false}
      />
    </>
  )
}
