import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { PeopleWorkspace } from "./PeopleWorkspace"


const personId = "60000000-0000-0000-0000-000000000001"


describe("PeopleWorkspace", () => {
  beforeEach(() => vi.restoreAllMocks())

  it("opens one synthetic person's complete archive", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      if (path.endsWith(`/workforce/persons/${personId}`)) {
        return Response.json({
          person: {
            id: personId,
            employee_number: "990001",
            display_name: "合成人员",
            former_name: null,
            gender_code: null,
            birth_date: null,
            nationality_code: null,
            country_code: "CN",
            status: "active",
          },
          employments: [{
            id: "61000000-0000-0000-0000-000000000001",
            person_id: personId,
            employee_type_code: "REGULAR",
            status: "pending_start",
            planned_start_date: "2026-08-10",
            actual_start_date: null,
            probation_end_date: null,
            end_date: null,
            contract_legal_entity_id: null,
            payroll_legal_entity_id: null,
            social_insurance_legal_entity_id: null,
            tax_legal_entity_id: null,
            version: 1,
          }],
          assignments: [],
          agreements: [],
        })
      }
      if (path.includes("/workforce/persons?")) {
        return Response.json({ items: [{
          id: personId,
          employee_number: "990001",
          display_name: "合成人员",
          former_name: null,
          gender_code: null,
          birth_date: null,
          nationality_code: null,
          country_code: "CN",
          status: "active",
        }], total: 1, limit: 200, offset: 0 })
      }
      if (path.includes("/workforce/legal-entities") || path.includes("/workforce/jobs")) {
        return Response.json({ items: [], total: 0, limit: 200, offset: 0 })
      }
      if (path.endsWith("/organizations/tree")) return Response.json([])
      return Response.json({}, { status: 404 })
    }))

    render(<PeopleWorkspace token="synthetic-token" canAdmin />)

    expect(await screen.findByText("990001")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "查看" }))

    expect(await screen.findByText("合成人员 · 990001")).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "劳动关系 1" })).toBeInTheDocument()
  })
})
