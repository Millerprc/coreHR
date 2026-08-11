import { fireEvent, render, screen, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { JobArchitecturePanel } from "./JobArchitecturePanel"


describe("JobArchitecturePanel", () => {
  beforeEach(() => vi.restoreAllMocks())

  it("shows effective-dated dimensions and a non-technical job editor", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      if (path.includes("/job-dimensions")) return Response.json({
        items: [
          { id: "level-1", dimension_type: "LEVEL", code: "LEVEL_06", name: "六级", parent_dimension_id: null, parent_dimension_type: null, parent_dimension_code: null, sort_order: 10, status: "active", effective_from: "2026-01-01", effective_to: null, version: 1, notes: null },
          { id: "grade-1", dimension_type: "GRADE", code: "GRADE_02", name: "二等", parent_dimension_id: null, parent_dimension_type: null, parent_dimension_code: null, sort_order: 10, status: "active", effective_from: "2026-01-01", effective_to: null, version: 1, notes: null },
          { id: "class-1", dimension_type: "CLASS", code: "CLASS_02", name: "二级职类", parent_dimension_id: null, parent_dimension_type: null, parent_dimension_code: null, sort_order: 10, status: "active", effective_from: "2026-01-01", effective_to: null, version: 1, notes: null },
          { id: "sequence-1", dimension_type: "SEQUENCE", code: "TECH", name: "技术", parent_dimension_id: null, parent_dimension_type: null, parent_dimension_code: null, sort_order: 10, status: "active", effective_from: "2026-01-01", effective_to: null, version: 1, notes: null },
        ],
        total: 4,
        limit: 500,
        offset: 0,
      })
      if (path.includes("/workforce/jobs")) return Response.json({ items: [], total: 0, limit: 200, offset: 0 })
      return Response.json({}, { status: 404 })
    }))

    render(<JobArchitecturePanel token="synthetic-token" canAdmin />)

    expect(await screen.findByText("LEVEL_06")).toBeInTheDocument()
    expect(screen.getByLabelText("职务体系查看日期")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "新增职务" }))
    const dialog = await screen.findByRole("dialog", { name: "创建职务版本" })
    expect(within(dialog).getByLabelText("职务代码")).toBeInTheDocument()
    expect(within(dialog).getByLabelText("职级")).toBeInTheDocument()
    expect(within(dialog).getByLabelText("职等")).toBeInTheDocument()
    expect(within(dialog).getByLabelText("职类")).toBeInTheDocument()
    expect(within(dialog).getByLabelText("序列")).toBeInTheDocument()
    expect(within(dialog).getByLabelText("生效日期")).toBeInTheDocument()
    expect(within(dialog).getByLabelText("变更原因")).toBeInTheDocument()
  })
})
