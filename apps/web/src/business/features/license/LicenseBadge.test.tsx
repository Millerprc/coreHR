// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import type { LicenseState } from "../../types"
import { LicenseBadge } from "./LicenseBadge"


const unlicensed: LicenseState = {
  status: "none",
  readonly_mode: true,
  tier: null,
  licensee: null,
  licensee_short: null,
  license_id: null,
  entitlements: {},
  issued_at: null,
  not_before: null,
  expires_at: null,
  seat_limit: null,
  activated_at: null,
}


const licensed: LicenseState = {
  ...unlicensed,
  status: "active",
  readonly_mode: false,
  tier: "commercial",
  licensee: "某某科技有限公司",
  licensee_short: "某某科技",
  license_id: "LIC-2026-000123",
  entitlements: {
    attendance: { read: true, write: true },
    workflow: { read: true, write: false },
  },
  issued_at: "2026-10-24T06:00:00Z",
  not_before: "2026-10-24T00:00:00Z",
  expires_at: "2027-10-24T00:00:00Z",
  seat_limit: 5000,
  activated_at: "2026-10-24T06:00:00Z",
}


describe("LicenseBadge", () => {
  it("marks an unlicensed system as a read-only demo", () => {
    render(<LicenseBadge state={unlicensed} />)

    expect(screen.getByText("未授权 · 只读演示")).toBeInTheDocument()
    expect(screen.getByLabelText("授权状态：未授权 · 只读演示")).toBeInTheDocument()
  })

  it("shows licensee, tier and expiry for an active license", () => {
    render(<LicenseBadge state={licensed} />)

    expect(screen.getByText("某某科技 · Commercial · 至 2027-10-24")).toBeInTheDocument()
    expect(screen.getByLabelText("授权状态：某某科技 · Commercial · 至 2027-10-24")).toBeInTheDocument()
  })

  it("marks an expired license as an expired read-only demo", () => {
    render(<LicenseBadge state={{ ...licensed, status: "expired" }} />)

    expect(screen.getByText("已过期 · 只读演示")).toBeInTheDocument()
  })

  it("marks a revoked license as a revoked read-only demo", () => {
    render(<LicenseBadge state={{ ...licensed, status: "revoked" }} />)

    expect(screen.getByText("已吊销 · 只读演示")).toBeInTheDocument()
  })

  it("marks a not yet valid license as a pending read-only demo", () => {
    render(<LicenseBadge state={{ ...licensed, status: "not_yet_valid" }} />)

    expect(screen.getByText("尚未生效 · 只读演示")).toBeInTheDocument()
  })

  it("falls back to the read-only demo label when the license state is unknown", () => {
    render(<LicenseBadge state={null} />)

    expect(screen.getByText("未授权 · 只读演示")).toBeInTheDocument()
  })
})
