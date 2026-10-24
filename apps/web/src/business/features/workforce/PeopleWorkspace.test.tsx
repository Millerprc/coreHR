// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { PeopleWorkspace } from "./PeopleWorkspace"


const personId = "60000000-0000-0000-0000-000000000001"
const today = new Date().toISOString().slice(0, 10)


interface RecordedCall {
  readonly url: string
  readonly method: string
  readonly body: Record<string, unknown> | undefined
}


const basePerson = {
  id: personId,
  employee_number: "990001",
  legal_name: "合成人员",
  display_name: "合成人员",
  former_name: null,
  gender_code: null,
  birth_date: null,
  ethnicity_code: null,
  nationality_code: null,
  country_code: "CN",
  marital_status_code: null,
  political_status_code: null,
  status: "active",
}


function archivePayload(corrections: unknown[] = []): Record<string, unknown> {
  return {
    person: { ...basePerson },
    registered_person: { ...basePerson },
    employments: [{
      id: "61000000-0000-0000-0000-000000000001",
      person_id: personId,
      employee_type_code: "REGULAR",
      status: "pending_start",
      planned_start_date: "2026-08-10",
      actual_start_date: null,
      probation_end_date: null,
      end_date: null,
      contract_legal_entity_id: null,
      payroll_legal_entity_id: null,
      social_insurance_legal_entity_id: null,
      tax_legal_entity_id: null,
      version: 1,
    }],
    legal_entity_relations: [],
    assignments: [],
    agreements: [],
    corrections,
    effective_at: today,
  }
}


const correctionRecord = {
  id: "62000000-0000-0000-0000-000000000001",
  person_id: personId,
  field_code: "gender_code",
  effective_from: "2026-08-01",
  effective_to: null,
  version: 1,
  new_value: "F",
  change_reason: "补录历史性别代码",
  created_by: "63000000-0000-0000-0000-000000000001",
  created_by_name: "合成管理员",
  created_at: "2026-08-01T02:00:00+00:00",
  updated_at: "2026-08-01T02:00:00+00:00",
}


function stubWorkspaceFetch(calls: RecordedCall[]): void {
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    const method = init?.method ?? "GET"
    calls.push({
      url,
      method,
      body: init?.body ? JSON.parse(String(init.body)) as Record<string, unknown> : undefined,
    })
    if (url.endsWith(`/workforce/persons/${personId}/corrections`) && method === "POST") {
      return Response.json(correctionRecord, { status: 201 })
    }
    if (url.endsWith(`/workforce/persons/${personId}`) && method === "PATCH") {
      return Response.json({ ...basePerson, gender_code: "F" })
    }
    if (url.endsWith(`/workforce/persons/${personId}`)) {
      return Response.json(archivePayload([correctionRecord]))
    }
    if (url.includes("/workforce/persons?")) {
      return Response.json({ items: [{ ...basePerson }], total: 1, limit: 200, offset: 0 })
    }
    if (url.includes("/workforce/legal-entities") || url.includes("/workforce/jobs")) {
      return Response.json({ items: [], total: 0, limit: 200, offset: 0 })
    }
    if (url.endsWith("/organizations/tree")) return Response.json([])
    return Response.json({}, { status: 404 })
  }))
}


async function openArchive(): Promise<void> {
  render(<PeopleWorkspace token="synthetic-token" canAdmin />)
  expect(await screen.findByText("990001")).toBeInTheDocument()
  fireEvent.click(screen.getByRole("button", { name: "查看档案" }))
  expect(await screen.findByText("合成人员 · 990001")).toBeInTheDocument()
}


