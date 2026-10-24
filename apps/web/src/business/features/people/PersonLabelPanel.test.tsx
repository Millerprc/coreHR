// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { PersonLabelPanel } from "./PersonLabelPanel"


const personId = "61000000-0000-0000-0000-000000000001"
const manualLabelId = "62000000-0000-0000-0000-000000000001"
const aiLabelId = "62000000-0000-0000-0000-000000000002"


function labelWire(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: manualLabelId,
    person_id: personId,
    label_name: "核心人才",
    label_type: "TALENT",
    source: "MANUAL",
    effective_from: "2026-01-01",
    effective_to: null,
    status: "active",
    is_ai_generated: false,
    ...overrides,
  }
}


const libraryWire = [
  {
    type_code: "TECH_SKILL",
    type_name: "技术技能",
    items: [
      { code: "PY_LANG", name: "Python" },
      { code: "GO_LANG", name: "Go" },
    ],
  },
]


interface StubOptions {
  readonly labels?: readonly Record<string, unknown>[]
  readonly types?: readonly Record<string, unknown>[]
  readonly library?: readonly Record<string, unknown>[]
  readonly onBatchPost?: (body: string) => void
  readonly onDelete?: (path: string) => void
}


function stubFetch(options: StubOptions) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    const method = init?.method ?? "GET"
    if (method === "POST" && path.endsWith(`/workforce/persons/${personId}/labels/batch`)) {
      options.onBatchPost?.(String(init?.body ?? ""))
      return Response.json({ created: [labelWire()] }, { status: 201 })
    }
    if (method === "DELETE" && path.includes("/workforce/person-labels/")) {
      options.onDelete?.(path)
      return new Response(null, { status: 204 })
    }
    if (path.endsWith(`/workforce/persons/${personId}/labels`)) {
      const items = options.labels ?? []
      return Response.json({ items, total: items.length })
    }
    if (path.endsWith("/workforce/label-types")) {
      return Response.json({ items: options.types ?? [] })
    }
    if (path.endsWith("/workforce/label-library")) {
      return Response.json({ items: options.library ?? [] })
    }
    return Response.json({})
  })
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}


