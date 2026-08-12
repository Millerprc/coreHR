import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { AccountWorkspace } from "./AccountWorkspace"


const currentUser = {
  id: "10000000-0000-0000-0000-000000000001",
  username: "synthetic-admin",
  display_name: "合成主管理员",
  status: "active" as const,
  person_id: null,
  roles: ["SYSTEM_ADMIN"],
}


describe("AccountWorkspace", () => {
  beforeEach(() => vi.restoreAllMocks())
  afterEach(() => vi.unstubAllGlobals())

  it("creates an SSC account without exposing its initial password", async () => {
    let accounts = [currentUser]
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      if (path.endsWith("/api/v1/platform/roles")) {
        return Response.json({
          items: [
            {
              id: "20000000-0000-0000-0000-000000000001",
              code: "SYSTEM_ADMIN",
              name: "主管理员",
              description: null,
              is_system: true,
              is_active: true,
            },
            {
              id: "20000000-0000-0000-0000-000000000002",
              code: "SSC_ADMIN",
              name: "SSC管理员",
              description: null,
              is_system: true,
              is_active: true,
            },
          ],
        })
      }
      if (path.endsWith("/api/v1/platform/users") && init?.method === "POST") {
        const body = JSON.parse(String(init.body)) as {
          username: string
          display_name: string
          role_codes: string[]
        }
        const created = {
          id: "10000000-0000-0000-0000-000000000002",
          username: body.username,
          display_name: body.display_name,
          status: "active" as const,
          person_id: null,
          roles: body.role_codes,
        }
        accounts = [...accounts, created]
        return Response.json(created, { status: 201 })
      }
      if (path.includes("/api/v1/platform/users?")) {
        return Response.json({ items: accounts, total: accounts.length, limit: 200, offset: 0 })
      }
      return Response.json({}, { status: 404 })
    })
    vi.stubGlobal("fetch", fetchMock)

    render(
      <AccountWorkspace
        token="synthetic-token"
        currentUserId={currentUser.id}
      />,
    )

    expect(await screen.findByText("synthetic-admin")).toBeInTheDocument()
    const currentUserDeactivate = screen.getByRole("button", { name: "停用" })
    expect(currentUserDeactivate).toBeDisabled()

    fireEvent.click(screen.getByRole("button", { name: "新建账号" }))
    const dialog = await screen.findByRole("dialog", { name: "新建账号" })
    fireEvent.change(within(dialog).getByLabelText("登录账号"), {
      target: { value: "ssc.synthetic" },
    })
    const password = within(dialog).getByLabelText("初始密码")
    expect(password).toHaveAttribute("type", "password")
    fireEvent.change(password, { target: { value: "synthetic-password-123" } })
    fireEvent.change(within(dialog).getByLabelText("显示名称"), {
      target: { value: "合成SSC管理员" },
    })
    fireEvent.change(within(dialog).getByLabelText("操作原因"), {
      target: { value: "创建合成SSC账号" },
    })
    fireEvent.click(within(dialog).getByRole("button", { name: /保\s*存/ }))

    expect(await screen.findByText("ssc.synthetic")).toBeInTheDocument()
    expect(screen.queryByDisplayValue("synthetic-password-123")).not.toBeInTheDocument()
    const createCall = fetchMock.mock.calls.find(([input, init]) => (
      String(input).endsWith("/api/v1/platform/users") && init?.method === "POST"
    ))
    const body = JSON.parse(String(createCall?.[1]?.body)) as Record<string, unknown>
    expect(body).toMatchObject({
      username: "ssc.synthetic",
      display_name: "合成SSC管理员",
      password: "synthetic-password-123",
      role_codes: ["SSC_ADMIN"],
      reason: "创建合成SSC账号",
    })
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5))
  })
})
