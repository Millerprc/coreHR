export interface CsvImportRow {
  readonly source_record_id: string
  readonly data: Readonly<Record<string, string | number>>
}


export function parseCsv(content: string): string[][] {
  const rows: string[][] = []
  let row: string[] = []
  let field = ""
  let quoted = false

  for (let index = 0; index < content.length; index += 1) {
    const character = content[index]
    if (quoted) {
      if (character === '"') {
        if (content[index + 1] === '"') {
          field += '"'
          index += 1
        } else {
          quoted = false
        }
      } else {
        field += character
      }
      continue
    }
    if (character === '"' && field.length === 0) {
      quoted = true
    } else if (character === ",") {
      row.push(field)
      field = ""
    } else if (character === "\n") {
      row.push(field.replace(/\r$/, ""))
      if (row.some((value) => value.trim())) rows.push(row)
      row = []
      field = ""
    } else {
      field += character
    }
  }
  if (quoted) throw new Error("CSV存在未闭合的引号")
  row.push(field.replace(/\r$/, ""))
  if (row.some((value) => value.trim())) rows.push(row)
  if (rows[0]?.[0]) rows[0][0] = rows[0][0].replace(/^\uFEFF/, "")
  return rows
}


export function csvToImportRows(
  content: string,
  columns: readonly string[],
  requiredColumns: readonly string[],
): CsvImportRow[] {
  const matrix = parseCsv(content)
  if (matrix.length < 2) throw new Error("CSV至少需要表头和一行数据")
  const headers = matrix[0].map((value) => value.trim())
  if (new Set(headers).size !== headers.length) throw new Error("CSV表头不能重复")
  const allowed = new Set(["source_record_id", ...columns])
  const unexpected = headers.filter((header) => !allowed.has(header))
  if (unexpected.length) throw new Error(`存在不支持的列：${unexpected.join("、")}`)
  const missing = ["source_record_id", ...requiredColumns].filter(
    (column) => !headers.includes(column),
  )
  if (missing.length) throw new Error(`缺少必填列：${missing.join("、")}`)

  const sourceIds = new Set<string>()
  const result = matrix.slice(1).map((values, rowIndex) => {
    if (values.length > headers.length) throw new Error(`第 ${rowIndex + 2} 行列数超过表头`)
    const record = Object.fromEntries(
      headers.map((header, index) => [header, (values[index] ?? "").trim()]),
    )
    const sourceId = record.source_record_id
    if (!sourceId) throw new Error(`第 ${rowIndex + 2} 行缺少来源记录ID`)
    if (sourceIds.has(sourceId)) throw new Error(`来源记录ID不能重复：${sourceId}`)
    sourceIds.add(sourceId)
    const missingValues = requiredColumns.filter((column) => !record[column])
    if (missingValues.length) {
      throw new Error(`第 ${rowIndex + 2} 行缺少必填值：${missingValues.join("、")}`)
    }
    const data: Record<string, string | number> = {}
    for (const column of columns) {
      const value = record[column]
      if (!value) continue
      data[column] = column === "sort_order" ? Number(value) : value
      if (column === "sort_order" && !Number.isInteger(data[column])) {
        throw new Error(`第 ${rowIndex + 2} 行排序号必须是整数`)
      }
    }
    return { source_record_id: sourceId, data }
  })
  if (result.length > 1000) throw new Error("单批最多允许1000行，请拆分文件")
  return result
}
