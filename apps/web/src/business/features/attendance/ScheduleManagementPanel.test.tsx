// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ScheduleManagementPanel } from "./ScheduleManagementPanel"


const page = (items: readonly unknown[]) => ({ items, total: items.length, limit: 200, offset: 0 })


describe("ScheduleManagementPanel", () => {
  beforeEach(() => vi.restoreAllMocks())

  it("shows schedule types, cycles and swap records", async () => {
    const decided: unknown[] = []
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      if (init?.method === "PATCH" && path.includes("/schedule-swaps/")) {
        decided.push(path)
        return Response.json({
          id: "swap-1",
          request_number: "SW00000001",
          employment_id_a: "employment-1",
          employment_id_b: "employment-2",
          work_date: "2026-09-10",
          original_shift_id: "shift-1",
          new_shift_id: "shift-2",
          status: "approved",
          requested_by: "user-1",
          requested_at: "2026-09-01T00:00:00Z",
          decided_at: "2026-09-02T00:00:00Z",
          decided_by: "user-1",
          effective_at: "2026-09-02T00:00:00Z",
          remark: null,
          created_at: "2026-09-01T00:00:00Z",
          updated_at: "2026-09-02T00:00:00Z",
        })
      }
      if (path.includes("/employment-options")) return Response.json(page([
        {
          id: "employment-1",
          person_id: "person-1",
          employee_number: "993101",
          display_name: "合成排班员工甲",
          employee_type_code: "REGULAR",
          status: "active",
        },
        {
          id: "employment-2",
          person_id: "person-2",
          employee_number: "993102",
          display_name: "合成排班员工乙",
          employee_type_code: "REGULAR",
          status: "active",
        },
      ]))
      if (path.includes("/shifts?")) return Response.json(page([{
        id: "shift-1",
        code: "DAY",
        name: "白班",
        start_time: "09:00:00",
        end_time: "18:00:00",
        crosses_midnight: false,
        rule_set_id: "rule-1",
        rule_set_version: 1,
        rule_snapshot: {},
        status: "active",
      }]))
      if (path.includes("/schedule-types?")) return Response.json(page([{
        id: "type-1",
        code: "ROTATING",
        name: "轮班",
        requires_shift_cycle: true,
        requires_flexible_window: false,
        allows_multiple_shifts_per_day: false,
        requires_publish: true,
        status: "active",
        rules: {},
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      }]))
      if (path.includes("/shift-cycles?")) return Response.json(page([{
        id: "cycle-1",
        code: "CYCLE-14",
        name: "合成轮班周期",
        schedule_type_id: "type-1",
        cycle_start_date: "2026-01-05",
        cycle_days: 14,
        shift_sequence: [],
        status: "draft",
        rules: {},
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      }]))
      if (path.includes("/flexible-windows?")) return Response.json(page([]))
      if (path.includes("/schedule-publish-batches?")) return Response.json(page([{
        id: "publish-1",
        batch_number: "SP00000001",
        period_code: "2026-09",
        period_start: "2026-09-01",
        period_end: "2026-09-30",
        schedule_type_id: null,
        status: "draft",
        published_at: null,
        published_by: null,
        created_by: "user-1",
        published_count: 0,
        created_at: "2026-09-01T00:00:00Z",
        updated_at: "2026-09-01T00:00:00Z",
      }]))
      if (path.includes("/schedule-swaps?")) return Response.json(page([{
        id: "swap-1",
        request_number: "SW00000001",
        employment_id_a: "employment-1",
        employment_id_b: "employment-2",
        work_date: "2026-09-10",
        original_shift_id: "shift-1",
        new_shift_id: "shift-2",
        status: "draft",
        requested_by: "user-1",
        requested_at: "2026-09-01T00:00:00Z",
        decided_at: null,
        decided_by: null,
        effective_at: null,
        remark: null,
        created_at: "2026-09-01T00:00:00Z",
        updated_at: "2026-09-01T00:00:00Z",
      }]))
      return Response.json(page([]))
    }))

    render(<ScheduleManagementPanel token="synthetic-token" canAdmin />)

    // 排班类型名称在「排班类型」表与「轮班周期」表的类型列各出现一次。
    expect((await screen.findAllByText("轮班")).length).toBeGreaterThan(0)
    expect(screen.getByText("合成轮班周期")).toBeInTheDocument()
    expect(screen.getByText("SW00000001")).toBeInTheDocument()
    expect(screen.getByText("合成排班员工甲")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "批量生成草稿" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "新建换班记录" })).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "批准" }))
    await waitFor(() => expect(decided).toHaveLength(1))
    expect(decided[0]).toContain("/schedule-swaps/swap-1")
  }, 15_000)
})
