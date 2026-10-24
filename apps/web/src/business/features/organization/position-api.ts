// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { apiRequest } from "../../client"


// Requirement: ORG-PROT-001 / D-087 — 职位管理把后端既有职务体系显性化为独立宿主页，
// 前端只按后端 contracts 字段组织请求与响应，不新增领域模型。

export type PositionDimensionType = "LEVEL" | "GRADE" | "CLASS" | "SEQUENCE"


export interface Position {
  readonly id: string
  readonly code: string
  readonly name: string
  readonly level_code: string
  readonly grade_code: string
  readonly class_code: string
  readonly sequence_code: string
  readonly status: string
  readonly effective_from: string
  readonly effective_to: string | null
  readonly version: number
  readonly source_job_id: string | null
  readonly notes: string | null
  readonly attributes: Readonly<Record<string, unknown>>
}


export interface PositionDimension {
  readonly id: string
  readonly dimension_type: PositionDimensionType
  readonly code: string
  readonly name: string
  readonly parent_dimension_id: string | null
  readonly parent_dimension_type: PositionDimensionType | null
  readonly parent_dimension_code: string | null
  readonly sort_order: number
  readonly status: string
  readonly effective_from: string
  readonly effective_to: string | null
  readonly version: number
  readonly notes: string | null
}


export interface PositionPage<T> {
  readonly items: readonly T[]
  readonly total: number
  readonly limit: number
  readonly offset: number
}


export interface PositionListQuery {
  readonly effectiveAt?: string
  readonly limit?: number
  readonly offset?: number
  readonly dimensionType?: PositionDimensionType
}


export interface PositionVersionPayload {
  readonly name: string
  readonly level_code: string
  readonly grade_code: string
  readonly class_code: string
  readonly sequence_code: string
  readonly status: string
  readonly effective_from: string
  readonly effective_to?: string
  readonly source_job_id?: string
  readonly notes?: string
  readonly attributes?: Record<string, unknown>
  readonly change_reason: string
}


export interface PositionCreatePayload extends PositionVersionPayload {
  readonly code: string
}


export interface PositionDimensionVersionPayload {
  readonly name: string
  readonly parent_dimension_type?: PositionDimensionType
  readonly parent_dimension_code?: string
  readonly sort_order: number
  readonly status: string
  readonly effective_from: string
  readonly effective_to?: string
  readonly notes?: string
  readonly change_reason: string
}


export interface PositionDimensionCreatePayload extends PositionDimensionVersionPayload {
  readonly dimension_type: PositionDimensionType
  readonly code: string
}


function listQuery(query: PositionListQuery): string {
  const params = new URLSearchParams()
  if (query.effectiveAt) params.set("effective_at", query.effectiveAt)
  if (query.limit !== undefined) params.set("limit", String(query.limit))
  if (query.offset !== undefined) params.set("offset", String(query.offset))
  if (query.dimensionType) params.set("dimension_type", query.dimensionType)
  return params.toString()
}


export const positionApi = {
  positions: (token: string, query: PositionListQuery = {}) =>
    apiRequest<PositionPage<Position>>(`/api/v1/workforce/jobs?${listQuery(query)}`, token),
  createPosition: (token: string, body: PositionCreatePayload) =>
    apiRequest<Position>("/api/v1/workforce/jobs", token, { method: "POST", body }),
  createPositionVersion: (token: string, positionId: string, body: PositionVersionPayload) =>
    apiRequest<Position>(
      `/api/v1/workforce/jobs/${positionId}/versions`,
      token,
      { method: "POST", body },
    ),
  dimensions: (token: string, query: PositionListQuery = {}) =>
    apiRequest<PositionPage<PositionDimension>>(
      `/api/v1/workforce/job-dimensions?${listQuery(query)}`,
      token,
    ),
  createDimension: (token: string, body: PositionDimensionCreatePayload) =>
    apiRequest<PositionDimension>(
      "/api/v1/workforce/job-dimensions",
      token,
      { method: "POST", body },
    ),
  createDimensionVersion: (
    token: string,
    dimensionId: string,
    body: PositionDimensionVersionPayload,
  ) =>
    apiRequest<PositionDimension>(
      `/api/v1/workforce/job-dimensions/${dimensionId}/versions`,
      token,
      { method: "POST", body },
    ),
}
