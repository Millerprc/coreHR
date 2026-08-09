import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { DictionaryWorkspace } from "./DictionaryWorkspace"


const dictionary = {
  id: "20000000-0000-0000-0000-000000000001",
  code: "EMPLOYEE_TYPE",
  name: "人员类型",
  english_name: null,
  description: null,
  source: "manual",
  is_active: true,
}


describe("DictionaryWorkspace", () => {
  beforeEach(() => vi.restoreAllMocks())

  it("loads a dictionary tree and creates a synthetic dictionary item", async () => {
    let items = [
      {
        id: "21000000-0000-0000-0000-000000000001",
        dictionary_id: dictionary.id,
        parent_item_id: null,
        code: "REGULAR",
        name: "正式员工",
        english_name: null,
        sort_order: 0,
        level: 0,
        description: null,
        is_active: true,
      },
    ]
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      if (path.endsWith("/configuration/dictionaries?limit=200&offset=0")) {
        return Response.json({ items: [dictionary], total: 1, limit: 200, offset: 0 })
      }
      if (path.endsWith(`/configuration/dictionaries/${dictionary.id}/items`) && init?.method === "POST") {
        const body = JSON.parse(String(init.body)) as { code: string; name: string }
        const created = {
          ...items[0],
          id: "21000000-0000-0000-0000-000000000002",
          code: body.code,
          name: body.name,
          sort_order: 1,
        }
        items = [...items, created]
        return Response.json(created, { status: 201 })
      }
      if (path.endsWith(`/configuration/dictionaries/${dictionary.id}/items`)) {
        return Response.json({ items, total: items.length })
      }
      return Response.json({}, { status: 404 })
    })
    vi.stubGlobal("fetch", fetchMock)

    render(<DictionaryWorkspace token="synthetic-token" canAdmin />)

    expect(await screen.findByText("正式员工")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "新建字典项" }))
    fireEvent.change(screen.getByLabelText("代码"), { target: { value: "CAMPUS" } })
    fireEvent.change(screen.getByLabelText("中文名称"), { target: { value: "校招生" } })
    fireEvent.click(screen.getByRole("button", { name: "保存" }))

    expect(await screen.findByText("校招生")).toBeInTheDocument()
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        `/api/v1/configuration/dictionaries/${dictionary.id}/items`,
        expect.objectContaining({ method: "POST" }),
      )
    })
  })

  it("shows a permission-specific state for a denied viewer", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json(
        { code: "PERMISSION_DENIED", message: "没有配置查看权限" },
        { status: 403 },
      )),
    )

    render(<DictionaryWorkspace token="restricted-token" canAdmin={false} />)

    expect(await screen.findByText("无权查看配置中心")).toBeInTheDocument()
  })
})
