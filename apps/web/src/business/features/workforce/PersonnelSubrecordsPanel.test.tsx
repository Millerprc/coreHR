import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { PersonnelSubrecordsPanel } from "./PersonnelSubrecordsPanel"


const personId = "60000000-0000-0000-0000-000000000009"
const documentId = "62000000-0000-0000-0000-000000000009"


describe("PersonnelSubrecordsPanel", () => {
  beforeEach(() => vi.restoreAllMocks())

  it("keeps sensitive values masked until an audited reveal reason is submitted", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      if (path.includes("/sensitive-values/document/") && init?.method === "POST") {
        expect(JSON.parse(String(init.body))).toEqual({ reason: "Synthetic verification" })
        return Response.json({ value: "SYN199001010001" })
      }
      if (path.endsWith(`/workforce/persons/${personId}/documents`)) {
        return Response.json([{
          id: documentId,
          person_id: personId,
          document_type_code: "SYNTHETIC_ID",
          masked_document_number: "SYN********0001",
          issuing_country_code: "CN",
          issue_date: null,
          expiry_date: null,
          is_primary: true,
          verification_status: "unverified",
          effective_from: "2026-08-12",
          effective_to: null,
        }])
      }
      return Response.json([])
    })
    vi.stubGlobal("fetch", fetchMock)

    render(<PersonnelSubrecordsPanel token="synthetic-token" personId={personId} canAdmin />)

    expect(await screen.findByText("SYN********0001")).toBeInTheDocument()
    expect(screen.queryByText("SYN199001010001")).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "查看明文" }))
    fireEvent.change(screen.getByLabelText("查看原因"), { target: { value: "Synthetic verification" } })
    fireEvent.click(screen.getByRole("button", { name: "确认查看" }))

    expect(await screen.findByText("SYN199001010001")).toBeInTheDocument()
  })

  it("expires a sensitive record without deleting it", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      if (path.endsWith(`/records/document/${documentId}/expire`) && init?.method === "POST") {
        expect(JSON.parse(String(init.body))).toEqual({
          effective_to: "2026-08-31",
          reason: "Synthetic expiry",
        })
        return Response.json({})
      }
      if (path.endsWith(`/workforce/persons/${personId}/documents`)) {
        return Response.json([{
          id: documentId,
          person_id: personId,
          document_type_code: "SYNTHETIC_ID",
          masked_document_number: "SYN********0001",
          issuing_country_code: "CN",
          issue_date: null,
          expiry_date: null,
          is_primary: true,
          verification_status: "verified",
          effective_from: "2026-08-12",
          effective_to: null,
        }])
      }
      return Response.json([])
    })
    vi.stubGlobal("fetch", fetchMock)

    render(<PersonnelSubrecordsPanel token="synthetic-token" personId={personId} canAdmin />)

    fireEvent.click(await screen.findByRole("button", { name: /失\s*效/ }))
    fireEvent.change(screen.getByLabelText("失效日期"), { target: { value: "2026-08-31" } })
    fireEvent.change(screen.getByLabelText("操作原因"), { target: { value: "Synthetic expiry" } })
    fireEvent.click(screen.getByRole("button", { name: "确认失效" }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/workforce/persons/${personId}/records/document/${documentId}/expire`,
      expect.objectContaining({ method: "POST" }),
    ))
  })

  it("corrects a document while keeping its current plaintext masked", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      if (path.endsWith(`/documents/${documentId}`) && init?.method === "PATCH") {
        expect(JSON.parse(String(init.body))).toEqual({
          expiry_date: "2027-08-31",
          change_reason: "Synthetic correction",
        })
        return Response.json({})
      }
      if (path.endsWith(`/workforce/persons/${personId}/documents`)) {
        return Response.json([{
          id: documentId,
          person_id: personId,
          document_type_code: "SYNTHETIC_ID",
          masked_document_number: "SYN********0001",
          issuing_country_code: "CN",
          issue_date: "2026-01-01",
          expiry_date: null,
          is_primary: true,
          verification_status: "verified",
          effective_from: "2026-08-12",
          effective_to: null,
        }])
      }
      return Response.json([])
    })
    vi.stubGlobal("fetch", fetchMock)

    render(<PersonnelSubrecordsPanel token="synthetic-token" personId={personId} canAdmin />)

    fireEvent.click(await screen.findByRole("button", { name: /更\s*正/ }))
    expect(screen.getByLabelText("新证件号码")).toHaveValue("")
    fireEvent.change(screen.getByLabelText("到期日期"), { target: { value: "2027-08-31" } })
    fireEvent.change(screen.getByLabelText("操作原因"), { target: { value: "Synthetic correction" } })
    fireEvent.click(screen.getByRole("button", { name: "保存更正" }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/workforce/persons/${personId}/documents/${documentId}`,
      expect.objectContaining({ method: "PATCH" }),
    ))
  })
})
