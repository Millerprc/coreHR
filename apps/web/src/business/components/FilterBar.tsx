// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { Form } from "antd"
import type { JSX, ReactNode } from "react"


// Requirement: D-091 — 同一能力域不得出现第二套结构写法：
// 筛选栏统一由本组件承载，三种既有写法作为 layout 变体保留：
//   flat  —— 扁平样式（.filter-flat）：标签在上、控件在下，查询/重置靠行尾；
//   grid  —— 四列栅格（.filter-grid），字段直接作为子节点；
//   inline —— antd Form layout="inline"，字段为 Form.Item，actions 也需是 Form.Item。
export interface FilterBarProps {
  readonly layout?: "flat" | "grid" | "inline"
  readonly ariaLabel?: string
  readonly actions?: ReactNode
  readonly actionsPlacement?: "in-row" | "below"
  readonly children: ReactNode
}


export function FilterBar({
  layout = "grid",
  ariaLabel,
  actions,
  actionsPlacement = "in-row",
  children,
}: FilterBarProps): JSX.Element {
  if (layout === "inline") {
    return (
      <Form layout="inline" role="search" aria-label={ariaLabel}>
        {children}
        {actions}
      </Form>
    )
  }

  if (layout === "flat") {
    return (
      <div className="filter-flat" role="search" aria-label={ariaLabel}>
        {children}
        {actions ? <div className="filter-flat-actions">{actions}</div> : null}
      </div>
    )
  }

  return (
    <>
      <div className="filter-grid">
        {children}
        {actionsPlacement === "in-row" ? actions : null}
      </div>
      {actionsPlacement === "below" ? actions : null}
    </>
  )
}
