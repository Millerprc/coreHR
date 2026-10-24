// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import type { JSX, ReactNode } from "react"


// Requirement: D-091 — 同一能力域不得出现第二套结构写法：
// 筛选字段统一由本组件承载（标签在上、控件在下），各工作区只负责给标签与控件。
export interface FilterFieldProps {
  readonly label: string
  readonly htmlFor?: string
  readonly children: ReactNode
}


export function FilterField({ label, htmlFor, children }: FilterFieldProps): JSX.Element {
  return (
    <div className="filter-field">
      <label className="field-label" htmlFor={htmlFor}>{label}</label>
      {children}
    </div>
  )
}
