// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ConcurrentPositionPanel, ConcurrentPositionSection } from "./ConcurrentPositionPanel"


const personId = "51000000-0000-0000-0000-000000000001"
const organizationId = "52000000-0000-0000-0000-000000000001"
const jobId = "53000000-0000-0000-0000-000000000001"
const relationId = "54000000-0000-0000-0000-000000000001"


function today(): string {
  const now = new Date()
  const offset = now.getTimezoneOffset() * 60_000
  return new Date(now.getTime() - offset).toISOString().slice(0, 10)
}


function positionPayload(overrides: Record<string, unknown> = {}) {
  return {
    id: relationId,
    person_id: personId,
    person_name: "合成兼岗人员",
    organization_id: organizationId,
    organization_name: "合成部门甲",
    job_id: jobId,
    job_name: "合成职务甲",
    relation_type: "concurrent",
    effective_from: today(),
    effective_to: null,
    change_reason: "合成兼岗",
    ...overrides,
  }
}


function personsPayload() {
  return {
    items: [
      { id: personId, display_name: "合成兼岗人员", employee_number: "E001", legal_name: "合成兼岗人员" },
    ],
    total: 1,
    limit: 200,
    offset: 0,
  }
}


function organizationsPayload() {
  return [
    {
      id: organizationId,
      code: "SYN_ORG_A",
      name: "合成部门甲",
      children: [],
    },
  ]
}


function jobsPayload() {
  return {
    items: [
      { id: jobId, code: "SYN_JOB_A", name: "合成职务甲" },
    ],
    total: 1,
    limit: 200,
    offset: 0,
  }
}


function concurrentFetchMock(positions: readonly unknown[] = [positionPayload()]) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    const method = init?.method ?? "GET"
    if (path.includes("/concurrent-positions") && method === "DELETE") {
      return new Response(null, { status: 204 })
    }
    if (path.includes("/concurrent-positions") && method === "POST") {
      return Response.json(positionPayload(), { status: 201 })
    }
    if (path.includes("/persons/") && path.includes("/concurrent-positions")) {
      return Response.json(positions)
    }
    if (path.includes("/concurrent-positions")) {
      return Response.json({
        items: positions,
        total: positions.length,
        page: 1,
        page_size: 20,
      })
    }
    if (path.includes("/api/v1/workforce/persons")) {
      return Response.json(personsPayload())
    }
    if (path.includes("/api/v1/organizations/tree")) {
      return Response.json(organizationsPayload())
    }
    if (path.includes("/api/v1/workforce/jobs")) {
      return Response.json(jobsPayload())
    }
    return Response.json({}, { status: 404 })
  })
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}


