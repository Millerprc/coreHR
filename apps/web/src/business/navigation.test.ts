// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { describe, expect, it } from "vitest"

import {
  organizationDetailRouteFromHash,
  organizationDetailUrl,
  workspaceFromHash,
  workspaces,
} from "./navigation"


describe("organization detail navigation", () => {
  it("keeps a detail tab inside department management and preserves its effective date", () => {
    const organizationId = "30000000-0000-0000-0000-000000000001"
    const hash = `#organization/${organizationId}?effective_at=2026-08-20`

    expect(workspaceFromHash(hash)).toBe("organization")
    expect(organizationDetailRouteFromHash(hash)).toEqual({
      organizationId,
      effectiveAt: "2026-08-20",
    })
    expect(organizationDetailUrl(organizationId, "2026-08-20")).toBe(hash)
  })

  it("rejects malformed detail routes", () => {
    expect(organizationDetailRouteFromHash("#organization/not-a-uuid")).toBeNull()
    expect(organizationDetailRouteFromHash("#organization/30000000-0000-0000-0000-000000000001?effective_at=20-08-2026")).toBeNull()
  })
})


// Requirement: D-108 — 授权管理的导航契约：
// 被锁模块保留在导航里（可见可进入），平台权限码语义不变，授权归属另用独立字段表达。
describe("license managed navigation", () => {
  it("adds the license workspace for main administrators", () => {
    const workspace = workspaces.find((item) => item.key === "license")

    expect(workspace?.label).toBe("授权管理")
    expect(workspace?.permission).toBe("*")
    expect(workspace?.available).toBe(true)
    expect(workspaceFromHash("#license")).toBe("license")
  })

  it("marks the license managed modules without touching the permission contract", () => {
    const attendance = workspaces.find((item) => item.key === "attendance")
    expect(attendance?.permission).toBe("ATTENDANCE_ADMIN")
    expect(attendance?.licensedModules).toEqual(["attendance"])

    // 员工生命周期同时承载审批与流程引擎，因此归属两个授权模块。
    const lifecycle = workspaces.find((item) => item.key === "lifecycle")
    expect(lifecycle?.permission).toBe("LIFECYCLE_ADMIN")
    expect(lifecycle?.licensedModules).toEqual(["lifecycle", "workflow"])

    const governance = workspaces.find((item) => item.key === "governance")
    expect(governance?.permission).toBe("DATA_GOVERNANCE_VIEW")
    expect(governance?.licensedModules).toEqual(["governance"])

    // 未受授权管理的入口不带授权标记。
    const people = workspaces.find((item) => item.key === "people")
    expect(people?.licensedModules).toBeUndefined()
  })

  it("keeps the locked modules visible in the workspace list", () => {
    const keys = workspaces.map((item) => item.key)

    expect(keys).toContain("attendance")
    expect(keys).toContain("lifecycle")
    expect(keys).toContain("governance")
    expect(workspaceFromHash("#attendance")).toBe("attendance")
    expect(workspaceFromHash("#lifecycle")).toBe("lifecycle")
    expect(workspaceFromHash("#governance")).toBe("governance")
  })
})