describe("PersonLabelPanel", () => {
  beforeEach(() => vi.restoreAllMocks())
  afterEach(() => vi.unstubAllGlobals())

  it("按标签类型分组展示标签并显示类型名称", async () => {
    stubFetch({
      labels: [labelWire(), labelWire({ id: aiLabelId, label_name: "高潜人才" })],
      types: [{ code: "TALENT", name: "人才发展", count: 2 }],
      library: libraryWire,
    })

    render(<PersonLabelPanel token="synthetic-token" canAdmin personId={personId} />)

    expect(await screen.findByText("核心人才")).toBeInTheDocument()
    expect(screen.getByText("高潜人才")).toBeInTheDocument()
    expect(screen.getByText("人才发展")).toBeInTheDocument()
    expect(screen.getByText("共 2 个标签")).toBeInTheDocument()
  })

  it("标签类型名称取不到时退回显示编码", async () => {
    stubFetch({ labels: [labelWire()], types: [], library: libraryWire })

    render(<PersonLabelPanel token="synthetic-token" canAdmin personId={personId} />)

    expect(await screen.findByText("核心人才")).toBeInTheDocument()
    expect(screen.getByText("TALENT")).toBeInTheDocument()
  })

  it("区分 AI 生成标签与人工标签", async () => {
    stubFetch({
      labels: [
        labelWire(),
        labelWire({ id: aiLabelId, label_name: "高潜人才", source: "AI", is_ai_generated: true }),
      ],
      types: [{ code: "TALENT", name: "人才发展", count: 2 }],
      library: libraryWire,
    })

    render(<PersonLabelPanel token="synthetic-token" canAdmin personId={personId} />)

    expect(await screen.findByText("🤖 高潜人才")).toBeInTheDocument()
    expect(screen.getByText("核心人才")).toBeInTheDocument()
    expect(screen.getByText("AI 生成")).toBeInTheDocument()
    expect(screen.getByText("人工标记")).toBeInTheDocument()
  })

  it("展示标签有效期并标记当前有效", async () => {
    stubFetch({
      labels: [
        labelWire(),
        labelWire({ id: aiLabelId, label_name: "历史标签", effective_to: "2026-06-30" }),
      ],
      types: [{ code: "TALENT", name: "人才发展", count: 2 }],
      library: libraryWire,
    })

    render(<PersonLabelPanel token="synthetic-token" canAdmin personId={personId} />)

    expect(await screen.findByText("2026-01-01 起")).toBeInTheDocument()
    expect(screen.getByText("当前有效")).toBeInTheDocument()
    expect(screen.getByText("2026-01-01 至 2026-06-30")).toBeInTheDocument()
    expect(screen.getByText("已结束")).toBeInTheDocument()
  })

  it("按画板把标签渲染为上行标签、下行来源与有效性的两行结构", async () => {
    stubFetch({
      labels: [
        labelWire(),
        labelWire({ id: aiLabelId, label_name: "高潜人才", source: "AI", is_ai_generated: true }),
      ],
      types: [{ code: "TALENT", name: "人才发展", count: 2 }],
      library: libraryWire,
    })

    render(<PersonLabelPanel token="synthetic-token" canAdmin personId={personId} />)

    const tag = await screen.findByText("核心人才")
    expect(tag).toHaveClass("ant-tag")
    expect(tag).toHaveClass("ant-tag-outlined")
    const item = tag.closest(".label-item")
    expect(item).not.toBeNull()
    const meta = item?.querySelector(".label-item-meta")?.textContent ?? ""
    expect(meta).toContain("人工标记")
    expect(meta).toContain("当前有效")
    expect(meta).toContain("结束")

    const aiTag = screen.getByText("🤖 高潜人才")
    expect(aiTag).toHaveClass("ant-tag")
    expect(aiTag.closest(".label-item")?.querySelector(".label-item-meta")?.textContent).toContain("AI 生成")

    // 工具条左侧是标签总数，右侧是新增标签主按钮。
    expect(screen.getByText("共 2 个标签")).toBeInTheDocument()
  })

  it("没有标签时展示空态", async () => {
    stubFetch({ labels: [], types: [], library: libraryWire })

    render(<PersonLabelPanel token="synthetic-token" canAdmin personId={personId} />)

    expect(await screen.findByText("暂无标签")).toBeInTheDocument()
  })

  it("标签加载失败时展示错误原因且不显示空态", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      if (path.endsWith(`/workforce/persons/${personId}/labels`)) {
        return Response.json({ code: "FORBIDDEN", message: "无权读取员工标签" }, { status: 403 })
      }
      return Response.json({ items: [] })
    })
    vi.stubGlobal("fetch", fetchMock)

    render(<PersonLabelPanel token="synthetic-token" canAdmin personId={personId} />)

    expect(await screen.findByText("无权读取员工标签")).toBeInTheDocument()
    expect(screen.queryByText("暂无标签")).not.toBeInTheDocument()
  })

  it("已结束的标签不再提供结束操作", async () => {
    stubFetch({
      labels: [labelWire({ effective_to: "2026-06-30" })],
      types: [{ code: "TALENT", name: "人才发展", count: 1 }],
      library: libraryWire,
    })

    render(<PersonLabelPanel token="synthetic-token" canAdmin personId={personId} />)

    expect(await screen.findByText("核心人才")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "结束" })).not.toBeInTheDocument()
  })

  it("没有管理权限时禁用写操作", async () => {
    stubFetch({
      labels: [labelWire()],
      types: [{ code: "TALENT", name: "人才发展", count: 1 }],
      library: libraryWire,
    })

    render(<PersonLabelPanel token="synthetic-token" canAdmin={false} personId={personId} />)

    await screen.findByText("核心人才")
    expect(screen.getByRole("button", { name: "新增标签" })).toBeDisabled()
    expect(screen.getByRole("button", { name: "结束" })).toBeDisabled()
  })

  it("标签类型选项来自标签类型接口而不是写死", async () => {
    stubFetch({
      labels: [],
      types: [{ code: "TECH_SKILL", name: "技术技能", count: 2 }],
      library: libraryWire,
    })

    render(<PersonLabelPanel token="synthetic-token" canAdmin personId={personId} />)

    fireEvent.click(await screen.findByRole("button", { name: "新增标签" }))
    fireEvent.mouseDown(screen.getByLabelText("标签类型"))

    expect(await screen.findByText("技术技能（TECH_SKILL）")).toBeInTheDocument()
    expect(screen.queryByText("人才发展")).not.toBeInTheDocument()
  })

  it("多选标签后一次发出批量打标签请求", async () => {
    const posted: string[] = []
    stubFetch({
      labels: [],
      types: [{ code: "TECH_SKILL", name: "技术技能", count: 2 }],
      library: libraryWire,
      onBatchPost: (body) => posted.push(body),
    })

    render(<PersonLabelPanel token="synthetic-token" canAdmin personId={personId} />)

    fireEvent.click(await screen.findByRole("button", { name: "新增标签" }))
    fireEvent.mouseDown(screen.getByLabelText("标签"))
    fireEvent.click(await screen.findByText("Python"))
    fireEvent.click(await screen.findByText("Go"))
    fireEvent.change(screen.getByLabelText("生效日期"), { target: { value: "2026-10-24" } })
    fireEvent.click(screen.getByRole("button", { name: /保\s*存/ }))

    await waitFor(() => expect(posted).toHaveLength(1))
    expect(JSON.parse(posted[0])).toEqual({
      effective_from: "2026-10-24",
      source: "MANUAL",
      labels: [
        { label_type_code: "TECH_SKILL", label_code: "PY_LANG" },
        { label_type_code: "TECH_SKILL", label_code: "GO_LANG" },
      ],
    })
  })

  it("二次确认后结束标签", async () => {
    const deleted: string[] = []
    stubFetch({
      labels: [labelWire()],
      types: [{ code: "TALENT", name: "人才发展", count: 1 }],
      library: libraryWire,
      onDelete: (path) => deleted.push(path),
    })

    render(<PersonLabelPanel token="synthetic-token" canAdmin personId={personId} />)

    await screen.findByText("核心人才")
    fireEvent.click(screen.getByRole("button", { name: "结束" }))
    fireEvent.click(await screen.findByRole("button", { name: "确认结束" }))

    await waitFor(() => expect(deleted).toEqual([`/api/v1/workforce/person-labels/${manualLabelId}`]))
  })
})
