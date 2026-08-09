import type { Page } from "../workforce/types"


export type LifecyclePage<T> = Page<T>


export interface WorkflowDefinition {
  readonly id: string
  readonly code: string
  readonly name: string
  readonly category: string
  readonly status: string
  readonly active_version: number | null
  readonly description: string | null
  readonly created_at: string
  readonly updated_at: string
}


export interface WorkflowTask {
  readonly id: string
  readonly workflow_instance_id: string
  readonly node_code: string
  readonly sign_mode: "all" | "any"
  readonly assignee_type: string
  readonly assignee_ref: string
  readonly status: string
  readonly decision: string | null
  readonly comment: string | null
  readonly decided_by: string | null
  readonly decided_at: string | null
}


export interface WorkflowInstance {
  readonly id: string
  readonly instance_number: string
  readonly workflow_version_id: string
  readonly business_object_type: string
  readonly business_object_id: string
  readonly status: string
  readonly current_node_code: string | null
  readonly started_by: string | null
  readonly started_at: string
  readonly completed_at: string | null
  readonly context: Record<string, unknown>
}


export interface Candidate {
  readonly id: string
  readonly candidate_number: string
  readonly display_name: string
  readonly contact_payload: Record<string, unknown>
  readonly status: "active" | "converted" | "inactive"
  readonly linked_person_id: string | null
  readonly created_at: string
  readonly updated_at: string
}


export interface JobApplication {
  readonly id: string
  readonly candidate_id: string
  readonly recruitment_request_id: string
  readonly status: string
  readonly current_stage: string | null
  readonly offer_payload: Record<string, unknown>
}


export interface ContractRecord {
  readonly id: string
  readonly person_id: string
  readonly employment_id: string | null
  readonly contract_type_code: string
  readonly contract_number: string
  readonly legal_entity_id: string | null
  readonly effective_from: string
  readonly effective_to: string | null
  readonly status: string
  readonly metadata_payload: Record<string, unknown>
}


export interface HrEvent {
  readonly id: string
  readonly event_number: string
  readonly event_type: string
  readonly object_type: string
  readonly object_id: string
  readonly effective_date: string
  readonly status: string
  readonly source: string
  readonly reason: string
  readonly before_payload: Record<string, unknown>
  readonly planned_payload: Record<string, unknown>
  readonly actual_payload: Record<string, unknown>
  readonly workflow_instance_id: string | null
  readonly related_event_id: string | null
  readonly attempts: number
  readonly last_error: string | null
  readonly executed_at: string | null
  readonly version: number
}
