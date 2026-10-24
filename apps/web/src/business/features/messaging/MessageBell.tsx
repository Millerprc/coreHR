// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { Alert, Badge, Drawer, Empty, Skeleton, Tag, Typography } from "antd"
import { useCallback, useEffect, useMemo, useState } from "react"

import { messagingApi } from "./api"
import { openMessageStream } from "./stream"
import type { InboxMessage, MessageCategory } from "./types"


// Requirement: D-100 — 未读数走轮询兜底，实时推送由 SSE 承担，两者都以服务端为准。
const UNREAD_POLL_INTERVAL_MS = 30000
const MESSAGE_PAGE_SIZE = 20


export function formatMessageTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const month = String(date.getMonth() + 1).padStart(2, "0")
  const day = String(date.getDate()).padStart(2, "0")
  const hour = String(date.getHours()).padStart(2, "0")
  const minute = String(date.getMinutes()).padStart(2, "0")
  return `${month}-${day} ${hour}:${minute}`
}


export function MessageBell({ token }: { readonly token: string }) {
  const [unreadCount, setUnreadCount] = useState(0)
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [messages, setMessages] = useState<readonly InboxMessage[]>([])
  const [categories, setCategories] = useState<readonly MessageCategory[]>([])

  const labelByCode = useMemo(
    () => new Map(categories.map((category) => [category.code, category.label])),
    [categories],
  )

  useEffect(() => {
    let active = true
    const refresh = async (): Promise<void> => {
      try {
        const result = await messagingApi.unreadCount(token)
        if (active && typeof result.unread_count === "number") {
          setUnreadCount(result.unread_count)
        }
      } catch {
        // 轮询失败不打断页面，实时推送与下次轮询会继续纠正未读数。
      }
    }
    void refresh()
    const timer = window.setInterval(() => {
      void refresh()
    }, UNREAD_POLL_INTERVAL_MS)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [token])

  useEffect(() => {
    const handle = openMessageStream(token, {
      onMessage: (message) => {
        setUnreadCount((current) => current + 1)
        setMessages((current) =>
          current.some((item) => item.id === message.id)
            ? current
            : [message, ...current],
        )
      },
    })
    return () => handle.close()
  }, [token])

  const handleOpen = useCallback(async () => {
    setOpen(true)
    setLoading(true)
    setError(null)
    try {
      const [listing, catalog] = await Promise.all([
        messagingApi.list(token, { limit: MESSAGE_PAGE_SIZE }),
        messagingApi.categories(token),
      ])
      setMessages(listing.items)
      setCategories(catalog)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "消息加载失败")
    } finally {
      setLoading(false)
    }
  }, [token])

  const handleRead = useCallback(
    async (message: InboxMessage) => {
      if (message.read_at) return
      try {
        await messagingApi.markRead(token, message.id)
        setMessages((current) =>
          current.map((item) =>
            item.id === message.id
              ? { ...item, read_at: new Date().toISOString() }
              : item,
          ),
        )
        setUnreadCount((current) => Math.max(current - 1, 0))
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "标记已读失败")
      }
    },
    [token],
  )

  return (
    <>
      <Badge count={unreadCount} size="small" overflowCount={99}>
        <button
          type="button"
          className="messaging-bell-button"
          aria-label={unreadCount > 0 ? `消息通知，未读 ${unreadCount} 条` : "消息通知"}
          onClick={() => void handleOpen()}
        >
          <span className="messaging-bell-icon" aria-hidden="true" />
        </button>
      </Badge>
      <Drawer
        title="消息"
        open={open}
        size={420}
        onClose={() => setOpen(false)}
      >
        <div className="messaging-panel">
          {error && <Alert type="error" showIcon title={error} />}
          {loading && <Skeleton active paragraph={{ rows: 3 }} />}
          {!loading && messages.length === 0 && !error && (
            <Empty description="暂无消息" />
          )}
          {messages.length > 0 && (
            <ul className="messaging-list">
              {messages.map((message) => (
                <li key={message.id} className="messaging-list-item">
                  <button
                    type="button"
                    className={
                      message.read_at
                        ? "messaging-item messaging-item-read"
                        : "messaging-item messaging-item-unread"
                    }
                    onClick={() => void handleRead(message)}
                  >
                    <span className="messaging-item-head">
                      <Tag color="processing">
                        {labelByCode.get(message.category) ?? message.category_label}
                      </Tag>
                      <span className="messaging-item-time">
                        {formatMessageTime(message.created_at)}
                      </span>
                    </span>
                    {/* Requirement: D-100 — 消息正文只按纯文本渲染，不解释 HTML。 */}
                    <Typography.Text strong className="messaging-item-title">
                      {message.title}
                    </Typography.Text>
                    <Typography.Text className="messaging-item-body">
                      {message.body}
                    </Typography.Text>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </Drawer>
    </>
  )
}
