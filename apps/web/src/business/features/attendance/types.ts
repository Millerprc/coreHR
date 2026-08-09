import type { Page } from "../workforce/types"


export type AttendancePage<T> = Page<T>


export interface AttendanceEmploymentOption {
  readonly id: string
  readonly person_id: string
  readonly employee_number: string | null
  readonly display_name: string
  readonly employee_type_code: string
  readonly status: string
}


export interface AttendanceRuleSet {
  readonly id: string
  readonly code: string
  readonly name: string
  readonly timezone: string
  readonly version: number
  readonly status: string
  readonly effective_from: string
  readonly effective_to: string | null
  readonly rules: Record<string, unknown>
  readonly created_at: string
  readonly updated_at: string
}


export interface Shift {
  readonly id: string
  readonly code: string
  readonly name: string
  readonly start_time: string
  readonly end_time: string
  readonly crosses_midnight: boolean
  readonly rule_set_id: string
  readonly status: string
}


export interface ScheduleAssignment {
  readonly id: string
  readonly employment_id: string
  readonly work_date: string
  readonly shift_id: string
  readonly source: string
  readonly status: string
}


export interface AttendancePunch {
  readonly id: string
  readonly employment_id: string
  readonly punched_at: string
  readonly punch_type: "in" | "out" | null
  readonly source: string
  readonly source_record_id: string
  readonly raw_payload: Record<string, unknown>
}


export interface LeaveType {
  readonly id: string
  readonly code: string
  readonly name: string
  readonly unit: "day" | "hour"
  readonly status: string
  readonly rules: Record<string, unknown>
}


export interface LeaveRequest {
  readonly id: string
  readonly request_number: string
  readonly employment_id: string
  readonly leave_type_id: string
  readonly start_date: string
  readonly end_date: string
  readonly amount: string
  readonly status: string
  readonly reason: string
  readonly workflow_instance_id: string | null
  readonly cancellation_of_id: string | null
}


export interface AttendanceDailyResult {
  readonly id: string
  readonly employment_id: string
  readonly work_date: string
  readonly status: string
  readonly scheduled_minutes: number
  readonly worked_minutes: number
  readonly late_minutes: number
  readonly early_leave_minutes: number
  readonly exception_codes: readonly string[]
  readonly evidence: Record<string, unknown>
  readonly version: number
  readonly is_current: boolean
}


export interface AttendanceMonthlyResult {
  readonly id: string
  readonly employment_id: string
  readonly period_month: string
  readonly scheduled_days: string
  readonly worked_days: string
  readonly leave_days: string
  readonly absent_days: string
  readonly late_minutes: number
  readonly early_leave_minutes: number
  readonly version: number
  readonly is_current: boolean
  readonly status: string
}


export interface AttendancePeriodFreeze {
  readonly id: string
  readonly freeze_type: "monthly" | "special"
  readonly date_from: string
  readonly date_to: string
  readonly status: "active" | "released"
  readonly reason: string
  readonly frozen_by: string
  readonly frozen_at: string
  readonly released_by: string | null
  readonly released_at: string | null
  readonly release_reason: string | null
  readonly created_at: string
  readonly updated_at: string
}
