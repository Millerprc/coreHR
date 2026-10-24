// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { apiRequest } from "../../client"


export type ReportingRelationType = "direct" | "dotted"


export interface ReportingRelation {
  readonly id: string
  readonly managerPersonId: string
  readonly managerName: string
  readonly subordinatePersonId: string
  readonly subordinateName: string
  readonly relationType: ReportingRelationType
  readonly effectiveFrom: string
  readonly effectiveTo: string | null
}


export interface ReportingRelationPage {
  readonly items: readonly ReportingRelation[]
  readonly total: number
  readonly page: number
  readonly pageSize: number
}


export interface ReportingRelationQuery {
  readonly effectiveAt?: string
  readonly managerPersonId?: string
  readonly subordinatePersonId?: string
  readonly page?: number
  readonly pageSize?: number
}


export interface CreateReportingRelationInput {
  readonly managerPersonId: string
  readonly subordinatePersonId: string
  readonly relationType: ReportingRelationType
  readonly effectiveFrom: string
  readonly effectiveTo?: string
}


export interface PersonOption {
  readonly id: string
  readonly displayName: string
  readonly employeeNumber: string | null
}


// 后端汇报关系响应按 snake_case 命名；本文件是唯一的后端字段映射点，
// 后端契约变化时只改这里，页面与测试继续使用 camelCase 的领域类型。
interface ReportingRelationPayload {
  readonly id?: string
  readonly manager_person_id?: string
  readonly manager_name?: string | null
  readonly subordinate_person_id?: string
  readonly subordinate_name?: string | null
  readonly relation_type?: string | null
  readonly effective_from?: string | null
  readonly effective_to?: string | null
}


interface ReportingRelationPagePayload {
  readonly items?: readonly ReportingRelationPayload[]
  readonly total?: number
  readonly page?: number
  readonly page_size?: number
}


interface PersonPayload {
  readonly id?: string
  readonly display_name?: string | null
  readonly employee_number?: string | null
}


interface PersonPagePayload {
  readonly items?: readonly PersonPayload[]
  readonly total?: number
}


const REPORTING_RELATIONS_PATH = "/api/v1/workforce/reporting-relations"
const PERSONS_PATH = "/api/v1/workforce/persons"
const DEFAULT_PAGE_SIZE = 20
const PERSON_SEARCH_LIMIT = 200


function toRelationType(value: string | null | undefined): ReportingRelationType {
  // Requirement: ORG-REPORT-001 — 汇报关系类型只允许实线 direct 与虚线 dotted，
  // 历史数据中的其他写法统一按实线处理。
  return value === "dotted" ? "dotted" : "direct"
}


function mapRelation(payload: ReportingRelationPayload): ReportingRelation {
  return {
    id: payload.id ?? "",
    managerPersonId: payload.manager_person_id ?? "",
    managerName: payload.manager_name ?? "",
    subordinatePersonId: payload.subordinate_person_id ?? "",
    subordinateName: payload.subordinate_name ?? "",
    relationType: toRelationType(payload.relation_type),
    effectiveFrom: payload.effective_from ?? "",
    effectiveTo: payload.effective_to ?? null,
  }
}


function mapRelationPage(payload: ReportingRelationPagePayload): ReportingRelationPage {
  const items = (payload.items ?? []).map(mapRelation)
  return {
    items,
    total: payload.total ?? items.length,
    page: payload.page ?? 1,
    pageSize: payload.page_size ?? items.length,
  }
}


function mapPerson(payload: PersonPayload): PersonOption {
  return {
    id: payload.id ?? "",
    displayName: payload.display_name ?? payload.employee_number ?? "",
    employeeNumber: payload.employee_number ?? null,
  }
}


function buildQueryString(query: ReportingRelationQuery): string {
  const params = new URLSearchParams()
  if (query.effectiveAt) params.set("effective_at", query.effectiveAt)
  if (query.managerPersonId) params.set("manager_person_id", query.managerPersonId)
  if (query.subordinatePersonId) params.set("subordinate_person_id", query.subordinatePersonId)
  params.set("page", String(query.page ?? 1))
  params.set("page_size", String(query.pageSize ?? DEFAULT_PAGE_SIZE))
  return params.toString()
}


export const reportingApi = {
  list: async (
    token: string,
    query: ReportingRelationQuery = {},
  ): Promise<ReportingRelationPage> => {
    const payload = await apiRequest<ReportingRelationPagePayload>(
      `${REPORTING_RELATIONS_PATH}?${buildQueryString(query)}`,
      token,
    )
    return mapRelationPage(payload)
  },
  create: async (
    token: string,
    input: CreateReportingRelationInput,
  ): Promise<ReportingRelation> => {
    const payload = await apiRequest<ReportingRelationPayload>(REPORTING_RELATIONS_PATH, token, {
      method: "POST",
      body: {
        manager_person_id: input.managerPersonId,
        subordinate_person_id: input.subordinatePersonId,
        relation_type: input.relationType,
        effective_from: input.effectiveFrom,
        ...(input.effectiveTo ? { effective_to: input.effectiveTo } : {}),
      },
    })
    return mapRelation(payload)
  },
  remove: (token: string, relationId: string): Promise<void> =>
    apiRequest<void>(`${REPORTING_RELATIONS_PATH}/${relationId}`, token, { method: "DELETE" }),
  persons: async (token: string, search = ""): Promise<readonly PersonOption[]> => {
    const params = new URLSearchParams({ limit: String(PERSON_SEARCH_LIMIT), offset: "0" })
    if (search) params.set("search", search)
    const payload = await apiRequest<PersonPagePayload>(`${PERSONS_PATH}?${params.toString()}`, token)
    return (payload.items ?? []).map(mapPerson)
  },
}
