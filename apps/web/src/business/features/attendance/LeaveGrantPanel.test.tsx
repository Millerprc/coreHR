// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { LeaveGrantPanel } from "./LeaveGrantPanel"


const page = (items: readonly unknown[]) => ({ items, total: items.length, limit: 200, offset: 0 })


describe("LeaveGrantPanel", () => {
  beforeEach(() => vi.restoreAllMocks())

  it("lists grant batches and marks unset enterprise rules as pending", async () => {
    const issued: unknown[] = []
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      if (init?.method === "POST" && path.includes("/issue")) {
        issued.push(path)
        return Response.json({
          id: "batch-1",
          batch_number: "LG00000001",
          period_code: "2026-01",
          period_type: "month",
          grant_date: "2026-01-01",
          status: "issued",
          source: "manual",
          created_by: "user-1",
          issued_at: "2026-01-01T00:00:00Z",
          issued_by: "user-1",
          voided_at: null,
          voided_by: null,
          void_reason: null,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        })
      }
      if (path.includes("/employment-options")) return Response.json(page([{
        id: "employment-1",
        person_id: "person-1",
        employee_number: "993001",
        display_name: "合成发假员工",
        employee_type_code: "REGULAR",
        status: "active",
      }]))
      if (path.includes("/leave-types?")) return Response.json(page([{
        id: "leave-type-1",
        code: "ANNUAL",
        name: "年假",
        unit: "day",
        status: "active",
        rules: { balance_mode: "enforced" },
      }]))
      if (path.includes("/leave-grant-rules?")) return Response.json(page([{
        id: "rule-1",
        code: "SYN_ANNUAL",
        name: "合成年假额度规则",
        version: 1,
        leave_type_id: "leave-type-1",
        status: "draft",
        entitlement_days: null,
        seniority_min_years: null,
        seniority_max_years: null,
        proration_method: null,
        accrual_frequency: null,
        cap_days: null,
        carryover_cap_days: null,
        valid_from: null,
        valid_to: null,
        reset_policy: null,
        termination_policy: null,
        effective_from: "2026-01-01",
        effective_to: null,
        rules: {},
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      }]))
      if (path.includes("/leave-grant-batches?")) return Response.json(page([{
        id: "batch-1",
        batch_number: "LG00000001",
        period_code: "2026-01",
        period_type: "month",
        grant_date: "2026-01-01",
        status: "draft",
        source: "manual",
        created_by: "user-1",
        issued_at: null,
        issued_by: null,
        voided_at: null,
        voided_by: null,
        void_reason: null,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      }]))
      return Response.json(page([]))
    }))

    render(<LeaveGrantPanel token="synthetic-token" canAdmin />)

    expect(await screen.findByText("LG00000001")).toBeInTheDocument()
    expect(screen.getByText("合成年假额度规则")).toBeInTheDocument()
    // 规则字段留空时提示「规则待配置」，不臆测取值。
    expect(screen.getAllByText("规则待配置").length).toBeGreaterThan(0)
    expect(screen.getByRole("button", { name: "新建发放批次" })).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "发放" }))
    await waitFor(() => expect(issued).toHaveLength(1))
    expect(issued[0]).toContain("/leave-grant-batches/batch-1/issue")
  }, 15_000)
})
