import { Alert, Tabs, Typography } from "antd"

import { ApplicationPanel } from "./ApplicationPanel"
import { ContractPanel } from "./ContractPanel"
import { HrEventPanel } from "./HrEventPanel"
import { WorkflowPanel } from "./WorkflowPanel"


interface LifecycleWorkspaceProps {
  readonly token: string
  readonly canAdmin: boolean
}


export function LifecycleWorkspace({ token, canAdmin }: LifecycleWorkspaceProps) {
  return <section className="workspace-section" aria-labelledby="lifecycle-title">
    <div className="workspace-heading">
      <div>
        <Typography.Title id="lifecycle-title" level={2}>员工生命周期</Typography.Title>
        <Typography.Paragraph type="secondary">管理应聘、合同、审批以及入转调离兼等人事事件，所有变更均保留过程和审计记录。</Typography.Paragraph>
      </div>
    </div>
    <Alert
      type="info"
      showIcon
      message="当前开放给主管理员"
      description="审批关系和数据权限已保留扩展点；第二阶段先确保管理员可以完整配置、执行、回退和追溯。"
    />
    <Tabs
      className="lifecycle-tabs"
      items={[
        { key: "events", label: "人事事件", children: <HrEventPanel token={token} canAdmin={canAdmin} /> },
        { key: "workflow", label: "流程与待办", children: <WorkflowPanel token={token} canAdmin={canAdmin} /> },
        { key: "applications", label: "候选人与应聘", children: <ApplicationPanel token={token} canAdmin={canAdmin} /> },
        { key: "contracts", label: "合同与协议", children: <ContractPanel token={token} canAdmin={canAdmin} /> },
      ]}
    />
  </section>
}
