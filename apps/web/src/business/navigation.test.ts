import { describe, expect, it } from "vitest"

import {
  organizationDetailRouteFromHash,
  organizationDetailUrl,
  workspaceFromHash,
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
