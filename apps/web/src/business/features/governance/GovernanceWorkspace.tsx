import {
  Alert,
  Button,
  Col,
  Drawer,
  Form,
  Input,
  Modal,
  Row,
  Select,
  Skeleton,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
} from "antd"
import { useCallback, useEffect, useState } from "react"

import { ApiClientError } from "../../client"
import { governanceApi } from "./api"
import { csvToImportRows } from "./csv"
import type { CsvImportRow } from "./csv"
import type {
  ImportBatch,
  ImportBatchRow,
  ImportBatchSummary,
  ImportEntityType,
  ExportEntityType,
  ImportTemplate,
} from "./types"


interface GovernanceWorkspaceProps {
  readonly token: string
  readonly canAdmin: boolean
}


interface ImportFormValues {
  readonly entity_type: ImportEntityType
  readonly source_system: string
  readonly source_table: string
}


const entityLabels: Readonly<Record<ImportEntityType, string>> = {
  dictionary: "数据字典",
  dictionary_item: "字典项",
  organization_type: "组织类型",
  legal_entity: "法人主体",
  job_dimension: "职务维度",
  job_dimension_version: "职务维度历史版本",
  job: "职务",
  job_version: "职务历史版本",
  organization: "组织",
}


const exportEntityLabels: Readonly<Record<ExportEntityType, string>> = {
  dictionary: entityLabels.dictionary,
  dictionary_item: entityLabels.dictionary_item,
  organization_type: entityLabels.organization_type,
  legal_entity: entityLabels.legal_entity,
  job_dimension: entityLabels.job_dimension,
  job: entityLabels.job,
  organization: entityLabels.organization,
}


const statusLabels: Readonly<Record<string, string>> = {
  validating: "校验中",
  validated: "校验通过",
  validated_with_errors: "部分拒绝",
  executing: "执行中",
  completed: "已完成",
  completed_with_errors: "完成但有拒绝",
}


function statusColor(status: string): string {
  if (status === "completed") return "success"
  if (status === "validated") return "processing"
  if (status.includes("errors")) return "warning"
  return "default"
}


function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID()
  return "10000000-0000-4000-8000-" + Date.now().toString().padStart(12, "0").slice(-12)
}


