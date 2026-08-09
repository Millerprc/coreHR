import { apiRequest } from "../../client"
import type { CsvImportRow } from "./csv"
import type {
  ImportBatch,
  ImportBatchList,
  ImportEntityType,
  ImportTemplate,
} from "./types"


export const governanceApi = {
  listBatches(token: string): Promise<ImportBatchList> {
    return apiRequest("/api/v1/governance/import-batches?limit=200&offset=0", token)
  },

  batch(token: string, batchId: string): Promise<ImportBatch> {
    return apiRequest(`/api/v1/governance/import-batches/${batchId}`, token)
  },

  template(token: string, entityType: ImportEntityType): Promise<ImportTemplate> {
    return apiRequest(`/api/v1/governance/import-templates/${entityType}`, token)
  },

  validate(
    token: string,
    payload: {
      readonly entity_type: ImportEntityType
      readonly source_system: string
      readonly source_table: string
      readonly file_name: string
      readonly idempotency_key: string
      readonly rows: readonly CsvImportRow[]
    },
  ): Promise<ImportBatch> {
    return apiRequest("/api/v1/governance/import-batches/validate", token, {
      method: "POST",
      body: payload,
    })
  },

  execute(token: string, batchId: string, reason: string): Promise<ImportBatch> {
    return apiRequest(`/api/v1/governance/import-batches/${batchId}/execute`, token, {
      method: "POST",
      body: { reason },
    })
  },
}
