import { describe, expect, it } from "vitest"

import { buildWorkflowDefinition } from "./workflowDefinition"


const base = {
  code: "transfer_approval",
  name: "调动审批",
  category: "hr_event",
  change_reason: "初始化条件流程",
  routing_mode: "conditional" as const,
  sign_mode: "any" as const,
  assignees: "HR_ADMIN, SSC_ADMIN",
  default_assignees: "SYSTEM_ADMIN",
}


describe("buildWorkflowDefinition", () => {
  it("builds a numeric condition and one default route", () => {
    const definition = buildWorkflowDefinition({
      ...base,
      condition_path: "amount",
      condition_operator: "gte",
      condition_value_type: "number",
      condition_value: "10000",
    })

    expect(definition.code).toBe("TRANSFER_APPROVAL")
    expect(definition.edges).toEqual(expect.arrayContaining([
      {
        source: "START",
        target: "MATCH_APPROVE",
        condition: {
          mode: "all",
          rules: [{ path: "amount", operator: "gte", value: 10000 }],
        },
      },
      { source: "START", target: "DEFAULT_APPROVE" },
    ]))
  })

  it("turns comma-separated membership values into a bounded list", () => {
    const definition = buildWorkflowDefinition({
      ...base,
      condition_path: "country_code",
      condition_operator: "in",
      condition_value_type: "text",
      condition_value: "CN, SG",
    })
    const edges = definition.edges as readonly Record<string, unknown>[]
    expect(edges[0]).toMatchObject({
      condition: { rules: [{ value: ["CN", "SG"] }] },
    })
  })

  it("rejects an invalid numeric comparison before calling the API", () => {
    expect(() => buildWorkflowDefinition({
      ...base,
      condition_path: "amount",
      condition_operator: "gte",
      condition_value_type: "number",
      condition_value: "not-a-number",
    })).toThrow("条件比较值必须是有效数字")
  })
})
