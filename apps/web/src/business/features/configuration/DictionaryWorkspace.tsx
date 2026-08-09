import {
  Alert,
  Button,
  Drawer,
  Empty,
  Form,
  Input,
  InputNumber,
  List,
  Modal,
  Select,
  Skeleton,
  Space,
  Tag,
  Tree,
  Typography,
} from "antd"
import { useCallback, useEffect, useMemo, useState } from "react"
import type { DataNode } from "antd/es/tree"

import { ApiClientError, apiRequest } from "../../client"


interface Dictionary {
  readonly id: string
  readonly code: string
  readonly name: string
  readonly english_name: string | null
  readonly description: string | null
  readonly source: string
  readonly is_active: boolean
}


interface DictionaryItem {
  readonly id: string
  readonly dictionary_id: string
  readonly parent_item_id: string | null
  readonly code: string
  readonly name: string
  readonly english_name: string | null
  readonly sort_order: number
  readonly level: number
  readonly description: string | null
  readonly is_active: boolean
}


interface DictionaryListResponse {
  readonly items: readonly Dictionary[]
  readonly total: number
}


interface DictionaryItemListResponse {
  readonly items: readonly DictionaryItem[]
  readonly total: number
}


interface DictionaryWorkspaceProps {
  readonly token: string
  readonly canAdmin: boolean
}


type EditorState =
  | { readonly kind: "dictionary" }
  | { readonly kind: "item"; readonly item?: DictionaryItem }
  | null


function itemTree(items: readonly DictionaryItem[], query: string): DataNode[] {
  const normalized = query.trim().toLocaleLowerCase()
  const matches = (item: DictionaryItem) =>
    !normalized ||
    item.name.toLocaleLowerCase().includes(normalized) ||
    item.code.toLocaleLowerCase().includes(normalized)
  const visible = normalized ? items.filter(matches) : [...items]
  const visibleIds = new Set(visible.map((item) => item.id))
  if (normalized) {
    for (const item of visible) {
      let parentId = item.parent_item_id
      while (parentId) {
        visibleIds.add(parentId)
        parentId = items.find((candidate) => candidate.id === parentId)?.parent_item_id ?? null
      }
    }
  }
  const children = new Map<string | null, DictionaryItem[]>()
  for (const item of items) {
    if (!visibleIds.has(item.id)) continue
    const group = children.get(item.parent_item_id) ?? []
    group.push(item)
    children.set(item.parent_item_id, group)
  }
  const build = (parentId: string | null): DataNode[] =>
    (children.get(parentId) ?? [])
      .sort((left, right) => left.sort_order - right.sort_order || left.code.localeCompare(right.code))
      .map((item) => ({
        key: item.id,
        title: (
          <span className={item.is_active ? undefined : "inactive-text"}>
            {item.name} <Typography.Text code>{item.code}</Typography.Text>
            {!item.is_active && <Tag>已停用</Tag>}
          </span>
        ),
        children: build(item.id),
      }))
  return build(null)
}