describe("ConcurrentPositionPanel", () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  // AntD 的下拉同时渲染一个只读无障碍镜像列表和可见虚拟列表，
  // 这里取最近打开的下拉容器，在其中点击真实可见的选项。
  async function openDropdown(dialog: HTMLElement, label: string): Promise<HTMLElement> {
    fireEvent.mouseDown(within(dialog).getByLabelText(label))
    const listboxes = await screen.findAllByRole("listbox")
    const dropdown = listboxes[listboxes.length - 1].closest(".ant-select-dropdown")
    if (!dropdown) throw new Error(`下拉未打开：${label}`)
    return dropdown as HTMLElement
  }

  it("lists person-level concurrent positions with the agreed columns", async () => {
    concurrentFetchMock()

    render(<ConcurrentPositionSection token="synthetic-token" canAdmin />)

    const table = await screen.findByRole("table")
    expect(within(table).getByText("合成兼岗人员")).toBeInTheDocument()
    expect(within(table).getByText("合成部门甲")).toBeInTheDocument()
    expect(within(table).getByText("合成职务甲")).toBeInTheDocument()
    expect(within(table).getByText("兼岗")).toBeInTheDocument()
    expect(within(table).getByText(today())).toBeInTheDocument()
    expect(within(table).getByText("长期有效")).toBeInTheDocument()

    // 列头与页面合同一致：人员、组织、职务、关系类型、生效日期、失效日期、操作。
    for (const header of ["人员", "组织", "职务", "关系类型", "生效日期", "失效日期", "操作"]) {
      expect(within(table).getByText(header)).toBeInTheDocument()
    }

    // 计数行与分页器总数口径一致。
    expect(screen.getAllByText("共 1 条兼岗")).toHaveLength(2)
  })

  it("offers the agreed filters and the create entry on the host page", async () => {
    concurrentFetchMock()

    render(<ConcurrentPositionSection token="synthetic-token" canAdmin />)

    await screen.findByRole("table")
    expect(screen.getByLabelText("按人员筛选")).toBeInTheDocument()
    expect(screen.getByLabelText("按组织筛选")).toBeInTheDocument()
    expect(screen.getByLabelText("按生效日期查看")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /重\s*置/ })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /查\s*询/ })).toBeInTheDocument()
    // 新建兼岗入口在宿主页上，Modal 覆盖宿主页，不叠加在员工档案 Drawer 之上。
    expect(screen.getByRole("button", { name: "新建兼岗" })).toBeInTheDocument()
  })

  it("shows the concurrent positions of one person read-only inside the archive drawer", async () => {
    concurrentFetchMock()

    render(<ConcurrentPositionPanel token="synthetic-token" personId={personId} />)

    const table = await screen.findByRole("table")
    expect(within(table).getByText("合成部门甲")).toBeInTheDocument()
    expect(within(table).getByText("合成职务甲")).toBeInTheDocument()
    // 只读展示：Drawer 内不再出现「结束」入口，也不再出现「新建兼岗」入口。
    expect(screen.queryByRole("button", { name: "结束" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "新建兼岗" })).not.toBeInTheDocument()
    expect(screen.getAllByText("共 1 条兼岗")).toHaveLength(1)
  })

  it("creates a concurrent position from the modal form", async () => {
    const fetchMock = concurrentFetchMock()

    render(<ConcurrentPositionSection token="synthetic-token" canAdmin />)

    await screen.findByRole("table")
    fireEvent.click(screen.getByRole("button", { name: "新建兼岗" }))

    const dialog = await screen.findByRole("dialog")
    expect(within(dialog).getByText("新建兼岗")).toBeInTheDocument()

    const personDropdown = await openDropdown(dialog, "选择人员")
    fireEvent.click(within(personDropdown).getByText("合成兼岗人员"))

    const organizationDropdown = await openDropdown(dialog, "选择组织")
    fireEvent.click(within(organizationDropdown).getByText("合成部门甲"))

    const jobDropdown = await openDropdown(dialog, "选择职务")
    fireEvent.click(within(jobDropdown).getByText("合成职务甲"))

    fireEvent.change(within(dialog).getByLabelText("填写变更原因"), {
      target: { value: "合成兼岗原因" },
    })

    fireEvent.click(within(dialog).getByRole("button", { name: /保\s*存/ }))

    await waitFor(() => {
      const postCall = fetchMock.mock.calls.find(([input, init]) => (
        String(input).includes("/concurrent-positions") && init?.method === "POST"
      ))
      expect(postCall).toBeDefined()
      expect(JSON.parse(String(postCall?.[1]?.body))).toEqual({
        person_id: personId,
        organization_id: organizationId,
        job_id: jobId,
        effective_from: today(),
        change_reason: "合成兼岗原因",
      })
    })
  })

  it("ends a concurrent position after a second confirmation", async () => {
    const fetchMock = concurrentFetchMock()

    render(<ConcurrentPositionSection token="synthetic-token" canAdmin />)

    await screen.findByRole("table")
    fireEvent.click(await screen.findByRole("button", { name: "结束" }))

    const confirmation = await screen.findByText("确认结束这条兼岗？")
    const popconfirm = confirmation.closest(".ant-popconfirm")
    if (!popconfirm) throw new Error("结束兼岗的二次确认未出现")
    fireEvent.click(within(popconfirm as HTMLElement).getByRole("button", { name: /确认结束/ }))

    await waitFor(() => {
      const deleteCall = fetchMock.mock.calls.find(([input, init]) => (
        String(input).includes(`/concurrent-positions/${relationId}`) && init?.method === "DELETE"
      ))
      expect(deleteCall).toBeDefined()
    })
  })

  it("disables write actions for accounts without administration permission", async () => {
    concurrentFetchMock()

    render(<ConcurrentPositionSection token="synthetic-token" canAdmin={false} />)

    await screen.findByRole("table")
    expect(screen.getByRole("button", { name: "新建兼岗" })).toBeDisabled()
    expect(await screen.findByRole("button", { name: "结束" })).toBeDisabled()
  })
})
