// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { apiRequest } from "../../client"


// Requirement: ADR-0002 / D-067 — person_labels 目标模型必须保留标签来源、有效性和 AI 标记。
// 标签库是基础资料字典：第 0 级为标签类型，第 1 级为该类型下的标签项，前端一律通过接口读取，
// 不在页面里硬编码类型或标签项；后端字段命名（snake_case ↔ camelCase）只在本文件落地。

export interface PersonLabel {
  readonly id: string
  readonly personId: string
  readonly labelName: string
  readonly labelType: string
  readonly source: string
  readonly effectiveFrom: string
  readonly effectiveTo: string | null
  readonly status: string
  readonly isAiGenerated: boolean
}


export interface LabelTypeOption {
  readonly code: string
  readonly name: string
  readonly count: number
}


export interface PersonLabelList {
  readonly items: readonly PersonLabel[]
  readonly total: number
}


export interface CreatePersonLabelCommand {
  readonly labelName: string
  readonly labelType: string
  readonly source: string
  readonly effectiveFrom: string
  readonly effectiveTo: string | null
}


// 标签库第 1 级：某个标签类型下的标签项。
export interface LabelLibraryItem {
  readonly code: string
  readonly name: string
}


// 标签库第 0 级：标签类型及其标签项。
export interface LabelLibraryType {
  readonly typeCode: string
  readonly typeName: string
  readonly items: readonly LabelLibraryItem[]
}


// 批量打标签的单条条目，对应标签库里的一个标签项。
export interface BatchLabelEntry {
  readonly labelTypeCode: string
  readonly labelCode: string
}


export interface CreatePersonLabelsBatchCommand {
  readonly effectiveFrom: string
  readonly source: string
  readonly labels: readonly BatchLabelEntry[]
}


export interface PersonLabelBatchResult {
  readonly created: readonly PersonLabel[]
}


// 后端并行开发期间字段命名可能落在 snake_case 或 camelCase，两种写法都在此显式接收。
interface PersonLabelWire {
  readonly id: string
  readonly person_id?: string
  readonly label_name?: string
  readonly label_type?: string
  readonly source?: string
  readonly effective_from?: string
  readonly effective_to?: string | null
  readonly status?: string
  readonly is_ai_generated?: boolean
  readonly personId?: string
  readonly labelName?: string
  readonly labelType?: string
  readonly effectiveFrom?: string
  readonly effectiveTo?: string | null
  readonly isAiGenerated?: boolean
  readonly label_code?: string
  readonly labelCode?: string
  readonly label_type_code?: string
  readonly labelTypeCode?: string
}


interface PersonLabelListWire {
  readonly items?: readonly PersonLabelWire[]
  readonly total?: number
}


interface PersonLabelBatchWire {
  readonly created?: readonly PersonLabelWire[]
}


interface LabelTypeWire {
  readonly code?: string
  readonly name?: string
  readonly count?: number
}


interface LabelTypeListWire {
  readonly items?: readonly LabelTypeWire[]
}


interface LabelLibraryItemWire {
  readonly code?: string
  readonly name?: string
  readonly label_code?: string
  readonly label_name?: string
}


interface LabelLibraryTypeWire {
  readonly type_code?: string
  readonly type_name?: string
  readonly label_type_code?: string
  readonly label_type_name?: string
  readonly items?: readonly LabelLibraryItemWire[]
}


interface LabelLibraryWire {
  readonly items?: readonly LabelLibraryTypeWire[]
}


function mapPersonLabel(wire: PersonLabelWire): PersonLabel {
  return {
    id: wire.id,
    personId: wire.person_id ?? wire.personId ?? "",
    labelName: wire.label_name ?? wire.labelName ?? wire.label_code ?? wire.labelCode ?? "",
    labelType: wire.label_type ?? wire.labelType ?? wire.label_type_code ?? wire.labelTypeCode ?? "",
    source: wire.source ?? "MANUAL",
    effectiveFrom: wire.effective_from ?? wire.effectiveFrom ?? "",
    effectiveTo: wire.effective_to ?? wire.effectiveTo ?? null,
    status: wire.status ?? "",
    isAiGenerated: wire.is_ai_generated ?? wire.isAiGenerated ?? false,
  }
}


function mapLabelType(wire: LabelTypeWire): LabelTypeOption {
  const code = wire.code ?? ""
  return {
    code,
    name: wire.name ?? code,
    count: wire.count ?? 0,
  }
}


function mapLibraryItem(wire: LabelLibraryItemWire): LabelLibraryItem {
  const code = wire.code ?? wire.label_code ?? ""
  return {
    code,
    name: wire.name ?? wire.label_name ?? code,
  }
}


function mapLibraryType(wire: LabelLibraryTypeWire): LabelLibraryType {
  const typeCode = wire.type_code ?? wire.label_type_code ?? ""
  return {
    typeCode,
    typeName: wire.type_name ?? wire.label_type_name ?? typeCode,
    items: (wire.items ?? []).map(mapLibraryItem),
  }
}


export const labelApi = {
  personLabels: (token: string, personId: string, effectiveAt?: string): Promise<PersonLabelList> => {
    const query = effectiveAt ? `?effective_at=${encodeURIComponent(effectiveAt)}` : ""
    return apiRequest<PersonLabelListWire>(`/api/v1/workforce/persons/${personId}/labels${query}`, token)
      .then((wire) => {
        const items = (wire.items ?? []).map(mapPersonLabel)
        return { items, total: wire.total ?? items.length }
      })
  },
  labelTypes: (token: string): Promise<readonly LabelTypeOption[]> =>
    apiRequest<LabelTypeListWire>("/api/v1/workforce/label-types", token)
      .then((wire) => (wire.items ?? []).map(mapLabelType)),
  // 标签库是基础资料字典，只读；新建与扩展标签项属于基础资料模块，不在本面板。
  labelLibrary: (token: string): Promise<readonly LabelLibraryType[]> =>
    apiRequest<LabelLibraryWire>("/api/v1/workforce/label-library", token)
      .then((wire) => (wire.items ?? []).map(mapLibraryType)),
  createPersonLabel: (
    token: string,
    personId: string,
    command: CreatePersonLabelCommand,
  ): Promise<PersonLabel> =>
    apiRequest<PersonLabelWire>(`/api/v1/workforce/persons/${personId}/labels`, token, {
      method: "POST",
      body: {
        label_name: command.labelName,
        label_type: command.labelType,
        source: command.source,
        effective_from: command.effectiveFrom,
        effective_to: command.effectiveTo,
      },
    }).then(mapPersonLabel),
  // 批量打标签整批原子：任一条在标签库中找不到，后端整批 422 且不落数据。
  createPersonLabelsBatch: (
    token: string,
    personId: string,
    command: CreatePersonLabelsBatchCommand,
  ): Promise<PersonLabelBatchResult> =>
    apiRequest<PersonLabelBatchWire>(`/api/v1/workforce/persons/${personId}/labels/batch`, token, {
      method: "POST",
      body: {
        effective_from: command.effectiveFrom,
        source: command.source,
        labels: command.labels.map((item) => ({
          label_type_code: item.labelTypeCode,
          label_code: item.labelCode,
        })),
      },
    }).then((wire) => ({ created: (wire.created ?? []).map(mapPersonLabel) })),
  endPersonLabel: (token: string, labelId: string): Promise<void> =>
    apiRequest<void>(`/api/v1/workforce/person-labels/${labelId}`, token, { method: "DELETE" }),
}
