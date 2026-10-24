// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { AuditLogWorkspace } from "./AuditLogWorkspace"


const auditLogItems = [
  {
    id: "30000000-0000-0000-0000-000000000001",
    occurred_at: "2026-03-05T02:15:00Z",
    actor_id: "10000000-0000-0000-0000-000000000009",
    actor_name: "合成主管理员",
    trace_id: "trace-0001",
    action: "user.update",
    object_type: "user",
    object_id: "20000000-0000-0000-0000-000000000007",
    reason: "调整账号角色",
    source: "web",
  },
  {
    id: "30000000-0000-0000-0000-000000000002",
    occurred_at: "2026-03-05T03:15:00Z",
    actor_id: "10000000-0000-0000-0000-000000000009",
    actor_name: null,
    trace_id: "trace-0002",
    action: "user.delete",
    object_type: "user",
    object_id: "20000000-0000-0000-0000-000000000008",
    reason: null,
    source: "api",
  },
]


// Requirement: P-13 — 操作人下拉的数据源是审计专用只读端点，
// 响应只包含 id、display_name、username 三个字段（不含邮箱、手机号等个人联系方式）。
const actorItems = [
  {
    id: "10000000-0000-0000-0000-000000000009",
    username: "synthetic-admin",
    display_name: "合成主管理员",
  },
  {
    id: "10000000-0000-0000-0000-000000000010",
    username: "ssc.synthetic",
    display_name: "合成SSC管理员",
  },
]


function localDateTime(value: string): string {
  const parsed = new Date(value)
  const pad = (part: number): string => String(part).padStart(2, "0")
  return `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())} `
    + `${pad(parsed.getHours())}:${pad(parsed.getMinutes())}:${pad(parsed.getSeconds())}`
}


function listRequests(fetchMock: ReturnType<typeof vi.fn>): URL[] {
  return fetchMock.mock.calls
    .map(([input]) => String(input))
    .filter((path) => path.includes("/api/v1/platform/audit-logs?"))
    .map((path) => new URL(path, "http://corehr.test"))
}


/**
 * 在日期面板中选取当前月份的起始日与结束日。
 * 面板只展示当前月与下一月，因此限定在第一个面板内按日号查找，避免跨月误选。
 */
async function pickCurrentMonthRange(startDay: number, endDay: number): Promise<void> {
  const startInput = screen.getByPlaceholderText("开始日期")
  fireEvent.mouseDown(startInput)
  fireEvent.click(startInput)
  await waitFor(() => expect(document.querySelector(".ant-picker-panel")).toBeTruthy())
  const panel = document.querySelector(".ant-picker-panel")
  const cells = Array.from(panel?.querySelectorAll("td.ant-picker-cell-in-view") ?? [])
  const pick = (day: number): void => {
    const cell = cells.find((item) => item.textContent === String(day))
    if (!cell) throw new Error(`日期面板缺少 ${day} 日`)
    fireEvent.click(cell)
  }
  pick(startDay)
  pick(endDay)
}


