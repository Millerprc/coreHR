// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { OrganizationDetailWorkspace } from "./OrganizationDetailWorkspace"


const organizationId = "30000000-0000-0000-0000-000000000002"
const legalEntityId = "40000000-0000-0000-0000-000000000001"


describe("OrganizationDetailWorkspace", () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      if (path.includes(`/organizations/${organizationId}/events?`)) {
        return Response.json({ items: [
          {
            id: "32000000-0000-0000-0000-000000000001",
            organization_id: organizationId,
            event_type: "VERSION_CHANGE",
            effective_date: "2026-04-01",
            status: "applied",
            payload: {},
            expected_version: 2,
            idempotency_key: "33000000-0000-0000-0000-000000000001",
            change_reason: path.endsWith("offset=50") ? "第二页历史记录" : "设立能效BG",
            applied_at: "2026-04-01T00:00:00+08:00",
            cancelled_at: null,
          },
        ], total: 51, limit: 50, offset: Number(new URL(path, "http://localhost").searchParams.get("offset")) })
      }
      if (path.includes(`/organizations/${organizationId}/relations`)) {
        return Response.json({
          effective_at: "2026-08-20",
          legal_entity_ids: [legalEntityId],
          legal_entity_version: 1,
          leader_person_ids: [],
          leader_version: 1,
          bp_membership_ids: [],
        })
      }
      if (path.includes(`/organizations/${organizationId}?effective_at=`)) {
        return Response.json({
          id: organizationId,
          code: "NO.531475",
          name: "能效BG",
          organization_type_id: "31000000-0000-0000-0000-000000000002",
          organization_type_code: "BG",
          organization_type_name: "BG",
          parent_organization_id: "30000000-0000-0000-0000-000000000001",
          parent_organization_code: "NO.531400",
          country_code: "CN",
          status: "active",
          effective_from: "2026-04-01",
          effective_to: null,
          version: 2,
          planned_events: [],
        })
      }
      if (path.includes("/organizations/tree")) {
        return Response.json([
          {
            id: "30000000-0000-0000-0000-000000000001",
            code: "NO.531400",
            name: "能效集团",
            organization_type_code: "GROUP",
            status: "active",
            children: [{
              id: organizationId,
              code: "NO.531475",
              name: "能效BG",
              organization_type_code: "BG",
              status: "active",
              children: [],
            }],
          },
        ])
      }
      if (path.endsWith("/organization-types")) {
        return Response.json([
          { id: "31000000-0000-0000-0000-000000000002", code: "BG", name: "BG", sort_order: 2, is_active: true },
        ])
      }
      if (path.includes("/workforce/legal-entities")) {
        return Response.json({
          items: [{ id: legalEntityId, code: "LE001", name: "能效电子科技有限公司" }],
          total: 1,
        })
      }
      return Response.json({}, { status: 404 })
    }))
  })

  it("shows the approved information page and its change record tab", async () => {
    render(
      <OrganizationDetailWorkspace
        token="synthetic-token"
        canAdmin
        organizationId={organizationId}
        initialEffectiveAt="2026-08-20"
      />,
    )

    expect(await screen.findByRole("heading", { name: "能效BG" })).toBeInTheDocument()
    expect(screen.getByText("部门路径：能效集团 / 能效BG")).toBeInTheDocument()
    expect(screen.getByText("能效电子科技有限公司")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "添加变更" })).toBeEnabled()
    expect(screen.getByRole("button", { name: "停用" })).toBeEnabled()

    fireEvent.click(screen.getByRole("tab", { name: "变更记录" }))

    expect(await screen.findByText("设立能效BG")).toBeInTheDocument()
    expect(screen.getByText("已生效")).toBeInTheDocument()
    fireEvent.click(screen.getByTitle("2"))
    expect(await screen.findByText("第二页历史记录")).toBeInTheDocument()
    expect(vi.mocked(fetch).mock.calls.some(([input]) => String(input).endsWith("/events?limit=50&offset=50"))).toBe(true)
  })

  it("reads the organization tree at the viewing timepoint", async () => {
    // Requirement: D-103 — 组织详情页按查看时点读取组织树与详情，并显示当前时点状态。
    render(
      <OrganizationDetailWorkspace
        token="synthetic-token"
        canAdmin
        organizationId={organizationId}
        initialEffectiveAt="2026-08-20"
      />,
    )

    expect(await screen.findByRole("heading", { name: "能效BG" })).toBeInTheDocument()
    expect(vi.mocked(fetch).mock.calls.some(([input]) => (
      String(input).endsWith("/organizations/tree?as_of=2026-08-20")
    ))).toBe(true)
    expect(screen.getAllByText("截至 2026-08-20").length).toBeGreaterThan(0)

    fireEvent.change(screen.getByLabelText("查看日期"), {
      target: { value: "2026-09-20" },
    })

    await waitFor(() => {
      expect(vi.mocked(fetch).mock.calls.some(([input]) => (
        String(input).endsWith("/organizations/tree?as_of=2026-09-20")
      ))).toBe(true)
    })
    expect(screen.getAllByText("截至 2026-09-20").length).toBeGreaterThan(0)
  })
})
