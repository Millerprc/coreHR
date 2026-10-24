// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import {
  Alert,
  Button,
  Descriptions,
  Empty,
  Popconfirm,
  Skeleton,
  Space,
  Table,
  Tag,
  Tabs,
  Typography,
} from "antd"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"

import { ApiClientError } from "../../client"
import { EffectiveDatePicker } from "../../components/EffectiveDatePicker"
import { command, organizationApi } from "./api"
import { OrganizationVersionDrawer } from "./OrganizationVersionDrawer"
import { localDate, treeAsOf, viewDateText } from "./view-date"
import type {
  DirectoryOption,
  Organization,
  OrganizationEvent,
  OrganizationRelations,
  OrganizationTreeNode,
  OrganizationType,
} from "./types"


interface OrganizationDetailWorkspaceProps {
  readonly token: string
  readonly canAdmin: boolean
  readonly organizationId: string
  readonly initialEffectiveAt: string | null
}


interface OrganizationOption {
  readonly id: string
  readonly name: string
  readonly code: string
}


interface OrganizationDetailData {
  readonly detail: Organization
  readonly relations: OrganizationRelations
  readonly events: readonly OrganizationEvent[]
  readonly eventTotal: number
  readonly types: readonly OrganizationType[]
  readonly organizations: readonly OrganizationOption[]
  readonly path: readonly OrganizationOption[]
  readonly legalEntities: readonly DirectoryOption[]
}


function flattenTree(
  nodes: readonly OrganizationTreeNode[],
  targetId: string,
  ancestors: readonly OrganizationOption[] = [],
): { organizations: OrganizationOption[]; path: readonly OrganizationOption[] } {
  const organizations: OrganizationOption[] = []
  let targetPath: readonly OrganizationOption[] = []
  for (const node of nodes) {
    const option = { id: node.id, name: node.name, code: node.code }
    const path = [...ancestors, option]
    organizations.push(option)
    if (node.id === targetId) targetPath = path
    const nested = flattenTree(node.children, targetId, path)
    organizations.push(...nested.organizations)
    if (!targetPath.length && nested.path.length) targetPath = nested.path
  }
  return { organizations, path: targetPath }
}


function directoryName(item: DirectoryOption): string {
  return item.name ?? item.display_name ?? item.code ?? item.id
}


const eventTypeLabels: Readonly<Record<string, string>> = {
  CREATE: "创建组织",
  VERSION_CHANGE: "组织变更",
}


const eventStatusLabels: Readonly<Record<string, { label: string; color: string }>> = {
  planned: { label: "待生效", color: "processing" },
  applied: { label: "已生效", color: "success" },
  cancelled: { label: "已取消", color: "default" },
}


