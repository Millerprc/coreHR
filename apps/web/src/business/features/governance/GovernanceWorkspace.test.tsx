import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { GovernanceWorkspace } from "./GovernanceWorkspace"


const batch = {
  id: "10000000-0000-0000-0000-000000000099",
  entity_type: "dictionary_item",
  source_system: "synthetic_ehr",
  source_table: "synthetic_dictionary_items",
  file_name: "synthetic.csv",
  idempotency_key: "20000000-0000-0000-0000-000000000099",
  status: "validated_with_errors",
  total_rows: 3,
  valid_rows: 2,
  rejected_rows: 1,
  imported_rows: 0,
  skipped_rows: 0,
  created_by: "30000000-0000-0000-0000-000000000099",
  executed_at: null,
  created_at: "2026-08-09T00:00:00Z",
  updated_at: "2026-08-09T00:00:00Z",
}


describe("GovernanceWorkspace", () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      if (path.endsWith(`/import-batches/${batch.id}`)) {
        return Response.json({
          ...batch,
          rows: [
            {
              id: "row-1",
              row_number: 1,
              source_record_id: "synthetic-1",
              status: "rejected",
              errors: [{ code: "ROW_SCHEMA_INVALID", field: "code", message: "代码格式错误" }],
              target_type: null,
              target_id: null,
            },
          ],
        })
      }
      if (path.includes("/import-templates/")) {
        return Response.json({
          entity_type: "dictionary_item",
          columns: ["dictionary_code", "code", "name", "sort_order"],
          required_columns: ["dictionary_code", "code", "name"],
        })
      }
      return Response.json({ items: [batch], total: 1, limit: 50, offset: 0 })
    }))
  })

  it("shows import batches and rejected row details", async () => {
    render(<GovernanceWorkspace token="synthetic-token" canAdmin />)

    expect(await screen.findByRole("heading", { name: "数据治理" })).toBeInTheDocument()
    expect(await screen.findByText("synthetic_dictionary_items")).toBeInTheDocument()
    expect(screen.getByText("1 条拒绝")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "查看" }))
    expect(await screen.findByText(/代码格式错误/)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "执行通过行" })).toBeInTheDocument()
  })

  it("opens a non-technical CSV import form", async () => {
    render(<GovernanceWorkspace token="synthetic-token" canAdmin />)
    await screen.findByText("synthetic_dictionary_items")

    fireEvent.click(screen.getByRole("button", { name: "新建导入批次" }))
    expect(screen.getByRole("dialog", { name: "新建主数据导入" })).toBeInTheDocument()
    expect(screen.getByText("仅接受主数据代码和名称，不要上传人员、证件、薪酬或联系方式")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "下载CSV模板" })).toBeInTheDocument()
  })
})
