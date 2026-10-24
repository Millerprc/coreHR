// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

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
  /** 绑定时的规则集版本号；班次绑定不可变版本行。 */
  readonly rule_set_version: number | null
  /** 绑定时冻结的规则内容快照。 */
  readonly rule_snapshot: Record<string, unknown>
  readonly status: string
}


export interface ScheduleAssignment {
  readonly id: string
  readonly employment_id: string
  readonly work_date: string
  readonly shift_id: string
  readonly source: string
  readonly status: string
  /** 草稿或已发布；草稿不参与考勤计算。 */
  readonly publish_status: "draft" | "published"
  /** 同日多班次的占位序号。 */
  readonly sequence_no: number
  readonly batch_id: string | null
  readonly schedule_type_id: string | null
}


export interface ScheduleType {
  readonly id: string
  readonly code: string
  readonly name: string
  readonly requires_shift_cycle: boolean
  readonly requires_flexible_window: boolean
  readonly allows_multiple_shifts_per_day: boolean
  readonly requires_publish: boolean
  readonly status: string
  readonly rules: Record<string, unknown>
  readonly created_at: string
  readonly updated_at: string
}


export interface ShiftCycle {
  readonly id: string
  readonly code: string
  readonly name: string
  readonly schedule_type_id: string
  readonly cycle_start_date: string
  readonly cycle_days: number
  readonly shift_sequence: readonly unknown[]
  readonly status: string
  readonly rules: Record<string, unknown>
  readonly created_at: string
  readonly updated_at: string
}


export interface FlexibleWindow {
  readonly id: string
  readonly code: string
  readonly name: string
  readonly schedule_type_id: string
  readonly arrival_window_start: string | null
  readonly arrival_window_end: string | null
  readonly departure_window_start: string | null
  readonly departure_window_end: string | null
  readonly standard_daily_minutes: number | null
  readonly status: string
  readonly rules: Record<string, unknown>
  readonly created_at: string
  readonly updated_at: string
}


export interface SchedulePublishBatch {
  readonly id: string
  readonly batch_number: string
  readonly period_code: string
  readonly period_start: string
  readonly period_end: string
  readonly schedule_type_id: string | null
  readonly status: string
  readonly published_at: string | null
  readonly published_by: string | null
  readonly created_by: string
  readonly published_count: number
  readonly created_at: string
  readonly updated_at: string
}


export interface ScheduleSwap {
  readonly id: string
  readonly request_number: string
  readonly employment_id_a: string
  readonly employment_id_b: string
  readonly work_date: string
  readonly original_shift_id: string | null
  readonly new_shift_id: string | null
  readonly status: string
  readonly requested_by: string
  readonly requested_at: string
  readonly decided_at: string | null
  readonly decided_by: string | null
  readonly effective_at: string | null
  readonly remark: string | null
  readonly created_at: string
  readonly updated_at: string
}


export interface ScheduleDraftFailure {
  readonly line_index: number
  readonly employment_id: string
  readonly work_date: string
  readonly code: string
  readonly message: string
}


export interface ScheduleDraftResult {
  readonly period_code: string
  readonly created: number
  readonly failed: readonly ScheduleDraftFailure[]
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


export interface LeaveBalanceAccount {
  readonly id: string
  readonly employment_id: string
  readonly leave_type_id: string
  readonly period_year: number
  readonly unit: "day" | "hour"
  readonly current_balance: string
  readonly version: number
  readonly status: "active" | "closed"
  /** 时点查询参数回显；为空表示未按时点查询。 */
  readonly as_of: string | null
  /** 该时点余额；未按时点查询时为空。 */
  readonly balance_as_of: string | null
  readonly created_at: string
  readonly updated_at: string
}


/** 发假额度规则（D-107 规则容器；字段为空表示规则待配置）。 */
export interface LeaveGrantRule {
  readonly id: string
  readonly code: string
  readonly name: string
  readonly version: number
  readonly leave_type_id: string
  readonly status: string
  readonly entitlement_days: string | null
  readonly seniority_min_years: number | null
  readonly seniority_max_years: number | null
  readonly proration_method: string | null
  readonly accrual_frequency: string | null
  readonly cap_days: string | null
  readonly carryover_cap_days: string | null
  readonly valid_from: string | null
  readonly valid_to: string | null
  readonly reset_policy: string | null
  readonly termination_policy: string | null
  readonly effective_from: string
  readonly effective_to: string | null
  readonly rules: Record<string, unknown>
  readonly created_at: string
  readonly updated_at: string
}


export interface LeaveGrantBatch {
  readonly id: string
  readonly batch_number: string
  readonly period_code: string
  readonly period_type: string
  readonly grant_date: string
  readonly status: string
  readonly source: string
  readonly created_by: string
  readonly issued_at: string | null
  readonly issued_by: string | null
  readonly voided_at: string | null
  readonly voided_by: string | null
  readonly void_reason: string | null
  readonly created_at: string
  readonly updated_at: string
}


export interface LeaveGrantItem {
  readonly id: string
  readonly batch_id: string
  readonly employment_id: string
  readonly leave_type_id: string
  readonly account_id: string | null
  readonly transaction_id: string | null
  readonly rule_id: string | null
  readonly grant_days: string
  readonly valid_from: string | null
  readonly valid_to: string | null
  readonly source: string
  readonly status: string
  readonly idempotency_key: string
  readonly created_at: string
  readonly updated_at: string
}


export interface LeaveGrantBatchDetail extends LeaveGrantBatch {
  readonly items: readonly LeaveGrantItem[]
}


export interface LeaveBalanceTransaction {
  readonly id: string
  readonly account_id: string
  readonly transaction_type: "grant" | "adjustment" | "carryover" | "accrual" | "usage" | "reversal"
  readonly amount: string
  readonly effective_date: string
  readonly balance_before: string
  readonly balance_after: string
  readonly account_version: number
  readonly source_type: string
  readonly source_id: string | null
  readonly idempotency_key: string
  readonly reason: string
  readonly actor_id: string
  readonly created_at: string
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