export function OrganizationDetailWorkspace({
  token,
  canAdmin,
  organizationId,
  initialEffectiveAt,
}: OrganizationDetailWorkspaceProps) {
  const [effectiveAt, setEffectiveAt] = useState(initialEffectiveAt ?? localDate)
  const [data, setData] = useState<OrganizationDetailData | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [editorIntent, setEditorIntent] = useState<"change" | "disable" | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const [eventPage, setEventPage] = useState(1)
  const requestSequence = useRef(0)

  const load = useCallback(async () => {
    // Requirement: ORG-PROT-002 — 日期切换时只有最新请求可以更新详情标签页。
    const currentRequest = ++requestSequence.current
    setLoading(true)
    setError(null)
    try {
      const [detail, relations, events, types, tree, legalEntityPage] = await Promise.all([
        organizationApi.organization(token, organizationId, effectiveAt),
        organizationApi.relations(token, organizationId, effectiveAt),
        organizationApi.events(token, organizationId, 50, (eventPage - 1) * 50),
        organizationApi.types(token),
        // Requirement: D-103 — 详情页的部门路径同样按查看时点读取组织树。
        organizationApi.tree(token, treeAsOf(effectiveAt)),
        organizationApi.legalEntities(token),
      ])
      if (currentRequest !== requestSequence.current) return
      const treeData = flattenTree(tree, organizationId)
      const linkedLegalEntities = legalEntityPage.items.filter((item) => (
        relations.legal_entity_ids.includes(item.id)
      ))
      setData({
        detail,
        relations,
        events: events.items,
        eventTotal: events.total,
        types,
        organizations: treeData.organizations,
        path: treeData.path,
        legalEntities: linkedLegalEntities,
      })
    } catch (caught) {
      if (currentRequest !== requestSequence.current) return
      setData(null)
      setError(caught instanceof Error ? caught.message : "部门详情加载失败")
    } finally {
      if (currentRequest === requestSequence.current) setLoading(false)
    }
  }, [effectiveAt, eventPage, organizationId, token])

  useEffect(() => {
    void load()
  }, [load, refreshKey])

  const legalEntityNames = useMemo(
    () => data?.legalEntities.map(directoryName).join("、") || "未关联",
    [data],
  )

  function changeEffectiveAt(value: string): void {
    requestSequence.current += 1
    setData(null)
    setEffectiveAt(value)
  }

  // Requirement: D-103 — 当天即当前时点，历史日期即历史时点；界面必须能看出当前查看的是哪个时点。
  const viewingCurrent = effectiveAt === localDate()

  function resetToCurrent(): void {
    changeEffectiveAt(localDate())
  }

  async function saveVersion(body: Record<string, unknown>): Promise<void> {
    if (!data) return
    setSaving(true)
    setError(null)
    try {
      await organizationApi.scheduleVersion(token, organizationId, body)
      setEditorIntent(null)
      setRefreshKey((current) => current + 1)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "组织变更保存失败")
      if (caught instanceof ApiClientError && caught.status === 409) {
        setRefreshKey((current) => current + 1)
      }
    } finally {
      setSaving(false)
    }
  }

  async function cancelEvent(event: OrganizationEvent): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      await organizationApi.cancelEvent(
        token,
        event.id,
        command(event.expected_version + 1, "取消未来组织变更"),
      )
      setRefreshKey((current) => current + 1)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "取消未来变更失败")
    } finally {
      setSaving(false)
    }
  }

  if (loading && !data) {
    return <section className="organization-detail-page"><Skeleton active paragraph={{ rows: 12 }} /></section>
  }

  if (!data) {
    return (
      <section className="organization-detail-page">
        <Alert type="error" showIcon title="无法打开部门详情" description={error ?? "该日期没有有效组织版本"} />
        <Button onClick={() => void load()}>重试</Button>
      </section>
    )
  }

  const { detail } = data
  const parent = data.path.at(-2)
  const pathText = data.path.length
    ? data.path.map((item) => item.name).join(" / ")
    : detail.name

  // Requirement: ORG-PROT-002 — 已确认的详情原型使用独立标签页、信息/记录页签和抽屉式变更。
  return (
    <section className="organization-detail-page" aria-labelledby="organization-detail-title">
      <div className="organization-detail-hero">
        <div>
          <Space align="center" wrap>
            <Typography.Title id="organization-detail-title" level={2}>{detail.name}</Typography.Title>
            <Tag color={detail.status === "active" ? "success" : "default"}>
              {detail.status === "active" ? "启用" : "停用"}
            </Tag>
          </Space>
          <Space size="large" wrap className="organization-detail-summary">
            <Typography.Text>编号：{detail.code}</Typography.Text>
            <Typography.Text>设立日期：{detail.effective_from}</Typography.Text>
            <Typography.Text>部门路径：{pathText}</Typography.Text>
          </Space>
        </div>
        {canAdmin && (
          <Space wrap>
            <Button onClick={() => setEditorIntent("change")}>添加变更</Button>
            <Button
              danger
              autoInsertSpace={false}
              disabled={detail.status !== "active"}
              onClick={() => setEditorIntent("disable")}
            >停用</Button>
          </Space>
        )}
      </div>

      {error && <Alert closable={{ onClose: () => setError(null) }} type="error" showIcon title={error} />}

      <Tabs
        items={[
          {
            key: "information",
            label: "组织信息",
            children: (
              <>
                <div className="organization-detail-datebar">
                  <EffectiveDatePicker value={effectiveAt} onChange={changeEffectiveAt} />
                  {/* Requirement: D-103 — 切换查看日期立即重新取数，
                      并用状态标签说明当前查看的是当前时点还是历史时点。 */}
                  <Space size={4} align="center">
                    <Tag color={viewingCurrent ? "default" : "processing"}>
                      {viewDateText(effectiveAt)}
                    </Tag>
                    {!viewingCurrent && (
                      <Button type="link" onClick={resetToCurrent}>回到当前</Button>
                    )}
                  </Space>
                </div>
                <div className="organization-detail-card">
                  <Typography.Title level={4}>基础信息</Typography.Title>
                  <Descriptions column={{ xs: 1, lg: 2 }} colon={false}>
                    <Descriptions.Item label="部门名称">{detail.name}</Descriptions.Item>
                    <Descriptions.Item label="上级部门">{parent?.name ?? detail.parent_organization_code ?? "无"}</Descriptions.Item>
                    <Descriptions.Item label="部门类型">{detail.organization_type_name}</Descriptions.Item>
                    <Descriptions.Item label="部门层级">{data.path.length ? `${data.path.length}级` : "—"}</Descriptions.Item>
                    <Descriptions.Item label="部门编号">{detail.code}</Descriptions.Item>
                    <Descriptions.Item label="法人公司">{legalEntityNames}</Descriptions.Item>
                    <Descriptions.Item label="国家或地区">{detail.country_code ?? "未设置"}</Descriptions.Item>
                    <Descriptions.Item label="状态">{detail.status === "active" ? "启用" : "停用"}</Descriptions.Item>
                  </Descriptions>
                </div>
              </>
            ),
          },
          {
            key: "history",
            label: "变更记录",
            children: (
              <Table<OrganizationEvent>
                rowKey="id"
                dataSource={[...data.events]}
                // Requirement: ORG-PROT-002 — 历史记录按服务端分页读取，不能只展示首批记录。
                loading={loading}
                pagination={{ current: eventPage, pageSize: 50, total: data.eventTotal, showSizeChanger: false, onChange: setEventPage }}
                locale={{ emptyText: <Empty description="暂无组织变更记录" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
                columns={[
                  { title: "生效日期", dataIndex: "effective_date", width: 140 },
                  { title: "变更类型", dataIndex: "event_type", width: 140, render: (value) => eventTypeLabels[value] ?? value },
                  { title: "变更原因", dataIndex: "change_reason" },
                  {
                    title: "状态",
                    dataIndex: "status",
                    width: 120,
                    render: (value) => {
                      const status = eventStatusLabels[value] ?? { label: value, color: "default" }
                      return <Tag color={status.color}>{status.label}</Tag>
                    },
                  },
                  {
                    title: "操作",
                    key: "action",
                    width: 100,
                    render: (_, event) => canAdmin && event.status === "planned" ? (
                      <Popconfirm title="确认取消这条未来变更？" onConfirm={() => void cancelEvent(event)}>
                        <Button type="link" danger loading={saving}>取消</Button>
                      </Popconfirm>
                    ) : "—",
                  },
                ]}
              />
            ),
          },
        ]}
      />

      <OrganizationVersionDrawer
        open={editorIntent !== null}
        mode="version"
        current={detail}
        types={data.types}
        organizations={data.organizations}
        saving={saving}
        initialStatus={editorIntent === "disable" ? "inactive" : undefined}
        onClose={() => setEditorIntent(null)}
        onSave={saveVersion}
      />
    </section>
  )
}
