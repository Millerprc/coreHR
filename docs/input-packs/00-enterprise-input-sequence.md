# 一至三阶段企业输入顺序

> 目的：一次只补一组资料；每组资料都对应明确开发和验收结果
> 当前项：`02-人员档案字段验收`

## 输入顺序

| 顺序 | 输入包 | 当前状态 | 补充后直接交付 |
|---:|---|---|---|
| 1 | [职务、职级、职等、职类、序列](./04-job-architecture-input.md) | `FIRST_SAMPLE_CONFIRMED` | 首个正式组合已冻结；后续目录按生效日期扩充 |
| 2 | [人员档案字段验收表](./05-personnel-record-field-acceptance.md) | `NOW / TEMPLATE_READY` | 完整档案表单、必填/唯一/可编辑/敏感字段规则 |
| 3 | [入职、转正、调动、兼岗、借调、离职、撤回/更正流程图](./06-hr-workflow-input.md) | `WAIT / TEMPLATE_READY` | 正式流程模板、条件、审批人和超时规则 |
| 4 | 合同/协议字段、归类、附件和提醒规则 | `WAIT` | 企业合同模板、附件安全与生命周期适配 |
| 5 | [考勤与假期规则包](./07-attendance-rule-input.md) | `WAIT / TEMPLATE_READY` | 企业日报/月报口径、自动计提/结转和精细核算 |
| 6 | [打卡来源与接口契约](./08-punch-interface-input.md) | `WAIT / TEMPLATE_READY` | 企业微信/设备连接器、补传、幂等和失败重试 |
| 7 | [部署、安全、备份与容量验收](./09-nonfunctional-acceptance-input.md) | `WAIT / TEMPLATE_READY` | 8GB/32GB部署方案及一万人场景压测计划 |

## 当前只需要做什么

先回答[人员档案字段验收包](./05-personnel-record-field-acceptance.md)第6节的8个问题。不需要一次整理完整表头；回答后我会先实现第一批52个第一阶段字段及敏感字段安全边界。

职务体系当前已冻结以下两份首版 CSV，无需重复填写：

1. [职务维度值模板](./templates/01-job-dimensions.csv)
2. [职务目录模板](./templates/01-job-catalog.csv)

以后同一稳定代码出现多个生效日期版本时，再补充：

3. [职务维度历史版本模板](./templates/02-job-dimension-versions.csv)
4. [职务历史版本模板](./templates/02-job-catalog-versions.csv)

职务补充说明见[职务体系输入包](./04-job-architecture-input.md)。当前轮只确认人员字段，不需要同时准备流程图或考勤规则。

## 处理规则

- 资料只在当前本机工作区处理，不上传第三方服务。
- 示例行可以直接覆盖或删除。
- 不确定的父级关系可以先留空，但职务行必须给出四个维度的实际组合。
- 每个稳定代码最早一行填入 `01-` 首版本模板，后续日期行填入 `02-` 历史版本模板；不要合并或覆盖历史行。
- 每次收到一组资料后，先完成映射、开发、测试和Review文档，再进入下一组。
