import { Alert, Button, Drawer, Form, Input, Modal, Select, Space, Table, Tag, Typography } from "antd"
import { useCallback, useEffect, useMemo, useState } from "react"

import { apiRequest } from "../../client"


interface Account {
  readonly id: string
  readonly username: string
  readonly display_name: string
  readonly status: "active" | "inactive"
  readonly person_id: string | null
  readonly roles: readonly string[]
}


interface Role {
  readonly id: string
  readonly code: string
  readonly name: string
  readonly description: string | null
  readonly is_system: boolean
  readonly is_active: boolean
}


interface AccountPage {
  readonly items: readonly Account[]
  readonly total: number
  readonly limit: number
  readonly offset: number
}


interface RoleList {
  readonly items: readonly Role[]
}


interface AccountWorkspaceProps {
  readonly token: string
  readonly currentUserId: string
}


type EditorState = { readonly kind: "create" } | { readonly kind: "edit"; readonly account: Account } | null


export function AccountWorkspace({ token, currentUserId }: AccountWorkspaceProps) {
  const [accounts, setAccounts] = useState<readonly Account[]>([])
  const [roles, setRoles] = useState<readonly Role[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [editor, setEditor] = useState<EditorState>(null)
  const [statusTarget, setStatusTarget] = useState<Account | null>(null)
  const [form] = Form.useForm()
  const [statusForm] = Form.useForm()

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [accountPage, roleList] = await Promise.all([
        apiRequest<AccountPage>("/api/v1/platform/users?limit=200&offset=0", token),
        apiRequest<RoleList>("/api/v1/platform/roles", token),
      ])
      setAccounts(accountPage.items)
      setRoles(roleList.items)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "账号与角色加载失败")
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { void load() }, [load])

  const roleOptions = useMemo(
    () => roles.map((role) => ({ label: `${role.name} (${role.code})`, value: role.code })),
    [roles],
  )

  function openCreate(): void {
    form.resetFields()
    form.setFieldsValue({ role_codes: ["SSC_ADMIN"] })
    setEditor({ kind: "create" })
  }

  function openEdit(account: Account): void {
    form.resetFields()
    form.setFieldsValue({
      display_name: account.display_name,
      role_codes: account.roles,
    })
    setEditor({ kind: "edit", account })
  }

  async function save(values: Record<string, unknown>): Promise<void> {
    if (!editor) return
    setSaving(true)
    setError(null)
    try {
      if (editor.kind === "create") {
        await apiRequest<Account>("/api/v1/platform/users", token, {
          method: "POST",
          body: values,
        })
      } else {
        await apiRequest<Account>(`/api/v1/platform/users/${editor.account.id}`, token, {
          method: "PATCH",
          body: values,
        })
      }
      setEditor(null)
      form.resetFields()
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "账号保存失败")
    } finally {
      setSaving(false)
    }
  }

  async function changeStatus(values: { reason: string }): Promise<void> {
    if (!statusTarget) return
    setSaving(true)
    setError(null)
    try {
      await apiRequest<Account>(`/api/v1/platform/users/${statusTarget.id}`, token, {
        method: "PATCH",
        body: {
          status: statusTarget.status === "active" ? "inactive" : "active",
          reason: values.reason,
        },
      })
      setStatusTarget(null)
      statusForm.resetFields()
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "账号状态修改失败")
    } finally {
      setSaving(false)
    }
  }

  function closeStatusDialog(): void {
    setStatusTarget(null)
    statusForm.resetFields()
  }

  return (
    <section aria-labelledby="account-title" className="workspace-section">
      <div className="workspace-heading">
        <div>
          <Typography.Title id="account-title" level={2}>账号与权限</Typography.Title>
          <Typography.Paragraph type="secondary">
            创建内部账号、分配角色并启停访问。密码不会在创建后回显，也不会进入审计日志。
          </Typography.Paragraph>
        </div>
        <Button type="primary" onClick={openCreate}>新建账号</Button>
      </div>
      {error && <Alert closable onClose={() => setError(null)} type="error" showIcon title={error} />}
      <Table
        size="small"
        loading={loading}
        rowKey="id"
        dataSource={[...accounts]}
        pagination={false}
        columns={[
          { title: "账号", dataIndex: "username", width: 220 },
          { title: "显示名称", dataIndex: "display_name", width: 220 },
          {
            title: "角色",
            dataIndex: "roles",
            render: (values: readonly string[]) => <Space wrap>{values.map((value) => <Tag key={value}>{value}</Tag>)}</Space>,
          },
          {
            title: "状态",
            dataIndex: "status",
            width: 110,
            render: (value: Account["status"]) => <Tag color={value === "active" ? "success" : "default"}>{value === "active" ? "有效" : "已停用"}</Tag>,
          },
          {
            title: "操作",
            width: 190,
            render: (_value, account: Account) => <Space>
              <Button type="link" onClick={() => openEdit(account)}>编辑角色</Button>
              <Button
                type="link"
                danger={account.status === "active"}
                disabled={account.id === currentUserId && account.status === "active"}
                title={account.id === currentUserId ? "不能停用当前登录账号" : undefined}
                onClick={() => setStatusTarget(account)}
              >
                {account.status === "active" ? "停用" : "启用"}
              </Button>
            </Space>,
          },
        ]}
      />

      <Drawer
        title={editor?.kind === "create" ? "新建账号" : "编辑账号角色"}
        size="large"
        open={editor !== null}
        destroyOnHidden
        onClose={() => setEditor(null)}
        extra={<Button type="primary" loading={saving} onClick={() => form.submit()}>保存</Button>}
      >
        {editor?.kind === "create" && (
          <Alert
            type="info"
            showIcon
            title="初始密码只在这里填写一次"
            description="创建后系统不再显示密码，请通过企业认可的安全渠道交付给使用人。"
          />
        )}
        <Form form={form} layout="vertical" requiredMark={false} onFinish={(values) => void save(values)}>
          {editor?.kind === "create" && <>
            <Form.Item label="登录账号" name="username" rules={[{ required: true, message: "请输入登录账号" }]}>
              <Input autoComplete="off" placeholder="例如 ssc.admin01" />
            </Form.Item>
            <Form.Item label="初始密码" name="password" rules={[{ required: true, min: 12, message: "初始密码至少12位" }]}>
              <Input.Password autoComplete="new-password" />
            </Form.Item>
          </>}
          <Form.Item label="显示名称" name="display_name" rules={[{ required: true, message: "请输入显示名称" }]}>
            <Input />
          </Form.Item>
          <Form.Item label="角色" name="role_codes" rules={[{ required: true, message: "至少选择一个角色" }]}>
            <Select mode="multiple" options={roleOptions} />
          </Form.Item>
          <Form.Item label="操作原因" name="reason" rules={[{ required: true, message: "请输入操作原因" }]}>
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Drawer>

      <Modal
        title={statusTarget?.status === "active" ? "停用账号" : "启用账号"}
        open={statusTarget !== null}
        okText={statusTarget?.status === "active" ? "确认停用" : "确认启用"}
        okButtonProps={{ danger: statusTarget?.status === "active", loading: saving }}
        onOk={() => statusForm.submit()}
        onCancel={closeStatusDialog}
      >
        <Typography.Paragraph>
          {statusTarget?.status === "active"
            ? "停用后，该账号已有会话将在下一次请求时失效。"
            : "启用后，该账号可以重新登录系统。"}
        </Typography.Paragraph>
        <Form form={statusForm} layout="vertical" onFinish={(values) => void changeStatus(values)}>
          <Form.Item label="操作原因" name="reason" rules={[{ required: true, message: "请输入操作原因" }]}>
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </section>
  )
}
