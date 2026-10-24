// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { Empty } from "antd"
import type { JSX } from "react"


// Requirement: D-091 — 同一能力域不得出现第二套结构写法：
// 空态统一由本组件承载（简体占位图 + 中文文案），业务侧只负责给文案。
export interface EmptyStateProps {
  readonly description: string
}


export function EmptyState({ description }: EmptyStateProps): JSX.Element {
  return <Empty description={description} image={Empty.PRESENTED_IMAGE_SIMPLE} />
}
