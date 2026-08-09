import { fireEvent, render, screen } from "@testing-library/react"
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

  it("opens the organization workspace from the administrator menu", async () => {
    render(
      <AppShell
        token="synthetic-token"
        user={administrator}
        onSignedOut={() => undefined}
      />,
    )

    fireEvent.click(screen.getByRole("menuitem", { name: "组织中心" }))

    expect(
      await screen.findByRole("heading", { name: "组织中心" }),
    ).toBeInTheDocument()
    expect(window.location.hash).toBe("#organization")
  })

  it("opens the configuration workspace and keeps location in the hash", async () => {
    render(
      <AppShell
        token="synthetic-token"
        user={administrator}
        onSignedOut={() => undefined}
      />,
    )

    fireEvent.click(screen.getByRole("menuitem", { name: "配置中心" }))

    expect(
      await screen.findByRole("heading", { name: "配置中心" }),
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
})
