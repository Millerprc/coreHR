import { Button, Drawer, Form, Input, Select } from "antd"
import { useEffect } from "react"

import { command } from "./api"
import type { Organization, OrganizationType } from "./types"


interface OrganizationOption {
  readonly id: string
  readonly name: string
  readonly code: string
}


interface OrganizationVersionDrawerProps {
  readonly open: boolean
  readonly mode: "create" | "version"
  readonly current: Organization | null
  readonly types: readonly OrganizationType[]
  readonly organizations: readonly OrganizationOption[]
  readonly saving: boolean
  readonly onClose: () => void
  readonly onSave: (body: Record<string, unknown>) => Promise<void>
}


export function OrganizationVersionDrawer({
  open,
  mode,
  current,
  types,
  organizations,
  saving,
  onClose,
  onSave,
}: OrganizationVersionDrawerProps) {
  const [form] = Form.useForm()

  useEffect(() => {
    if (!open) return
    form.resetFields()
    if (mode === "version" && current) {
      form.setFieldsValue({
        name: current.name,
        organization_type_id: current.organization_type_id,
        parent_organization_id: current.parent_organization_id,
        country_code: current.country_code,
        status: current.status,
      })
    } else {
      form.setFieldsValue({ status: "active" })
    }
  }, [current, form, mode, open])

  async function submit(values: Record<string, unknown>): Promise<void> {
    const reason = String(values.change_reason)
    const body = {
      name: values.name,
      organization_type_id: values.organization_type_id,
      parent_organization_id: values.parent_organization_id ?? null,
      country_code: values.country_code || null,
      ...(mode === "create"
        ? {
            effective_from: values.effective_date,
            command: command(1, reason),
          }
        : {
            status: values.status,
            effective_date: values.effective_date,
            command: command(current?.version ?? 1, reason),
          }),
    }
    await onSave(body)
  }

  return (
    <Drawer
      title={mode === "create" ? "新建组织" : "创建未来组织版本"}
      size="large"
      open={open}
      onClose={onClose}
      destroyOnHidden
      extra={<Button type="primary" loading={saving} onClick={() => form.submit()}>保存</Button>}
    >
      <Form form={form} layout="vertical" requiredMark={false} onFinish={(values) => void submit(values)}>
        <Form.Item label="组织名称" name="name" rules={[{ required: true, message: "请输入组织名称" }]}>
          <Input />
        </Form.Item>
        <Form.Item label="组织类型" name="organization_type_id" rules={[{ required: true, message: "请选择组织类型" }]}>
          <Select
            options={types
              .filter((item) => item.is_active)
              .map((item) => ({ label: `${item.name} (${item.code})`, value: item.id }))}
          />
        </Form.Item>
        <Form.Item label="直接上级" name="parent_organization_id">
          <Select
            allowClear
            showSearch
            optionFilterProp="label"
            options={organizations
              .filter((item) => item.id !== current?.id)
              .map((item) => ({ label: `${item.name} (${item.code})`, value: item.id }))}
          />
        </Form.Item>
        <Form.Item label="国家或地区代码" name="country_code">
          <Input maxLength={3} placeholder="例如 CN" />
        </Form.Item>
        {mode === "version" && (
          <Form.Item label="状态" name="status" rules={[{ required: true }]}>
            <Select options={[{ label: "有效", value: "active" }, { label: "停用", value: "inactive" }]} />
          </Form.Item>
        )}
        <Form.Item
          label={mode === "create" ? "生效日期" : "未来生效日期"}
          name="effective_date"
          rules={[{ required: true, message: "请选择生效日期" }]}
        >
          <Input type="date" />
        </Form.Item>
        <Form.Item label="变更原因" name="change_reason" rules={[{ required: true, message: "请填写变更原因" }]}>
          <Input.TextArea rows={3} />
        </Form.Item>
      </Form>
    </Drawer>
  )
}
