import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { AttendanceWorkspace } from "./AttendanceWorkspace"


const page = (items: readonly unknown[]) => ({ items, total: items.length, limit: 200, offset: 0 })


describe("AttendanceWorkspace", () => {
  beforeEach(() => vi.restoreAllMocks())

  it("shows current daily results and versioned attendance rules", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      if (path.includes("/employment-options")) return Response.json(page([{
        id: "employment-1",
        person_id: "person-1",
        employee_number: "990005",
        display_name: "合成考勤员工",
        employee_type_code: "REGULAR",
        status: "active",
      }]))
      if (path.includes("/daily-results?")) return Response.json(page([{
        id: "daily-1",
        employment_id: "employment-1",
        work_date: "2026-08-10",
        status: "exception",
        scheduled_minutes: 540,
        worked_minutes: 520,
        late_minutes: 5,
        early_leave_minutes: 5,
        exception_codes: ["LATE", "EARLY_LEAVE"],
        evidence: { timezone: "Asia/Shanghai" },
        version: 2,
        is_current: true,
      }]))
      if (path.includes("/monthly-results?")) return Response.json(page([]))
      if (path.includes("/period-freezes?")) return Response.json(page([{
        id: "freeze-1",
        freeze_type: "special",
        date_from: "2026-08-15",
        date_to: "2026-08-20",
        status: "active",
        reason: "合成特殊业务冻结",
        frozen_by: "user-1",
        frozen_at: "2026-08-14T00:00:00Z",
        released_by: null,
        released_at: null,
        release_reason: null,
        created_at: "2026-08-14T00:00:00Z",
        updated_at: "2026-08-14T00:00:00Z",
      }]))
      if (path.includes("/rule-sets?")) return Response.json(page([{
        id: "rule-1",
        code: "STANDARD_CN",
        name: "中国标准考勤",
        timezone: "Asia/Shanghai",
        version: 1,
        status: "active",
        effective_from: "2026-01-01",
        effective_to: null,
        rules: { late_grace_minutes: 5, early_leave_grace_minutes: 5 },
        created_at: "2026-08-09T00:00:00Z",
        updated_at: "2026-08-09T00:00:00Z",
      }]))
      if (path.includes("/shifts?")) return Response.json(page([]))
      return Response.json(page([]))
    }))

    render(<AttendanceWorkspace token="synthetic-token" canAdmin />)

    expect(await screen.findByText("合成考勤员工")).toBeInTheDocument()
    expect(screen.getByText("LATE")).toBeInTheDocument()
    expect(screen.getByText("v2")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("tab", { name: "规则与班次" }))
    expect(await screen.findByText("STANDARD_CN")).toBeInTheDocument()
    expect(screen.getByText("中国标准考勤")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "新版本" })).toBeInTheDocument()

    fireEvent.click(screen.getByRole("tab", { name: "期间冻结" }))
    expect(await screen.findByText("合成特殊业务冻结")).toBeInTheDocument()
    expect(screen.getByText("冻结中")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "解冻" })).toBeInTheDocument()
  }, 15_000)
})
