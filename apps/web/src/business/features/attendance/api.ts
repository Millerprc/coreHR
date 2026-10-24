// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { apiRequest } from "../../client"
import type {
  AttendanceDailyResult,
  AttendanceEmploymentOption,
  AttendanceMonthlyResult,
  AttendancePeriodFreeze,
  AttendancePage,
  AttendancePunch,
  AttendanceRuleSet,
  LeaveBalanceAccount,
  LeaveBalanceTransaction,
  LeaveGrantBatch,
  LeaveGrantBatchDetail,
  LeaveGrantRule,
  LeaveRequest,
  LeaveType,
  FlexibleWindow,
  ScheduleAssignment,
  ScheduleDraftResult,
  SchedulePublishBatch,
  ScheduleSwap,
  ScheduleType,
  Shift,
  ShiftCycle,
} from "./types"


/** 批量计算任务的报表类型：日报 / 月报。 */
export type AttendanceCalculationKind = "daily" | "monthly"


/** 批量计算任务的人员范围：全员 / 指定人员 / 排除人员。 */
export type AttendanceCalculationScope = "all" | "selected" | "excluded"


/** 批量计算任务状态：待处理 / 处理中 / 成功 / 失败 / 已取消。 */
export type AttendanceCalculationTaskStatus = "pending" | "running" | "succeeded" | "failed" | "canceled"


/**
 * 批量计算任务入参。
 *
 * 约束：kind=daily 必须带 work_date 且不得带 period_month；
 * kind=monthly 必须带 period_month（该月第一天）且不得带 work_date；
 * scope=all 时 employment_ids 必须为空数组。
 */
export interface AttendanceCalculationTaskRequest {
  readonly kind: AttendanceCalculationKind
  readonly scope: AttendanceCalculationScope
  readonly employment_ids: readonly string[]
  /** kind=daily 时必填；kind=monthly 时不得出现。 */
  readonly work_date?: string
  /** kind=monthly 时必填（该月第一天）；kind=daily 时不得出现。 */
  readonly period_month?: string
  readonly reason?: string
}


/** 批量计算任务完成后的统计结果（仅 succeeded 时非空）。 */
export interface AttendanceCalculationTaskResult {
  readonly kind: AttendanceCalculationKind
  readonly scope: AttendanceCalculationScope
  /** kind=daily 时回显本次计算的工作日期。 */
  readonly work_date?: string
  /** kind=monthly 时回显本次计算的账期（该月第一天）。 */
  readonly period_month?: string
  readonly target_count: number
  readonly succeeded_count: number
  readonly failed_count: number
  /** 受控失败错误码 → 失败人数。 */
  readonly failure_codes: Readonly<Record<string, number>>
}


/** 批量计算任务创建响应（202）。 */
export interface AttendanceCalculationTaskCreated {
  readonly id: string
  readonly task_type: string
  readonly status: AttendanceCalculationTaskStatus
  readonly created_at: string
}


/** 批量计算任务详情。 */
export interface AttendanceCalculationTask {
  readonly id: string
  readonly task_type: string
  readonly status: AttendanceCalculationTaskStatus
  readonly payload: Readonly<Record<string, unknown>>
  readonly result: AttendanceCalculationTaskResult | null
  readonly error_code: string | null
  readonly attempts: number
  readonly max_attempts: number
  readonly next_attempt_at: string
  readonly lease_owner: string | null
  readonly lease_expires_at: string | null
  readonly started_at: string | null
  readonly finished_at: string | null
  readonly created_by: string | null
  readonly idempotency_key: string | null
  /** 人类可读的进度文案（如「已处理 120 / 200 人」）；后端存字符串，不是数字。 */
  readonly progress: string | null
  readonly created_at: string
  readonly updated_at: string
}


