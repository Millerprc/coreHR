// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ReportingWorkspace } from "./ReportingWorkspace"


const managerId = "40000000-0000-0000-0000-000000000001"
const subordinateId = "40000000-0000-0000-0000-000000000002"
const dottedSubordinateId = "40000000-0000-0000-0000-000000000003"
const directRelationId = "41000000-0000-0000-0000-000000000001"
const dottedRelationId = "41000000-0000-0000-0000-000000000002"


function today(): string {
  const now = new Date()
  const offset = now.getTimezoneOffset() * 60_000
  return new Date(now.getTime() - offset).toISOString().slice(0, 10)
}


function relationPayload(overrides: Record<string, unknown> = {}) {
  return {
    id: directRelationId,
    manager_person_id: managerId,
    manager_name: "王经理",
    subordinate_person_id: subordinateId,
    subordinate_name: "李下属",
    relation_type: "direct",
    effective_from: today(),
    effective_to: null,
    ...overrides,
  }
}


function personsPayload() {
  return {
    items: [
      { id: managerId, display_name: "王经理", employee_number: "E001" },
      { id: subordinateId, display_name: "李下属", employee_number: "E002" },
      { id: dottedSubordinateId, display_name: "赵虚线", employee_number: "E003" },
    ],
    total: 3,
    limit: 200,
    offset: 0,
  }
}


function reportingFetchMock(relations: readonly unknown[] = [relationPayload()]) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    const method = init?.method ?? "GET"
    if (path.includes("/reporting-relations") && method === "DELETE") {
      return new Response(null, { status: 204 })
    }
    if (path.includes("/reporting-relations") && method === "POST") {
      return Response.json(relationPayload(), { status: 201 })
    }
    if (path.includes("/reporting-relations")) {
      return Response.json({
        items: relations,
        total: relations.length,
        page: 1,
        page_size: 20,
      })
    }
    if (path.includes("/workforce/persons")) {
      return Response.json(personsPayload())
    }
    return Response.json({}, { status: 404 })
  })
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}


