import { apiRequest } from "../../client"
import type {
  HeadcountFreeze,
  HeadcountResult,
  Job,
  JobDimension,
  LegalEntity,
  OccupancyRule,
  OrganizationOption,
  Page,
  Person,
  PersonArchive,
  PersonAddress,
  PersonContact,
  PersonDocument,
  EmergencyContact,
  EducationRecord,
  FamilyMember,
  WorkExperience,
  RecruitmentRequest,
} from "./types"


interface OrganizationTreeNode extends OrganizationOption {
  readonly children: readonly OrganizationTreeNode[]
}


function flattenOrganizations(nodes: readonly OrganizationTreeNode[]): readonly OrganizationOption[] {
  return nodes.flatMap((node) => [
    { id: node.id, code: node.code, name: node.name },
    ...flattenOrganizations(node.children),
  ])
}


export const workforceApi = {
  persons: (token: string, search = "") =>
    apiRequest<Page<Person>>(
      `/api/v1/workforce/persons?limit=200&offset=0${search ? `&search=${encodeURIComponent(search)}` : ""}`,
      token,
    ),
  personArchive: (token: string, personId: string) =>
    apiRequest<PersonArchive>(`/api/v1/workforce/persons/${personId}`, token),
  createPerson: (token: string, body: unknown) =>
    apiRequest<Person>("/api/v1/workforce/persons", token, { method: "POST", body }),
  updatePerson: (token: string, personId: string, body: unknown) =>
    apiRequest<Person>(`/api/v1/workforce/persons/${personId}`, token, { method: "PATCH", body }),
  personDocuments: (token: string, personId: string) =>
    apiRequest<readonly PersonDocument[]>(`/api/v1/workforce/persons/${personId}/documents`, token),
  createPersonDocument: (token: string, personId: string, body: unknown) =>
    apiRequest<PersonDocument>(`/api/v1/workforce/persons/${personId}/documents`, token, { method: "POST", body }),
  personContacts: (token: string, personId: string) =>
    apiRequest<readonly PersonContact[]>(`/api/v1/workforce/persons/${personId}/contacts`, token),
  createPersonContact: (token: string, personId: string, body: unknown) =>
    apiRequest<PersonContact>(`/api/v1/workforce/persons/${personId}/contacts`, token, { method: "POST", body }),
  personAddresses: (token: string, personId: string) =>
    apiRequest<readonly PersonAddress[]>(`/api/v1/workforce/persons/${personId}/addresses`, token),
  createPersonAddress: (token: string, personId: string, body: unknown) =>
    apiRequest<PersonAddress>(`/api/v1/workforce/persons/${personId}/addresses`, token, { method: "POST", body }),
  emergencyContacts: (token: string, personId: string) =>
    apiRequest<readonly EmergencyContact[]>(`/api/v1/workforce/persons/${personId}/emergency-contacts`, token),
  createEmergencyContact: (token: string, personId: string, body: unknown) =>
    apiRequest<EmergencyContact>(`/api/v1/workforce/persons/${personId}/emergency-contacts`, token, { method: "POST", body }),
  educationRecords: (token: string, personId: string) =>
    apiRequest<readonly EducationRecord[]>(`/api/v1/workforce/persons/${personId}/education-records`, token),
  createEducationRecord: (token: string, personId: string, body: unknown) =>
    apiRequest<EducationRecord>(`/api/v1/workforce/persons/${personId}/education-records`, token, { method: "POST", body }),
  workExperiences: (token: string, personId: string) =>
    apiRequest<readonly WorkExperience[]>(`/api/v1/workforce/persons/${personId}/work-experiences`, token),
  createWorkExperience: (token: string, personId: string, body: unknown) =>
    apiRequest<WorkExperience>(`/api/v1/workforce/persons/${personId}/work-experiences`, token, { method: "POST", body }),
  familyMembers: (token: string, personId: string) =>
    apiRequest<readonly FamilyMember[]>(`/api/v1/workforce/persons/${personId}/family-members`, token),
  createFamilyMember: (token: string, personId: string, body: unknown) =>
    apiRequest<FamilyMember>(`/api/v1/workforce/persons/${personId}/family-members`, token, { method: "POST", body }),
  updateSensitiveRecord: (
    token: string,
    personId: string,
    resourcePath: string,
    recordId: string,
    body: unknown,
  ) => apiRequest(
    `/api/v1/workforce/persons/${personId}/${resourcePath}/${recordId}`,
    token,
    { method: "PATCH", body },
  ),
  expireSensitiveRecord: (
    token: string,
    personId: string,
    recordType: string,
    recordId: string,
    effectiveTo: string,
    reason: string,
  ) => apiRequest(
    `/api/v1/workforce/persons/${personId}/records/${recordType}/${recordId}/expire`,
    token,
    { method: "POST", body: { effective_to: effectiveTo, reason } },
  ),
  revealSensitiveValue: (
    token: string,
    personId: string,
    recordType: string,
    recordId: string,
    fieldCode: string,
    reason: string,
  ) => apiRequest<{ readonly value: string }>(
    `/api/v1/workforce/persons/${personId}/sensitive-values/${recordType}/${recordId}/${fieldCode}/reveal`,
    token,
    { method: "POST", body: { reason } },
  ),
  createEmployment: (token: string, body: unknown) =>
    apiRequest("/api/v1/workforce/employments", token, { method: "POST", body }),
  createLegalEntityRelationVersion: (token: string, employmentId: string, body: unknown) =>
    apiRequest(`/api/v1/workforce/employments/${employmentId}/legal-entity-relations`, token, { method: "POST", body }),
  createAssignment: (token: string, body: unknown) =>
    apiRequest("/api/v1/workforce/employment-assignments", token, { method: "POST", body }),
  createAgreement: (token: string, body: unknown) =>
    apiRequest("/api/v1/workforce/agreement-relationships", token, { method: "POST", body }),
  jobs: (token: string, effectiveAt?: string) => apiRequest<Page<Job>>(
    `/api/v1/workforce/jobs?limit=200&offset=0${effectiveAt ? `&effective_at=${encodeURIComponent(effectiveAt)}` : ""}`,
    token,
  ),
  createJob: (token: string, body: unknown) =>
    apiRequest<Job>("/api/v1/workforce/jobs", token, { method: "POST", body }),
  createJobVersion: (token: string, jobId: string, body: unknown) =>
    apiRequest<Job>(`/api/v1/workforce/jobs/${jobId}/versions`, token, { method: "POST", body }),
  jobDimensions: (token: string, effectiveAt?: string) =>
    apiRequest<Page<JobDimension>>(
      `/api/v1/workforce/job-dimensions?limit=500&offset=0${effectiveAt ? `&effective_at=${encodeURIComponent(effectiveAt)}` : ""}`,
      token,
    ),
  createJobDimension: (token: string, body: unknown) =>
    apiRequest<JobDimension>("/api/v1/workforce/job-dimensions", token, { method: "POST", body }),
  createJobDimensionVersion: (token: string, dimensionId: string, body: unknown) =>
    apiRequest<JobDimension>(`/api/v1/workforce/job-dimensions/${dimensionId}/versions`, token, { method: "POST", body }),
  legalEntities: (token: string) =>
    apiRequest<Page<LegalEntity>>("/api/v1/workforce/legal-entities?limit=200&offset=0", token),
  createLegalEntity: (token: string, body: unknown) =>
    apiRequest<LegalEntity>("/api/v1/workforce/legal-entities", token, { method: "POST", body }),
  organizations: async (token: string) =>
    flattenOrganizations(await apiRequest<readonly OrganizationTreeNode[]>("/api/v1/organizations/tree", token)),
  headcountResults: (
    token: string,
    periodMonth: string,
    asOf: string,
    organizationId?: string,
    jobId?: string,
  ) => {
    const params = new URLSearchParams({ period_month: periodMonth, as_of: asOf })
    if (organizationId) params.set("organization_id", organizationId)
    if (jobId) params.set("job_id", jobId)
    return apiRequest<HeadcountResult>(`/api/v1/workforce/headcount-results?${params}`, token)
  },
  createHeadcountPlan: (token: string, body: unknown) =>
    apiRequest("/api/v1/workforce/headcount-plans", token, { method: "POST", body }),
  occupancyRules: (token: string) =>
    apiRequest<Page<OccupancyRule>>("/api/v1/workforce/occupancy-rules?limit=200&offset=0", token),
  createOccupancyRule: (token: string, body: unknown) =>
    apiRequest<OccupancyRule>("/api/v1/workforce/occupancy-rules", token, { method: "POST", body }),
  freezes: (token: string) =>
    apiRequest<Page<HeadcountFreeze>>("/api/v1/workforce/headcount-freezes?limit=200&offset=0", token),
  createFreeze: (token: string, body: unknown) =>
    apiRequest<HeadcountFreeze>("/api/v1/workforce/headcount-freezes", token, { method: "POST", body }),
  closeFreeze: (token: string, freezeId: string, reason: string) =>
    apiRequest<HeadcountFreeze>(`/api/v1/workforce/headcount-freezes/${freezeId}/close`, token, {
      method: "POST",
      body: { reason },
    }),
  createSnapshot: (token: string, body: unknown) =>
    apiRequest("/api/v1/workforce/headcount-snapshots", token, { method: "POST", body }),
  recruitmentRequests: (token: string) =>
    apiRequest<Page<RecruitmentRequest>>("/api/v1/lifecycle/recruitment-requests?limit=200&offset=0", token),
  createRecruitmentRequest: (token: string, body: unknown) =>
    apiRequest<RecruitmentRequest>("/api/v1/lifecycle/recruitment-requests", token, { method: "POST", body }),
  updateRecruitmentRequest: (token: string, requestId: string, body: unknown) =>
    apiRequest<RecruitmentRequest>(`/api/v1/lifecycle/recruitment-requests/${requestId}`, token, {
      method: "PATCH",
      body,
    }),
}
