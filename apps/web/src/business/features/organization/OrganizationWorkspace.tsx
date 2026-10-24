// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import {
  Alert,
  Button,
  Descriptions,
  Empty,
  Input,
  Popconfirm,
  Select,
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
import { organizationDetailUrl } from "../../navigation"
import { command, organizationApi } from "./api"
import { OrganizationRelationsTabs } from "./OrganizationRelationsTabs"
import { OrganizationTree } from "./OrganizationTree"
import { OrganizationVersionDrawer } from "./OrganizationVersionDrawer"
import { localDate, treeAsOf, viewDateText } from "./view-date"
import type {
  Organization,
  OrganizationTreeNode,
  OrganizationType,
} from "./types"


interface OrganizationWorkspaceProps {
  readonly token: string
  readonly canAdmin: boolean
}


interface OrganizationOption {
  readonly id: string
  readonly name: string
  readonly code: string
  readonly organizationTypeCode: string
  readonly parentName: string | null
  readonly status: string
}


function flattenTree(
  nodes: readonly OrganizationTreeNode[],
  parentName: string | null = null,
): OrganizationOption[] {
  return nodes.flatMap((node) => [
    {
      id: node.id,
      name: node.name,
      code: node.code,
      organizationTypeCode: node.organization_type_code,
      parentName,
      status: node.status,
    },
    ...flattenTree(node.children, node.name),
  ])
}


function firstOrganizationId(nodes: readonly OrganizationTreeNode[]): string | null {
  return nodes[0]?.id ?? null
}


