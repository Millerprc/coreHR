import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { OrganizationWorkspace } from "./OrganizationWorkspace"


const organizationId = "30000000-0000-0000-0000-000000000001"


describe("OrganizationWorkspace", () => {
  beforeEach(() => vi.restoreAllMocks())

  it("keeps the current tree stable while the effective date changes detail queries", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      if (path.endsWith("/organization-types")) return Response.json([])
      if (path.endsWith("/organizations/tree")) {
        return Response.json([
          {
            id: organizationId,
            code: "730001",
            name: "合成集团",
            organization_type_code: "GROUP",
            status: "active",
            children: [],
          },
        ])
      }
      if (path.includes(`/organizations/${organizationId}?effective_at=`)) {
        return Response.json({
          id: organizationId,
          code: "730001",
          name: "合成集团",
          organization_type_id: "31000000-0000-0000-0000-000000000001",
          organization_type_code: "GROUP",
          organization_type_name: "集团",
          parent_organization_id: null,
          parent_organization_code: null,
          country_code: "CN",
          status: "active",
          effective_from: "2026-01-01",
          effective_to: null,
          version: 1,
          planned_events: [
            {
              id: "32000000-0000-0000-0000-000000000001",
              organization_id: organizationId,
              event_type: "VERSION_SCHEDULED",
              effective_date: "2027-01-01",
              status: "planned",
              payload: {},
              expected_version: 1,
              idempotency_key: "33000000-0000-0000-0000-000000000001",
              change_reason: "合成未来调整",
              applied_at: null,
              cancelled_at: null,
            },
          ],
        })
      }
      if (path.includes(`/organizations/${organizationId}/relations`)) {
        return Response.json({
          effective_at: "2026-08-09",
          legal_entity_ids: [],
          legal_entity_version: 1,
          leader_person_ids: [],
          leader_version: 1,
          bp_membership_ids: [],
        })
      }
      if (path.endsWith("/cost-centers")) return Response.json([])
      if (path.includes(`/organizations/${organizationId}/cost-allocation`)) {
        return Response.json({ code: "COST_ALLOCATION_NOT_FOUND", message: "没有分摊" }, { status: 404 })
      }
      if (path.includes(`/organizations/${organizationId}/revenue-targets`)) {
        return Response.json({
          organization_id: organizationId,
          year: 2026,
          include_descendants: false,
          targets: [],
          totals_by_currency: {},
        })
      }
      if (path.includes("/workforce/legal-entities") || path.includes("/workforce/persons")) {
        return Response.json({ items: [], total: 0, limit: 200, offset: 0 })
      }
      return Response.json({}, { status: 404 })
    })
    vi.stubGlobal("fetch", fetchMock)

    render(<OrganizationWorkspace token="synthetic-token" canAdmin />)

    expect(await screen.findByRole("heading", { name: "合成集团", level: 3 })).toBeInTheDocument()
    expect(screen.getByText("合成未来调整，状态：planned")).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText("查看日期"), {
      target: { value: "2027-01-01" },
    })

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        `/api/v1/organizations/${organizationId}?effective_at=2027-01-01`,
        expect.any(Object),
      )
    })
    const treeCalls = fetchMock.mock.calls.filter(([input]) => String(input).endsWith("/organizations/tree"))
    expect(treeCalls).toHaveLength(1)
  })
})
