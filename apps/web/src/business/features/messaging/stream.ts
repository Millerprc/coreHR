// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { MESSAGING_STREAM_PATH } from "./api"
import type { InboxMessage } from "./types"


// Requirement: D-100 — 实时推送用 SSE，但**不使用浏览器原生 SSE 客户端**：
// 原生客户端无法携带 Authorization 头，这里用 fetch + ReadableStream 消费。
const RECONNECT_BASE_DELAY_MS = 1000
const RECONNECT_MAX_DELAY_MS = 30000


export interface MessageStreamHandlers {
  readonly onMessage: (message: InboxMessage) => void
  readonly onError?: (error: Error) => void
  readonly onReconnected?: () => void
}


export interface MessageStreamHandle {
  readonly close: () => void
}


interface SseFrame {
  readonly id: string | null
  readonly event: string
  readonly data: string
}


function parseFrame(raw: string): SseFrame | null {
  let id: string | null = null
  let event = "message"
  const data: string[] = []
  for (const line of raw.split("\n")) {
    if (!line || line.startsWith(":")) continue
    const separator = line.indexOf(":")
    const field = separator < 0 ? line : line.slice(0, separator)
    const value = separator < 0 ? "" : line.slice(separator + 1).replace(/^ /, "")
    if (field === "id") id = value
    else if (field === "event") event = value
    else if (field === "data") data.push(value)
  }
  if (data.length === 0) return null
  return { id, event, data: data.join("\n") }
}


async function consumeStream(
  body: ReadableStream<Uint8Array>,
  onFrame: (frame: SseFrame) => void,
): Promise<void> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let separator = buffer.indexOf("\n\n")
    while (separator >= 0) {
      const frame = parseFrame(buffer.slice(0, separator))
      buffer = buffer.slice(separator + 2)
      if (frame) onFrame(frame)
      separator = buffer.indexOf("\n\n")
    }
  }
}


export function openMessageStream(
  token: string,
  handlers: MessageStreamHandlers,
): MessageStreamHandle {
  const controller = new AbortController()
  let closed = false
  let attempt = 0
  let lastEventId: string | null = null
  let pendingTimer: number | null = null
  let releasePending: (() => void) | null = null

  const wait = (milliseconds: number): Promise<void> => new Promise((resolve) => {
    releasePending = resolve
    pendingTimer = window.setTimeout(() => {
      pendingTimer = null
      releasePending = null
      resolve()
    }, milliseconds)
  })

  const run = async (): Promise<void> => {
    while (!closed) {
      try {
        const response = await fetch(MESSAGING_STREAM_PATH, {
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: "text/event-stream",
            ...(lastEventId ? { "Last-Event-ID": lastEventId } : {}),
          },
          signal: controller.signal,
        })
        if (!response.ok) {
          throw new Error(`实时消息连接失败（${response.status}）`)
        }
        if (!response.body) {
          throw new Error("实时消息连接未返回数据流")
        }
        const contentType = response.headers.get("content-type") ?? ""
        if (!contentType.includes("text/event-stream")) {
          throw new Error("实时消息连接返回了非事件流内容")
        }
        if (attempt > 0) handlers.onReconnected?.()
        attempt = 0
        await consumeStream(response.body, (frame) => {
          if (frame.id) lastEventId = frame.id
          if (frame.event !== "message") return
          try {
            handlers.onMessage(JSON.parse(frame.data) as InboxMessage)
          } catch {
            // Requirement: D-100 — 单条事件解析失败不影响后续推送。
          }
        })
      } catch (error) {
        if (closed || controller.signal.aborted) return
        handlers.onError?.(
          error instanceof Error ? error : new Error("实时消息连接中断"),
        )
      }
      if (closed) return
      attempt += 1
      await wait(
        Math.min(
          RECONNECT_BASE_DELAY_MS * 2 ** (attempt - 1),
          RECONNECT_MAX_DELAY_MS,
        ),
      )
    }
  }

  void run()

  return {
    close: () => {
      closed = true
      controller.abort()
      if (pendingTimer !== null) {
        window.clearTimeout(pendingTimer)
        pendingTimer = null
      }
      if (releasePending) {
        releasePending()
        releasePending = null
      }
    },
  }
}
