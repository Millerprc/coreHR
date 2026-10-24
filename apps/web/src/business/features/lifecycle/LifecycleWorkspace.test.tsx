// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { fireEvent, render, screen, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { LifecycleWorkspace } from "./LifecycleWorkspace"


const page = (items: readonly unknown[]) => ({ items, total: items.length, limit: 200, offset: 0 })


describe("LifecycleWorkspace", () => {
  beforeEach(() => vi.restoreAllMocks())

  it("shows executable HR events and workflow tasks", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      if (path.includes("/lifecycle/hr-events?")) return Response.json(page([{
        id: "event-1",
        event_number: "E0000000001",
        event_type: "TRANSFER",
        object_type: "employment",
        object_id: "employment-1",
        effective_date: "2026-08-10",
        status: "pending_approval",
        source: "api",
        reason: "Synthetic transfer",
        before_payload: {},
        planned_payload: {},
        actual_payload: {},
        workflow_instance_id: null,
        related_event_id: null,
        attempts: 0,
        last_error: null,
        executed_at: null,
        version: 1,
      }]))
      if (path.includes("/workforce/persons?")) return Response.json(page([]))
      if (path.endsWith("/organizations/tree")) return Response.json([])
      if (path.includes("/workforce/jobs")) return Response.json(page([]))
      if (path.includes("/workflows/definitions")) return Response.json(page([{
        id: "definition-1",
        code: "TRANSFER_APPROVAL",
        name: "调动审批",
        category: "hr_event",
        status: "active",
        active_version: 1,
        description: null,
        created_at: "2026-08-09T00:00:00Z",
        updated_at: "2026-08-09T00:00:00Z",
      }]))
      if (path.includes("/workflow-instances")) return Response.json(page([]))
      if (path.includes("/workflow-tasks")) return Response.json(page([{
        id: "task-1",
        workflow_instance_id: "instance-1",
        node_code: "APPROVE",
        sign_mode: "any",
        assignee_type: "role",
        assignee_ref: "HR_ADMIN",
        status: "pending",
        decision: null,
        comment: null,
        decided_by: null,
        decided_at: null,
      }]))
      return Response.json({}, { status: 404 })
    }))

    render(<LifecycleWorkspace token="synthetic-token" canAdmin />)

    expect(await screen.findByText("E0000000001")).toBeInTheDocument()
    // Requirement: CHECKPOINT-001 — 查询必须限定在目标行内。
    //
    // 为什么不用 getByRole：它在 jsdom 里要为整篇文档计算无障碍树与可见性，
    // 每算一次可见性就要调 getComputedStyle，而 antd 6 的 CSS-in-JS 在运行时往
    // <style> 里注入了成千上万条规则 —— 实测**单次行内 getByRole 要 4.8~5.0 秒**，
    // 而 getByText 只需 1 毫秒。本用例原本要 9 秒（CI runner 上顶穿 15 秒上限、随机变红）。
    //
    // 改用「文本定位 + 断言它确实是个 button」，语义强度不变，成本降三个数量级。
    const eventRow = screen.getByText("E0000000001").closest("tr")!
    expect(within(eventRow).getByText("发起审批").closest("button")).not.toBeNull()

    fireEvent.click(screen.getByText("流程与待办"))
    expect(await screen.findByText("TRANSFER_APPROVAL")).toBeInTheDocument()
    const taskRow = screen.getByText("或签").closest("tr")!
    expect(within(taskRow).getByText(/通\s*过/).closest("button")).not.toBeNull()
    expect(within(taskRow).getByText("或签")).toBeInTheDocument()
  }, 30_000)
})