describe("PeopleWorkspace", () => {
  beforeEach(() => vi.restoreAllMocks())

  it("opens one synthetic person's complete archive", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      if (path.endsWith(`/workforce/persons/${personId}`)) {
        return Response.json(archivePayload())
      }
      if (path.includes("/workforce/persons?")) {
        return Response.json({ items: [{ ...basePerson }], total: 1, limit: 200, offset: 0 })
      }
      if (path.includes("/workforce/legal-entities") || path.includes("/workforce/jobs")) {
        return Response.json({ items: [], total: 0, limit: 200, offset: 0 })
      }
      if (path.endsWith("/organizations/tree")) return Response.json([])
      return Response.json({}, { status: 404 })
    }))

    await openArchive()

    expect(screen.getByText("员工档案 · 人员中心")).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "劳动关系 1" })).toBeInTheDocument()
  })

  it("按画板呈现人员列表的七列与筛选栏", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      if (path.includes("/workforce/persons?")) {
        return Response.json({ items: [{ ...basePerson }], total: 1, limit: 200, offset: 0 })
      }
      if (path.includes("/workforce/legal-entities") || path.includes("/workforce/jobs")) {
        return Response.json({ items: [], total: 0, limit: 200, offset: 0 })
      }
      if (path.endsWith("/organizations/tree")) return Response.json([])
      return Response.json({}, { status: 404 })
    }))

    render(<PeopleWorkspace token="synthetic-token" canAdmin />)

    await screen.findByText("990001")
    const table = await screen.findByRole("table")
    for (const header of ["姓名", "工号", "主组织", "职位", "在职状态", "入职日期", "操作"]) {
      expect(within(table).getByRole("columnheader", { name: header })).toBeInTheDocument()
    }
    expect(within(table).getByText("在职")).toBeInTheDocument()
    // 筛选栏按画板给出姓名或工号、在职状态与查询/重置。
    expect(screen.getByLabelText("搜索姓名或工号")).toBeInTheDocument()
    expect(screen.getByLabelText("在职状态")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /重\s*置/ })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /查\s*询/ })).toBeInTheDocument()
  })

  // Requirement: D-095 — 抽屉头把「更正基础信息」拆成【编辑】与【修正】两个入口。
  it("抽屉头提供编辑与修正两个入口", async () => {
    const calls: RecordedCall[] = []
    stubWorkspaceFetch(calls)

    await openArchive()

    expect(screen.getByRole("button", { name: /编\s*辑/ })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /修\s*正/ })).toBeInTheDocument()
    expect(screen.queryByText("更正基础信息")).not.toBeInTheDocument()
  })

  // Requirement: D-095 — 编辑态只提交用户实际改动的字段。
  it("编辑态只提交改动过的字段", async () => {
    const calls: RecordedCall[] = []
    stubWorkspaceFetch(calls)

    await openArchive()
    fireEvent.click(screen.getByRole("button", { name: /编\s*辑/ }))

    expect(await screen.findByText("员工档案 · 编辑基础信息")).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText("性别代码"), { target: { value: "F" } })
    fireEvent.change(screen.getByLabelText("变更原因"), { target: { value: "补录性别代码" } })
    fireEvent.click(screen.getByRole("button", { name: /保\s*存/ }))

    await waitFor(() => {
      const patch = calls.find((call) => call.method === "PATCH")
      expect(patch).toBeDefined()
      expect(patch?.body).toEqual({ gender_code: "F", change_reason: "补录性别代码" })
    })
  })

  // Requirement: D-095 — 修正态要求生效日期，提交后不写主档。
  it("修正态要求待修正字段与生效日期并提交修正记录", async () => {
    const calls: RecordedCall[] = []
    stubWorkspaceFetch(calls)

    await openArchive()
    fireEvent.click(screen.getByRole("button", { name: /修\s*正/ }))

    expect(await screen.findByText("员工档案 · 修正基础信息")).toBeInTheDocument()
    expect(screen.getByLabelText("待修正字段")).toBeInTheDocument()
    expect(screen.getByLabelText("修正后值")).toBeInTheDocument()
    expect(screen.getByLabelText("生效日期")).toBeInTheDocument()
    expect(screen.getByLabelText("修正原因")).toBeInTheDocument()

    // 选了字段之后给出「登记值 / 当前生效值」对照。
    // AntD 的下拉同时渲染只读镜像列表与可见列表，这里取最近打开的下拉容器。
    fireEvent.mouseDown(screen.getByRole("combobox", { name: "待修正字段" }))
    const listboxes = await screen.findAllByRole("listbox")
    const dropdown = listboxes[listboxes.length - 1].closest(".ant-select-dropdown")
    if (!dropdown) throw new Error("待修正字段下拉未打开")
    fireEvent.click(within(dropdown as HTMLElement).getByTitle("性别代码"))
    expect(await screen.findByText("登记值")).toBeInTheDocument()
    expect(screen.getByText("当前生效值")).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText("修正后值"), { target: { value: "F" } })
    fireEvent.change(screen.getByLabelText("修正原因"), { target: { value: "补录历史性别代码" } })
    fireEvent.click(screen.getByRole("button", { name: /提\s*交\s*修\s*正/ }))

    await waitFor(() => {
      const posted = calls.find((call) => call.method === "POST")
      expect(posted).toBeDefined()
      expect(posted?.url).toContain(`/workforce/persons/${personId}/corrections`)
      expect(posted?.body).toEqual({
        field_code: "gender_code",
        new_value: "F",
        effective_from: today,
        change_reason: "补录历史性别代码",
      })
    })
  })

  // Requirement: D-095 — 修正记录是只读清单，登记在抽屉的独立 Tab。
  it("修正记录 Tab 列出该员工的修正记录", async () => {
    const calls: RecordedCall[] = []
    stubWorkspaceFetch(calls)

    await openArchive()

    fireEvent.click(screen.getByRole("tab", { name: "修正记录 1" }))
    // 抽屉里还有人员列表表，修正记录表按 tabpanel 定位。
    const panel = await screen.findByRole("tabpanel")
    const correctionTable = within(panel).getByRole("table")
    for (const header of ["字段", "修正后值", "生效日期", "原因", "记录时间"]) {
      expect(within(correctionTable).getByRole("columnheader", { name: header })).toBeInTheDocument()
    }
    expect(within(correctionTable).getByText("性别代码")).toBeInTheDocument()
    expect(within(correctionTable).getByText("F")).toBeInTheDocument()
    expect(within(correctionTable).getByText("2026-08-01")).toBeInTheDocument()
    expect(within(correctionTable).getByText("补录历史性别代码")).toBeInTheDocument()
  })
})
