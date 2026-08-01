import type {
  LoginResponse,
  ModuleRegistry,
  PageResult,
  UserProfile,
} from "./types"

const TOKEN_KEY = "corehr.business.access_token"

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as
      | { message?: string }
      | null
    throw new Error(body?.message ?? `请求失败（${response.status}）`)
  }
  return (await response.json()) as T
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

async function authorizedGet<T>(path: string, token: string): Promise<T> {
  const response = await fetch(path, {
    headers: { Authorization: `Bearer ${token}` },
  })
  return parseResponse<T>(response)
}

export function getProfile(token: string): Promise<UserProfile> {
  return authorizedGet<UserProfile>("/api/v1/auth/me", token)
}

export function getModules(token: string): Promise<ModuleRegistry> {
  return authorizedGet<ModuleRegistry>("/api/v1/system/modules", token)
}

export function getPageCount(path: string, token: string): Promise<number> {
  return authorizedGet<PageResult>(`${path}?limit=1&offset=0`, token).then(
    (result) => result.total,
  )
}

export async function logout(token: string): Promise<void> {
  await fetch("/api/v1/auth/logout", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  })
}
