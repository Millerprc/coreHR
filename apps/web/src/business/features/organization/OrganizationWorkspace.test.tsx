import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { OrganizationWorkspace } from "./OrganizationWorkspace"


const organizationId = "30000000-0000-0000-0000-000000000001"
const secondOrganizationId = "30000000-0000-0000-0000-000000000002"


function organizationDetail(
  name = "合成集团",
  effectiveFrom = "2026-01-01",
  id = organizationId,
  code = "730001",
) {
  return {
    id,
    code,
    name,
    organization_type_id: "31000000-0000-0000-0000-000000000001",
    organization_type_code: "GROUP",
    organization_type_name: "集团",
    parent_organization_id: null,
    parent_organization_code: null,
    country_code: "CN",
    status: "active",
    effective_from: effectiveFrom,
    effective_to: null,
    version: 1,
    planned_events: [
      {
        id: "32000000-0000-0000-0000-000000000001",
        organization_id: id,
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
  }
}


describe("OrganizationWorkspace", () => {
  beforeEach(() => vi.restoreAllMocks())

  function organizationFetchMock(
    detailResponder?: (path: string) => Response | Promise<Response>,
  ) {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      if (path.endsWith("/organization-types")) {
        return Response.json([
          { id: "31000000-0000-0000-0000-000000000001", code: "GROUP", name: "集团", sort_order: 1, is_active: true },
          { id: "31000000-0000-0000-0000-000000000002", code: "DEPARTMENT", name: "部门", sort_order: 2, is_active: true },
        ])
      }
      if (path.endsWith("/organizations/tree")) {
        return Response.json([
          {
            id: organizationId,
            code: "730001",
            name: "合成集团",
            organization_type_code: "GROUP",
            status: "active",
            children: [
              {
                id: secondOrganizationId,
                code: "730002",
                name: "合成部门",
                organization_type_code: "DEPARTMENT",
                status: "active",
                children: [],
              },
            ],
          },
        ])
      }
      if (path.includes("/relations")) {
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
      if (path.includes("/cost-allocation")) {
        return Response.json({ code: "COST_ALLOCATION_NOT_FOUND", message: "没有分摊" }, { status: 404 })
      }
      if (path.includes("/revenue-targets")) {
        return Response.json({
          organization_id: organizationId,
          year: 2026,
          include_descendants: false,
          targets: [],
          totals_by_currency: {},
        })
      }
      if (path.includes("/organizations/") && path.includes("?effective_at=")) {
        if (detailResponder) return detailResponder(path)
        return path.includes(secondOrganizationId)
          ? Response.json(organizationDetail("合成部门", "2026-01-01", secondOrganizationId, "730002"))
          : Response.json(organizationDetail())
      }
      if (path.includes("/workforce/legal-entities") || path.includes("/workforce/persons")) {
        return Response.json({ items: [], total: 0, limit: 200, offset: 0 })
      }
      return Response.json({}, { status: 404 })
    })
    vi.stubGlobal("fetch", fetchMock)
    return fetchMock
  }

  it("shows the approved department list from the real organization tree", async () => {
    organizationFetchMock()
    const openDetail = vi.spyOn(window, "open").mockImplementation(() => null)

    render(<OrganizationWorkspace token="synthetic-token" canAdmin />)

    expect(await screen.findByText("部门管理", { selector: "h2" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "列表" })).toHaveAttribute("aria-selected", "true")
    expect((await screen.findAllByText("合成集团")).length).toBeGreaterThan(0)
    expect(screen.getByText("730001")).toBeInTheDocument()
    expect(screen.getByText("集团", { selector: "td" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "添加变更" })).toBeDisabled()

    fireEvent.click(screen.getAllByText("查看")[0])
    expect(openDetail).toHaveBeenCalledWith(
      expect.stringMatching(/^#organization\/30000000-0000-0000-0000-000000000001\?effective_at=\d{4}-\d{2}-\d{2}$/),
      "_blank",
      "noopener,noreferrer",
    )

    fireEvent.change(screen.getByPlaceholderText("搜索部门名称或编号"), {
      target: { value: "不存在" },
    })

    expect(await screen.findByText("没有符合条件的部门")).toBeInTheDocument()
  })

  it("locates the selected department in the organization tree", async () => {
    const fetchMock = organizationFetchMock()

    render(<OrganizationWorkspace token="synthetic-token" canAdmin />)

    await screen.findAllByText("合成集团")

    fireEvent.click(screen.getAllByText("树中定位")[1])

    expect(screen.getByRole("tab", { name: "组织架构树" })).toHaveAttribute("aria-selected", "true")
    expect(await screen.findByText("合成部门", { selector: "h3" })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(new RegExp(`/api/v1/organizations/${secondOrganizationId}\\?effective_at=\\d{4}-\\d{2}-\\d{2}`)),
      expect.any(Object),
    )
    expect(screen.getByRole("button", { name: "添加变更" })).toBeEnabled()
  })

  it("keeps the current tree stable while the effective date changes detail queries", async () => {
    const fetchMock = organizationFetchMock()

    render(<OrganizationWorkspace token="synthetic-token" canAdmin />)

    fireEvent.click(await screen.findByRole("tab", { name: "组织架构树" }))
    expect(await screen.findByRole("heading", { name: "合成集团", level: 3 })).toBeInTheDocument()
    expect(screen.getByText("合成未来调整，状态：planned")).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText("查看日期"), {
      target: { value: "2027-01-01" },
    })
    expect(screen.getByRole("button", { name: "添加变更" })).toBeDisabled()

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        `/api/v1/organizations/${organizationId}?effective_at=2027-01-01`,
        expect.any(Object),
      )
    })
    const treeCalls = fetchMock.mock.calls.filter(([input]) => String(input).endsWith("/organizations/tree"))
    expect(treeCalls).toHaveLength(1)
  })

  it("ignores a stale detail response after a newer date has loaded", async () => {
    let resolveStale: ((response: Response) => void) | undefined
    const fetchMock = organizationFetchMock((path) => {
      if (path.includes("effective_at=2027-01-01")) {
        return new Promise<Response>((resolve) => {
          resolveStale = resolve
        })
      }
      if (path.includes("effective_at=2028-01-01")) {
        return Response.json(organizationDetail("最新组织结果", "2028-01-01"))
      }
      return Response.json(organizationDetail())
    })

    render(<OrganizationWorkspace token="synthetic-token" canAdmin />)
    fireEvent.click(await screen.findByRole("tab", { name: "组织架构树" }))
    expect(await screen.findByRole("heading", { name: "合成集团", level: 3 })).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText("查看日期"), {
      target: { value: "2027-01-01" },
    })
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/organizations/${organizationId}?effective_at=2027-01-01`,
      expect.any(Object),
    ))

    fireEvent.change(screen.getByLabelText("查看日期"), {
      target: { value: "2028-01-01" },
    })
    expect(await screen.findByRole("heading", { name: "最新组织结果", level: 3 })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "添加变更" })).toBeEnabled()

    await act(async () => {
      resolveStale?.(Response.json(organizationDetail("过期组织结果", "2027-01-01")))
    })

    expect(screen.getByRole("heading", { name: "最新组织结果", level: 3 })).toBeInTheDocument()
    expect(screen.queryByRole("heading", { name: "过期组织结果", level: 3 })).not.toBeInTheDocument()
  })
})
