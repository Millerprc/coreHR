// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { Alert, Button, Descriptions, Form, Input, Modal, Space, Tag, Typography } from "antd"
import { useCallback, useEffect, useState } from "react"
import type { JSX } from "react"

import { ApiClientError, activateLicense, deactivateLicense, getLicense } from "../../client"
import { DataTable } from "../../components/DataTable"
import { WorkspaceShell } from "../../components/WorkspaceShell"
import type { LicenseModuleKey, LicenseState } from "../../types"
import { LICENSE_MODULE_LABELS, LICENSE_STATUS_LABELS, LICENSE_TIER_LABELS } from "./licenseLabels"
import { formatLicenseDate, normalizeLicenseState } from "./licenseState"


export interface LicenseWorkspaceProps {
  readonly token: string
  /** 授权状态变化后通知外壳刷新顶栏徽标与侧栏锁标。 */
  readonly onLicenseChanged?: () => void
}


interface EntitlementRow {
  readonly key: string
  readonly label: string
  readonly read: boolean
  readonly write: boolean
}


const MODULE_ORDER: readonly LicenseModuleKey[] = [
  "attendance",
  "workflow",
  "lifecycle",
  "governance",
  "workforce",
  "performance",
]


function moduleLabel(module: string): string {
  const labels = LICENSE_MODULE_LABELS as Readonly<Record<string, string>>
  return labels[module] ?? module
}


function entitlementRows(license: LicenseState | null): readonly EntitlementRow[] {
  const entitlements = license?.entitlements ?? {}
  const modules = [
    ...MODULE_ORDER,
    ...Object.keys(entitlements).filter((key) => !MODULE_ORDER.includes(key as LicenseModuleKey)),
  ]
  return modules.map((module) => {
    const entitlement = entitlements[module]
    return {
      key: module,
      label: moduleLabel(module),
      // 未授权时读接口仍然开放，写操作一律禁用（只读演示模式）。
      read: entitlement ? entitlement.read : true,
      write: entitlement?.write === true,
    }
  })
}


/** 激活失败时把后端错误码翻译成可执行的中文提示。 */
function activationErrorMessage(caught: unknown): string {
  if (caught instanceof ApiClientError) {
    if (caught.code === "LICENSE_INVALID_TOKEN") return "License Token 格式无效，请确认复制完整后重试。"
    if (caught.code === "LICENSE_INVALID_SIGNATURE") return "License Token 签名校验失败，文件可能已被篡改。"
    return caught.message
  }
  return caught instanceof Error ? caught.message : "授权激活失败"
}


