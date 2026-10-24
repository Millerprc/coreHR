// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { fireEvent, render, screen, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { AppShell } from "./AppShell"
import type { UserProfile } from "./types"


const administrator: UserProfile = {
  id: "10000000-0000-0000-0000-000000000001",
  username: "admin.synthetic",
  display_name: "合成管理员",
  status: "active",
  roles: ["SYSTEM_ADMIN"],
  permissions: [
    "CONFIGURATION_VIEW",
    "CONFIGURATION_ADMIN",
    "ORGANIZATION_VIEW",
    "ORGANIZATION_ADMIN",
  ],
}


describe("AppShell navigation", () => {
  beforeEach(() => {
    window.location.hash = "#dashboard"
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        if (path.includes("/configuration/dictionaries")) {
          return new Response(
            JSON.stringify({ items: [], total: 0, limit: 50, offset: 0 }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          )
        }
        if (path.includes("/organizations/tree")) {
          return new Response(JSON.stringify([]), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          })
        }
        if (path.includes("/organization-types")) {
          return new Response(JSON.stringify([]), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          })
        }
        return new Response(JSON.stringify({ items: [], total: 0 }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      }),
    )
  })

  it("opens department management from the organization management group", async () => {
    render(
      <AppShell
        token="synthetic-token"
        user={administrator}
        onSignedOut={() => undefined}
      />,
    )

    expect(screen.getByRole("menuitem", { name: "组织管理" })).toBeInTheDocument()
    fireEvent.click(screen.getByRole("menuitem", { name: "部门管理" }))

    expect(
      await screen.findByRole("heading", { name: "部门管理" }),
    ).toBeInTheDocument()
    expect(screen.getByText("组织管理", { selector: ".business-breadcrumb-group" })).toBeInTheDocument()
    expect(window.location.hash).toBe("#organization")
  })

  it("opens basic data from the organization management group and keeps location in the hash", async () => {
    render(
      <AppShell
        token="synthetic-token"
        user={administrator}
        onSignedOut={() => undefined}
      />,
    )

    fireEvent.click(screen.getByRole("menuitem", { name: "基础资料" }))

    expect(
      await screen.findByRole("heading", { name: "基础资料" }),
    ).toBeInTheDocument()
    expect(window.location.hash).toBe("#configuration")
  })

  it("treats the administrator wildcard as access to every available workspace", async () => {
    render(
      <AppShell
        token="synthetic-token"
        user={{ ...administrator, permissions: ["*"] }}
        onSignedOut={() => undefined}
      />,
    )

    fireEvent.click(screen.getByRole("menuitem", { name: "人员中心" }))

    expect(await screen.findByRole("heading", { name: "人员中心" })).toBeInTheDocument()
    expect(window.location.hash).toBe("#people")
  })

  // Requirement: D-108 — 未授权时被锁模块仍然可见：菜单保留入口 + 锁标，
  // 进入后显示授权说明面板而不是空白页或假表单。
  it("keeps license managed workspaces visible with a lock marker and an explanation panel", async () => {
    render(
      <AppShell
        token="synthetic-token"
        user={{ ...administrator, permissions: ["*"] }}
        onSignedOut={() => undefined}
      />,
    )

    expect(await screen.findByText("未授权 · 只读演示")).toBeInTheDocument()

    const attendanceItem = screen.getByRole("menuitem", { name: /考勤管理/ })
    expect(attendanceItem).toBeInTheDocument()
    const lockMarker = within(attendanceItem).getByRole("img", { name: "需要授权" })
    expect(lockMarker).toBeInTheDocument()

    // 锁标悬停给出「需要 XX 模块授权」指引。
    fireEvent.mouseEnter(lockMarker)
    expect((await screen.findAllByText("需要 考勤管理 模块授权")).length).toBeGreaterThan(0)
    fireEvent.mouseLeave(lockMarker)

    fireEvent.click(attendanceItem)

    // 进入被锁模块后显示授权说明面板，不出现假表单。
    expect(
      await screen.findByText("需要 考勤管理 模块授权", { selector: ".ant-result-title" }),
    ).toBeInTheDocument()
    expect(screen.getByText("前往授权管理")).toBeInTheDocument()
  })
})
