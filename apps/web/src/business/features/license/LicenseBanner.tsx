// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { Button, Descriptions, Result, Typography } from "antd"
import type { JSX } from "react"

import type { LicenseModuleKey, LicenseState } from "../../types"
import { LICENSE_STATUS_LABELS, LICENSE_TIER_LABELS, licenseModuleNames } from "./licenseLabels"
import { formatLicenseDate } from "./licenseState"


export interface LicenseBannerProps {
  /** 当前被锁定的授权模块。 */
  readonly modules: readonly LicenseModuleKey[]
  readonly state: LicenseState | null
  /** 跳转到「授权管理」的入口；没有授权管理权限时不提供。 */
  readonly onOpenLicense?: () => void
}


// Requirement: D-108 — 被锁模块进入的是授权说明面板：
// 只讲「哪个模块需要授权、怎么申请」，不渲染假表格或占位业务表单。
export function LicenseBanner({ modules, state, onOpenLicense }: LicenseBannerProps): JSX.Element {
  const moduleNames = licenseModuleNames(modules)
  return (
    <Result
      status="warning"
      title={`需要 ${moduleNames} 模块授权`}
      subTitle="当前处于只读演示模式：该模块可以浏览、数据可以读取，写操作已禁用。"
      extra={onOpenLicense
        ? [<Button key="open-license" type="primary" onClick={onOpenLicense}>前往授权管理</Button>]
        : undefined}
    >
      <Typography.Title level={5}>申请指引</Typography.Title>
      <ol className="license-guide">
        <li>联系 coreHR 授权服务，说明需要的模块与授权期限，获取 License Token。</li>
        <li>在「授权管理」工作区粘贴 Token 并激活；Token 只在提交时出现一次，后端只保存摘要。</li>
        <li>激活成功后该模块的写能力立即生效，不需要重启服务。</li>
      </ol>
      <Descriptions bordered size="small" column={2} items={[
        {
          key: "status",
          label: "当前授权状态",
          children: LICENSE_STATUS_LABELS[state?.status ?? "none"],
        },
        {
          key: "tier",
          label: "当前版本",
          children: state?.tier ? LICENSE_TIER_LABELS[state.tier] : "—",
        },
        {
          key: "licensee",
          label: "被授权方",
          children: state?.licensee_short ?? state?.licensee ?? "—",
        },
        {
          key: "expires",
          label: "有效期至",
          children: formatLicenseDate(state?.expires_at ?? null) || "—",
        },
      ]} />
    </Result>
  )
}
