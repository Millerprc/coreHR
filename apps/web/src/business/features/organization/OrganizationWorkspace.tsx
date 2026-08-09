import {
  Alert,
  Button,
  Descriptions,
  Drawer,
  Empty,
  Form,
  Input,
  InputNumber,
  List,
  Popconfirm,
  Select,
  Skeleton,
  Space,
  Tag,
  Typography,
} from "antd"
import { useCallback, useEffect, useMemo, useState } from "react"

import { ApiClientError } from "../../client"
import { EffectiveDatePicker } from "../../components/EffectiveDatePicker"
import { command, organizationApi } from "./api"
import { OrganizationRelationsTabs } from "./OrganizationRelationsTabs"
import { OrganizationTree } from "./OrganizationTree"
import { OrganizationVersionDrawer } from "./OrganizationVersionDrawer"
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
}


function localDate(): string {
  const now = new Date()
  const offset = now.getTimezoneOffset() * 60_000
  return new Date(now.getTime() - offset).toISOString().slice(0, 10)
}


function flattenTree(nodes: readonly OrganizationTreeNode[]): OrganizationOption[] {
  return nodes.flatMap((node) => [
    { id: node.id, name: node.name, code: node.code },
    ...flattenTree(node.children),
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
  const [typeDrawerOpen, setTypeDrawerOpen] = useState(false)
  const [editingType, setEditingType] = useState<OrganizationType | null>(null)
  const [typeForm] = Form.useForm()

  const organizationOptions = useMemo(() => flattenTree(tree), [tree])

  const loadBase = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [nextTree, nextTypes] = await Promise.all([
        organizationApi.tree(token),
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
      else setError(caught instanceof Error ? caught.message : "组织中心加载失败")
    } finally {
      setLoading(false)
    }
  }, [token])

  const loadDetail = useCallback(async () => {
    if (!selectedId) {
      setDetail(null)
      return
    }
    setDetailLoading(true)
    setError(null)
    try {
      setDetail(await organizationApi.organization(token, selectedId, effectiveAt))
    } catch (caught) {
      setDetail(null)
      setError(caught instanceof Error ? caught.message : "组织详情加载失败")
    } finally {
      setDetailLoading(false)
    }
  }, [effectiveAt, selectedId, token])

  useEffect(() => {
    void loadBase()
  }, [loadBase])

  useEffect(() => {
    void loadDetail()
  }, [loadDetail])

  async function saveOrganization(body: Record<string, unknown>): Promise<void> {
    setSaving(true)
    setError(null)
    try {
      if (editorMode === "create") {
        const created = await organizationApi.createOrganization(token, body)
        await loadBase()
        setSelectedId(created.id)
      } else if (editorMode === "version" && selectedId) {
        await organizationApi.scheduleVersion(token, selectedId, body)
        await loadDetail()
      }
      setEditorMode(null)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "组织保存失败")
      if (caught instanceof ApiClientError && caught.status === 409) await loadDetail()
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
        command(detail.version, "取消未来组织变更"),
      )
      await loadDetail()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "取消失败")
    } finally {
      setSaving(false)
    }
  }

  function openTypeEditor(type?: OrganizationType): void {
    typeForm.resetFields()
    setEditingType(type ?? null)
    typeForm.setFieldsValue(
      type
        ? {
            code: type.code,
            name: type.name,
            sort_order: type.sort_order,
            is_active: type.is_active,
            change_reason: "维护组织类型",
          }
        : { sort_order: 0 },
    )
  }

  async function saveType(values: Record<string, unknown>): Promise<void> {
    setSaving(true)
    try {
      if (editingType) {
        const { code: _code, ...body } = values
        await organizationApi.updateType(token, editingType.id, body)
      } else {
        await organizationApi.createType(token, values)
      }
      setEditingType(null)
      typeForm.resetFields()
      await loadBase()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "组织类型保存失败")
    } finally {
      setSaving(false)
    }
  }

  if (forbidden) {
    return (
      <section aria-labelledby="organization-title">
        <Typography.Title id="organization-title" level={2}>组织中心</Typography.Title>
        <Alert type="error" showIcon message="无权查看组织中心" description="请联系主管理员分配组织查看权限。" />
      </section>
    )
  }

  return (
    <section aria-labelledby="organization-title" className="workspace-section">
      <div className="workspace-heading">
        <div>
          <Typography.Title id="organization-title" level={2}>组织中心</Typography.Title>
          <Typography.Paragraph type="secondary">
            左侧始终显示当前有效组织树。查看日期只影响右侧组织详情、关系和财务维度。
          </Typography.Paragraph>
        </div>
        {canAdmin && (
          <Space wrap>
            <Button onClick={() => setTypeDrawerOpen(true)}>组织类型</Button>
            <Button onClick={() => setEditorMode("create")}>新建组织</Button>
            <Button type="primary" disabled={!detail} onClick={() => setEditorMode("version")}>创建未来版本</Button>
          </Space>
        )}
      </div>
      {error && <Alert closable onClose={() => setError(null)} type="error" showIcon message={error} />}
      {loading ? (
        <Skeleton active paragraph={{ rows: 10 }} />
      ) : (
        <div className="organization-layout">
          <aside className="organization-tree-panel">
            <div className="panel-heading">
              <Typography.Title level={5}>当前有效组织树</Typography.Title>
              <Tag>{organizationOptions.length} 个组织</Tag>
            </div>
            <OrganizationTree nodes={tree} selectedId={selectedId} onSelect={setSelectedId} />
          </aside>
          <div className="organization-detail-panel">
            <div className="detail-toolbar">
              <EffectiveDatePicker value={effectiveAt} onChange={setEffectiveAt} />
              <Typography.Text type="secondary">树结构不随查看日期重绘</Typography.Text>
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
                  <List
                    dataSource={[...detail.planned_events]}
                    locale={{ emptyText: <Empty description="没有待生效组织变更" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
                    renderItem={(event) => (
                      <List.Item
                        actions={canAdmin ? [
                          <Popconfirm key="cancel" title="确认取消这条未来变更？" onConfirm={() => void cancelEvent(event.id)}>
                            <Button type="link" danger loading={saving}>取消</Button>
                          </Popconfirm>,
                        ] : undefined}
                      >
                        <List.Item.Meta
                          title={`${event.effective_date} 生效`}
                          description={`${event.change_reason}，状态：${event.status}`}
                        />
                      </List.Item>
                    )}
                  />
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
      )}

      <OrganizationVersionDrawer
        open={editorMode !== null}
        mode={editorMode ?? "create"}
        current={detail}
        types={types}
        organizations={organizationOptions}
        saving={saving}
        onClose={() => setEditorMode(null)}
        onSave={saveOrganization}
      />

      <Drawer
        title="组织类型"
        size="large"
        open={typeDrawerOpen}
        onClose={() => setTypeDrawerOpen(false)}
      >
        <div className="detail-toolbar">
          <Typography.Paragraph type="secondary">预置集团、BG、BU、部门，也可增加企业自定义类型。</Typography.Paragraph>
          <Button type="primary" onClick={() => openTypeEditor()}>新建类型</Button>
        </div>
        <List
          dataSource={[...types]}
          renderItem={(type) => (
            <List.Item actions={[<Button key="edit" type="link" onClick={() => openTypeEditor(type)}>编辑</Button>]}>
              <List.Item.Meta title={`${type.name} (${type.code})`} description={`排序 ${type.sort_order}，${type.is_active ? "有效" : "已停用"}`} />
            </List.Item>
          )}
        />
        <Form form={typeForm} layout="vertical" requiredMark={false} onFinish={(values) => void saveType(values)}>
          <Form.Item label="类型代码" name="code" rules={[{ required: true }]}><Input disabled={Boolean(editingType)} /></Form.Item>
          <Form.Item label="类型名称" name="name" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item label="排序号" name="sort_order"><InputNumber min={0} precision={0} /></Form.Item>
          {editingType && (
            <>
              <Form.Item label="状态" name="is_active"><Select options={[{ label: "有效", value: true }, { label: "停用", value: false }]} /></Form.Item>
              <Form.Item label="变更原因" name="change_reason" rules={[{ required: true }]}><Input /></Form.Item>
            </>
          )}
          <Button type="primary" htmlType="submit" loading={saving}>{editingType ? "保存修改" : "创建类型"}</Button>
        </Form>
      </Drawer>
    </section>
  )
}
