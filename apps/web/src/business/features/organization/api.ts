import { ApiClientError, apiRequest } from "../../client"
import type {
  BpMembership,
  CostAllocation,
  CostCenter,
  DirectoryOption,
  Organization,
  OrganizationRelations,
  OrganizationTreeNode,
  OrganizationType,
  PageResponse,
  RevenueAggregation,
  RevenueTarget,
} from "./types"


export function command(expectedVersion: number, changeReason: string) {
  return {
    expected_version: expectedVersion,
    idempotency_key: crypto.randomUUID(),
    change_reason: changeReason,
  }
}


export const organizationApi = {
  types: (token: string) =>
    apiRequest<readonly OrganizationType[]>("/api/v1/organization-types", token),
  createType: (token: string, body: unknown) =>
    apiRequest<OrganizationType>("/api/v1/organization-types", token, { method: "POST", body }),
  updateType: (token: string, id: string, body: unknown) =>
    apiRequest<OrganizationType>(`/api/v1/organization-types/${id}`, token, { method: "PATCH", body }),
  tree: (token: string) =>
    apiRequest<readonly OrganizationTreeNode[]>("/api/v1/organizations/tree", token),
  organization: (token: string, id: string, effectiveAt: string) =>
    apiRequest<Organization>(
      `/api/v1/organizations/${id}?effective_at=${encodeURIComponent(effectiveAt)}`,
      token,
    ),
  createOrganization: (token: string, body: unknown) =>
    apiRequest<Organization>("/api/v1/organizations", token, { method: "POST", body }),
  scheduleVersion: (token: string, id: string, body: unknown) =>
    apiRequest(`/api/v1/organizations/${id}/versions`, token, { method: "POST", body }),
  cancelEvent: (token: string, id: string, body: unknown) =>
    apiRequest(`/api/v1/organization-events/${id}/cancel`, token, { method: "POST", body }),
  relations: (token: string, id: string, effectiveAt: string) =>
    apiRequest<OrganizationRelations>(
      `/api/v1/organizations/${id}/relations?effective_at=${encodeURIComponent(effectiveAt)}`,
      token,
    ),
  setLegalEntities: (token: string, id: string, body: unknown) =>
    apiRequest(`/api/v1/organizations/${id}/legal-entities`, token, { method: "PUT", body }),
  setLeaders: (token: string, id: string, body: unknown) =>
    apiRequest(`/api/v1/organizations/${id}/leaders`, token, { method: "PUT", body }),
  createBpMembership: (token: string, body: unknown) =>
    apiRequest<BpMembership>("/api/v1/bp-memberships", token, { method: "POST", body }),
  bpMembership: (token: string, id: string) =>
    apiRequest<BpMembership>(`/api/v1/bp-memberships/${id}`, token),
  setBpScopes: (token: string, id: string, body: unknown) =>
    apiRequest<BpMembership>(`/api/v1/bp-memberships/${id}/service-scopes`, token, {
      method: "PUT",
      body,
    }),
  costCenters: (token: string) =>
    apiRequest<readonly CostCenter[]>("/api/v1/cost-centers", token),
  createCostCenter: (token: string, body: unknown) =>
    apiRequest<CostCenter>("/api/v1/cost-centers", token, { method: "POST", body }),
  allocation: async (token: string, id: string, effectiveAt: string) => {
    try {
      return await apiRequest<CostAllocation>(
        `/api/v1/organizations/${id}/cost-allocation?effective_at=${encodeURIComponent(effectiveAt)}`,
        token,
      )
    } catch (caught) {
      if (caught instanceof ApiClientError && caught.status === 404) return null
      throw caught
    }
  },
  setAllocation: (token: string, id: string, body: unknown) =>
    apiRequest<CostAllocation>(`/api/v1/organizations/${id}/cost-allocation`, token, {
      method: "PUT",
      body,
    }),
  revenue: (token: string, id: string, year: number, descendants: boolean) =>
    apiRequest<RevenueAggregation>(
      `/api/v1/organizations/${id}/revenue-targets?year=${year}&include_descendants=${descendants}`,
      token,
    ),
  setRevenue: (token: string, id: string, year: number, currency: string, body: unknown) =>
    apiRequest<RevenueTarget>(
      `/api/v1/organizations/${id}/revenue-targets/${year}/${currency}`,
      token,
      { method: "PUT", body },
    ),
  legalEntities: (token: string) =>
    apiRequest<PageResponse<DirectoryOption>>(
      "/api/v1/workforce/legal-entities?limit=200&offset=0",
      token,
    ),
  persons: (token: string) =>
    apiRequest<PageResponse<DirectoryOption>>(
      "/api/v1/workforce/persons?limit=200&offset=0",
      token,
    ),
}
