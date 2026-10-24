// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import type { JSX, ReactNode } from "react"


// Requirement: D-091 — 同一能力域不得出现第二套结构写法：
// 指标条统一由本组件承载（数值在上、标签在下、数值取主题蓝、标签取灰色、无竖分隔线），
// 各工作区只负责给出指标项，不再各自拼装 Statistic。
export interface MetricStripItem {
  readonly label: string
  readonly value: ReactNode
}


export interface MetricStripProps {
  readonly items: readonly MetricStripItem[]
}


export function MetricStrip({ items }: MetricStripProps): JSX.Element {
  return (
    <div className="metric-strip">
      {items.map((item) => (
        <div className="metric-item" key={item.label}>
          <span className="metric-value">{item.value}</span>
          <span className="metric-label">{item.label}</span>
        </div>
      ))}
    </div>
  )
}
