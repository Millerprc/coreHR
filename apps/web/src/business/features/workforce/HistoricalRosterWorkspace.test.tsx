// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { HistoricalRosterWorkspace } from "./HistoricalRosterWorkspace"


interface RecordedCall {
  readonly url: string
}


const rosterRow = {
  person_id: "70000000-0000-0000-0000-000000000001",
  employee_number: "990501",
  display_name: "合成花名册人员",
  legal_name: "合成花名册人员",
  organization_id: "71000000-0000-0000-0000-000000000001",
  organization_code: "ROSTER-A",
  organization_name: "合成原部门",
  job_id: "72000000-0000-0000-0000-000000000001",
  job_code: "ROSTER-JOB",
  job_name: "合成职位",
  employment_status: "active",
  hire_date: "2026-01-01",
  field_history_available: true,
  corrected_fields: ["display_name"],
}


function rosterPayload(items: unknown[] = [rosterRow], total = items.length): Record<string, unknown> {
  return {
    as_of: "2026-05-01",
    items,
    total,
    limit: 20,
    offset: 0,
    field_history_note:
      "时点的人员字段值 = 登记值 + 生效日期不晚于该时点的最后一条修正；未被修正过的字段等于当前值，本结果不是完整的历史档案快照。",
  }
}


function stubFetch(calls: RecordedCall[], items: unknown[] = [rosterRow], total = items.length): void {
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    calls.push({ url })
    if (url.includes("/workforce/people/roster-history")) {
      return Response.json(rosterPayload(items, total))
    }
    if (url.endsWith("/organizations/tree")) return Response.json([])
    return Response.json({}, { status: 404 })
  }))
}


describe("HistoricalRosterWorkspace", () => {
  beforeEach(() => vi.restoreAllMocks())

  // Requirement: D-102 — 页面合同：表头带「（时点）」后缀，筛选区按画板顺序排列。
  it("按画板呈现表头列、筛选栏与计数行", async () => {
    stubFetch([])
    render(<HistoricalRosterWorkspace token="synthetic-token" />)

    const table = await screen.findByRole("table")
    for (const header of [
      "工号",
      "姓名（时点）",
      "主组织（时点）",
      "职位（时点）",
      "在职状态（时点）",
      "入职日期（时点）",
      "操作",
    ]) {
      expect(within(table).getByRole("columnheader", { name: header })).toBeInTheDocument()
    }

    expect(screen.getByLabelText("查看日期")).toBeInTheDocument()
    expect(screen.getByLabelText("主组织")).toBeInTheDocument()
    expect(screen.getByLabelText("在职状态")).toBeInTheDocument()
    expect(screen.getByLabelText("搜索姓名或工号")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /重\s*置/ })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /查\s*询/ })).toBeInTheDocument()

    // 计数行与分页器取同一个 total。
    expect(await screen.findByText("共 1 人（截至 2026-05-01）")).toBeInTheDocument()
    expect(within(table).getByText("990501")).toBeInTheDocument()
    expect(within(table).getByText("合成原部门")).toBeInTheDocument()
    expect(within(table).getByText("在职")).toBeInTheDocument()
  })

  // Requirement: D-102 — 提示条写明字段级历史的边界，不得暗示是完整档案快照。
  it("提示条写明时点字段值的口径", async () => {
    stubFetch([])
    render(<HistoricalRosterWorkspace token="synthetic-token" />)

    expect(
      await screen.findByText(
        "时点的人员字段值 = 登记值 + 生效日期不晚于该时点的最后一条修正；未被修正过的字段等于当前值。",
      ),
    ).toBeInTheDocument()
  })

  // Requirement: D-102 — 该时点没有在册员工时给出空态文案。
  it("该时点没有在册员工时显示空态", async () => {
    stubFetch([], [], 0)
    render(<HistoricalRosterWorkspace token="synthetic-token" />)

    expect(await screen.findByText("该时点没有在册员工")).toBeInTheDocument()
    expect(await screen.findByText("共 0 人（截至 2026-05-01）")).toBeInTheDocument()
  })

  // Requirement: D-091 — 草稿式筛选：改值不立即查询，点「查询」才提交。
  it("筛选为草稿式，点查询才把条件提交给接口", async () => {
    const calls: RecordedCall[] = []
    stubFetch(calls)
    render(<HistoricalRosterWorkspace token="synthetic-token" />)

    await screen.findByRole("table")
    const before = calls.filter((call) => call.url.includes("roster-history")).length

    fireEvent.change(screen.getByLabelText("查看日期"), { target: { value: "2026-04-01" } })
    fireEvent.change(screen.getByLabelText("搜索姓名或工号"), { target: { value: "合成花名册" } })
    expect(calls.filter((call) => call.url.includes("roster-history")).length).toBe(before)

    fireEvent.click(screen.getByRole("button", { name: /查\s*询/ }))

    await waitFor(() => {
      const submitted = calls.filter((call) => call.url.includes("roster-history")).at(-1)
      expect(submitted?.url).toContain("as_of=2026-04-01")
      expect(submitted?.url).toContain("search=%E5%90%88%E6%88%90%E8%8A%B1%E5%90%8D%E5%86%8C")
    })
  })

  // Requirement: D-102 — 「重置」清空筛选条件，查看日期回到今天。
  it("重置清空筛选条件", async () => {
    const calls: RecordedCall[] = []
    stubFetch(calls)
    render(<HistoricalRosterWorkspace token="synthetic-token" />)

    await screen.findByRole("table")
    fireEvent.change(screen.getByLabelText("查看日期"), { target: { value: "2026-04-01" } })
    fireEvent.click(screen.getByRole("button", { name: /重\s*置/ }))

    await waitFor(() => {
      const submitted = calls.filter((call) => call.url.includes("roster-history")).at(-1)
      expect(submitted?.url).not.toContain("search=")
    })
    expect(screen.getByLabelText("查看日期")).toHaveValue(localDate())
  })

  // Requirement: D-102 — 行操作给出该员工的时点字段与修正说明。
  it("行操作给出时点信息与修正过的字段", async () => {
    stubFetch([])
    render(<HistoricalRosterWorkspace token="synthetic-token" />)

    fireEvent.click(await screen.findByRole("button", { name: "查看时点信息" }))

    expect(await screen.findByText("修正过的字段")).toBeInTheDocument()
    expect(screen.getByText("显示姓名")).toBeInTheDocument()
    expect(screen.getByText("合成原部门 (ROSTER-A)")).toBeInTheDocument()
  })


  function localDate(): string {
    const now = new Date()
    const offset = now.getTimezoneOffset() * 60_000
    return new Date(now.getTime() - offset).toISOString().slice(0, 10)
  }
})
