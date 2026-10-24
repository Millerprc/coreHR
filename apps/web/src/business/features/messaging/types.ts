// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

// Requirement: D-100 — 消息分类标签由后端单一来源给出，前端不另写一套映射。
export interface MessageCategory {
  readonly code: string
  readonly label: string
}


export interface InboxMessage {
  readonly id: string
  readonly category: string
  readonly category_label: string
  readonly title: string
  readonly body: string
  readonly source: string
  readonly source_ref_id: string | null
  readonly read_at: string | null
  readonly created_at: string
}


export interface MessageListResponse {
  readonly items: readonly InboxMessage[]
  readonly total: number
  readonly limit: number
  readonly offset: number
}


export interface UnreadCountResponse {
  readonly unread_count: number
}
