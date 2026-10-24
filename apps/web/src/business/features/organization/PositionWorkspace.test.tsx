// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { positionApi } from "./position-api"
import { PositionWorkspace } from "./PositionWorkspace"


const positionId = "71000000-0000-0000-0000-000000000001"


function positionFixture() {
  return {
    id: positionId,
    code: "JOB_001",
    name: "高级后端工程师",
    level_code: "LEVEL_06",
    grade_code: "GRADE_04",
    class_code: "CLASS_02",
    sequence_code: "SEQ_TECH",
    status: "active",
    effective_from: "2026-01-01",
    effective_to: null,
    version: 3,
    source_job_id: null,
    notes: null,
    attributes: {},
  }
}


function dimensionFixtures() {
  return [
    {
      id: "72000000-0000-0000-0000-000000000001",
      dimension_type: "LEVEL",
      code: "LEVEL_06",
      name: "六级",
      parent_dimension_id: null,
      parent_dimension_type: null,
      parent_dimension_code: null,
      sort_order: 10,
      status: "active",
      effective_from: "2026-01-01",
      effective_to: null,
      version: 1,
      notes: null,
    },
    {
      id: "72000000-0000-0000-0000-000000000002",
      dimension_type: "GRADE",
      code: "GRADE_04",
      name: "四等",
      parent_dimension_id: null,
      parent_dimension_type: null,
      parent_dimension_code: null,
      sort_order: 20,
      status: "active",
      effective_from: "2026-01-01",
      effective_to: null,
      version: 1,
      notes: null,
    },
    {
      id: "72000000-0000-0000-0000-000000000003",
      dimension_type: "CLASS",
      code: "CLASS_02",
      name: "技术职类",
      parent_dimension_id: null,
      parent_dimension_type: null,
      parent_dimension_code: null,
      sort_order: 30,
      status: "active",
      effective_from: "2026-01-01",
      effective_to: null,
      version: 1,
      notes: null,
    },
    {
      id: "72000000-0000-0000-0000-000000000004",
      dimension_type: "SEQUENCE",
      code: "SEQ_TECH",
      name: "技术序列",
      parent_dimension_id: null,
      parent_dimension_type: null,
      parent_dimension_code: null,
      sort_order: 40,
      status: "active",
      effective_from: "2026-01-01",
      effective_to: null,
      version: 1,
      notes: null,
    },
  ]
}


function positionFetchMock(options: { jobs?: unknown[]; dimensions?: unknown[] } = {}) {
  const jobs = options.jobs ?? [positionFixture()]
  const dimensions = options.dimensions ?? dimensionFixtures()
  const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
    const path = String(input)
    if (path.includes("/api/v1/workforce/job-dimensions")) {
      return Response.json({ items: dimensions, total: dimensions.length, limit: 500, offset: 0 })
    }
    if (path.includes("/api/v1/workforce/jobs")) {
      return Response.json({ items: jobs, total: jobs.length, limit: 20, offset: 0 })
    }
    return Response.json({}, { status: 404 })
  })
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}