export const attendanceApi = {
  periodFreezes: (token: string) => apiRequest<AttendancePage<AttendancePeriodFreeze>>("/api/v1/attendance/period-freezes?limit=200&offset=0", token),
  createPeriodFreeze: (token: string, body: unknown) => apiRequest<AttendancePeriodFreeze>("/api/v1/attendance/period-freezes", token, { method: "POST", body }),
  releasePeriodFreeze: (token: string, id: string, body: unknown) => apiRequest<AttendancePeriodFreeze>(`/api/v1/attendance/period-freezes/${id}/release`, token, { method: "POST", body }),
  employmentOptions: (token: string, search = "") => apiRequest<AttendancePage<AttendanceEmploymentOption>>(`/api/v1/attendance/employment-options?limit=200&offset=0${search ? `&search=${encodeURIComponent(search)}` : ""}`, token),
  ruleSets: (token: string) => apiRequest<AttendancePage<AttendanceRuleSet>>("/api/v1/attendance/rule-sets?limit=200&offset=0", token),
  createRuleSet: (token: string, body: unknown) => apiRequest<AttendanceRuleSet>("/api/v1/attendance/rule-sets", token, { method: "POST", body }),
  createRuleVersion: (token: string, id: string, body: unknown) => apiRequest<AttendanceRuleSet>(`/api/v1/attendance/rule-sets/${id}/versions`, token, { method: "POST", body }),
  publishRuleSet: (token: string, id: string) => apiRequest<AttendanceRuleSet>(`/api/v1/attendance/rule-sets/${id}/publish`, token, { method: "POST" }),
  shifts: (token: string) => apiRequest<AttendancePage<Shift>>("/api/v1/attendance/shifts?limit=200&offset=0", token),
  createShift: (token: string, body: unknown) => apiRequest<Shift>("/api/v1/attendance/shifts", token, { method: "POST", body }),
  updateShift: (token: string, id: string, body: unknown) => apiRequest<Shift>(`/api/v1/attendance/shifts/${id}`, token, { method: "PATCH", body }),
  schedules: (token: string) => apiRequest<AttendancePage<ScheduleAssignment>>("/api/v1/attendance/schedules?limit=200&offset=0", token),
  createSchedule: (token: string, body: unknown) => apiRequest<ScheduleAssignment>("/api/v1/attendance/schedules", token, { method: "POST", body }),
  updateSchedule: (token: string, id: string, body: unknown) => apiRequest<ScheduleAssignment>(`/api/v1/attendance/schedules/${id}`, token, { method: "PATCH", body }),
  punches: (token: string) => apiRequest<AttendancePage<AttendancePunch>>("/api/v1/attendance/punches?limit=200&offset=0", token),
  createPunch: (token: string, body: unknown) => apiRequest("/api/v1/attendance/punches", token, { method: "POST", body }),
  leaveTypes: (token: string) => apiRequest<AttendancePage<LeaveType>>("/api/v1/attendance/leave-types?limit=200&offset=0", token),
  createLeaveType: (token: string, body: unknown) => apiRequest<LeaveType>("/api/v1/attendance/leave-types", token, { method: "POST", body }),
  updateLeaveType: (token: string, id: string, body: unknown) => apiRequest<LeaveType>(`/api/v1/attendance/leave-types/${id}`, token, { method: "PATCH", body }),
  leaveRequests: (token: string) => apiRequest<AttendancePage<LeaveRequest>>("/api/v1/attendance/leave-requests?limit=200&offset=0", token),
  createLeaveRequest: (token: string, body: unknown) => apiRequest<LeaveRequest>("/api/v1/attendance/leave-requests", token, { method: "POST", body }),
  updateLeaveRequest: (token: string, id: string, body: unknown) => apiRequest<LeaveRequest>(`/api/v1/attendance/leave-requests/${id}`, token, { method: "PATCH", body }),
  cancelLeaveRequest: (token: string, id: string, body: unknown) => apiRequest<LeaveRequest>(`/api/v1/attendance/leave-requests/${id}/cancel`, token, { method: "POST", body }),
  leaveBalances: (token: string, asOf = "") => apiRequest<AttendancePage<LeaveBalanceAccount>>(`/api/v1/attendance/leave-balances?limit=200&offset=0${asOf ? `&as_of=${encodeURIComponent(asOf)}` : ""}`, token),
  createLeaveBalanceTransaction: (token: string, body: unknown) => apiRequest<LeaveBalanceTransaction>("/api/v1/attendance/leave-balances/transactions", token, { method: "POST", body }),
  leaveBalanceTransactions: (token: string, accountId: string) => apiRequest<AttendancePage<LeaveBalanceTransaction>>(`/api/v1/attendance/leave-balances/${accountId}/transactions?limit=200&offset=0`, token),
  leaveGrantRules: (token: string) => apiRequest<AttendancePage<LeaveGrantRule>>("/api/v1/attendance/leave-grant-rules?limit=200&offset=0", token),
  createLeaveGrantRule: (token: string, body: unknown) => apiRequest<LeaveGrantRule>("/api/v1/attendance/leave-grant-rules", token, { method: "POST", body }),
  updateLeaveGrantRule: (token: string, id: string, body: unknown) => apiRequest<LeaveGrantRule>(`/api/v1/attendance/leave-grant-rules/${id}`, token, { method: "PATCH", body }),
  activateLeaveGrantRule: (token: string, id: string) => apiRequest<LeaveGrantRule>(`/api/v1/attendance/leave-grant-rules/${id}/activate`, token, { method: "POST" }),
  leaveGrantBatches: (token: string) => apiRequest<AttendancePage<LeaveGrantBatch>>("/api/v1/attendance/leave-grant-batches?limit=200&offset=0", token),
  createLeaveGrantBatch: (token: string, body: unknown) => apiRequest<LeaveGrantBatch>("/api/v1/attendance/leave-grant-batches", token, { method: "POST", body }),
  leaveGrantBatch: (token: string, id: string) => apiRequest<LeaveGrantBatchDetail>(`/api/v1/attendance/leave-grant-batches/${id}`, token),
  issueLeaveGrantBatch: (token: string, id: string) => apiRequest<LeaveGrantBatch>(`/api/v1/attendance/leave-grant-batches/${id}/issue`, token, { method: "POST" }),
  voidLeaveGrantBatch: (token: string, id: string, body: unknown) => apiRequest<LeaveGrantBatch>(`/api/v1/attendance/leave-grant-batches/${id}/void`, token, { method: "POST", body }),
  scheduleTypes: (token: string) => apiRequest<AttendancePage<ScheduleType>>("/api/v1/attendance/schedule-types?limit=200&offset=0", token),
  createScheduleType: (token: string, body: unknown) => apiRequest<ScheduleType>("/api/v1/attendance/schedule-types", token, { method: "POST", body }),
  shiftCycles: (token: string) => apiRequest<AttendancePage<ShiftCycle>>("/api/v1/attendance/shift-cycles?limit=200&offset=0", token),
  createShiftCycle: (token: string, body: unknown) => apiRequest<ShiftCycle>("/api/v1/attendance/shift-cycles", token, { method: "POST", body }),
  flexibleWindows: (token: string) => apiRequest<AttendancePage<FlexibleWindow>>("/api/v1/attendance/flexible-windows?limit=200&offset=0", token),
  createFlexibleWindow: (token: string, body: unknown) => apiRequest<FlexibleWindow>("/api/v1/attendance/flexible-windows", token, { method: "POST", body }),
  generateScheduleDrafts: (token: string, body: unknown) => apiRequest<ScheduleDraftResult>("/api/v1/attendance/schedules/draft", token, { method: "POST", body }),
  schedulePublishBatches: (token: string) => apiRequest<AttendancePage<SchedulePublishBatch>>("/api/v1/attendance/schedule-publish-batches?limit=200&offset=0", token),
  createSchedulePublishBatch: (token: string, body: unknown) => apiRequest<SchedulePublishBatch>("/api/v1/attendance/schedule-publish-batches", token, { method: "POST", body }),
  publishScheduleBatch: (token: string, id: string) => apiRequest<SchedulePublishBatch>(`/api/v1/attendance/schedule-publish-batches/${id}/publish`, token, { method: "POST" }),
  scheduleSwaps: (token: string) => apiRequest<AttendancePage<ScheduleSwap>>("/api/v1/attendance/schedule-swaps?limit=200&offset=0", token),
  createScheduleSwap: (token: string, body: unknown) => apiRequest<ScheduleSwap>("/api/v1/attendance/schedule-swaps", token, { method: "POST", body }),
  decideScheduleSwap: (token: string, id: string, body: unknown) => apiRequest<ScheduleSwap>(`/api/v1/attendance/schedule-swaps/${id}`, token, { method: "PATCH", body }),
  dailyResults: (token: string) => apiRequest<AttendancePage<AttendanceDailyResult>>("/api/v1/attendance/daily-results?limit=200&offset=0", token),
  calculateDaily: (token: string, body: unknown) => apiRequest<AttendanceDailyResult>("/api/v1/attendance/daily-results/calculate", token, { method: "POST", body }),
  monthlyResults: (token: string) => apiRequest<AttendancePage<AttendanceMonthlyResult>>("/api/v1/attendance/monthly-results?limit=200&offset=0", token),
  calculateMonthly: (token: string, body: unknown) => apiRequest<AttendanceMonthlyResult>("/api/v1/attendance/monthly-results/calculate", token, { method: "POST", body }),
  submitCalculationTask: (token: string, body: AttendanceCalculationTaskRequest) => apiRequest<AttendanceCalculationTaskCreated>("/api/v1/attendance/calculation-tasks", token, { method: "POST", body }),
  getCalculationTask: (token: string, id: string) => apiRequest<AttendanceCalculationTask>(`/api/v1/attendance/calculation-tasks/${id}`, token),
}
