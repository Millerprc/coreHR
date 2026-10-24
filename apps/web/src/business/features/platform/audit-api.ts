// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { apiDownload, apiRequest } from "../../client"


/**
 * 审计日志读取契约。
 *
 * 后端 `audit_logs` 目前只写不读，本模块是前端唯一的读取入口。
 * 后端字段命名（snake_case）与前端模型（camelCase）之间的映射全部收敛在本文件，
 * 后端调整字段名时只需要修改 `mapAuditLogEntry` / `mapAuditLogPage` / `mapActionCount`，
 * 页面与表格不需要改动。
 */

export interface AuditLogFilters {
  readonly occurredFrom?: string
  readonly occurredTo?: string
  readonly actorId?: string
  readonly action?: string
  readonly objectType?: string
  readonly traceId?: string
}


export interface AuditLogPagination {
  readonly page: number
  readonly pageSize: number
}


export interface AuditLogEntry {
  readonly id: string
  readonly occurredAt: string
  readonly actorId: string | null
  readonly actorName: string | null
  readonly traceId: string | null
  readonly action: string
  readonly objectType: string | null
  readonly objectId: string | null
  readonly reason: string | null
  readonly source: string | null
}


export interface AuditLogPage {
  readonly items: readonly AuditLogEntry[]
  readonly total: number
  readonly page: number
  readonly pageSize: number
}


export interface AuditActionCount {
  readonly code: string
  readonly count: number
}


export interface AuditActor {
  readonly id: string
  readonly name: string
}


export interface AuditCsvDownload {
  readonly blob: Blob
  readonly filename: string
}


type RawRecord = Readonly<Record<string, unknown>>


const FALLBACK_EXPORT_FILENAME = "audit-logs.csv"
const SHARED_CLIENT_FALLBACK_FILENAME = "master-data-current.csv"


function isRecord(value: unknown): value is RawRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}


function readText(record: RawRecord, ...keys: readonly string[]): string | null {
  for (const key of keys) {
    const value = record[key]
    if (typeof value === "string" && value.trim() !== "") return value
    if (typeof value === "number" && Number.isFinite(value)) return String(value)
  }
  return null
}


function readNumber(record: RawRecord, ...keys: readonly string[]): number {
  for (const key of keys) {
    const value = record[key]
    if (typeof value === "number" && Number.isFinite(value)) return value
    if (typeof value === "string" && value.trim() !== "" && Number.isFinite(Number(value))) return Number(value)
  }
  return 0
}


function readItems(payload: unknown): readonly RawRecord[] {
  if (Array.isArray(payload)) return payload.filter(isRecord)
  if (isRecord(payload)) {
    for (const key of ["items", "results", "data"]) {
      const value = payload[key]
      if (Array.isArray(value)) return value.filter(isRecord)
    }
  }
  return []
}


export function mapAuditLogEntry(raw: RawRecord): AuditLogEntry {
  return {
    id: readText(raw, "id", "audit_log_id", "auditLogId") ?? "",
    occurredAt: readText(raw, "occurred_at", "occurredAt") ?? "",
    actorId: readText(raw, "actor_id", "actorId"),
    actorName: readText(raw, "actor_name", "actorName"),
    traceId: readText(raw, "trace_id", "traceId"),
    action: readText(raw, "action", "action_code", "actionCode") ?? "",
    objectType: readText(raw, "object_type", "objectType"),
    objectId: readText(raw, "object_id", "objectId"),
    reason: readText(raw, "reason", "change_reason", "changeReason"),
    source: readText(raw, "source", "source_system", "sourceSystem"),
  }
}


export function mapAuditLogPage(payload: unknown): AuditLogPage {
  const record = isRecord(payload) ? payload : {}
  return {
    items: readItems(payload).map(mapAuditLogEntry),
    total: readNumber(record, "total", "count"),
    page: readNumber(record, "page", "page_no", "pageNo"),
    pageSize: readNumber(record, "page_size", "pageSize"),
  }
}


export function mapActionCount(raw: RawRecord): AuditActionCount {
  return {
    code: readText(raw, "code", "action", "action_code", "actionCode") ?? "",
    count: readNumber(raw, "count", "total"),
  }
}


export function mapAuditActor(raw: RawRecord): AuditActor {
  const id = readText(raw, "id", "user_id", "userId") ?? ""
  const displayName = readText(raw, "display_name", "displayName")
  const username = readText(raw, "username", "login_name", "loginName")
  return { id, name: displayName ?? username ?? id }
}


export function buildAuditLogQuery(filters: AuditLogFilters, pagination?: AuditLogPagination): string {
  const params = new URLSearchParams()
  if (filters.occurredFrom) params.set("occurred_from", filters.occurredFrom)
  if (filters.occurredTo) params.set("occurred_to", filters.occurredTo)
  if (filters.actorId) params.set("actor_id", filters.actorId)
  if (filters.action) params.set("action", filters.action)
  if (filters.objectType) params.set("object_type", filters.objectType)
  if (filters.traceId) params.set("trace_id", filters.traceId)
  if (pagination) {
    params.set("page", String(pagination.page))
    params.set("page_size", String(pagination.pageSize))
  }
  return params.toString()
}


function normalizeFilename(filename: string): string {
  const trimmed = filename.trim()
  if (!trimmed || trimmed === SHARED_CLIENT_FALLBACK_FILENAME) return FALLBACK_EXPORT_FILENAME
  return trimmed
}


export const auditApi = {
  async list(token: string, filters: AuditLogFilters, pagination: AuditLogPagination): Promise<AuditLogPage> {
    const query = buildAuditLogQuery(filters, pagination)
    const payload = await apiRequest<unknown>(`/api/v1/platform/audit-logs?${query}`, token)
    return mapAuditLogPage(payload)
  },

  async actions(token: string): Promise<readonly AuditActionCount[]> {
    const payload = await apiRequest<unknown>("/api/v1/platform/audit-logs/actions", token)
    return readItems(payload)
      .map(mapActionCount)
      .filter((item) => item.code !== "")
  },

  /**
   * Requirement: P-13 — 操作人下拉改用审计专用只读端点 GET /api/v1/platform/audit/actors。
   * 原先复用主管理员专用的 /api/v1/platform/users（权限码 `*`），
   * 导致持有 DATA_GOVERNANCE_ADMIN 的治理管理员必然 403、下拉恒为空。
   * 新端点只返回 id + display_name + username，按 display_name 升序。
   */
  async actors(token: string): Promise<readonly AuditActor[]> {
    const payload = await apiRequest<unknown>("/api/v1/platform/audit/actors", token)
    return readItems(payload)
      .map(mapAuditActor)
      .filter((item) => item.id !== "")
  },

  async exportCsv(token: string, filters: AuditLogFilters): Promise<AuditCsvDownload> {
    const query = buildAuditLogQuery(filters)
    const download = await apiDownload(`/api/v1/platform/audit-logs/export?${query}`, token)
    return { blob: download.blob, filename: normalizeFilename(download.filename) }
  },
}
