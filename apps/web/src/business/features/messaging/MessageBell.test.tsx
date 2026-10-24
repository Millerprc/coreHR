// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { MessageBell } from "./MessageBell"


// Requirement: D-100 — 站内信铃铛、未读数、消息列表与标记已读的界面行为。
const message = {
  id: "10000000-0000-0000-0000-000000000051",
  category: "approval",
  category_label: "审批待办",
  title: "有一条审批待办",
  body: "流程 FY2026-0001 等待您处理。",
  source: "workflow.approved",
  source_ref_id: null,
  read_at: null,
  created_at: "2026-10-24T06:30:00+00:00",
}


function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  })
}


function eventStreamResponse(frames: readonly string[]): Response {
  const encoder = new TextEncoder()
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const frame of frames) controller.enqueue(encoder.encode(frame))
      controller.close()
    },
  })
  return new Response(stream, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  })
}


describe("MessageBell", () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it("shows the unread badge and lists messages in a drawer", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        if (path.includes("/api/v1/messaging/stream")) {
          return eventStreamResponse([])
        }
        if (path.includes("/unread-count")) {
          return jsonResponse({ unread_count: 2 })
        }
        if (path.includes("/api/v1/messaging/categories")) {
          return jsonResponse([{ code: "approval", label: "审批待办" }])
        }
        return jsonResponse({
          items: [message],
          total: 1,
          limit: 20,
          offset: 0,
        })
      }),
    )

    render(<MessageBell token="synthetic-token" />)

    expect(
      await screen.findByRole("button", { name: "消息通知，未读 2 条" }),
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: /消息通知/ }))

    expect(await screen.findByText("有一条审批待办")).toBeInTheDocument()
    expect(screen.getByText("流程 FY2026-0001 等待您处理。")).toBeInTheDocument()
    expect(screen.getByText("审批待办")).toBeInTheDocument()
  })

  it("marks a message as read when it is clicked", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      if (path.includes("/api/v1/messaging/stream")) {
        return eventStreamResponse([])
      }
      if (path.includes("/unread-count")) {
        return jsonResponse({ unread_count: 1 })
      }
      if (path.includes("/api/v1/messaging/categories")) {
        return jsonResponse([{ code: "approval", label: "审批待办" }])
      }
      if (path.includes("/read")) {
        return jsonResponse({ ...message, read_at: "2026-10-24T07:00:00+00:00" })
      }
      return jsonResponse({
        items: [message],
        total: 1,
        limit: 20,
        offset: 0,
      })
    })
    vi.stubGlobal("fetch", fetchMock)

    render(<MessageBell token="synthetic-token" />)
    await screen.findByRole("button", { name: "消息通知，未读 1 条" })

    fireEvent.click(screen.getByRole("button", { name: /消息通知/ }))
    const item = await screen.findByText("有一条审批待办")

    fireEvent.click(item)

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        `/api/v1/messaging/messages/${message.id}/read`,
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({ Authorization: "Bearer synthetic-token" }),
        }),
      )
    })
    expect(
      await screen.findByRole("button", { name: "消息通知" }),
    ).toBeInTheDocument()
  })

  it("renders the message body as plain text instead of markup", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        if (path.includes("/api/v1/messaging/stream")) {
          return eventStreamResponse([])
        }
        if (path.includes("/unread-count")) {
          return jsonResponse({ unread_count: 0 })
        }
        if (path.includes("/api/v1/messaging/categories")) {
          return jsonResponse([])
        }
        return jsonResponse({
          items: [{ ...message, body: "<script>alert(1)</script>" }],
          total: 1,
          limit: 20,
          offset: 0,
        })
      }),
    )

    render(<MessageBell token="synthetic-token" />)
    fireEvent.click(screen.getByRole("button", { name: /消息通知/ }))

    expect(
      await screen.findByText("<script>alert(1)</script>"),
    ).toBeInTheDocument()
    expect(document.querySelector("script")).toBeNull()
  })

  it("receives pushed messages over the server-sent event stream", async () => {
    let streamCalls = 0
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        if (path.includes("/api/v1/messaging/stream")) {
          streamCalls += 1
          if (streamCalls > 1) return eventStreamResponse([])
          return eventStreamResponse([
            `id: ${message.id}\nevent: message\ndata: ${JSON.stringify(message)}\n\n`,
          ])
        }
        if (path.includes("/unread-count")) {
          // 保持未读数请求悬空，验证徽标数字只由实时推送决定。
          return new Promise<Response>(() => undefined)
        }
        if (path.includes("/api/v1/messaging/categories")) {
          return jsonResponse([])
        }
        return jsonResponse({ items: [], total: 0, limit: 20, offset: 0 })
      }),
    )

    render(<MessageBell token="synthetic-token" />)

    expect(
      await screen.findByRole("button", { name: "消息通知，未读 1 条" }),
    ).toBeInTheDocument()
  })
})
