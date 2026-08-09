import {
  Alert,
  Button,
  Checkbox,
  Descriptions,
  Divider,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
} from "antd"
import { useCallback, useEffect, useMemo, useState } from "react"

import { ApiClientError } from "../../client"
import { command, organizationApi } from "./api"
import type {
  BpMembership,
  CostAllocationLine,
  CostCenter,
  DirectoryOption,
  OrganizationRelations,
  RevenueAggregation,
} from "./types"


interface OrganizationOption {
  readonly id: string
  readonly name: string
  readonly code: string
}


interface OrganizationRelationsTabsProps {
  readonly token: string
  readonly organizationId: string
  readonly effectiveAt: string
  readonly canAdmin: boolean
  readonly organizations: readonly OrganizationOption[]
}


const currentYear = new Date().getFullYear()


function optionLabel(item: DirectoryOption): string {
  const name = item.name ?? item.display_name ?? item.code ?? item.id
  const code = item.code ?? item.employee_number
  return code ? `${name} (${code})` : name
}


function errorMessage(caught: unknown, fallback: string): string {
  if (caught instanceof ApiClientError && caught.status === 409) {
    return "数据已发生变化，已刷新最新内容，请确认后重试。"
  }
  return caught instanceof Error ? caught.message : fallback
}


export function OrganizationRelationsTabs({
  token,
  organizationId,
  effectiveAt,
  canAdmin,
  organizations,
}: OrganizationRelationsTabsProps) {
  const [relations, setRelations] = useState<OrganizationRelations | null>(null)
  const [legalEntities, setLegalEntities] = useState<readonly DirectoryOption[]>([])
  const [people, setPeople] = useState<readonly DirectoryOption[]>([])
  const [costCenters, setCostCenters] = useState<readonly CostCenter[]>([])
  const [allocation, setAllocation] = useState<readonly CostAllocationLine[]>([])
  const [allocationVersion, setAllocationVersion] = useState(1)
  const [revenue, setRevenue] = useState<RevenueAggregation | null>(null)
  const [year, setYear] = useState(currentYear)
  const [includeDescendants, setIncludeDescendants] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [legalIds, setLegalIds] = useState<readonly string[]>([])
  const [leaderIds, setLeaderIds] = useState<readonly string[]>([])
  const [relationDate, setRelationDate] = useState(effectiveAt)
  const [reason, setReason] = useState("")
  const [selectedMembershipId, setSelectedMembershipId] = useState<string | null>(null)
  const [membership, setMembership] = useState<BpMembership | null>(null)
  const [bpPersonId, setBpPersonId] = useState<string | null>(null)
  const [bpType, setBpType] = useState<BpMembership["bp_type"]>("HRBP")
  const [bpOrganizationIds, setBpOrganizationIds] = useState<readonly string[]>([organizationId])
  const [newCostCenterOpen, setNewCostCenterOpen] = useState(false)
  const [costCenterForm] = Form.useForm()
  const [currency, setCurrency] = useState("CNY")
  const [annualAmount, setAnnualAmount] = useState("0.0000")
  const [monthAmounts, setMonthAmounts] = useState<readonly string[]>(
    Array.from({ length: 12 }, () => "0.0000"),
  )

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [nextRelations, nextCostCenters, nextAllocation, nextRevenue, legalPage, personPage] =
        await Promise.all([
          organizationApi.relations(token, organizationId, effectiveAt),
          organizationApi.costCenters(token),
          organizationApi.allocation(token, organizationId, effectiveAt),
          organizationApi.revenue(token, organizationId, year, includeDescendants),
          organizationApi.legalEntities(token),
          organizationApi.persons(token),
        ])
      setRelations(nextRelations)
      setLegalIds(nextRelations.legal_entity_ids)
      setLeaderIds(nextRelations.leader_person_ids)
      setSelectedMembershipId(nextRelations.bp_membership_ids[0] ?? null)
      setCostCenters(nextCostCenters)
      setAllocation(nextAllocation?.lines ?? [])
      setAllocationVersion(nextAllocation?.version ?? 1)
      setRevenue(nextRevenue)
      setLegalEntities(legalPage.items)
      setPeople(personPage.items)
      setRelationDate(effectiveAt)
    } catch (caught) {
      setError(errorMessage(caught, "组织关系加载失败"))
    } finally {
      setLoading(false)
    }
  }, [effectiveAt, includeDescendants, organizationId, token, year])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (!selectedMembershipId) {
      setMembership(null)
      setBpOrganizationIds([organizationId])
      return
    }
    void organizationApi.bpMembership(token, selectedMembershipId)
      .then((result) => {
        setMembership(result)
        setBpPersonId(result.person_id)
        setBpType(result.bp_type)
        setBpOrganizationIds(result.organization_ids)
      })
      .catch((caught) => setError(errorMessage(caught, "BP关系加载失败")))
  }, [organizationId, selectedMembershipId, token])

  useEffect(() => {
    const target = revenue?.targets.find((item) => item.currency_code === currency)
    setAnnualAmount(target?.annual_amount ?? "0.0000")
    setMonthAmounts(
      target
        ? Array.from({ length: 12 }, (_, index) =>
            target.months.find((month) => month.month === index + 1)?.amount ?? "0.0000",
          )
        : Array.from({ length: 12 }, () => "0.0000"),
    )
  }, [currency, revenue])

  const personOptions = useMemo(
    () => people.map((person) => ({ label: optionLabel(person), value: person.id })),
    [people],
  )
  const legalOptions = useMemo(
    () => legalEntities.map((entity) => ({ label: optionLabel(entity), value: entity.id })),
    [legalEntities],
  )
  const organizationOptions = useMemo(
    () => organizations.map((item) => ({ label: `${item.name} (${item.code})`, value: item.id })),
    [organizations],
  )

  async function write(operation: () => Promise<unknown>, fallback: string): Promise<boolean> {
    setSaving(true)
    setError(null)
    try {
      await operation()
      setReason("")
      await load()
      return true
    } catch (caught) {
      setError(errorMessage(caught, fallback))
      if (caught instanceof ApiClientError && caught.status === 409) await load()
      return false
    } finally {
      setSaving(false)
    }
  }

  function relationControls(): React.ReactNode {
    return (
      <div className="relation-controls">
        <label>
          <span className="field-label">生效日期</span>
          <Input type="date" value={relationDate} onChange={(event) => setRelationDate(event.target.value)} />
        </label>
        <label>
          <span className="field-label">变更原因</span>
          <Input value={reason} onChange={(event) => setReason(event.target.value)} />
        </label>
      </div>
    )
  }

  const allocationTotal = allocation.reduce(
    (total, line) => total + Number(line.allocation_percent || 0),
    0,
  )
  const allocationValid = allocation.length > 0 && Math.abs(allocationTotal - 100) < 0.00005
  const monthTotal = monthAmounts.reduce((total, amount) => total + Number(amount || 0), 0)
  const revenueValid = Math.abs(monthTotal - Number(annualAmount || 0)) < 0.00005

  const tabItems = [
    {
      key: "legal",
      label: "法人主体",
      children: (
        <div className="relation-panel">
          <Typography.Paragraph type="secondary">一个组织可同时关联多个法人主体，关系按生效日期保留历史。</Typography.Paragraph>
          <label>
            <span className="field-label">关联法人</span>
            <Select mode="multiple" showSearch optionFilterProp="label" value={legalIds} options={legalOptions} onChange={setLegalIds} disabled={!canAdmin} />
          </label>
          {canAdmin && relationControls()}
          {canAdmin && (
            <Button
              type="primary"
              loading={saving}
              disabled={!reason.trim() || !relations}
              onClick={() => void write(
                () => organizationApi.setLegalEntities(token, organizationId, {
                  legal_entity_ids: legalIds,
                  effective_from: relationDate,
                  command: command(relations?.legal_entity_version ?? 1, reason),
                }),
                "法人关系保存失败",
              )}
            >保存法人关系</Button>
          )}
        </div>
      ),
    },
    {
      key: "leaders",
      label: "负责人",
      children: (
        <div className="relation-panel">
          <Typography.Paragraph type="secondary">最多三名负责人，三者均为主负责人，不区分排序。</Typography.Paragraph>
          <label>
            <span className="field-label">负责人（最多三人）</span>
            <Select mode="multiple" maxCount={3} showSearch optionFilterProp="label" value={leaderIds} options={personOptions} onChange={setLeaderIds} disabled={!canAdmin} />
          </label>
          {canAdmin && relationControls()}
          {canAdmin && (
            <Button
              type="primary"
              loading={saving}
              disabled={!reason.trim() || !relations || leaderIds.length > 3}
              onClick={() => void write(
                () => organizationApi.setLeaders(token, organizationId, {
                  person_ids: leaderIds,
                  effective_from: relationDate,
                  command: command(relations?.leader_version ?? 1, reason),
                }),
                "负责人保存失败",
              )}
            >保存负责人</Button>
          )}
        </div>
      ),
    },
    {
      key: "bp",
      label: "BP服务",
      children: (
        <div className="relation-panel">
          <Typography.Paragraph type="secondary">同一人员在同一期间只能属于一种BP类型，但可服务多个组织。</Typography.Paragraph>
          <label>
            <span className="field-label">已有BP关系</span>
            <Select
              allowClear
              value={selectedMembershipId}
              placeholder="新建BP关系"
              options={(relations?.bp_membership_ids ?? []).map((id) => ({ label: id, value: id }))}
              onChange={(value) => setSelectedMembershipId(value ?? null)}
            />
          </label>
          <div className="relation-grid">
            <label>
              <span className="field-label">人员</span>
              <Select showSearch optionFilterProp="label" value={bpPersonId} options={personOptions} onChange={setBpPersonId} disabled={!canAdmin || Boolean(membership)} />
            </label>
            <label>
              <span className="field-label">BP类型</span>
              <Select
                value={bpType}
                disabled={!canAdmin || Boolean(membership)}
                onChange={setBpType}
                options={["HRBP", "EBP", "TBP", "FBP"].map((value) => ({ label: value, value }))}
              />
            </label>
          </div>
          <label>
            <span className="field-label">服务组织</span>
            <Select mode="multiple" showSearch optionFilterProp="label" value={bpOrganizationIds} options={organizationOptions} onChange={setBpOrganizationIds} disabled={!canAdmin} />
          </label>
          {canAdmin && relationControls()}
          {canAdmin && (
            <Space>
              <Button
                type="primary"
                loading={saving}
                disabled={!reason.trim() || !bpPersonId || !bpOrganizationIds.length}
                onClick={() => void write(
                  () => membership
                    ? organizationApi.setBpScopes(token, membership.id, {
                        organization_ids: bpOrganizationIds,
                        effective_from: relationDate,
                        command: command(membership.version, reason),
                      })
                    : organizationApi.createBpMembership(token, {
                        person_id: bpPersonId,
                        bp_type: bpType,
                        organization_ids: bpOrganizationIds,
                        effective_from: relationDate,
                        command: command(1, reason),
                      }),
                  "BP关系保存失败",
                )}
              >{membership ? "保存服务范围" : "新建BP关系"}</Button>
              {membership && <Button onClick={() => setSelectedMembershipId(null)}>新建另一条</Button>}
            </Space>
          )}
        </div>
      ),
    },
    {
      key: "cost",
      label: "成本分摊",
      children: (
        <div className="relation-panel">
          <div className="detail-toolbar">
            <Typography.Paragraph type="secondary">同一生效版本的分摊比例必须精确等于100%。</Typography.Paragraph>
            {canAdmin && <Button onClick={() => setNewCostCenterOpen(true)}>新建成本中心</Button>}
          </div>
          <Table
            pagination={false}
            rowKey={(_, index) => String(index)}
            dataSource={[...allocation]}
            locale={{ emptyText: <Empty description="当前日期没有成本分摊版本" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
            columns={[
              {
                title: "成本中心",
                dataIndex: "cost_center_id",
                render: (value: string, _row, index) => (
                  <Select
                    aria-label={`第${index + 1}行成本中心`}
                    value={value}
                    disabled={!canAdmin}
                    options={costCenters.map((center) => ({ label: `${center.name} (${center.code})`, value: center.id }))}
                    onChange={(next) => setAllocation((rows) => rows.map((row, rowIndex) => rowIndex === index ? { ...row, cost_center_id: next } : row))}
                  />
                ),
              },
              {
                title: "比例（%）",
                dataIndex: "allocation_percent",
                width: 180,
                render: (value: string, _row, index) => (
                  <InputNumber
                    aria-label={`第${index + 1}行分摊比例`}
                    min={0.0001}
                    max={100}
                    precision={4}
                    value={Number(value)}
                    disabled={!canAdmin}
                    onChange={(next) => setAllocation((rows) => rows.map((row, rowIndex) => rowIndex === index ? { ...row, allocation_percent: Number(next ?? 0).toFixed(4) } : row))}
                  />
                ),
              },
              ...(canAdmin
                ? [{
                    title: "操作",
                    width: 90,
                    render: (_value: unknown, _row: CostAllocationLine, index: number) => (
                      <Button type="link" danger onClick={() => setAllocation((rows) => rows.filter((_, rowIndex) => rowIndex !== index))}>移除</Button>
                    ),
                  }]
                : []),
            ]}
          />
          {canAdmin && (
            <Space wrap>
              <Button onClick={() => setAllocation((rows) => [...rows, { cost_center_id: costCenters[0]?.id ?? "", allocation_percent: "0.0000" }])} disabled={!costCenters.length}>增加一行</Button>
              <Tag color={allocationValid ? "success" : "error"}>当前合计 {allocationTotal.toFixed(4)}%</Tag>
            </Space>
          )}
          {canAdmin && relationControls()}
          {canAdmin && (
            <Button
              type="primary"
              loading={saving}
              disabled={!allocationValid || !reason.trim() || allocation.some((line) => !line.cost_center_id)}
              onClick={() => void write(
                () => organizationApi.setAllocation(token, organizationId, {
                  effective_from: relationDate,
                  lines: allocation,
                  command: command(allocationVersion, reason),
                }),
                "成本分摊保存失败",
              )}
            >保存成本分摊</Button>
          )}
        </div>
      ),
    },
    {
      key: "revenue",
      label: "收入目标",
      children: (
        <div className="relation-panel">
          <div className="relation-grid relation-grid-three">
            <label>
              <span className="field-label">年度</span>
              <InputNumber min={2000} max={2200} precision={0} value={year} onChange={(value) => setYear(Number(value ?? currentYear))} />
            </label>
            <label>
              <span className="field-label">币种</span>
              <Select value={currency} onChange={setCurrency} options={["CNY", "USD", "EUR", "HKD"].map((value) => ({ label: value, value }))} />
            </label>
            <label>
              <span className="field-label">年度目标</span>
              <InputNumber min="0" precision={4} stringMode value={annualAmount} onChange={(value) => setAnnualAmount(String(value ?? "0.0000"))} disabled={!canAdmin} />
            </label>
          </div>
          <Checkbox checked={includeDescendants} onChange={(event) => setIncludeDescendants(event.target.checked)}>汇总全部下级组织</Checkbox>
          <Table
            pagination={false}
            rowKey="month"
            size="small"
            dataSource={monthAmounts.map((amount, index) => ({ month: index + 1, amount }))}
            columns={[
              { title: "月份", dataIndex: "month", width: 100, render: (value: number) => `${value}月` },
              {
                title: "目标金额",
                dataIndex: "amount",
                render: (value: string, _row, index) => (
                  <InputNumber
                    aria-label={`${index + 1}月收入目标`}
                    min="0"
                    precision={4}
                    stringMode
                    value={value}
                    disabled={!canAdmin}
                    onChange={(next) => setMonthAmounts((amounts) => amounts.map((amount, monthIndex) => monthIndex === index ? String(next ?? "0.0000") : amount))}
                  />
                ),
              },
            ]}
          />
          <Tag color={revenueValid ? "success" : "error"}>月度合计 {monthTotal.toFixed(4)} {currency}</Tag>
          {canAdmin && (
            <>
              <label>
                <span className="field-label">变更原因</span>
                <Input value={reason} onChange={(event) => setReason(event.target.value)} />
              </label>
              <Button
                type="primary"
                loading={saving}
                disabled={!revenueValid || !reason.trim()}
                onClick={() => {
                  const target = revenue?.targets.find((item) => item.currency_code === currency)
                  void write(
                    () => organizationApi.setRevenue(token, organizationId, year, currency, {
                      year,
                      currency_code: currency,
                      annual_amount: annualAmount,
                      months: monthAmounts.map((amount, index) => ({ month: index + 1, amount })),
                      command: command(target?.version ?? 1, reason),
                    }),
                    "收入目标保存失败",
                  )
                }}
              >保存收入目标</Button>
            </>
          )}
          <Divider />
          <Typography.Title level={5}>按币种汇总</Typography.Title>
          {revenue && Object.keys(revenue.totals_by_currency).length ? (
            <Descriptions column={2} size="small">
              {Object.entries(revenue.totals_by_currency).map(([code, total]) => (
                <Descriptions.Item key={code} label={code}>{total.annual_amount}</Descriptions.Item>
              ))}
            </Descriptions>
          ) : <Empty description="本年度尚未设置收入目标" image={Empty.PRESENTED_IMAGE_SIMPLE} />}
        </div>
      ),
    },
  ]

  return (
    <div aria-busy={loading}>
      {error && <Alert closable onClose={() => setError(null)} type="error" showIcon message={error} />}
      <Tabs items={tabItems} />
      <Modal
        title="新建成本中心"
        open={newCostCenterOpen}
        okText="保存"
        confirmLoading={saving}
        onOk={() => costCenterForm.submit()}
        onCancel={() => setNewCostCenterOpen(false)}
      >
        <Form
          form={costCenterForm}
          layout="vertical"
          requiredMark={false}
          onFinish={(values) => void write(
            () => organizationApi.createCostCenter(token, values),
            "成本中心创建失败",
          ).then((saved) => {
            if (!saved) return
            setNewCostCenterOpen(false)
            costCenterForm.resetFields()
          })}
        >
          <Form.Item label="成本中心代码" name="code" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item label="成本中心名称" name="name" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item label="国家或地区代码" name="country_code"><Input maxLength={3} /></Form.Item>
          <Form.Item label="生效日期" name="effective_from" initialValue={effectiveAt} rules={[{ required: true }]}><Input type="date" /></Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
