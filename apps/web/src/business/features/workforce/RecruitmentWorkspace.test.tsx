import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { RecruitmentWorkspace } from "./RecruitmentWorkspace"


describe("RecruitmentWorkspace", () => {
  beforeEach(() => vi.restoreAllMocks())

  it("keeps recruitment usable when no matching headcount plan exists", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      if (path.endsWith("/organizations/tree")) return Response.json([{ id: "org-1", code: "730001", name: "合成组织", children: [] }])
      if (path.includes("/workforce/jobs")) return Response.json({ items: [{ id: "job-1", code: "JOB-1", name: "合成职务" }], total: 1, limit: 200, offset: 0 })
      if (path.includes("/lifecycle/recruitment-requests")) return Response.json({ items: [{
        id: "request-1",
        request_number: "R00000001",
        organization_id: "org-1",
        job_id: "job-1",
        requested_count: 2,
        target_month: "2026-08-01",
        status: "draft",
        reason: "合成招聘需求",
        workflow_instance_id: null,
      }], total: 1, limit: 200, offset: 0 })
      if (path.includes("/workforce/headcount-results")) return Response.json({ period_month: "2026-08-01", as_of: "2026-08-09", items: [] })
      return Response.json({}, { status: 404 })
    }))

    render(<RecruitmentWorkspace token="synthetic-token" canAdmin />)

    expect(await screen.findByText("R00000001")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "查看编制" }))

    expect(await screen.findByText("相同组织、职务和月份暂无编制记录；仍可继续招聘")).toBeInTheDocument()
    expect(screen.getByText("参考信息不会阻断招聘")).toBeInTheDocument()
  })
})
