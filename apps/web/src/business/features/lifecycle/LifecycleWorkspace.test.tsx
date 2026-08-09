import { fireEvent, render, screen } from "@testing-library/react"
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
    expect(screen.getByRole("button", { name: "发起审批" })).toBeInTheDocument()

    fireEvent.click(screen.getByRole("tab", { name: "流程与待办" }))
    expect(await screen.findByText("TRANSFER_APPROVAL")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /通\s*过/ })).toBeInTheDocument()
    expect(screen.getByText("或签")).toBeInTheDocument()
  }, 15_000)
})