export function DictionaryWorkspace({ token, canAdmin }: DictionaryWorkspaceProps) {
  const [dictionaries, setDictionaries] = useState<readonly Dictionary[]>([])
  const [items, setItems] = useState<readonly DictionaryItem[]>([])
  const [selectedDictionaryId, setSelectedDictionaryId] = useState<string | null>(null)
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null)
  const [query, setQuery] = useState("")
  const [loading, setLoading] = useState(true)
  const [itemsLoading, setItemsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [forbidden, setForbidden] = useState(false)
  const [editor, setEditor] = useState<EditorState>(null)
  const [saving, setSaving] = useState(false)
  const [deactivating, setDeactivating] = useState<DictionaryItem | null>(null)
  const [deactivateReason, setDeactivateReason] = useState("")
  const [form] = Form.useForm()

  const selectedDictionary = dictionaries.find(
    (dictionary) => dictionary.id === selectedDictionaryId,
  )
  const selectedItem = items.find((item) => item.id === selectedItemId)

  const loadDictionaries = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await apiRequest<DictionaryListResponse>(
        "/api/v1/configuration/dictionaries?limit=200&offset=0",
        token,
      )
      setDictionaries(result.items)
      setSelectedDictionaryId((current) =>
        current && result.items.some((item) => item.id === current)
          ? current
          : result.items[0]?.id ?? null,
      )
    } catch (caught) {
      if (caught instanceof ApiClientError && caught.status === 403) {
        setForbidden(true)
      } else {
        setError(caught instanceof Error ? caught.message : "字典加载失败")
      }
    } finally {
      setLoading(false)
    }
  }, [token])

  const loadItems = useCallback(async () => {
    if (!selectedDictionaryId) {
      setItems([])
      return
    }
    setItemsLoading(true)
    setError(null)
    try {
      const result = await apiRequest<DictionaryItemListResponse>(
        `/api/v1/configuration/dictionaries/${selectedDictionaryId}/items`,
        token,
      )
      setItems(result.items)
      setSelectedItemId((current) =>
        current && result.items.some((item) => item.id === current) ? current : null,
      )
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "字典项加载失败")
    } finally {
      setItemsLoading(false)
    }
  }, [selectedDictionaryId, token])

  useEffect(() => {
    void loadDictionaries()
  }, [loadDictionaries])

  useEffect(() => {
    void loadItems()
  }, [loadItems])

  const filteredDictionaries = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase()
    if (!normalized) return dictionaries
    return dictionaries.filter(
      (dictionary) =>
        dictionary.name.toLocaleLowerCase().includes(normalized) ||
        dictionary.code.toLocaleLowerCase().includes(normalized),
    )
  }, [dictionaries, query])

  const treeData = useMemo(() => itemTree(items, query), [items, query])

  function openDictionaryEditor(): void {
    form.resetFields()
    setEditor({ kind: "dictionary" })
  }

  function openItemEditor(item?: DictionaryItem): void {
    form.resetFields()
    form.setFieldsValue(
      item
        ? {
            code: item.code,
            name: item.name,
            english_name: item.english_name,
            parent_item_id: item.parent_item_id,
            sort_order: item.sort_order,
            description: item.description,
          }
        : { sort_order: 0, parent_item_id: selectedItemId },
    )
    setEditor({ kind: "item", item })
  }

  async function save(values: Record<string, unknown>): Promise<void> {
    if (!editor) return
    setSaving(true)
    setError(null)
    try {
      if (editor.kind === "dictionary") {
        const created = await apiRequest<Dictionary>(
          "/api/v1/configuration/dictionaries",
          token,
          { method: "POST", body: values },
        )
        setEditor(null)
        await loadDictionaries()
        setSelectedDictionaryId(created.id)
      } else if (editor.item) {
        const { code: _code, ...editable } = values
        await apiRequest<DictionaryItem>(
          `/api/v1/configuration/dictionary-items/${editor.item.id}`,
          token,
          { method: "PATCH", body: editable },
        )
        setEditor(null)
        await loadItems()
      } else if (selectedDictionaryId) {
        await apiRequest<DictionaryItem>(
          `/api/v1/configuration/dictionaries/${selectedDictionaryId}/items`,
          token,
          { method: "POST", body: values },
        )
        setEditor(null)
        await loadItems()
      }
    } catch (caught) {
      if (caught instanceof ApiClientError && caught.status === 409) {
        setError("数据已发生变化，已刷新最新内容，请确认后重试。")
        await loadItems()
      } else {
        setError(caught instanceof Error ? caught.message : "保存失败")
      }
    } finally {
      setSaving(false)
    }
  }

  async function deactivate(): Promise<void> {
    if (!deactivating || !deactivateReason.trim()) return
    setSaving(true)
    try {
      await apiRequest<DictionaryItem>(
        `/api/v1/configuration/dictionary-items/${deactivating.id}/deactivate`,
        token,
        { method: "POST", body: { reason: deactivateReason } },
      )
      setDeactivating(null)
      setDeactivateReason("")
      await loadItems()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "停用失败")
    } finally {
      setSaving(false)
    }
  }

  if (forbidden) {
    return (
      <section aria-labelledby="configuration-title">
        <Typography.Title id="configuration-title" level={2}>配置中心</Typography.Title>
        <Alert type="error" showIcon message="无权查看配置中心" description="请联系主管理员分配配置查看权限。" />
      </section>
    )
  }

  return (
    <section aria-labelledby="configuration-title" className="workspace-section">
      <div className="workspace-heading">
        <div>
          <Typography.Title id="configuration-title" level={2}>配置中心</Typography.Title>
          <Typography.Paragraph type="secondary">
            维护稳定业务代码、层级关系和启停状态。历史业务记录不会因显示名称变化而改写。
          </Typography.Paragraph>
        </div>
        {canAdmin && <Button type="primary" onClick={openDictionaryEditor}>新建字典</Button>}
      </div>
      {error && <Alert closable onClose={() => setError(null)} type="error" showIcon message={error} />}
      <Input.Search
        aria-label="搜索字典和字典项"
        allowClear
        placeholder="搜索名称或代码"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        className="workspace-search"
      />
      {loading ? (
        <Skeleton active paragraph={{ rows: 8 }} />
      ) : (
        <div className="dictionary-layout">
          <aside className="dictionary-list" aria-label="字典列表">
            <List
              dataSource={[...filteredDictionaries]}
              locale={{ emptyText: <Empty description="没有匹配的字典" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
              renderItem={(dictionary) => (
                <List.Item
                  className={dictionary.id === selectedDictionaryId ? "selected-row" : undefined}
                  onClick={() => setSelectedDictionaryId(dictionary.id)}
                >
                  <button type="button" className="plain-row-button">
                    <span>{dictionary.name}</span>
                    <Typography.Text code>{dictionary.code}</Typography.Text>
                  </button>
                </List.Item>
              )}
            />
          </aside>
          <div className="dictionary-detail">
            {!selectedDictionary ? (
              <Empty description="请选择字典，或新建第一个字典" />
            ) : (
              <>
                <div className="detail-toolbar">
                  <div>
                    <Typography.Title level={4}>{selectedDictionary.name}</Typography.Title>
                    <Typography.Text type="secondary">{selectedDictionary.code}</Typography.Text>
                  </div>
                  {canAdmin && (
                    <Space>
                      <Button onClick={() => openItemEditor()}>新建字典项</Button>
                      <Button disabled={!selectedItem} onClick={() => selectedItem && openItemEditor(selectedItem)}>编辑</Button>
                      <Button danger disabled={!selectedItem?.is_active} onClick={() => selectedItem && setDeactivating(selectedItem)}>停用</Button>
                    </Space>
                  )}
                </div>
                {itemsLoading ? (
                  <Skeleton active paragraph={{ rows: 6 }} />
                ) : treeData.length ? (
                  <Tree
                    aria-label={`${selectedDictionary.name}字典项`}
                    blockNode
                    defaultExpandAll
                    selectedKeys={selectedItemId ? [selectedItemId] : []}
                    treeData={treeData}
                    onSelect={(keys) => setSelectedItemId(String(keys[0] ?? "") || null)}
                  />
                ) : (
                  <Empty description="当前字典还没有字典项" />
                )}
              </>
            )}
          </div>
        </div>
      )}

      <Drawer
        title={editor?.kind === "dictionary" ? "新建字典" : editor?.item ? "编辑字典项" : "新建字典项"}
        size="large"
        open={editor !== null}
        onClose={() => setEditor(null)}
        destroyOnHidden
        extra={<Button autoInsertSpace={false} type="primary" loading={saving} onClick={() => form.submit()}>保存</Button>}
      >
        <Form form={form} layout="vertical" requiredMark={false} onFinish={(values) => void save(values)}>
          <Form.Item label="代码" name="code" rules={[{ required: true, message: "请输入稳定代码" }]}>
            <Input disabled={editor?.kind === "item" && Boolean(editor.item)} placeholder="例如 EMPLOYEE_TYPE" />
          </Form.Item>
          <Form.Item label="中文名称" name="name" rules={[{ required: true, message: "请输入中文名称" }]}>
            <Input />
          </Form.Item>
          <Form.Item label="英文名称" name="english_name"><Input /></Form.Item>
          {editor?.kind === "item" && (
            <>
              <Form.Item label="上级字典项" name="parent_item_id">
                <Select
                  allowClear
                  options={items
                    .filter((item) => item.id !== editor.item?.id && item.is_active)
                    .map((item) => ({ label: `${item.name} (${item.code})`, value: item.id }))}
                />
              </Form.Item>
              <Form.Item label="排序号" name="sort_order"><InputNumber min={0} precision={0} /></Form.Item>
            </>
          )}
          <Form.Item label="说明" name="description"><Input.TextArea rows={4} /></Form.Item>
        </Form>
      </Drawer>

      <Modal
        title="停用字典项"
        open={deactivating !== null}
        okText="确认停用"
        okButtonProps={{ danger: true, disabled: !deactivateReason.trim(), loading: saving }}
        onOk={() => void deactivate()}
        onCancel={() => setDeactivating(null)}
      >
        <Typography.Paragraph>
          停用后不能用于新业务记录，已有历史记录保持不变。
        </Typography.Paragraph>
        <label className="field-label" htmlFor="deactivate-reason">停用原因</label>
        <Input.TextArea
          id="deactivate-reason"
          rows={3}
          value={deactivateReason}
          onChange={(event) => setDeactivateReason(event.target.value)}
        />
      </Modal>
    </section>
  )
}
