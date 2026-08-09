export interface VersionCommand {
  readonly expected_version: number
  readonly idempotency_key: string
  readonly change_reason: string
}


export interface OrganizationType {
  readonly id: string
  readonly code: string
  readonly name: string
  readonly sort_order: number
  readonly is_active: boolean
}


export interface OrganizationEvent {
  readonly id: string
  readonly organization_id: string
  readonly event_type: string
  readonly effective_date: string
  readonly status: string
  readonly payload: Record<string, unknown>
  readonly expected_version: number
  readonly idempotency_key: string
  readonly change_reason: string
  readonly applied_at: string | null
  readonly cancelled_at: string | null
}


export interface Organization {
  readonly id: string
  readonly code: string
  readonly name: string
  readonly organization_type_id: string
  readonly organization_type_code: string
  readonly organization_type_name: string
  readonly parent_organization_id: string | null
  readonly parent_organization_code: string | null
  readonly country_code: string | null
  readonly status: string
  readonly effective_from: string
  readonly effective_to: string | null
  readonly version: number
  readonly planned_events: readonly OrganizationEvent[]
}


export interface OrganizationTreeNode {
  readonly id: string
  readonly code: string
  readonly name: string
  readonly organization_type_code: string
  readonly status: string
  readonly children: readonly OrganizationTreeNode[]
}


export interface OrganizationRelations {
  readonly effective_at: string
  readonly legal_entity_ids: readonly string[]
  readonly legal_entity_version: number
  readonly leader_person_ids: readonly string[]
  readonly leader_version: number
  readonly bp_membership_ids: readonly string[]
}


export interface CostCenter {
  readonly id: string
  readonly code: string
  readonly name: string
  readonly country_code: string | null
  readonly status: string
  readonly effective_from: string
  readonly effective_to: string | null
  readonly version: number
}


export interface CostAllocationLine {
  readonly cost_center_id: string
  readonly allocation_percent: string
}


export interface CostAllocation {
  readonly organization_id: string
  readonly effective_at: string
  readonly version: number
  readonly lines: readonly CostAllocationLine[]
}


export interface RevenueMonth {
  readonly month: number
  readonly amount: string
}


export interface RevenueTarget {
  readonly id: string
  readonly organization_id: string
  readonly year: number
  readonly currency_code: string
  readonly annual_amount: string
  readonly months: readonly RevenueMonth[]
  readonly version: number
}


export interface RevenueCurrencyTotal {
  readonly annual_amount: string
  readonly months: Readonly<Record<string, string>>
}


export interface RevenueAggregation {
  readonly organization_id: string
  readonly year: number
  readonly include_descendants: boolean
  readonly targets: readonly RevenueTarget[]
  readonly totals_by_currency: Readonly<Record<string, RevenueCurrencyTotal>>
}


export interface DirectoryOption {
  readonly id: string
  readonly code?: string
  readonly name?: string
  readonly display_name?: string
  readonly employee_number?: string | null
}


export interface PageResponse<T> {
  readonly items: readonly T[]
  readonly total: number
}


export interface BpMembership {
  readonly id: string
  readonly person_id: string
  readonly bp_type: "HRBP" | "EBP" | "TBP" | "FBP"
  readonly organization_ids: readonly string[]
  readonly effective_from: string
  readonly effective_to: string | null
  readonly version: number
  readonly status: string
}
