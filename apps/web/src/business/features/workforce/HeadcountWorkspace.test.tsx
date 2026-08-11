import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { HeadcountWorkspace } from "./HeadcountWorkspace"


describe("HeadcountWorkspace", () => {
  beforeEach(() => vi.restoreAllMocks())

  it("shows plan, current, snapshot average and freeze as one result", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      if (path.endsWith("/organizations/tree")) return Response.json([])
      if (path.includes("/workforce/job-dimensions")) return Response.json({ items: [], total: 0, limit: 500, offset: 0 })
      if (path.includes("/workforce/jobs")) return Response.json({ items: [], total: 0, limit: 200, offset: 0 })
      if (path.includes("/workforce/headcount-results")) return Response.json({
        period_month: "2026-08-01",
        as_of: "2026-08-15",
        items: [{
          organization_id: "70000000-0000-0000-0000-000000000001",
          organization_code: "730001",
          job_id: "71000000-0000-0000-0000-000000000001",
          job_code: "JOB-1",
          job_name: "合成职务",
          period_month: "2026-08-01",
          planned_count: "10.00",
          plan_version: 2,
          current_count: 8,
          variance: "2.00",
          month_start_count: 7,
          month_end_count: 9,
          average_count: "8.00",
          frozen: true,
        }],
      })
      if (path.includes("/workforce/occupancy-rules") || path.includes("/workforce/headcount-freezes")) {
        return Response.json({ items: [], total: 0, limit: 200, offset: 0 })
      }
      return Response.json({}, { status: 404 })
    }))

    render(<HeadcountWorkspace token="synthetic-token" canAdmin />)

    expect(await screen.findByText("合成职务 (JOB-1)")).toBeInTheDocument()
    expect(screen.getByText("8.00")).toBeInTheDocument()
    expect(screen.getByText("已冻结")).toBeInTheDocument()
  })
})
