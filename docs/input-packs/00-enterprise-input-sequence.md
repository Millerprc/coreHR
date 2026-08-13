# 一至三阶段企业输入顺序

> 目的：一次只补一组资料；每组资料都对应明确开发和验收结果
> 当前项：`03-入职流程图与审批规则`

## 输入顺序

| 顺序 | 输入包 | 当前状态 | 补充后直接交付 |
|---:|---|---|---|
| 1 | [职务、职级、职等、职类、序列](./04-job-architecture-input.md) | `FIRST_SAMPLE_CONFIRMED` | 首个正式组合已冻结；后续目录按生效日期扩充 |
| 2 | [人员档案字段验收表](./05-personnel-record-field-acceptance.md) | `IMPLEMENTED / UAT_READY` | 完整档案表单、必填/唯一/可编辑/敏感字段规则 |
| 3 | [入职、转正、调动、兼岗、借调、离职、撤回/更正流程图](./06-hr-workflow-input.md) | `CURRENT / ONBOARDING_FIRST` | 正式流程模板、条件、审批人和超时规则 |
| 4 | 合同/协议字段、归类、附件和提醒规则 | `WAIT` | 企业合同模板、附件安全与生命周期适配 |
| 5 | [考勤与假期规则包](./07-attendance-rule-input.md) | `WAIT / TEMPLATE_READY` | 企业日报/月报口径、自动计提/结转和精细核算 |
| 6 | [打卡来源与接口契约](./08-punch-interface-input.md) | `WAIT / TEMPLATE_READY` | 企业微信/设备连接器、补传、幂等和失败重试 |
| 7 | [部署、安全、备份与容量验收](./09-nonfunctional-acceptance-input.md) | `WAIT / TEMPLATE_READY` | 8GB/32GB部署方案及一万人场景压测计划 |

## 当前只需要做什么

人员字段推荐值、敏感字段安全ADR、子档案更正/失效及待入职主证件闸门已经实现并通过工程验收，当前不需要继续补人员表头。下一项只处理`ONBOARDING`入职流程：先按[第二阶段需求规格](../01-foundation/12-第二阶段需求规格.md)确认`P2-Q001`生效日期规则；随后可以提供现有入职流程图，或填写[流程输入包](./06-hr-workflow-input.md)中四张模板。

职务体系当前已冻结以下两份首版 CSV，无需重复填写：

1. [职务维度值模板](./templates/01-job-dimensions.csv)
2. [职务目录模板](./templates/01-job-catalog.csv)

以后同一稳定代码出现多个生效日期版本时，再补充：

3. [职务维度历史版本模板](./templates/02-job-dimension-versions.csv)
4. [职务历史版本模板](./templates/02-job-catalog-versions.csv)

职务补充说明见[职务体系输入包](./04-job-architecture-input.md)。当前轮先确认入职流程，不需要同时准备其余人事流程、合同字段或考勤规则。

第二阶段页面和UAT边界见[第二阶段PRD](../01-foundation/13-第二阶段PRD.md)；第三阶段需求和页面边界见[第三阶段需求规格](../01-foundation/14-第三阶段需求规格.md)与[第三阶段PRD](../01-foundation/15-第三阶段PRD.md)。标记为`PENDING_ENTERPRISE_INPUT`的内容不得由AI自行猜测并固化。

## 处理规则

- 资料只在当前本机工作区处理，不上传第三方服务。
- 示例行可以直接覆盖或删除。
- 不确定的父级关系可以先留空，但职务行必须给出四个维度的实际组合。
- 每个稳定代码最早一行填入 `01-` 首版本模板，后续日期行填入 `02-` 历史版本模板；不要合并或覆盖历史行。
- 每次收到一组资料后，先完成映射、开发、测试和Review文档，再进入下一组。