describe("ReportingWorkspace", () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  // AntD 的下拉同时渲染一个只读无障碍镜像列表和可见虚拟列表，
  // 这里取最近打开的下拉容器，在其中点击真实可见的选项。
  async function openPersonDropdown(dialog: HTMLElement, label: string): Promise<HTMLElement> {
    fireEvent.mouseDown(within(dialog).getByLabelText(label))
    const listboxes = await screen.findAllByRole("listbox")
    const dropdown = listboxes[listboxes.length - 1].closest(".ant-select-dropdown")
    if (!dropdown) throw new Error(`人员下拉未打开：${label}`)
    return dropdown as HTMLElement
  }

  it("lists relations and distinguishes direct from dotted reporting lines", async () => {
    reportingFetchMock([
      relationPayload(),
      relationPayload({
        id: dottedRelationId,
        relation_type: "dotted",
        subordinate_person_id: dottedSubordinateId,
        subordinate_name: "赵虚线",
      }),
    ])

    render(<ReportingWorkspace token="synthetic-token" canAdmin />)

    expect(await screen.findByText("汇报关系", { selector: "h2" })).toBeInTheDocument()
    const table = await screen.findByRole("table")
    expect(within(table).getAllByText("王经理")).toHaveLength(2)
    expect(within(table).getByText("李下属")).toBeInTheDocument()
    expect(within(table).getByText("赵虚线")).toBeInTheDocument()
    expect(within(table).getByText("直属")).toBeInTheDocument()
    expect(within(table).getByText("虚线")).toBeInTheDocument()
    expect(within(table).getAllByText(today())).toHaveLength(2)
    expect(within(table).getAllByText("长期有效")).toHaveLength(2)
  })

  it("按画板把关系类型渲染为带描边的整块标签，并给出三项筛选与查询重置", async () => {
    reportingFetchMock([
      relationPayload(),
      relationPayload({
        id: dottedRelationId,
        relation_type: "dotted",
        subordinate_person_id: dottedSubordinateId,
        subordinate_name: "赵虚线",
      }),
    ])

    render(<ReportingWorkspace token="synthetic-token" canAdmin />)

    const table = await screen.findByRole("table")
    // 关系类型的文字在标签内部，并且是带描边的 outlined 变体。
    const directTag = within(table).getByText("直属")
    expect(directTag).toHaveClass("ant-tag")
    expect(directTag).toHaveClass("ant-tag-outlined")
    const dottedTag = within(table).getByText("虚线")
    expect(dottedTag).toHaveClass("ant-tag")
    expect(dottedTag).toHaveClass("ant-tag-outlined")

    // 筛选区三项：生效日期、上级、下级，右侧是重置与查询。
    expect(screen.getByLabelText("按生效日期筛选")).toBeInTheDocument()
    expect(screen.getByLabelText("按上级筛选")).toBeInTheDocument()
    expect(screen.getByLabelText("按下级筛选")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /重\s*置/ })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /查\s*询/ })).toBeInTheDocument()

    // 列表计数行与分页器总数一致（两处都出现同一个总数）。
    expect(screen.getAllByText("共 2 条汇报关系")).toHaveLength(2)
  })

  it("switches to the reporting graph tab and renders the reporting tree", async () => {
    reportingFetchMock([
      relationPayload(),
      relationPayload({
        id: dottedRelationId,
        relation_type: "dotted",
        subordinate_person_id: dottedSubordinateId,
        subordinate_name: "赵虚线",
      }),
    ])

    render(<ReportingWorkspace token="synthetic-token" canAdmin />)

    await screen.findByText("汇报关系", { selector: "h2" })
    const graphTab = screen.getByRole("tab", { name: "关系图" })
    fireEvent.click(graphTab)

    expect(graphTab).toHaveAttribute("aria-selected", "true")
    const tree = await screen.findByRole("tree")
    expect(within(tree).getByText("王经理")).toBeInTheDocument()
    expect(within(tree).getByText("李下属")).toBeInTheDocument()
    expect(within(tree).getByText("直属")).toBeInTheDocument()
    expect(within(tree).getByText("虚线")).toBeInTheDocument()
  })

  it("shows empty states for both the relation list and the graph", async () => {
    reportingFetchMock([])

    render(<ReportingWorkspace token="synthetic-token" canAdmin />)

    expect(await screen.findByText("没有符合条件的汇报关系")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("tab", { name: "关系图" }))
    expect(await screen.findByText("暂无生效的汇报关系")).toBeInTheDocument()
  })

  it("disables write actions for accounts without administration permission", async () => {
    reportingFetchMock([relationPayload()])

    render(<ReportingWorkspace token="synthetic-token" canAdmin={false} />)

    await screen.findByText("汇报关系", { selector: "h2" })
    expect(screen.getByRole("button", { name: "新增关系" })).toBeDisabled()
    expect(await screen.findByRole("button", { name: "结束" })).toBeDisabled()
    expect(screen.getByText("当前账号为只读权限，不能新增或结束汇报关系。")).toBeInTheDocument()
  })

  it("creates a reporting relation from the modal form", async () => {
    const fetchMock = reportingFetchMock()

    render(<ReportingWorkspace token="synthetic-token" canAdmin />)

    await screen.findByText("汇报关系", { selector: "h2" })
    fireEvent.click(screen.getByRole("button", { name: "新增关系" }))

    const dialog = await screen.findByRole("dialog")
    expect(within(dialog).getByText("直属（实线汇报）")).toBeInTheDocument()

    const managerDropdown = await openPersonDropdown(dialog, "上级")
    fireEvent.click(within(managerDropdown).getByText("王经理"))

    const subordinateDropdown = await openPersonDropdown(dialog, "下级")
    fireEvent.click(within(subordinateDropdown).getByText("李下属"))

    fireEvent.click(within(dialog).getByRole("button", { name: /保\s*存/ }))

    await waitFor(() => {
      const postCall = fetchMock.mock.calls.find(([input, init]) => (
        String(input).includes("/reporting-relations") && init?.method === "POST"
      ))
      expect(postCall).toBeDefined()
      expect(JSON.parse(String(postCall?.[1]?.body))).toEqual({
        manager_person_id: managerId,
        subordinate_person_id: subordinateId,
        relation_type: "direct",
        effective_from: today(),
      })
    })
  })

  it("picks people from the workforce persons endpoint with remote search", async () => {
    const fetchMock = reportingFetchMock()

    render(<ReportingWorkspace token="synthetic-token" canAdmin />)

    await screen.findByText("汇报关系", { selector: "h2" })
    fireEvent.click(screen.getByRole("button", { name: "新增关系" }))

    const dialog = await screen.findByRole("dialog")
    const managerInput = await within(dialog).findByLabelText("上级")
    expect(managerInput).toBeInTheDocument()

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/workforce/persons?"),
        expect.any(Object),
      )
    })

    fireEvent.change(managerInput, { target: { value: "李" } })

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("search=%E6%9D%8E"),
        expect.any(Object),
      )
    })
  })
})