export function OrganizationWorkspace({ token, canAdmin }: OrganizationWorkspaceProps) {
  const [tree, setTree] = useState<readonly OrganizationTreeNode[]>([])
  const [types, setTypes] = useState<readonly OrganizationType[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [effectiveAt, setEffectiveAt] = useState(localDate)
  const [detail, setDetail] = useState<Organization | null>(null)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [forbidden, setForbidden] = useState(false)
  const [editorMode, setEditorMode] = useState<"create" | "version" | null>(null)
  // Requirement: ORG-PROT-001 — 部门管理宿主页默认提供列表，并保留组织架构树上下文。
  const [activeView, setActiveView] = useState<"list" | "tree">("list")
  const [searchText, setSearchText] = useState("")
  const [typeFilter, setTypeFilter] = useState<string>()
  const [detailRefreshKey, setDetailRefreshKey] = useState(0)
  const detailRequestSequence = useRef(0)

  const organizationOptions = useMemo(() => flattenTree(tree), [tree])
  const typeNames = useMemo(
    () => new Map(types.map((type) => [type.code, type.name])),
    [types],
  )
  const typeFilterOptions = useMemo(
    () => Array.from(new Set(organizationOptions.map((item) => item.organizationTypeCode)))
      .sort()
      .map((code) => ({ label: typeNames.get(code) ?? code, value: code })),
    [organizationOptions, typeNames],
  )
  const filteredOrganizations = useMemo(() => {
    const query = searchText.trim().toLocaleLowerCase()
    return organizationOptions.filter((item) => (
      (!query || item.name.toLocaleLowerCase().includes(query) || item.code.toLocaleLowerCase().includes(query))
      && (!typeFilter || item.organizationTypeCode === typeFilter)
    ))
  }, [organizationOptions, searchText, typeFilter])
  // Requirement: ORG-PROT-002 — 多个未来版本按聚合版本连续追加，并只允许逆序取消。
  const detailExpectedVersion = useMemo(() => detail
    ? Math.max(
        detail.version,
        ...detail.planned_events.map((event) => event.expected_version + 1),
      )
    : 1, [detail])

  const loadBase = useCallback(async () => {
    // Requirement: ORG-PROT-001 — 重载组织树时同步作废旧详情，避免树与详情属于不同数据时刻。
    detailRequestSequence.current += 1
    setDetail(null)
    setLoading(true)
    setError(null)
    try {
      const [nextTree, nextTypes] = await Promise.all([
        // Requirement: D-103 — 组织树按查看时点读取：当天即当前树，历史日期即历史时点。
        organizationApi.tree(token, treeAsOf(effectiveAt)),
        organizationApi.types(token),
      ])
      setTree(nextTree)
      setTypes(nextTypes)
      setSelectedId((current) =>
        current && flattenTree(nextTree).some((item) => item.id === current)
          ? current
          : firstOrganizationId(nextTree),
      )
    } catch (caught) {
      if (caught instanceof ApiClientError && caught.status === 403) setForbidden(true)
      else setError(caught instanceof Error ? caught.message : "部门管理加载失败")
    } finally {
      setLoading(false)
    }
  }, [effectiveAt, token])

  const loadDetail = useCallback(async () => {
    // Requirement: ORG-PROT-001 — 快速切换组织或日期时，只允许最新详情请求更新当前操作对象。
    const requestSequence = ++detailRequestSequence.current
    if (!selectedId) {
      setDetail(null)
      setDetailLoading(false)
      return
    }
    setDetail(null)
    setDetailLoading(true)
    setError(null)
    try {
      const nextDetail = await organizationApi.organization(token, selectedId, effectiveAt)
      if (requestSequence === detailRequestSequence.current) setDetail(nextDetail)
    } catch (caught) {
      if (requestSequence === detailRequestSequence.current) {
        setDetail(null)
        setError(caught instanceof Error ? caught.message : "组织详情加载失败")
      }
    } finally {
      if (requestSequence === detailRequestSequence.current) setDetailLoading(false)
    }
  }, [effectiveAt, selectedId, token])

  const selectOrganization = useCallback((organizationId: string) => {
    // Requirement: ORG-PROT-001 — 用户操作发生时立即作废旧请求，不等待下一轮effect。
    detailRequestSequence.current += 1
    setDetail(null)
    setSelectedId(organizationId)
  }, [])

  const changeEffectiveAt = useCallback((value: string) => {
    detailRequestSequence.current += 1
    setDetail(null)
    setEffectiveAt(value)
  }, [])

  // Requirement: D-103 — 当天即当前时点，历史日期即历史时点；界面必须能看出当前查看的是哪个时点。
  const viewingCurrent = effectiveAt === localDate()

  const resetToCurrent = useCallback(() => {
    changeEffectiveAt(localDate())
  }, [changeEffectiveAt])

  useEffect(() => {
    void loadBase()
  }, [loadBase])

  useEffect(() => {
    void loadDetail()
  }, [detailRefreshKey, loadDetail])

  async function saveOrganization(body: Record<string, unknown>): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      if (editorMode === "create") {
        const created = await organizationApi.createOrganization(token, body)
        await loadBase()
        selectOrganization(created.id)
      } else if (editorMode === "version" && selectedId) {
        await organizationApi.scheduleVersion(token, selectedId, body)
        setDetailRefreshKey((current) => current + 1)
      }
      setEditorMode(null)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "组织保存失败")
      if (caught instanceof ApiClientError && caught.status === 409) {
        setDetailRefreshKey((current) => current + 1)
      }
    } finally {
      setSaving(false)
    }
  }

  async function cancelEvent(eventId: string): Promise<void> {
    if (!detail) return
    setSaving(true)
    try {
      await organizationApi.cancelEvent(
        token,
        eventId,
        command(detailExpectedVersion, "取消未来组织变更"),
      )
      // Requirement: ORG-PROT-001 — 异步操作完成后刷新用户当前所选组织，不重放操作发起时的旧详情请求。
      setDetailRefreshKey((current) => current + 1)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "取消失败")
    } finally {
      setSaving(false)
    }
  }

  if (forbidden) {
    return (
      <section aria-labelledby="organization-title">
        <Typography.Title id="organization-title" level={2}>部门管理</Typography.Title>
        <Alert type="error" showIcon title="无权查看部门管理" description="请联系主管理员分配组织查看权限。" />
      </section>
    )
  }

  return (
    <section aria-labelledby="organization-title" className="workspace-section">
      <div className="workspace-heading">
        <div>
          <Typography.Title id="organization-title" level={2}>部门管理</Typography.Title>
          <Typography.Paragraph type="secondary">
            维护公司与部门；查看日期决定组织树、列表与详情的读取时点，只支持查看当前与历史时点。
          </Typography.Paragraph>
        </div>
        {canAdmin && (
          <Space wrap>
            <Button type="primary" onClick={() => setEditorMode("create")}>新建部门</Button>
            <Button
              disabled={activeView !== "tree" || detailLoading || !detail || detail.id !== selectedId}
              onClick={() => setEditorMode("version")}
            >添加变更</Button>
          </Space>
        )}
      </div>
      {error && <Alert closable={{ onClose: () => setError(null) }} type="error" showIcon title={error} />}
      {loading ? (
        <Skeleton active paragraph={{ rows: 10 }} />
      ) : (
        <Tabs
          className="organization-view-tabs"
          activeKey={activeView}
          onChange={(key) => setActiveView(key as "list" | "tree")}
          items={[
            {
              key: "list",
              label: "列表",
              children: (
                <div className="organization-list-view">
                  <div className="organization-list-filters" role="search" aria-label="部门筛选">
                    <Input
                      allowClear
                      aria-label="搜索部门名称或编号"
                      placeholder="搜索部门名称或编号"
                      value={searchText}
                      onChange={(event) => setSearchText(event.target.value)}
                    />
                    <Select
                      allowClear
                      aria-label="全部部门类型"
                      placeholder="全部部门类型"
                      options={typeFilterOptions}
                      value={typeFilter}
                      onChange={setTypeFilter}
                    />
                    {/* Requirement: D-103 — 列表随组织树一起按查看时点切片，
                        筛选区必须显示当前查看的是哪个时点。 */}
                    <Tag color={viewingCurrent ? "default" : "processing"}>
                      {viewDateText(effectiveAt)}
                    </Tag>
                    <Button onClick={() => {
                      setSearchText("")
                      setTypeFilter(undefined)
                    }}>重置</Button>
                  </div>
                  <Table<OrganizationOption>
                    rowKey="id"
                    dataSource={filteredOrganizations}
                    locale={{ emptyText: <Empty description="没有符合条件的部门" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
                    pagination={{
                      pageSize: 20,
                      showSizeChanger: false,
                      showTotal: (total) => `共 ${total} 个部门`,
                    }}
                    columns={[
                      { title: "部门名称", dataIndex: "name", fixed: "left", width: 220 },
                      { title: "编号", dataIndex: "code", width: 160 },
                      {
                        title: "部门类型",
                        dataIndex: "organizationTypeCode",
                        width: 140,
                        render: (value) => typeNames.get(value) ?? value,
                      },
                      { title: "上级部门", dataIndex: "parentName", width: 220, render: (value) => value ?? "—" },
                      {
                        title: "状态",
                        dataIndex: "status",
                        width: 110,
                        render: (value) => <Tag color={value === "active" ? "success" : "error"}>{value === "active" ? "启用" : "禁用"}</Tag>,
                      },
                      {
                        title: "操作",
                        key: "action",
                        fixed: "right",
                        width: 190,
                        render: (_, item) => (
                          <Space size={0}>
                            {/* Requirement: ORG-PROT-002 — 列表查看在新标签页打开已确认的组织详情。 */}
                            <Button
                              type="link"
                              onClick={() => window.open(
                                organizationDetailUrl(item.id, effectiveAt),
                                "_blank",
                                "noopener,noreferrer",
                              )}
                            >查看</Button>
                            <Button type="link" onClick={() => {
                              selectOrganization(item.id)
                              setActiveView("tree")
                            }}>树中定位</Button>
                          </Space>
                        ),
                      },
                    ]}
                  />
                </div>
              ),
            },
            {
              key: "tree",
              label: "组织架构树",
              children: (
                <div className="organization-layout">
                  <aside className="organization-tree-panel">
                    <div className="panel-heading">
                      <Typography.Title level={5}>
                        {viewingCurrent ? "当前有效组织树" : `截至 ${effectiveAt} 的组织树`}
                      </Typography.Title>
                      <Tag>{organizationOptions.length} 个组织</Tag>
                    </div>
                    <OrganizationTree
                      nodes={tree}
                      selectedId={selectedId}
                      onSelect={selectOrganization}
                      label={viewingCurrent ? "当前有效组织树" : `截至 ${effectiveAt} 的组织树`}
                    />
                  </aside>
                  <div className="organization-detail-panel">
                    <div className="detail-toolbar">
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
                    {detailLoading ? (
                      <Skeleton active paragraph={{ rows: 8 }} />
                    ) : !detail ? (
                      <Empty description={selectedId ? "该日期没有有效组织版本" : "请选择组织"} />
                    ) : (
                      <>
                        <div className="organization-title-row">
                          <div>
                            <Typography.Title level={3}>{detail.name}</Typography.Title>
                            <Space><Typography.Text code>{detail.code}</Typography.Text><Tag>{detail.organization_type_name}</Tag></Space>
                          </div>
                          <Tag color={detail.status === "active" ? "success" : "default"}>{detail.status === "active" ? "有效" : "停用"}</Tag>
                        </div>
                        <Descriptions bordered size="small" column={{ xs: 1, lg: 2 }}>
                          <Descriptions.Item label="生效起始">{detail.effective_from}</Descriptions.Item>
                          <Descriptions.Item label="生效结束">{detail.effective_to ?? "长期"}</Descriptions.Item>
                          <Descriptions.Item label="直接上级编码">{detail.parent_organization_code ?? "无"}</Descriptions.Item>
                          <Descriptions.Item label="国家或地区">{detail.country_code ?? "未设置"}</Descriptions.Item>
                          <Descriptions.Item label="当前版本">{detail.version}</Descriptions.Item>
                        </Descriptions>
                        <div className="future-events">
                          <Typography.Title level={4}>未来变更</Typography.Title>
                          {/* Requirement: D-068 — 使用语义列表替代Ant Design 6已废弃的List组件。 */}
                          {detail.planned_events.length ? (
                            <ul className="future-event-list">
                              {detail.planned_events.map((event) => (
                                <li key={event.id}>
                                  <div>
                                    <Typography.Text strong>{event.effective_date} 生效</Typography.Text>
                                    <Typography.Text type="secondary">{event.change_reason}，状态：{event.status}</Typography.Text>
                                  </div>
                                  {canAdmin && event.expected_version + 1 === detailExpectedVersion && (
                                    <Popconfirm title="确认取消这条未来变更？" onConfirm={() => void cancelEvent(event.id)}>
                                      <Button type="link" danger loading={saving}>取消</Button>
                                    </Popconfirm>
                                  )}
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <Empty description="没有待生效组织变更" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                          )}
                        </div>
                        <OrganizationRelationsTabs
                          token={token}
                          organizationId={detail.id}
                          effectiveAt={effectiveAt}
                          canAdmin={canAdmin}
                          organizations={organizationOptions}
                        />
                      </>
                    )}
                  </div>
                </div>
              ),
            },
          ]}
        />
      )}

      <OrganizationVersionDrawer
        open={editorMode !== null}
        mode={editorMode ?? "create"}
        current={detail}
        types={types}
        organizations={organizationOptions}
        saving={saving}
        expectedVersion={detailExpectedVersion}
        onClose={() => setEditorMode(null)}
        onSave={saveOrganization}
      />
    </section>
  )
}
