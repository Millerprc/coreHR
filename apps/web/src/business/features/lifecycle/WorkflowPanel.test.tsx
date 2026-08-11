import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { WorkflowPanel } from "./WorkflowPanel"


const emptyPage = { items: [], total: 0, limit: 200, offset: 0 }


describe("WorkflowPanel", () => {
  beforeEach(() => vi.restoreAllMocks())

  it("shows a non-technical condition route builder", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json(emptyPage)))
    render(<WorkflowPanel token="synthetic-token" canAdmin />)

    fireEvent.click(await screen.findByRole("button", { name: "新建流程模板" }))
    const dialog = await screen.findByRole("dialog", { name: "新建审批流程模板" })
    fireEvent.click(within(dialog).getByLabelText("按条件分流"))

    await waitFor(() => expect(within(dialog).getByLabelText("判断字段")).toBeInTheDocument())
    expect(within(dialog).getByLabelText("符合条件时的办理角色")).toBeInTheDocument()
    expect(within(dialog).getByLabelText("不符合条件时的办理角色")).toBeInTheDocument()
    expect(within(dialog).getByText(/无需.*JSON|读取发起流程时提交的业务数据/)).toBeInTheDocument()
  })
})
