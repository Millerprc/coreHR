import { apiRequest } from "../../client"
import type {
  Candidate,
  ContractRecord,
  HrEvent,
  JobApplication,
  LifecyclePage,
  WorkflowDefinition,
  WorkflowInstance,
  WorkflowTask,
} from "./types"


export const lifecycleApi = {
  definitions: (token: string) =>
    apiRequest<LifecyclePage<WorkflowDefinition>>("/api/v1/workflows/definitions?limit=200&offset=0", token),
  createDefinition: (token: string, body: unknown) =>
    apiRequest<WorkflowDefinition>("/api/v1/workflows/definitions", token, { method: "POST", body }),
  publishDefinition: (token: string, definitionId: string) =>
    apiRequest(`/api/v1/lifecycle/workflows/${definitionId}/publish`, token, { method: "POST" }),
  instances: (token: string) =>
    apiRequest<LifecyclePage<WorkflowInstance>>("/api/v1/lifecycle/workflow-instances?limit=200&offset=0", token),
  startWorkflow: (token: string, body: unknown) =>
    apiRequest<WorkflowInstance>("/api/v1/lifecycle/workflow-instances", token, { method: "POST", body }),
  tasks: (token: string) =>
    apiRequest<LifecyclePage<WorkflowTask>>("/api/v1/lifecycle/workflow-tasks?limit=200&offset=0", token),
  decideTask: (token: string, taskId: string, body: unknown) =>
    apiRequest<WorkflowTask>(`/api/v1/lifecycle/workflow-tasks/${taskId}/decision`, token, { method: "POST", body }),
  candidates: (token: string) =>
    apiRequest<LifecyclePage<Candidate>>("/api/v1/lifecycle/candidates?limit=200&offset=0", token),
  createCandidate: (token: string, body: unknown) =>
    apiRequest<Candidate>("/api/v1/lifecycle/candidates", token, { method: "POST", body }),
  updateCandidate: (token: string, candidateId: string, body: unknown) =>
    apiRequest<Candidate>(`/api/v1/lifecycle/candidates/${candidateId}`, token, { method: "PATCH", body }),
  applications: (token: string) =>
    apiRequest<LifecyclePage<JobApplication>>("/api/v1/lifecycle/applications?limit=200&offset=0", token),
  createApplication: (token: string, body: unknown) =>
    apiRequest<JobApplication>("/api/v1/lifecycle/applications", token, { method: "POST", body }),
  updateApplication: (token: string, applicationId: string, body: unknown) =>
    apiRequest<JobApplication>(`/api/v1/lifecycle/applications/${applicationId}`, token, { method: "PATCH", body }),
  contracts: (token: string) =>
    apiRequest<LifecyclePage<ContractRecord>>("/api/v1/lifecycle/contracts?limit=200&offset=0", token),
  createContract: (token: string, body: unknown) =>
    apiRequest<ContractRecord>("/api/v1/lifecycle/contracts", token, { method: "POST", body }),
  updateContract: (token: string, contractId: string, body: unknown) =>
    apiRequest<ContractRecord>(`/api/v1/lifecycle/contracts/${contractId}`, token, { method: "PATCH", body }),
  hrEvents: (token: string) =>
    apiRequest<LifecyclePage<HrEvent>>("/api/v1/lifecycle/hr-events?limit=200&offset=0", token),
  createHrEvent: (token: string, body: unknown) =>
    apiRequest<HrEvent>("/api/v1/lifecycle/hr-events", token, { method: "POST", body }),
  processHrEvents: (token: string, asOf: string) =>
    apiRequest("/api/v1/lifecycle/hr-events/process", token, { method: "POST", body: { as_of: asOf } }),
  rollbackHrEvent: (token: string, eventId: string, body: unknown) =>
    apiRequest<HrEvent>(`/api/v1/lifecycle/hr-events/${eventId}/rollback`, token, { method: "POST", body }),
}
