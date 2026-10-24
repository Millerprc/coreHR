// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { Tag, Tooltip } from "antd"
import type { JSX } from "react"

import type { LicenseState } from "../../types"
import { LICENSE_STATUS_LABELS, LICENSE_TIER_LABELS } from "./licenseLabels"
import { formatLicenseDate, licenseBadgeText } from "./licenseState"


export interface LicenseBadgeProps {
  readonly state: LicenseState | null
}


/** 悬停说明：徽标文案之外再给出状态、版本与有效期，避免只看到一行短标签。 */
function badgeTooltip(state: LicenseState | null): string {
  if (state?.status !== "active" || !state) {
    return `${LICENSE_STATUS_LABELS[state?.status ?? "none"]}：当前为只读演示模式，可浏览与读取全部数据，写操作需要授权。`
  }
  const parts = [
    state.licensee_short ?? state.licensee ?? "未署名客户",
    state.tier ? LICENSE_TIER_LABELS[state.tier] : "未知版本",
  ]
  const expires = formatLicenseDate(state.expires_at)
  if (expires) parts.push(`有效期至 ${expires}`)
  if (state.license_id) parts.push(`许可证编号 ${state.license_id}`)
  return parts.join(" · ")
}


// Requirement: D-108 — 授权徽标放在顶栏最右端，一眼可见且带描边；
// 未授权与各类失效状态在文案上可区分。
export function LicenseBadge({ state }: LicenseBadgeProps): JSX.Element {
  const text = licenseBadgeText(state)
  const active = state?.status === "active"
  return (
    <Tooltip title={badgeTooltip(state)}>
      <Tag
        variant="outlined"
        color={active ? "blue" : "orange"}
        className="license-badge"
        aria-label={`授权状态：${text}`}
      >
        {text}
      </Tag>
    </Tooltip>
  )
}
