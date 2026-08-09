import { Alert, Tabs, Typography } from "antd"

import { LeavePanel } from "./LeavePanel"
import { PeriodFreezePanel } from "./PeriodFreezePanel"
import { ReportPanel } from "./ReportPanel"
import { RuleShiftPanel } from "./RuleShiftPanel"
import { SchedulePunchPanel } from "./SchedulePunchPanel"


interface AttendanceWorkspaceProps {
  readonly token: string
  readonly canAdmin: boolean
}


export function AttendanceWorkspace({ token, canAdmin }: AttendanceWorkspaceProps) {
  return <section className="workspace-section" aria-labelledby="attendance-title">
    <div className="workspace-heading">
      <div>
        <Typography.Title id="attendance-title" level={2}>考勤管理</Typography.Title>
        <Typography.Paragraph type="secondary">维护规则、班次、排班、打卡与假勤，并生成可追溯、可重算的日报和月报。</Typography.Paragraph>
      </div>
    </div>
    <Alert type="info" showIcon message="时区进入规则和打卡证据" description="月份边界、班次起止和打卡时间按规则时区计算；当前默认提供 Asia/Shanghai。" />
    <Tabs className="lifecycle-tabs" items={[
      { key: "reports", label: "日报与月报", children: <ReportPanel token={token} canAdmin={canAdmin} /> },
      { key: "schedules", label: "排班与打卡", children: <SchedulePunchPanel token={token} canAdmin={canAdmin} /> },
      { key: "leave", label: "请假与销假", children: <LeavePanel token={token} canAdmin={canAdmin} /> },
      { key: "freeze", label: "期间冻结", children: <PeriodFreezePanel token={token} canAdmin={canAdmin} /> },
      { key: "rules", label: "规则与班次", children: <RuleShiftPanel token={token} canAdmin={canAdmin} /> },
    ]} />
  </section>
}
