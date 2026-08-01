import type { ModuleRegistryResponse } from "./types"

export class ApiRequestError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiRequestError"
    this.status = status
  }
}

async function requestJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, {
    headers: { Accept: "application/json" },
    signal,
  })

  if (!response.ok) {
    throw new ApiRequestError(response.status, `请求失败：HTTP ${response.status}`)
  }

  return (await response.json()) as T
}

export function getModuleRegistry(
  signal?: AbortSignal,
): Promise<ModuleRegistryResponse> {
  return requestJson<ModuleRegistryResponse>("/api/v1/system/modules", signal)
}

