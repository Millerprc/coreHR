// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

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

