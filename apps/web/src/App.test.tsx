import { render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import App from "./App"


describe("App", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          items: [
            {
              phase: 1,
              code: "CORE_HR",
              name: "组织、人事与编制",
              status: "uat_ready",
              available_capabilities: ["有效日期组织与人员主数据"],
              available_endpoints: ["/api/v1/organizations"],
              pending_inputs: ["员工档案表头"],
            },
          ],
        }),
      }),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("renders the phase overview returned by the API", async () => {
    render(<App />)

    expect(screen.getByText("业务一至三阶段建设总览")).toBeInTheDocument()
    expect(await screen.findByText("组织、人事与编制")).toBeInTheDocument()
    expect(screen.getByText("工程 MVP 可验收")).toBeInTheDocument()
    expect(screen.getByText("有效日期组织与人员主数据")).toBeInTheDocument()
  })
})
