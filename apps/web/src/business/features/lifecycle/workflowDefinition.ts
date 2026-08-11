export type WorkflowConditionOperator = "eq" | "ne" | "gt" | "gte" | "lt" | "lte" | "in" | "not_in" | "exists" | "not_exists"
export type WorkflowConditionValueType = "text" | "number" | "boolean"


export interface WorkflowTemplateValues {
  readonly code: string
  readonly name: string
  readonly category: string
  readonly description?: string
  readonly change_reason: string
  readonly routing_mode: "linear" | "conditional"
  readonly sign_mode: "all" | "any"
  readonly assignees: string
  readonly condition_path?: string
  readonly condition_operator?: WorkflowConditionOperator
  readonly condition_value_type?: WorkflowConditionValueType
  readonly condition_value?: string
  readonly default_assignees?: string
}


function assignees(raw: string): readonly { readonly assignee_type: "role"; readonly assignee_ref: string }[] {
  const references = raw.split(",").map((value) => value.trim()).filter(Boolean)
  if (!references.length) throw new Error("至少填写一个办理角色")
  return references.map((assignee_ref) => ({
    assignee_type: "role" as const,
    assignee_ref,
  }))
}


function scalar(raw: string, valueType: WorkflowConditionValueType): string | number | boolean {
  const value = raw.trim()
  if (valueType === "number") {
    const parsed = Number(value)
    if (!value || !Number.isFinite(parsed)) throw new Error("条件比较值必须是有效数字")
    return parsed
  }
  if (valueType === "boolean") {
    if (value.toLowerCase() === "true") return true
    if (value.toLowerCase() === "false") return false
    throw new Error("布尔比较值只能填写 true 或 false")
  }
  if (!value) throw new Error("条件比较值不能为空")
  return value
}


function conditionValue(
  operator: WorkflowConditionOperator,
  raw: string | undefined,
  valueType: WorkflowConditionValueType,
): string | number | boolean | readonly (string | number | boolean)[] | undefined {
  if (operator === "exists" || operator === "not_exists") return undefined
  if (operator === "in" || operator === "not_in") {
    const values = (raw ?? "").split(",").map((value) => value.trim()).filter(Boolean)
    if (!values.length) throw new Error("包含条件至少填写一个比较值")
    return values.map((value) => scalar(value, valueType))
  }
  return scalar(raw ?? "", valueType)
}


export function buildWorkflowDefinition(values: WorkflowTemplateValues): Record<string, unknown> {
  const common = {
    code: values.code.toUpperCase(),
    name: values.name,
    category: values.category,
    description: values.description || null,
    change_reason: values.change_reason,
  }
  if (values.routing_mode === "linear") {
    return {
      ...common,
      nodes: [
        { code: "START", name: "开始", node_type: "start" },
        {
          code: "APPROVE",
          name: "主管理员审批",
          node_type: "approval",
          sign_mode: values.sign_mode,
          assignees: assignees(values.assignees),
        },
        { code: "END", name: "结束", node_type: "end" },
      ],
      edges: [
        { source: "START", target: "APPROVE" },
        { source: "APPROVE", target: "END" },
      ],
    }
  }

  const operator = values.condition_operator
  const path = values.condition_path?.trim()
  if (!operator || !path) throw new Error("条件分流必须填写判断字段和判断方式")
  const value = conditionValue(operator, values.condition_value, values.condition_value_type ?? "text")
  const rule = value === undefined ? { path, operator } : { path, operator, value }
  return {
    ...common,
    nodes: [
      { code: "START", name: "开始", node_type: "start" },
      {
        code: "MATCH_APPROVE",
        name: "符合条件审批",
        node_type: "approval",
        sign_mode: values.sign_mode,
        assignees: assignees(values.assignees),
      },
      {
        code: "DEFAULT_APPROVE",
        name: "默认审批",
        node_type: "approval",
        sign_mode: values.sign_mode,
        assignees: assignees(values.default_assignees ?? ""),
      },
      { code: "END", name: "结束", node_type: "end" },
    ],
    edges: [
      { source: "START", target: "MATCH_APPROVE", condition: { mode: "all", rules: [rule] } },
      { source: "START", target: "DEFAULT_APPROVE" },
      { source: "MATCH_APPROVE", target: "END" },
      { source: "DEFAULT_APPROVE", target: "END" },
    ],
  }
}
