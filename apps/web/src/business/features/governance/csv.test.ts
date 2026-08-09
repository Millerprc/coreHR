import { describe, expect, it } from "vitest"

import { csvToImportRows, parseCsv } from "./csv"


describe("governance CSV parser", () => {
  it("parses quoted commas and escaped quotes", () => {
    expect(parseCsv('source_record_id,code,name\r\n1,REGULAR,"正式,员工"\r\n2,OTHER,"含""引号"""')).toEqual([
      ["source_record_id", "code", "name"],
      ["1", "REGULAR", "正式,员工"],
      ["2", "OTHER", '含"引号"'],
    ])
  })

  it("builds typed import rows and omits empty optional cells", () => {
    expect(csvToImportRows(
      "source_record_id,dictionary_code,code,name,sort_order,parent_item_code\n1,EMPLOYEE_TYPE,REGULAR,正式员工,10,",
      ["dictionary_code", "code", "name", "sort_order", "parent_item_code"],
      ["dictionary_code", "code", "name"],
    )).toEqual([
      {
        source_record_id: "1",
        data: {
          dictionary_code: "EMPLOYEE_TYPE",
          code: "REGULAR",
          name: "正式员工",
          sort_order: 10,
        },
      },
    ])
  })

  it("rejects missing required columns and duplicate source ids", () => {
    expect(() => csvToImportRows(
      "source_record_id,code\n1,REGULAR",
      ["code", "name"],
      ["code", "name"],
    )).toThrow("缺少必填列：name")
    expect(() => csvToImportRows(
      "source_record_id,code,name\n1,A,甲\n1,B,乙",
      ["code", "name"],
      ["code", "name"],
    )).toThrow("来源记录ID不能重复：1")
  })

  it("rejects columns outside the selected master-data template", () => {
    expect(() => csvToImportRows(
      "source_record_id,code,name,personal_phone\n1,REGULAR,正式员工,synthetic",
      ["code", "name"],
      ["code", "name"],
    )).toThrow("存在不支持的列：personal_phone")
  })
})