export function GovernanceWorkspace({ token, canAdmin }: GovernanceWorkspaceProps) {
  const [batches, setBatches] = useState<readonly ImportBatchSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [forbidden, setForbidden] = useState(false)
  const [editorOpen, setEditorOpen] = useState(false)
  const [exportOpen, setExportOpen] = useState(false)
  const [exportType, setExportType] = useState<ExportEntityType>("dictionary_item")
  const [exporting, setExporting] = useState(false)
  const [template, setTemplate] = useState<ImportTemplate | null>(null)
  const [fileName, setFileName] = useState("")
  const [rows, setRows] = useState<readonly CsvImportRow[]>([])
  const [fileInputKey, setFileInputKey] = useState(0)
  const [validating, setValidating] = useState(false)
  const [detail, setDetail] = useState<ImportBatch | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [reason, setReason] = useState("")
  const [executing, setExecuting] = useState(false)
  const [form] = Form.useForm<ImportFormValues>()

  const loadBatches = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await governanceApi.listBatches(token)
      setBatches(result.items)
    } catch (caught) {
      if (caught instanceof ApiClientError && caught.status === 403) setForbidden(true)
      else setError(caught instanceof Error ? caught.message : "导入批次加载失败")
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    void loadBatches()
  }, [loadBatches])

  const loadTemplate = useCallback(async (entityType: ImportEntityType) => {
    setTemplate(null)
    setRows([])
    setFileName("")
    setFileInputKey((current) => current + 1)
    try {
      setTemplate(await governanceApi.template(token, entityType))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "模板加载失败")
    }
  }, [token])

  function openEditor(): void {
    const entityType: ImportEntityType = "dictionary_item"
    form.resetFields()
    form.setFieldsValue({
      entity_type: entityType,
      source_system: "manual_mapping",
      source_table: "master_code_mapping",
    })
    setEditorOpen(true)
    void loadTemplate(entityType)
  }

  async function exportCurrent(): Promise<void> {
    setExporting(true)
    setError(null)
    try {
      const download = await governanceApi.exportCurrent(token, exportType)
      const url = URL.createObjectURL(download.blob)
      const anchor = document.createElement("a")
      anchor.href = url
      anchor.download = download.filename
      anchor.click()
      URL.revokeObjectURL(url)
      setExportOpen(false)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "当前主数据导出失败")
    } finally {
      setExporting(false)
    }
  }

  async function readFile(file: File | undefined): Promise<void> {
    if (!file || !template) return
    setError(null)
    try {
      const content = await file.text()
      const parsed = csvToImportRows(
        content,
        template.columns,
        template.required_columns,
      )
      setFileName(file.name)
      setRows(parsed)
    } catch (caught) {
      setFileName("")
      setRows([])
      setError(caught instanceof Error ? caught.message : "CSV读取失败")
    }
  }

  function downloadTemplate(): void {
    if (!template) return
    const content = `\uFEFF${["source_record_id", ...template.columns].join(",")}\r\n`
    const url = URL.createObjectURL(new Blob([content], { type: "text/csv;charset=utf-8" }))
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = `${template.entity_type}-template.csv`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  async function validateBatch(values: ImportFormValues): Promise<void> {
    if (!rows.length || !fileName) {
      setError("请先选择并读取CSV文件")
      return
    }
    setValidating(true)
    setError(null)
    try {
      const result = await governanceApi.validate(token, {
        ...values,
        file_name: fileName,
        idempotency_key: newIdempotencyKey(),
        rows,
      })
      setEditorOpen(false)
      setDetail(result)
      setReason("")
      await loadBatches()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "批次校验失败")
    } finally {
      setValidating(false)
    }
  }

  async function openDetail(batchId: string): Promise<void> {
    setDetailLoading(true)
    setError(null)
    try {
      setDetail(await governanceApi.batch(token, batchId))
      setReason("")
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "批次详情加载失败")
    } finally {
      setDetailLoading(false)
    }
  }

  async function execute(): Promise<void> {
    if (!detail || !reason.trim()) return
    setExecuting(true)
    setError(null)
    try {
      setDetail(await governanceApi.execute(token, detail.id, reason.trim()))
      await loadBatches()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "批次执行失败")
    } finally {
      setExecuting(false)
    }
  }

  if (forbidden) {
    return (
      <section aria-labelledby="governance-title">
        <Typography.Title id="governance-title" level={2}>数据治理</Typography.Title>
        <Alert type="error" showIcon title="无权查看数据治理" description="请联系主管理员分配数据治理查看权限。" />
      </section>
    )
  }

  return (
    <section aria-labelledby="governance-title" className="workspace-section">
      <div className="workspace-heading">
        <div>
          <Typography.Title id="governance-title" level={2}>数据治理</Typography.Title>
          <Typography.Paragraph type="secondary">
            主数据先校验、后执行。非法行进入拒绝报告，重复来源不会重复创建目标记录。
          </Typography.Paragraph>
        </div>
        <Space wrap>
          <Button onClick={() => setExportOpen(true)}>导出当前主数据</Button>
          {canAdmin && <Button type="primary" onClick={openEditor}>新建导入批次</Button>}
        </Space>
      </div>
      <Alert
        type="info"
        showIcon
        title="当前只开放无人员敏感信息的主数据初始化"
        description="支持数据字典、字典项、组织类型、法人、职务和组织；人员、证件、薪酬及联系方式不会由该入口接收。"
      />
      {error && <Alert closable onClose={() => setError(null)} type="error" showIcon title={error} />}
      {loading ? <Skeleton active paragraph={{ rows: 8 }} /> : (
        <Table<ImportBatchSummary>
          rowKey="id"
          dataSource={[...batches]}
          pagination={false}
          locale={{ emptyText: "还没有导入批次" }}
          columns={[
            {
              title: "创建时间",
              dataIndex: "created_at",
              render: (value: string) => new Date(value).toLocaleString("zh-CN"),
            },
            {
              title: "主数据类型",
              dataIndex: "entity_type",
              render: (value: ImportEntityType) => entityLabels[value],
            },
            { title: "来源", dataIndex: "source_table" },
            {
              title: "状态",
              dataIndex: "status",
              render: (value: string) => <Tag color={statusColor(value)}>{statusLabels[value] ?? value}</Tag>,
            },
            {
              title: "结果",
              render: (_value, item) => (
                <Space wrap>
                  <span>{item.total_rows} 行</span>
                  {item.imported_rows > 0 && <Tag color="success">{item.imported_rows} 条导入</Tag>}
                  {item.skipped_rows > 0 && <Tag>{item.skipped_rows} 条跳过</Tag>}
                  {item.rejected_rows > 0 && <Tag color="warning">{item.rejected_rows} 条拒绝</Tag>}
                </Space>
              ),
            },
            {
              title: "操作",
              render: (_value, item) => <Button autoInsertSpace={false} onClick={() => void openDetail(item.id)}>查看</Button>,
            },
          ]}
        />
      )}

      <Modal
        title="导出当前主数据"
        open={exportOpen}
        okText="下载CSV"
        confirmLoading={exporting}
        onOk={() => void exportCurrent()}
        onCancel={() => setExportOpen(false)}
      >
        <Space orientation="vertical" size="middle" className="full-width">
          <Alert
            type="info"
            showIcon
            title="只导出当前有效的非敏感主数据"
            description="按业务时区当天生效口径导出，不包含人员、证件、薪酬或联系方式。文件用于核对与审阅。"
          />
          <label className="field-label" htmlFor="master-data-export-type">主数据类型</label>
          <Select
            id="master-data-export-type"
            aria-label="主数据类型"
            className="full-width"
            value={exportType}
            options={Object.entries(exportEntityLabels).map(([value, label]) => ({ value, label }))}
            onChange={(value: ExportEntityType) => setExportType(value)}
          />
        </Space>
      </Modal>

      <Modal
        title="新建主数据导入"
        open={editorOpen}
        forceRender
        okText="校验批次"
        okButtonProps={{ loading: validating, disabled: !rows.length }}
        onOk={() => form.submit()}
        onCancel={() => setEditorOpen(false)}
        destroyOnHidden
      >
        <Alert
          type="warning"
          showIcon
          title="仅接受主数据代码和名称，不要上传人员、证件、薪酬或联系方式"
        />
        <Form form={form} layout="vertical" requiredMark={false} onFinish={(values) => void validateBatch(values)}>
          <Form.Item label="主数据类型" name="entity_type" rules={[{ required: true }]}>
            <Select
              options={Object.entries(entityLabels).map(([value, label]) => ({ value, label }))}
              onChange={(value: ImportEntityType) => void loadTemplate(value)}
            />
          </Form.Item>
          <Form.Item label="来源系统" name="source_system" rules={[{ required: true, message: "请输入来源系统" }]}>
            <Input placeholder="例如 EHR 或 MANUAL_MAPPING" />
          </Form.Item>
          <Form.Item label="来源表或文件用途" name="source_table" rules={[{ required: true, message: "请输入来源表或用途" }]}>
            <Input placeholder="例如 ehr_dict_element" />
          </Form.Item>
          <Space orientation="vertical" size="middle" className="full-width">
            <Button disabled={!template} onClick={downloadTemplate}>下载CSV模板</Button>
            <label className="field-label" htmlFor="governance-csv-file">选择填写后的CSV文件</label>
            <input
              key={fileInputKey}
              id="governance-csv-file"
              aria-label="选择CSV文件"
              type="file"
              accept=".csv,text/csv"
              onChange={(event) => void readFile(event.target.files?.[0])}
            />
            {rows.length > 0 && (
              <Alert
                type="success"
                showIcon
                title={`已读取 ${rows.length} 行：${fileName}`}
                description="点击“校验批次”只生成校验和拒绝报告，不会立即写入主数据。"
              />
            )}
          </Space>
        </Form>
      </Modal>

      <Drawer
        title="导入批次详情"
        size="large"
        open={detail !== null || detailLoading}
        onClose={() => setDetail(null)}
      >
        {detailLoading || !detail ? <Skeleton active /> : (
          <Space orientation="vertical" size="large" className="full-width">
            <Row gutter={[12, 12]}>
              <Col span={6}><Statistic title="总行数" value={detail.total_rows} /></Col>
              <Col span={6}><Statistic title="通过校验" value={detail.valid_rows} /></Col>
              <Col span={6}><Statistic title="已导入" value={detail.imported_rows} /></Col>
              <Col span={6}><Statistic title="拒绝" value={detail.rejected_rows} /></Col>
            </Row>
            <Table<ImportBatchRow>
              rowKey="id"
              dataSource={[...detail.rows]}
              pagination={false}
              columns={[
                { title: "行号", dataIndex: "row_number" },
                { title: "来源记录ID", dataIndex: "source_record_id" },
                { title: "状态", dataIndex: "status" },
                {
                  title: "校验结果",
                  render: (_value, item) => item.errors.length
                    ? item.errors.map((itemError) => (
                        <div key={`${itemError.code}-${itemError.field ?? "_"}`}>
                          {itemError.field ? `${itemError.field}：` : ""}{itemError.message}
                        </div>
                      ))
                    : "通过",
                },
              ]}
            />
            {canAdmin && detail.status.startsWith("validated") && (
              <div>
                <label className="field-label" htmlFor="import-execute-reason">执行原因</label>
                <Input.TextArea
                  id="import-execute-reason"
                  rows={3}
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  placeholder="说明本次初始化依据和确认人"
                />
                <Button
                  type="primary"
                  className="drawer-primary-action"
                  disabled={!reason.trim()}
                  loading={executing}
                  onClick={() => void execute()}
                >
                  执行通过行
                </Button>
              </div>
            )}
          </Space>
        )}
      </Drawer>
    </section>
  )
}
