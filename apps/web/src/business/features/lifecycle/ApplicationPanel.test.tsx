import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ApplicationPanel } from "./ApplicationPanel"


const page = (items: readonly unknown[]) => ({ items, total: items.length, limit: 200, offset: 0 })


describe("ApplicationPanel", () => {
  beforeEach(() => vi.restoreAllMocks())

  it("confirms an offer through the pending-start hire command", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      if (path.includes("/lifecycle/candidates?")) return Response.json(page([{
        id: "candidate-1",
        candidate_number: "C000000001",
        display_name: "Synthetic candidate",
        contact_payload: {},
        status: "active",
        linked_person_id: null,
        created_at: "2026-08-09T00:00:00Z",
        updated_at: "2026-08-09T00:00:00Z",
      }]))
      if (path.includes("/lifecycle/applications?")) return Response.json(page([{
        id: "application-1",
        candidate_id: "candidate-1",
        recruitment_request_id: "request-1",
        status: "offer",
        current_stage: "offer",
        offer_payload: {},
      }]))
      if (path.includes("/lifecycle/recruitment-requests?")) return Response.json(page([{
        id: "request-1",
        request_number: "R000000001",
        organization_id: "organization-1",
        job_id: "job-1",
        requested_count: 1,
        target_month: "2026-09-01",
        status: "submitted",
        reason: "Synthetic request",
        workflow_instance_id: null,
      }]))
      if (path.includes("/workforce/legal-entities?")) return Response.json(page([{
        id: "legal-1",
        code: "LE-SYN",
        name: "Synthetic legal entity",
        country_code: "CN",
        status: "active",
        effective_from: "2026-01-01",
        effective_to: null,
      }]))
      if (path.includes("/workforce/persons?")) return Response.json(page([]))
      if (path.endsWith("/lifecycle/applications/application-1/hire") && init?.method === "POST") {
        return Response.json({
          id: "conversion-1",
          application_id: "application-1",
          candidate_id: "candidate-1",
          person_id: "person-1",
          employment_id: "employment-1",
          assignment_id: "assignment-1",
          idempotency_key: "00000000-0000-4000-8000-000000000001",
          planned_start_date: "2026-09-01",
          employee_type_code: "REGULAR",
          converted_by: "admin-1",
          converted_at: "2026-08-09T00:00:00Z",
          created_at: "2026-08-09T00:00:00Z",
          updated_at: "2026-08-09T00:00:00Z",
        }, { status: 201 })
      }
      return Response.json({}, { status: 404 })
    })
    vi.stubGlobal("fetch", fetchMock)

    render(<ApplicationPanel token="synthetic-token" canAdmin />)

    fireEvent.click(await screen.findByRole("button", { name: "确认录用" }))
    const dialog = await screen.findByRole("dialog", { name: "确认录用并创建待入职档案" })
    fireEvent.change(within(dialog).getByLabelText("计划入职日期"), {
      target: { value: "2026-09-01" },
    })
    fireEvent.change(within(dialog).getByLabelText("录用原因"), {
      target: { value: "Synthetic accepted offer" },
    })
    fireEvent.click(within(dialog).getByRole("button", { name: "确认录用" }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/v1/lifecycle/applications/application-1/hire",
        expect.objectContaining({ method: "POST" }),
      )
    })
    const hireCall = fetchMock.mock.calls.find(([input, init]) => (
      String(input).endsWith("/lifecycle/applications/application-1/hire")
      && init?.method === "POST"
    ))
    const body = JSON.parse(String(hireCall?.[1]?.body)) as Record<string, unknown>
    expect(body).toMatchObject({
      planned_start_date: "2026-09-01",
      employee_type_code: "REGULAR",
      contract_legal_entity_id: "legal-1",
      reason: "Synthetic accepted offer",
    })
    expect(body.idempotency_key).toMatch(/^[0-9a-f-]{36}$/)
  }, 15_000)
})
