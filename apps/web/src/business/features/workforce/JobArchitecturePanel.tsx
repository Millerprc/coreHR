import { Alert, Button, Empty, Form, Input, InputNumber, Modal, Select, Space, Table, Tabs, Tag, Typography } from "antd"
import { useCallback, useEffect, useMemo, useState } from "react"

import { workforceApi } from "./api"
import type { Job, JobDimension } from "./types"


type Editor =
  | { readonly kind: "dimension"; readonly item?: JobDimension }
  | { readonly kind: "job"; readonly item?: Job }
  | null


interface JobArchitecturePanelProps {
  readonly token: string
  readonly canAdmin: boolean
  readonly onJobsChanged?: () => Promise<void> | void
}


const dimensionLabels: Record<JobDimension["dimension_type"], string> = {
  LEVEL: "职级",
  GRADE: "职等",
  CLASS: "职类",
  SEQUENCE: "序列",
}


function today(): string {
  const value = new Date()
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, "0")
  const day = String(value.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}


export function JobArchitecturePanel({ token, canAdmin, onJobsChanged }: JobArchitecturePanelProps) {
  const [dimensions, setDimensions] = useState<readonly JobDimension[]>([])
  const [jobs, setJobs] = useState<readonly Job[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [editor, setEditor] = useState<Editor>(null)
  const [effectiveAt, setEffectiveAt] = useState(today)
  const [form] = Form.useForm()

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [dimensionPage, jobPage] = await Promise.all([
        workforceApi.jobDimensions(token, effectiveAt),
        workforceApi.jobs(token, effectiveAt),
      ])
      setDimensions(dimensionPage.items)
      setJobs(jobPage.items)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "职务体系加载失败")
    } finally {
      setLoading(false)
    }
  }, [effectiveAt, token])

  useEffect(() => { void load() }, [load])

  function openDimension(item?: JobDimension): void {
    setEditor({ kind: "dimension", item })
    form.resetFields()
    form.setFieldsValue(item ? {
      name: item.name,
      parent_reference: item.parent_dimension_type && item.parent_dimension_code
        ? `${item.parent_dimension_type}:${item.parent_dimension_code}`
        : undefined,
      parent_dimension_type: item.parent_dimension_type,
      parent_dimension_code: item.parent_dimension_code,
      sort_order: item.sort_order,
      status: item.status,
      notes: item.notes,
    } : {
      dimension_type: "LEVEL",
      sort_order: 0,
      status: "active",
      effective_from: today(),
    })
  }

  function openJob(item?: Job): void {
    setEditor({ kind: "job", item })
    form.resetFields()
    form.setFieldsValue(item ? {
      name: item.name,
      level_code: item.level_code,
      grade_code: item.grade_code,
      class_code: item.class_code,
      sequence_code: item.sequence_code,
      status: item.status,
      source_job_id: item.source_job_id,
      notes: item.notes,
    } : {
      status: "active",
      effective_from: today(),
    })
  }

  function closeEditor(): void {
    setEditor(null)
    form.resetFields()
  }

  async function save(values: Record<string, unknown>): Promise<void> {
    if (!editor) return
    setSaving(true)
    setError(null)
    try {
      if (editor.kind === "dimension") {
        if (editor.item) {
          await workforceApi.createJobDimensionVersion(token, editor.item.id, values)
        } else {
          await workforceApi.createJobDimension(token, values)
        }
      } else {
        const jobValues = {
          ...values,
          attributes: editor.item?.attributes ?? {},
        }
        if (editor.item) {
          await workforceApi.createJobVersion(token, editor.item.id, jobValues)
        } else {
          await workforceApi.createJob(token, jobValues)
        }
      }
      closeEditor()
      const savedDate = typeof values.effective_from === "string"
        ? values.effective_from
        : effectiveAt
      if (savedDate === effectiveAt) {
        await load()
      } else {
        setEffectiveAt(savedDate)
      }
      await onJobsChanged?.()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "职务体系保存失败")
    } finally {
      setSaving(false)
    }
  }

  const dimensionOptions = useMemo(
    () => dimensions.map((item) => ({
      label: `${dimensionLabels[item.dimension_type]} · ${item.name} (${item.code})`,
      value: `${item.dimension_type}:${item.code}`,
      item,
    })),
    [dimensions],
  )
  const optionsByType = (dimensionType: JobDimension["dimension_type"]) =>
    dimensions
      .filter((item) => item.dimension_type === dimensionType && item.status === "active")
      .map((item) => ({ label: `${item.name} (${item.code})`, value: item.code }))

  const parentValue = Form.useWatch("parent_reference", form) as string | undefined
  useEffect(() => {
    if (!parentValue) {
      form.setFieldsValue({ parent_dimension_type: undefined, parent_dimension_code: undefined })
      return
    }
    const [parentType, ...codeParts] = parentValue.split(":")
    form.setFieldsValue({
      parent_dimension_type: parentType,
      parent_dimension_code: codeParts.join(":"),
    })
  }, [form, parentValue])

  return <>
    <div className="panel-heading">
      <div>
        <Typography.Title level={4}>职务体系</Typography.Title>
        <Typography.Text type="secondary">职级、职等、职类、序列独立维护；职务引用四类有效代码，所有调整形成生效日期版本。</Typography.Text>
      </div>
      <Space wrap>
        <label>
          <span className="field-label">查看日期</span>
          <Input
            aria-label="职务体系查看日期"
            type="date"
            value={effectiveAt}
            onChange={(event) => setEffectiveAt(event.target.value || today())}
          />
        </label>
        {canAdmin && <>
          <Button onClick={() => openDimension()}>新增维度值</Button>
          <Button type="primary" onClick={() => openJob()}>新增职务</Button>
        </>}
      </Space>
    </div>
    {error && <Alert closable onClose={() => setError(null)} type="error" showIcon title={error} />}
    <Tabs items={[
      {
        key: "dimensions",
        label: `维度值 ${dimensions.length}`,
        children: <Table
          loading={loading}
          rowKey="id"
          pagination={false}
          dataSource={[...dimensions]}
          locale={{ emptyText: <Empty description="请先维护职级、职等、职类和序列" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
          columns={[
            { title: "类型", dataIndex: "dimension_type", render: (value) => dimensionLabels[value as JobDimension["dimension_type"]] },
            { title: "代码", dataIndex: "code" },
            { title: "名称", dataIndex: "name" },
            { title: "父级", render: (_value, row) => row.parent_dimension_code ? `${dimensionLabels[row.parent_dimension_type!]} · ${row.parent_dimension_code}` : "—" },
            { title: "生效日期", dataIndex: "effective_from" },
            { title: "版本", dataIndex: "version" },
            { title: "状态", dataIndex: "status", render: (value) => <Tag color={value === "active" ? "green" : "default"}>{value === "active" ? "启用" : "停用"}</Tag> },
            { title: "操作", render: (_value, row) => canAdmin ? <Button type="link" onClick={() => openDimension(row)}>新增版本</Button> : "—" },
          ]}
        />,
      },
      {
        key: "jobs",
        label: `职务 ${jobs.length}`,
        children: <Table
          loading={loading}
          rowKey="id"
          pagination={false}
          scroll={{ x: 1050 }}
          dataSource={[...jobs]}
          locale={{ emptyText: <Empty description="维度准备好后建立职务目录" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
          columns={[
            { title: "职务代码", dataIndex: "code", fixed: "left", width: 160 },
            { title: "职务名称", dataIndex: "name", fixed: "left", width: 200 },
            { title: "职级", dataIndex: "level_code" },
            { title: "职等", dataIndex: "grade_code" },
            { title: "职类", dataIndex: "class_code" },
            { title: "序列", dataIndex: "sequence_code" },
            { title: "生效日期", dataIndex: "effective_from" },
            { title: "版本", dataIndex: "version" },
            { title: "状态", dataIndex: "status", render: (value) => <Tag color={value === "active" ? "green" : "default"}>{value === "active" ? "启用" : "停用"}</Tag> },
            { title: "操作", fixed: "right", render: (_value, row) => canAdmin ? <Button type="link" onClick={() => openJob(row)}>新增版本</Button> : "—" },
          ]}
        />,
      },
    ]} />

    <Modal
      destroyOnHidden
      width={620}
      title={editor?.kind === "dimension" ? `${editor.item ? "新增" : "创建"}维度版本` : `${editor?.item ? "新增" : "创建"}职务版本`}
      open={Boolean(editor)}
      okText="保存"
      confirmLoading={saving}
      onOk={() => form.submit()}
      onCancel={closeEditor}
    >
      <Form form={form} layout="vertical" requiredMark={false} onFinish={(values) => void save(values)}>
        {editor?.kind === "dimension" && <>
          {editor.item ? <Typography.Paragraph>稳定代码：{dimensionLabels[editor.item.dimension_type]} · {editor.item.code}</Typography.Paragraph> : <>
            <Form.Item label="维度类型" name="dimension_type" rules={[{ required: true }]}><Select options={Object.entries(dimensionLabels).map(([value, label]) => ({ value, label }))} /></Form.Item>
            <Form.Item label="稳定代码" name="code" rules={[{ required: true }, { pattern: /^[A-Z0-9][A-Z0-9_.-]{0,49}$/, message: "使用大写字母、数字、点、下划线或短横线" }]}><Input placeholder="例如 LEVEL_06" /></Form.Item>
          </>}
          <Form.Item label="名称" name="name" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item label="父维度（可选）" name="parent_reference"><Select allowClear showSearch optionFilterProp="label" options={dimensionOptions.filter((option) => option.item.id !== editor.item?.id)} /></Form.Item>
          <Form.Item name="parent_dimension_type" hidden><Input /></Form.Item>
          <Form.Item name="parent_dimension_code" hidden><Input /></Form.Item>
          <Form.Item label="显示顺序" name="sort_order" rules={[{ required: true }]}><InputNumber min={0} precision={0} /></Form.Item>
        </>}
        {editor?.kind === "job" && <>
          {editor.item ? <Typography.Paragraph>稳定代码：{editor.item.code}</Typography.Paragraph> : <Form.Item label="职务代码" name="code" rules={[{ required: true }, { pattern: /^[A-Z0-9][A-Z0-9_.-]{0,49}$/, message: "使用大写字母、数字、点、下划线或短横线" }]}><Input /></Form.Item>}
          <Form.Item label="职务名称" name="name" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item label="职级" name="level_code" rules={[{ required: true }]}><Select showSearch optionFilterProp="label" options={optionsByType("LEVEL")} /></Form.Item>
          <Form.Item label="职等" name="grade_code" rules={[{ required: true }]}><Select showSearch optionFilterProp="label" options={optionsByType("GRADE")} /></Form.Item>
          <Form.Item label="职类" name="class_code" rules={[{ required: true }]}><Select showSearch optionFilterProp="label" options={optionsByType("CLASS")} /></Form.Item>
          <Form.Item label="序列" name="sequence_code" rules={[{ required: true }]}><Select showSearch optionFilterProp="label" options={optionsByType("SEQUENCE")} /></Form.Item>
          <Form.Item label="来源职务ID（可选）" name="source_job_id"><Input /></Form.Item>
        </>}
        {editor && <>
          <Form.Item label="状态" name="status" rules={[{ required: true }]}><Select options={[{ value: "active", label: "启用" }, { value: "inactive", label: "停用" }]} /></Form.Item>
          <Form.Item label="生效日期" name="effective_from" rules={[{ required: true }]}><Input type="date" /></Form.Item>
          <Form.Item label="失效日期（可选）" name="effective_to"><Input type="date" /></Form.Item>
          <Form.Item label="说明" name="notes"><Input.TextArea rows={2} /></Form.Item>
          <Form.Item label="变更原因" name="change_reason" rules={[{ required: true }]}><Input.TextArea rows={2} /></Form.Item>
        </>}
      </Form>
    </Modal>
  </>
}