describe("PositionWorkspace", () => {
  beforeEach(() => vi.restoreAllMocks())

  it("展示后端返回的职位目录并按生效日期重新查询", async () => {
    const fetchMock = positionFetchMock()

    render(<PositionWorkspace token="synthetic-token" canAdmin />)

    expect(await screen.findByRole("heading", { name: "职位管理", level: 2 })).toBeInTheDocument()
    expect(await screen.findByText("JOB_001")).toBeInTheDocument()
    expect(screen.getByText("高级后端工程师")).toBeInTheDocument()
    expect(screen.getByText("LEVEL_06")).toBeInTheDocument()
    expect(screen.getByText("GRADE_04")).toBeInTheDocument()
    expect(screen.getByText("CLASS_02")).toBeInTheDocument()
    expect(screen.getByText("SEQ_TECH")).toBeInTheDocument()
    expect(screen.getByText("2026-01-01 至 长期")).toBeInTheDocument()
    expect(screen.getByText("启用")).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "职位列表" })).toHaveAttribute("aria-selected", "true")
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/^\/api\/v1\/workforce\/jobs\?effective_at=\d{4}-\d{2}-\d{2}&limit=20&offset=0$/),
      expect.any(Object),
    )

    fireEvent.change(screen.getByLabelText("生效日期"), { target: { value: "2027-01-01" } })

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("effective_at=2027-01-01"),
        expect.any(Object),
      )
    })

    fireEvent.change(screen.getByLabelText("搜索职位或职务维度"), { target: { value: "不存在" } })

    expect(await screen.findByText("没有符合条件的职位")).toBeInTheDocument()
  })

  it("职位为空时展示空态而不是残留数据", async () => {
    positionFetchMock({ jobs: [] })

    render(<PositionWorkspace token="synthetic-token" canAdmin />)

    await waitFor(() => {
      expect(document.querySelector("[aria-busy='true']")).toBeNull()
    })
    expect(await screen.findByText("没有符合条件的职位")).toBeInTheDocument()
    expect(screen.queryByText("JOB_001")).toBeNull()
  })

  it("没有职务体系维护权限时禁用全部写操作", async () => {
    positionFetchMock()

    render(<PositionWorkspace token="synthetic-token" canAdmin={false} />)

    await screen.findByText("JOB_001")
    expect(screen.getByRole("button", { name: "新建职位" })).toBeDisabled()
    const versionButtons = screen.getAllByRole("button", { name: "新增版本" })
    expect(versionButtons.length).toBeGreaterThan(0)
    for (const button of versionButtons) expect(button).toBeDisabled()
  })

  it("切换到职务维度页签展示四类职务维度", async () => {
    positionFetchMock()

    render(<PositionWorkspace token="synthetic-token" canAdmin />)

    fireEvent.click(screen.getByRole("tab", { name: "职务维度" }))

    const panel = await screen.findByRole("tabpanel", { name: "职务维度" })
    expect(within(panel).getByRole("columnheader", { name: "维度代码" })).toBeInTheDocument()
    expect(within(panel).getByText("六级")).toBeInTheDocument()
    expect(within(panel).getByText("技术职类")).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "职务维度" })).toHaveAttribute("aria-selected", "true")
    expect(within(panel).getByText("职级")).toBeInTheDocument()
  })

  it("新建职位表单按后端必填项呈现字段", async () => {
    positionFetchMock()

    render(<PositionWorkspace token="synthetic-token" canAdmin />)

    await screen.findByText("JOB_001")
    fireEvent.click(screen.getByRole("button", { name: "新建职位" }))

    const dialog = await screen.findByRole("dialog", { name: "新建职位" })
    expect(within(dialog).getByLabelText("职位编码")).toBeInTheDocument()
    expect(within(dialog).getByLabelText("职位名称")).toBeInTheDocument()
    expect(within(dialog).getByLabelText("职级")).toBeInTheDocument()
    expect(within(dialog).getByLabelText("职等")).toBeInTheDocument()
    expect(within(dialog).getByLabelText("职类")).toBeInTheDocument()
    expect(within(dialog).getByLabelText("序列")).toBeInTheDocument()
    expect(within(dialog).getByLabelText("生效日期")).toBeInTheDocument()
    expect(within(dialog).getByLabelText("变更原因")).toBeInTheDocument()
  })

  it("按画板把指标条放在页签之上、筛选区放在页签内容之内并展开十列表头", async () => {
    positionFetchMock()

    render(<PositionWorkspace token="synthetic-token" canAdmin />)

    await screen.findByText("JOB_001")

    // 指标条位于页签之前，数值在上、标签在下。
    const metrics = document.querySelector(".metric-strip")
    expect(metrics).not.toBeNull()
    expect(metrics?.querySelector(".metric-value")?.textContent).toBe("1")
    for (const label of ["有效职位", "职级", "职等", "职类", "序列"]) {
      expect(metrics?.textContent).toContain(label)
    }
    expect(metrics?.nextElementSibling?.querySelector('[role="tablist"]')).not.toBeNull()

    // 筛选区在「职位列表」页签内容之内。
    const panel = screen.getByRole("tabpanel", { name: "职位列表" })
    expect(within(panel).getByLabelText("生效日期")).toBeInTheDocument()
    expect(within(panel).getByLabelText("搜索职位或职务维度")).toBeInTheDocument()
    expect(within(panel).getByRole("button", { name: /重\s*置/ })).toBeInTheDocument()

    // 列表计数行与分页器共用同一口径（两处都出现同一个总数）。
    expect(within(panel).getAllByText("共 1 个职位")).toHaveLength(2)

    const table = within(panel).getByRole("table")
    for (const header of ["职位编码", "职位名称", "职级", "职等", "职类", "序列", "生效日期", "版本", "状态", "操作"]) {
      expect(within(table).getByRole("columnheader", { name: header })).toBeInTheDocument()
    }
    expect(within(table).getByText("启用")).toHaveClass("ant-tag")
  })

  it("按后端契约提交职位创建与版本请求", async () => {
    const fetchMock = positionFetchMock()

    await positionApi.createPosition("synthetic-token", {
      code: "JOB_002",
      name: "前端工程师",
      level_code: "LEVEL_05",
      grade_code: "GRADE_03",
      class_code: "CLASS_01",
      sequence_code: "SEQ_TECH",
      status: "active",
      effective_from: "2026-01-01",
      attributes: {},
      change_reason: "新增职位",
    })
    await positionApi.createPositionVersion("synthetic-token", positionId, {
      name: "高级后端工程师",
      level_code: "LEVEL_07",
      grade_code: "GRADE_05",
      class_code: "CLASS_02",
      sequence_code: "SEQ_TECH",
      status: "active",
      effective_from: "2027-01-01",
      change_reason: "晋升职级",
    })

    const [createUrl, createInit] = fetchMock.mock.calls[0]
    expect(String(createUrl)).toBe("/api/v1/workforce/jobs")
    expect((createInit as RequestInit).method).toBe("POST")
    expect(JSON.parse(String((createInit as RequestInit).body))).toEqual({
      code: "JOB_002",
      name: "前端工程师",
      level_code: "LEVEL_05",
      grade_code: "GRADE_03",
      class_code: "CLASS_01",
      sequence_code: "SEQ_TECH",
      status: "active",
      effective_from: "2026-01-01",
      attributes: {},
      change_reason: "新增职位",
    })

    const [versionUrl, versionInit] = fetchMock.mock.calls[1]
    expect(String(versionUrl)).toBe(`/api/v1/workforce/jobs/${positionId}/versions`)
    expect((versionInit as RequestInit).method).toBe("POST")
    expect(JSON.parse(String((versionInit as RequestInit).body))).toMatchObject({
      effective_from: "2027-01-01",
      change_reason: "晋升职级",
    })
  })
})
