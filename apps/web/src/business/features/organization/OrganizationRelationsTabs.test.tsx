import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { OrganizationRelationsTabs } from "./OrganizationRelationsTabs"


const organizationId = "30000000-0000-0000-0000-000000000001"
const costCenterId = "40000000-0000-0000-0000-000000000001"


function installApiMock() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input)
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
    if (path.endsWith("/cost-centers")) {
      return Response.json([{
        id: costCenterId,
        code: "CC-SYNTHETIC",
        name: "合成测试成本中心",
        country_code: "CN",
        status: "active",
        effective_from: "2026-01-01",
        effective_to: null,
        version: 1,
      }])
    }
    if (path.includes(`/organizations/${organizationId}/cost-allocation`)) {
      return Response.json({
        organization_id: organizationId,
        effective_at: "2026-08-09",
        version: 2,
        lines: [{ cost_center_id: costCenterId, allocation_percent: "50.0000" }],
      })
    }
    if (path.includes(`/organizations/${organizationId}/revenue-targets`)) {
      return Response.json({
        organization_id: organizationId,
        year: new Date().getFullYear(),
        include_descendants: false,
        targets: [{
          id: "50000000-0000-0000-0000-000000000001",
          organization_id: organizationId,
          year: new Date().getFullYear(),
          currency_code: "CNY",
          annual_amount: "100.0000",
          months: Array.from({ length: 12 }, (_, index) => ({
            month: index + 1,
            amount: index === 0 ? "50.0000" : "0.0000",
          })),
          version: 2,
        }],
        totals_by_currency: {},
      })
    }
    if (path.includes("/workforce/legal-entities") || path.includes("/workforce/persons")) {
      return Response.json({ items: [], total: 0, limit: 200, offset: 0 })
    }
    return Response.json({}, { status: 404 })
  })
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}


describe("OrganizationRelationsTabs", () => {
  beforeEach(() => vi.restoreAllMocks())

  it("blocks cost-allocation submission until the total is exactly 100 percent", async () => {
    installApiMock()
    render(
      <OrganizationRelationsTabs
        token="synthetic-token"
        organizationId={organizationId}
        effectiveAt="2026-08-09"
        canAdmin
        organizations={[{ id: organizationId, code: "730001", name: "合成组织" }]}
      />,
    )

    fireEvent.click(await screen.findByRole("tab", { name: "成本分摊" }))
    const panel = screen.getByRole("tabpanel")
    const save = within(panel).getByRole("button", { name: "保存成本分摊" })
    expect(save).toBeDisabled()

    fireEvent.change(screen.getByLabelText("第1行分摊比例"), { target: { value: "100" } })
    fireEvent.change(within(panel).getByText("变更原因").parentElement!.querySelector("input")!, {
      target: { value: "合成测试调整" },
    })

    await waitFor(() => expect(save).toBeEnabled())
  })

  it("blocks revenue submission until monthly amounts equal the annual amount", async () => {
    installApiMock()
    render(
      <OrganizationRelationsTabs
        token="synthetic-token"
        organizationId={organizationId}
        effectiveAt="2026-08-09"
        canAdmin
        organizations={[{ id: organizationId, code: "730001", name: "合成组织" }]}
      />,
    )

    fireEvent.click(await screen.findByRole("tab", { name: "收入目标" }))
    const panel = screen.getByRole("tabpanel")
    const save = within(panel).getByRole("button", { name: "保存收入目标" })
    expect(save).toBeDisabled()

    fireEvent.change(screen.getByLabelText("1月收入目标"), { target: { value: "100" } })
    fireEvent.change(within(panel).getByText("变更原因").parentElement!.querySelector("input")!, {
      target: { value: "合成测试调整" },
    })

    await waitFor(() => expect(save).toBeEnabled())
  })
})
