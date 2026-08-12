import { fireEvent, render, screen } from "@testing-library/react"
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
})
