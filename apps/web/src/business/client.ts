import type {
  LoginResponse,
  ModuleRegistry,
  PageResult,
  UserProfile,
} from "./types"

const TOKEN_KEY = "corehr.business.access_token"


interface ApiErrorBody {
  readonly code?: string
  readonly message?: string
  readonly details?: readonly unknown[]
  readonly trace_id?: string
}


export class ApiClientError extends Error {
  readonly status: number
  readonly code: string
  readonly details: readonly unknown[]
  readonly traceId: string | null

  constructor(response: Response, body: ApiErrorBody | null) {
    super(body?.message ?? `请求失败（${response.status}）`)
    this.name = "ApiClientError"
    this.status = response.status
    this.code = body?.code ?? "HTTP_ERROR"
    this.details = body?.details ?? []
    this.traceId = body?.trace_id ?? response.headers.get("X-Trace-ID")
  }
}


async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ApiErrorBody | null
    throw new ApiClientError(response, body)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}


export interface ApiRequestOptions {
  readonly method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE"
  readonly body?: unknown
  readonly signal?: AbortSignal
}


export async function apiRequest<T>(
  path: string,
  token: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const response = await fetch(path, {
    method: options.method ?? "GET",
    headers: {
      Authorization: `Bearer ${token}`,
      ...(options.body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: options.signal,
  })
  return parseResponse<T>(response)
}


export function storedToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY)
}


export function storeToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token)
}


export function clearToken(): void {
  sessionStorage.removeItem(TOKEN_KEY)
}


export async function login(username: string, password: string): Promise<LoginResponse> {
  const response = await fetch("/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  })
  return parseResponse<LoginResponse>(response)
}


export function getProfile(token: string): Promise<UserProfile> {
  return apiRequest<UserProfile>("/api/v1/auth/me", token)
}


export function getModules(token: string): Promise<ModuleRegistry> {
  return apiRequest<ModuleRegistry>("/api/v1/system/modules", token)
}


export function getPageCount(path: string, token: string): Promise<number> {
  return apiRequest<PageResult>(`${path}?limit=1&offset=0`, token).then(
    (result) => result.total,
  )
}


export async function logout(token: string): Promise<void> {
  await apiRequest<void>("/api/v1/auth/logout", token, { method: "POST" })
}
