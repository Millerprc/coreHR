export type ImportEntityType =
  | "dictionary"
  | "dictionary_item"
  | "organization_type"
  | "legal_entity"
  | "job"
  | "organization"


export interface ImportTemplate {
  readonly entity_type: ImportEntityType
  readonly columns: readonly string[]
  readonly required_columns: readonly string[]
}


export interface ImportRowError {
  readonly code: string
  readonly field: string | null
  readonly message: string
}


export interface ImportBatchRow {
  readonly id: string
  readonly row_number: number
  readonly source_record_id: string
  readonly status: string
  readonly errors: readonly ImportRowError[]
  readonly target_type: string | null
  readonly target_id: string | null
}


export interface ImportBatchSummary {
  readonly id: string
  readonly entity_type: ImportEntityType
  readonly source_system: string
  readonly source_table: string
  readonly file_name: string | null
  readonly idempotency_key: string
  readonly status: string
  readonly total_rows: number
  readonly valid_rows: number
  readonly rejected_rows: number
  readonly imported_rows: number
  readonly skipped_rows: number
  readonly created_by: string
  readonly executed_at: string | null
  readonly created_at: string
  readonly updated_at: string
}


export interface ImportBatch extends ImportBatchSummary {
  readonly rows: readonly ImportBatchRow[]
}


export interface ImportBatchList {
  readonly items: readonly ImportBatchSummary[]
  readonly total: number
  readonly limit: number
  readonly offset: number
}
