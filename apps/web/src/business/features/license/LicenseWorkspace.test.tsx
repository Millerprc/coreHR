// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { LicenseWorkspace } from "./LicenseWorkspace"


const activeLicense = {
  status: "active",
  readonly_mode: false,
  tier: "commercial",
  licensee: "某某科技有限公司",
  licensee_short: "某某科技",
  license_id: "LIC-2026-000123",
  entitlements: {
    attendance: { read: true, write: false },
    workflow: { read: true, write: false },
    lifecycle: { read: true, write: true },
    governance: { read: true, write: false },
    workforce: { read: true, write: true },
    performance: { read: true, write: false },
  },
  issued_at: "2026-10-24T06:00:00Z",
  not_before: "2026-10-24T00:00:00Z",
  expires_at: "2027-10-24T00:00:00Z",
  seat_limit: 5000,
  activated_at: "2026-10-24T06:00:00Z",
}


const unlicensedLicense = {
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


interface StubOptions {
  readonly license?: unknown
  readonly activateStatus?: number
  readonly activateCode?: string
}


function stubFetch(options: StubOptions = {}): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path.includes("/api/v1/license/activate")) {
      if (options.activateStatus && options.activateStatus >= 400) {
        return Response.json(
          { code: options.activateCode ?? "LICENSE_INVALID_TOKEN", message: "授权 Token 无效" },
          { status: options.activateStatus },
        )
      }
      return Response.json({
        activated: true,
        status: "active",
        tier: "commercial",
        licensee: "某某科技有限公司",
        entitlements: activeLicense.entitlements,
        expires_at: "2027-10-24T00:00:00Z",
      })
    }
    if (path.includes("/api/v1/license/deactivate")) {
      return Response.json({ status: "none", readonly_mode: true })
    }
    if (path.includes("/api/v1/license")) {
      return Response.json(options.license ?? activeLicense)
    }
    void init
    return Response.json({ items: [], total: 0 })
  })
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}


describe("LicenseWorkspace", () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("shows the current license status and the per-module entitlement scope", async () => {
    stubFetch()

    render(<LicenseWorkspace token="synthetic-token" />)

    expect(await screen.findByText("已授权")).toBeInTheDocument()
    expect(screen.getByText("某某科技有限公司")).toBeInTheDocument()
    expect(screen.getByText("LIC-2026-000123")).toBeInTheDocument()
    expect(screen.getByText("2027-10-24")).toBeInTheDocument()
    expect(screen.getByText("Commercial")).toBeInTheDocument()

    // 授权范围按模块列出读取与写入。
    expect(screen.getByText("考勤管理")).toBeInTheDocument()
    expect(screen.getByText("员工生命周期")).toBeInTheDocument()
    expect(screen.getByText("审批与流程引擎")).toBeInTheDocument()
    expect(screen.getByText("数据治理导入")).toBeInTheDocument()
    expect(screen.getAllByText("可读").length).toBeGreaterThan(0)
    expect(screen.getAllByText("不可写").length).toBeGreaterThan(0)
    expect(screen.getAllByText("可写").length).toBeGreaterThan(0)
  })

  it("explains the read-only demo mode when no license is registered", async () => {
    stubFetch({ license: unlicensedLicense })

    render(<LicenseWorkspace token="synthetic-token" />)

    expect(await screen.findByText("当前为只读演示模式")).toBeInTheDocument()
    expect(screen.getByText("未授权")).toBeInTheDocument()
  })

  it("submits the pasted token to the activation endpoint", async () => {
    const fetchMock = stubFetch()

    render(<LicenseWorkspace token="synthetic-token" />)

    await screen.findByText("已授权")

    fireEvent.change(screen.getByLabelText("License Token"), {
      target: { value: "coreHR.header.payload.signature" },
    })
    fireEvent.click(screen.getByRole("button", { name: /激活授权/ }))

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(([input]) => String(input).includes("/api/v1/license/activate"))
      expect(call).toBeDefined()
      const init = call?.[1] as RequestInit | undefined
      expect(init?.method).toBe("POST")
      expect(JSON.parse(String(init?.body))).toEqual({ token: "coreHR.header.payload.signature" })
      expect(init?.headers).toMatchObject({ Authorization: "Bearer synthetic-token" })
    })
  })

  it("shows a readable error when the token signature does not verify", async () => {
    stubFetch({ activateStatus: 400, activateCode: "LICENSE_INVALID_SIGNATURE" })

    render(<LicenseWorkspace token="synthetic-token" />)

    await screen.findByText("已授权")

    fireEvent.change(screen.getByLabelText("License Token"), {
      target: { value: "coreHR.tampered.payload.signature" },
    })
    fireEvent.click(screen.getByRole("button", { name: /激活授权/ }))

    expect(
      await screen.findByText("License Token 签名校验失败，文件可能已被篡改。"),
    ).toBeInTheDocument()
  })

  it("rejects an empty token without calling the activation endpoint", async () => {
    const fetchMock = stubFetch()

    render(<LicenseWorkspace token="synthetic-token" />)

    await screen.findByText("已授权")

    fireEvent.click(screen.getByRole("button", { name: /激活授权/ }))

    expect(await screen.findByText("请粘贴 License Token")).toBeInTheDocument()
    expect(
      fetchMock.mock.calls.some(([input]) => String(input).includes("/api/v1/license/activate")),
    ).toBe(false)
  })
})