// Requirement: D-108 — 授权管理工作区：查看授权状态与范围、粘贴 Token 激活、停用授权。
export function LicenseWorkspace({ token, onLicenseChanged }: LicenseWorkspaceProps): JSX.Element {
  const [license, setLicense] = useState<LicenseState | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activating, setActivating] = useState(false)
  const [deactivating, setDeactivating] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [form] = Form.useForm<{ readonly token: string }>()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setLicense(normalizeLicenseState(await getLicense(token)))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "授权状态加载失败")
      setLicense(normalizeLicenseState(null))
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { void load() }, [load])

  async function activate(values: { readonly token: string }): Promise<void> {
    setActivating(true)
    setError(null)
    try {
      await activateLicense(token, values.token.trim())
      form.resetFields()
      await load()
      onLicenseChanged?.()
    } catch (caught) {
      setError(activationErrorMessage(caught))
    } finally {
      setActivating(false)
    }
  }

  async function deactivate(): Promise<void> {
    setDeactivating(true)
    setError(null)
    try {
      await deactivateLicense(token)
      setConfirmOpen(false)
      await load()
      onLicenseChanged?.()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "授权停用失败")
    } finally {
      setDeactivating(false)
    }
  }

  const active = license?.status === "active"
  const rows = entitlementRows(license)

  return (
    <WorkspaceShell
      titleId="license-title"
      title="授权管理"
      subtitle="coreHR 按模块授权：未授权时系统进入只读演示模式，功能可浏览、数据可读取，写操作一律禁用。"
      error={error}
      onErrorClose={() => setError(null)}
      actions={active
        ? <Button danger loading={deactivating} onClick={() => setConfirmOpen(true)}>停用授权</Button>
        : null}
    >
      {!active && (
        <Alert
          type="info"
          showIcon
          title="当前为只读演示模式"
          description="全部功能可浏览、可读取真实数据，一切写操作已禁用。获取授权后在下方粘贴 License Token 激活即可。"
        />
      )}

      <Typography.Title level={5}>授权信息</Typography.Title>
      <Descriptions bordered size="small" column={2} items={[
        {
          key: "status",
          label: "授权状态",
          children: (
            <Tag color={active ? "success" : "warning"}>
              {LICENSE_STATUS_LABELS[license?.status ?? "none"]}
            </Tag>
          ),
        },
        {
          key: "tier",
          label: "授权版本",
          children: license?.tier ? LICENSE_TIER_LABELS[license.tier] : "—",
        },
        {
          key: "licensee",
          label: "被授权方",
          children: license?.licensee ?? "—",
        },
        {
          key: "license-id",
          label: "许可证编号",
          children: license?.license_id ?? "—",
        },
        {
          key: "not-before",
          label: "生效日期",
          children: formatLicenseDate(license?.not_before ?? null) || "—",
        },
        {
          key: "expires",
          label: "有效期至",
          children: formatLicenseDate(license?.expires_at ?? null) || "—",
        },
        {
          key: "activated",
          label: "激活时间",
          children: license?.activated_at ?? "—",
        },
        {
          key: "seat",
          label: "席位上限",
          children: license?.seat_limit === null || license?.seat_limit === undefined
            ? "—"
            : `${license.seat_limit}（仅作合同条款，不做运行时功能裁剪）`,
        },
      ]} />

      <Typography.Title level={5}>授权范围</Typography.Title>
      <DataTable<EntitlementRow>
        rowKey="key"
        dataSource={rows}
        loading={loading}
        emptyText="暂无授权信息"
        columns={[
          { title: "授权模块", dataIndex: "label", width: 240 },
          {
            title: "读取",
            dataIndex: "read",
            width: 120,
            render: (value: boolean) => (
              <Tag color={value ? "success" : "default"}>{value ? "可读" : "不可读"}</Tag>
            ),
          },
          {
            title: "写入",
            dataIndex: "write",
            width: 120,
            render: (value: boolean) => (
              <Tag color={value ? "success" : "default"}>{value ? "可写" : "不可写"}</Tag>
            ),
          },
        ]}
      />
      <Typography.Paragraph type="secondary">
        未授权时读接口仍然开放（只读演示），写操作一律禁用。
      </Typography.Paragraph>

      <Typography.Title level={5}>激活授权</Typography.Title>
      <Typography.Paragraph type="secondary">
        把签发方提供的 License Token 粘贴到下方。Token 明文只在这一次提交中出现，服务端只保存摘要。
      </Typography.Paragraph>
      <Form form={form} layout="vertical" requiredMark={false} onFinish={(values) => void activate(values)}>
        <Form.Item
          label="License Token"
          name="token"
          rules={[{ required: true, message: "请粘贴 License Token" }]}
        >
          <Input.TextArea rows={4} placeholder="coreHR.<header>.<payload>.<signature>" />
        </Form.Item>
        <Space>
          <Button type="primary" htmlType="submit" loading={activating}>激活授权</Button>
        </Space>
      </Form>

      <Modal
        title="停用授权"
        open={confirmOpen}
        okText="确认停用"
        cancelText="取消"
        okButtonProps={{ danger: true, loading: deactivating }}
        onOk={() => void deactivate()}
        onCancel={() => setConfirmOpen(false)}
      >
        <Typography.Paragraph>
          停用后系统立即回落到只读演示模式：功能仍可浏览、数据仍可读取，所有写操作禁用。
        </Typography.Paragraph>
      </Modal>
    </WorkspaceShell>
  )
}
