// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { apiRequest } from "../../client"
import type {
  InboxMessage,
  MessageCategory,
  MessageListResponse,
  UnreadCountResponse,
} from "./types"


// Requirement: D-100 — 消息引擎是平台内核基础服务，前端只通过平台接口取用消息。
export const MESSAGING_STREAM_PATH = "/api/v1/messaging/stream"


export interface MessageListOptions {
  readonly limit?: number
  readonly offset?: number
  readonly unreadOnly?: boolean
}


export const messagingApi = {
  list(token: string, options: MessageListOptions = {}): Promise<MessageListResponse> {
    const params = new URLSearchParams()
    params.set("limit", String(options.limit ?? 20))
    params.set("offset", String(options.offset ?? 0))
    if (options.unreadOnly) params.set("unread_only", "true")
    return apiRequest<MessageListResponse>(
      `/api/v1/messaging/messages?${params.toString()}`,
      token,
    )
  },

  unreadCount(token: string): Promise<UnreadCountResponse> {
    return apiRequest<UnreadCountResponse>(
      "/api/v1/messaging/messages/unread-count",
      token,
    )
  },

  markRead(token: string, messageId: string): Promise<InboxMessage> {
    return apiRequest<InboxMessage>(
      `/api/v1/messaging/messages/${encodeURIComponent(messageId)}/read`,
      token,
      { method: "POST" },
    )
  },

  // Requirement: D-100 — 分类标签由后端单一来源提供，前端不另写一套映射。
  categories(token: string): Promise<readonly MessageCategory[]> {
    return apiRequest<readonly MessageCategory[]>(
      "/api/v1/messaging/categories",
      token,
    )
  },
}
