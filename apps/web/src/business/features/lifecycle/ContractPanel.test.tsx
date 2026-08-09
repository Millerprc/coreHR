import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { ContractPanel } from "./ContractPanel"


const page = (items: readonly unknown[]) => ({ items, total: items.length, limit: 200, offset: 0 })


describe("ContractPanel", () => {
  beforeEach(() => vi.restoreAllMocks())
  afterEach(() => vi.unstubAllGlobals())

  it("submits an auditable contract amendment command", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      if (path.includes("/contracts/expiry-alerts")) return Response.json({
        items: [{
          contract_id: "contract-1",
          contract_number: "SYN-CONTRACT-001",
          person_id: "person-1",
          effective_to: "2026-09-08",
          expiry_notice_days: 45,
          days_remaining: 30,
          status: "active",
        }],
        total: 1,
      })
      if (path.includes("/lifecycle/contracts?")) return Response.json(page([{
        id: "contract-1",
        person_id: "person-1",
        employment_id: "employment-1",
        agreement_relationship_id: null,
        predecessor_contract_id: null,
        contract_type_code: "LABOR",
        contract_number: "SYN-CONTRACT-001",
        legal_entity_id: "legal-1",
        signed_on: "2025-09-01",
        effective_from: "2025-09-09",
        effective_to: "2026-09-08",
        expiry_notice_days: 45,
        version: 1,
        status: "active",
        metadata_payload: {},
      }]))
      if (path.includes("/workforce/persons?")) return Response.json(page([{
        id: "person-1",
        employee_number: "990001",
        display_name: "Synthetic employee",
        former_name: null,
        gender_code: null,
        birth_date: null,
        nationality_code: null,
        country_code: "CN",
        status: "active",
      }]))
      if (path.includes("/workforce/legal-entities?")) return Response.json(page([{
        id: "legal-1",
        code: "LE-SYN",
        name: "Synthetic legal entity",
        country_code: "CN",
        status: "active",
        effective_from: "2025-01-01",
        effective_to: null,
      }]))
      if (path.endsWith("/lifecycle/contracts/contract-1/actions") && init?.method === "POST") {
        return Response.json({
          id: "event-1",
          event_number: "E0000000001",
          idempotency_key: "00000000-0000-4000-8000-000000000001",
          event_type: "CONTRACT_AMENDMENT",
          object_type: "contract",
          object_id: "contract-1",
          effective_date: "2026-08-09",
          status: "completed",
          source: "api",
          reason: "Synthetic amendment",
          before_payload: {},
          planned_payload: {},
          actual_payload: {},
          workflow_instance_id: null,
          related_event_id: null,
          attempts: 1,
          last_error: null,
          executed_at: "2026-08-09T00:00:00Z",
          version: 1,
        }, { status: 201 })
      }
      return Response.json({}, { status: 404 })
    })
    vi.stubGlobal("fetch", fetchMock)
    vi.stubGlobal("crypto", {
      randomUUID: () => "00000000-0000-4000-8000-000000000001",
    })

    render(<ContractPanel token="synthetic-token" canAdmin />)

    expect(await screen.findByText("未来 90 天有 1 份合同进入到期提醒期")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "处理" }))
    const dialog = await screen.findByRole("dialog", { name: "处理合同：SYN-CONTRACT-001" })
    fireEvent.change(within(dialog).getByLabelText("变更后结束日"), {
      target: { value: "2026-12-31" },
    })
    fireEvent.change(within(dialog).getByLabelText("处理原因"), {
      target: { value: "Synthetic amendment" },
    })
    fireEvent.click(within(dialog).getByRole("button", { name: /提\s*交/ }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/v1/lifecycle/contracts/contract-1/actions",
        expect.objectContaining({ method: "POST" }),
      )
    })
    const actionCall = fetchMock.mock.calls.find(([input, init]) => (
      String(input).endsWith("/lifecycle/contracts/contract-1/actions")
      && init?.method === "POST"
    ))
    const body = JSON.parse(String(actionCall?.[1]?.body)) as Record<string, unknown>
    expect(body).toMatchObject({
      idempotency_key: "00000000-0000-4000-8000-000000000001",
      action_type: "amendment",
      execution_mode: "direct",
      reason: "Synthetic amendment",
      amendment: { effective_to: "2026-12-31" },
    })
  }, 15_000)
})
