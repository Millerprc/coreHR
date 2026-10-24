// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ReportPanel } from "./ReportPanel"


const page = (items: readonly unknown[]) => ({ items, total: items.length, limit: 200, offset: 0 })

const employment = {
  id: "employment-1",
  person_id: "person-1",
  employee_number: "993001",
  display_name: "合成考勤员工",
  employee_type_code: "REGULAR",
  status: "active",
}

const dailyResult = {
  id: "daily-1",
  employment_id: "employment-1",
  work_date: "2026-10-24",
  status: "normal",
  scheduled_minutes: 480,
  worked_minutes: 480,
  late_minutes: 0,
  early_leave_minutes: 0,
  exception_codes: [],
  evidence: {},
  version: 1,
  is_current: true,
}


interface FetchStub {
  /** 提交到计算任务接口的请求体。 */
  readonly submitted: Record<string, unknown>[]
  /** 日报结果表的取数次数（用于判断结果表是否被刷新）。 */
  readonly dailyFetches: string[]
  /** 任务状态轮询次数。 */
  readonly taskFetches: string[]
}


function stubFetch(stub: FetchStub): void {
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (init?.method === "POST" && path.includes("/calculation-tasks")) {
      stub.submitted.push(JSON.parse(String(init.body)) as Record<string, unknown>)
      return Response.json({ id: "task-1", task_type: "attendance.calculate", status: "pending", created_at: "2026-10-24T00:00:00Z" }, { status: 202 })
    }
    if (path.includes("/calculation-tasks/")) {
      stub.taskFetches.push(path)
      return Response.json({
        id: "task-1",
        task_type: "attendance.calculate",
        status: "succeeded",
        payload: { kind: "daily", scope: "all" },
        result: {
          kind: "daily",
          scope: "all",
          work_date: "2026-10-24",
          target_count: 200,
          succeeded_count: 200,
          failed_count: 0,
          failure_codes: {},
        },
        error_code: null,
        attempts: 1,
        max_attempts: 3,
        next_attempt_at: "2026-10-24T00:00:10Z",
        lease_owner: null,
        lease_expires_at: null,
        started_at: "2026-10-24T00:00:01Z",
        finished_at: "2026-10-24T00:00:05Z",
        created_by: "user-1",
        idempotency_key: "key-1",
        progress: "已处理 200 / 200 人",
        created_at: "2026-10-24T00:00:00Z",
        updated_at: "2026-10-24T00:00:05Z",
      })
    }
    if (path.includes("/employment-options")) return Response.json(page([employment]))
    if (path.includes("/daily-results?")) {
      stub.dailyFetches.push(path)
      return Response.json(page([dailyResult]))
    }
    if (path.includes("/monthly-results?")) return Response.json(page([]))
    return Response.json(page([]))
  }))
}


/** 打开弹窗并返回弹窗容器（弹窗内容在 portal 里，查询要限定在 dialog 内）。 */
async function openDailyDialog(): Promise<HTMLElement> {
  fireEvent.click(screen.getByRole("button", { name: "计算日报" }))
  return screen.findByRole("dialog")
}


describe("ReportPanel", () => {
  beforeEach(() => vi.restoreAllMocks())

  it("默认按全员提交日报计算任务", async () => {
    const stub: FetchStub = { submitted: [], dailyFetches: [], taskFetches: [] }
    stubFetch(stub)
    render(<ReportPanel token="synthetic-token" canAdmin />)
    await screen.findByText("合成考勤员工")

    const dialog = await openDailyDialog()
    // 默认范围是全员，且不出现人员多选框。
    expect(within(dialog).getByRole("radio", { name: "全员" })).toBeChecked()
    expect(document.getElementById("daily_scope_employment_ids")).toBeNull()

    fireEvent.click(within(dialog).getByRole("button", { name: /计\s*算/ }))
    await waitFor(() => expect(stub.submitted).toHaveLength(1))
    expect(stub.submitted[0]).toMatchObject({ kind: "daily", scope: "all", employment_ids: [] })
    // 日报只带工作日期，不带账期。
    expect(typeof stub.submitted[0].work_date).toBe("string")
    expect("period_month" in stub.submitted[0]).toBe(false)
  }, 45_000)

  it("切到指定人员并选中人员后按选中人员提交", async () => {
    const stub: FetchStub = { submitted: [], dailyFetches: [], taskFetches: [] }
    stubFetch(stub)
    render(<ReportPanel token="synthetic-token" canAdmin />)
    await screen.findByText("合成考勤员工")

    const dialog = await openDailyDialog()
    fireEvent.click(within(dialog).getByRole("radio", { name: "指定人员" }))
    await waitFor(() => expect(screen.getByText(/已加载 1 人/)).toBeInTheDocument())

    const input = document.getElementById("daily_scope_employment_ids") as HTMLElement
    expect(input).not.toBeNull()
    const trigger = input.closest(".ant-select-content") ?? input
    fireEvent.mouseDown(trigger)
    fireEvent.click(await screen.findByText("合成考勤员工 (993001)"))

    fireEvent.click(within(dialog).getByRole("button", { name: /计\s*算/ }))
    await waitFor(() => expect(stub.submitted).toHaveLength(1))
    expect(stub.submitted[0]).toMatchObject({ kind: "daily", scope: "selected", employment_ids: ["employment-1"] })
  }, 45_000)

  it("提交后轮询到成功并刷新结果表", async () => {
    const stub: FetchStub = { submitted: [], dailyFetches: [], taskFetches: [] }
    stubFetch(stub)
    render(<ReportPanel token="synthetic-token" canAdmin />)
    await screen.findByText("合成考勤员工")
    const dailyFetchesBefore = stub.dailyFetches.length

    const dialog = await openDailyDialog()
    fireEvent.click(within(dialog).getByRole("button", { name: /计\s*算/ }))
    await waitFor(() => expect(stub.submitted).toHaveLength(1))

    // 任务刚提交时是待处理状态，状态区出现在两个结果表上方。
    expect(await screen.findByText("排队中")).toBeInTheDocument()
    expect(await screen.findByText("成功", {}, { timeout: 10_000 })).toBeInTheDocument()
    expect(screen.getByText("目标 200 人 · 成功 200 人 · 失败 0 人")).toBeInTheDocument()
    // 任务成功后结果表自动刷新。
    await waitFor(() => expect(stub.dailyFetches.length).toBeGreaterThan(dailyFetchesBefore), { timeout: 10_000 })
    // 轮询在终态后停止。
    const taskFetchesAfterDone = stub.taskFetches.length
    await new Promise((resolve) => setTimeout(resolve, 2500))
    expect(stub.taskFetches.length).toBe(taskFetchesAfterDone)
  }, 45_000)
})