describe("AuditLogWorkspace", () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    Reflect.deleteProperty(URL, "createObjectURL")
    Reflect.deleteProperty(URL, "revokeObjectURL")
  })

  function stubFetch(items: readonly unknown[] = auditLogItems): ReturnType<typeof vi.fn> {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      if (path.includes("/api/v1/platform/audit-logs/actions")) {
        return Response.json({ items: [{ code: "user.update", count: 12 }, { code: "user.delete", count: 3 }] })
      }
      if (path.includes("/api/v1/platform/audit-logs/export")) {
        return new Response("id,action\n", {
          status: 200,
          headers: {
            "Content-Type": "text/csv",
            "Content-Disposition": "attachment; filename=\"audit-logs-2026.csv\"",
          },
        })
      }
      if (path.includes("/api/v1/platform/audit/actors")) {
        return Response.json({ items: actorItems, total: actorItems.length })
      }
      if (path.includes("/api/v1/platform/audit-logs?")) {
        return Response.json({ items, total: items.length, page: 1, page_size: 20 })
      }
      return Response.json({}, { status: 404 })
    })
    vi.stubGlobal("fetch", fetchMock)
    return fetchMock
  }

  it("renders audit log rows with actor, action and trace identifiers", async () => {
    stubFetch()

    render(<AuditLogWorkspace token="synthetic-token" canAdmin={true} />)

    expect(await screen.findByText("合成主管理员")).toBeInTheDocument()
    expect(screen.getByText("user.update")).toBeInTheDocument()
    expect(screen.getByText("user.delete")).toBeInTheDocument()
    expect(screen.getByText("trace-0001")).toBeInTheDocument()
    expect(screen.getByText("调整账号角色")).toBeInTheDocument()
    expect(screen.getByText(localDateTime("2026-03-05T02:15:00Z"))).toBeInTheDocument()

    // 操作人姓名为空时回退到 actor_id。
    expect(screen.getByText("10000000-0000-0000-0000-000000000009")).toBeInTheDocument()
    expect(screen.getAllByText("web")).toHaveLength(1)
  })

  it("按画板给出五项筛选、查询重置与列表计数行", async () => {
    stubFetch()

    render(<AuditLogWorkspace token="synthetic-token" canAdmin={true} />)

    await screen.findByText("合成主管理员")

    expect(screen.getByText("时间范围")).toBeInTheDocument()
    expect(screen.getByPlaceholderText("开始日期")).toBeInTheDocument()
    expect(screen.getByLabelText("操作类型")).toBeInTheDocument()
    expect(screen.getByLabelText("对象类型")).toBeInTheDocument()
    expect(screen.getByLabelText("追踪 ID")).toBeInTheDocument()
    expect(screen.getByLabelText("操作人")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /重\s*置/ })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /查\s*询/ })).toBeInTheDocument()

    // 列表计数行与分页器总数一致（两处都出现同一个总数）。
    expect(screen.getAllByText("共 2 条操作日志")).toHaveLength(2)
  })

  it("sends the selected filters to the audit log query endpoint", async () => {
    const fetchMock = stubFetch()

    render(<AuditLogWorkspace token="synthetic-token" canAdmin={true} />)

    await screen.findByText("合成主管理员")

    fireEvent.change(screen.getByLabelText("对象类型"), { target: { value: "user" } })
    fireEvent.change(screen.getByLabelText("追踪 ID"), { target: { value: "trace-0001" } })

    fireEvent.mouseDown(screen.getByRole("combobox", { name: "操作类型" }))
    fireEvent.click(await screen.findByRole("option", { name: "user.update (12)" }))

    fireEvent.mouseDown(screen.getByRole("combobox", { name: "操作人" }))
    fireEvent.click(await screen.findByRole("option", { name: "合成SSC管理员" }))

    await pickCurrentMonthRange(1, 5)

    fireEvent.click(screen.getByRole("button", { name: /查\s*询/ }))

    await waitFor(() => {
      expect(listRequests(fetchMock).length).toBeGreaterThan(1)
    })
    const request = listRequests(fetchMock).at(-1)!
    expect(request.searchParams.get("action")).toBe("user.update")
    expect(request.searchParams.get("object_type")).toBe("user")
    expect(request.searchParams.get("trace_id")).toBe("trace-0001")
    expect(request.searchParams.get("actor_id")).toBe("10000000-0000-0000-0000-000000000010")
    const now = new Date()
    expect(request.searchParams.get("occurred_from")).toBe(
      new Date(now.getFullYear(), now.getMonth(), 1, 0, 0, 0, 0).toISOString(),
    )
    expect(request.searchParams.get("occurred_to")).toBe(
      new Date(now.getFullYear(), now.getMonth(), 5, 23, 59, 59, 999).toISOString(),
    )
    expect(request.searchParams.get("page")).toBe("1")
    expect(request.searchParams.get("page_size")).toBe("20")
  })

  it("shows an empty state when no audit log matches the filters", async () => {
    stubFetch([])

    render(<AuditLogWorkspace token="synthetic-token" canAdmin={true} />)

    expect(await screen.findByText("暂无符合条件的操作日志")).toBeInTheDocument()
  })

  it("hides the export action for users without administrator rights", async () => {
    const fetchMock = stubFetch()

    render(<AuditLogWorkspace token="synthetic-token" canAdmin={false} />)

    await screen.findByText("合成主管理员")
    expect(screen.queryByRole("button", { name: /导\s*出\s*CSV/ })).not.toBeInTheDocument()
    expect(listRequests(fetchMock)).toHaveLength(1)
  })

  it("loads the operator dropdown from the audit-specific actors endpoint", async () => {
    const fetchMock = stubFetch()

    render(<AuditLogWorkspace token="synthetic-token" canAdmin={true} />)

    await screen.findByText("合成主管理员")

    fireEvent.mouseDown(screen.getByRole("combobox", { name: "操作人" }))
    expect(await screen.findByRole("option", { name: "合成SSC管理员" })).toBeInTheDocument()

    // Requirement: P-13 — 下拉数据源必须是审计专用端点。
    const actorCall = fetchMock.mock.calls.find(([input]) => String(input).includes("/api/v1/platform/audit/actors"))
    expect(actorCall).toBeDefined()
    // 旧的 /api/v1/platform/users 权限码是 `*`，治理管理员必然 403，不得再被调用。
    expect(
      fetchMock.mock.calls.some(([input]) => String(input).includes("/api/v1/platform/users")),
    ).toBe(false)
  })

  it("exports the current filters as a CSV download for administrators", async () => {
    const fetchMock = stubFetch()
    const createObjectURL = vi.fn(() => "blob:audit-logs")
    Object.defineProperty(URL, "createObjectURL", { configurable: true, writable: true, value: createObjectURL })
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, writable: true, value: vi.fn() })

    render(<AuditLogWorkspace token="synthetic-token" canAdmin={true} />)

    await screen.findByText("合成主管理员")
    fireEvent.change(screen.getByLabelText("对象类型"), { target: { value: "user" } })
    fireEvent.click(screen.getByRole("button", { name: /查\s*询/ }))
    await waitFor(() => expect(listRequests(fetchMock).length).toBeGreaterThan(1))

    fireEvent.click(screen.getByRole("button", { name: /导\s*出\s*CSV/ }))

    await waitFor(() => expect(createObjectURL).toHaveBeenCalled())
    const exportCall = fetchMock.mock.calls.find(([input]) => String(input).includes("/api/v1/platform/audit-logs/export"))
    expect(exportCall).toBeDefined()
    const exportUrl = new URL(String(exportCall?.[0]), "http://corehr.test")
    expect(exportUrl.searchParams.get("object_type")).toBe("user")
    expect((exportCall?.[1] as RequestInit | undefined)?.headers).toMatchObject({
      Authorization: "Bearer synthetic-token",
    })
  })
})
