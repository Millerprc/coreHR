# EHR 源数据装配到 coreHR 的执行方案

> 状态：结构映射完成，数据导入待枚举与安全规则确认
> 来源：本地 `ehr_data.sql` 只读扫描
> 决策依据：[ADR-0002](../adr/ADR-0002-ehr-source-migration-boundary.md)

## 1. 装配原则

- MySQL `ehr_source` 是源镜像；PostgreSQL `coreHR` 是目标事实库。
- 不执行跨库双写，不让业务 API 直接查询 `ehr_source`。
- 每条已导入记录通过 `external_record_links` 保留来源表、来源主键和目标实体。
- 同一来源记录重复执行时更新或跳过既有目标，不重复创建。
- 源表无生效日期、稳定主键或明确枚举时，只生成候选或拒绝记录，不猜默认值。
- 证件、联系方式、银行账户、认证秘密和薪酬数据在安全模型确认前不进入目标库。

## 2. 装配顺序

| 顺序 | 输入 | coreHR 目标 | 闸门 |
|---|---|---|---|
| 1 | `ehr_dict`、`ehr_dict_element`、`country`、`city` | `data_dictionaries`、`data_dictionary_items` | 字典代码去重、父项存在 |
| 2 | `ehr_employee_info` 中的职务与法人字段 | `job_catalog`、`legal_entities` | 名称不能作为最终唯一键；生成来源对照 |
| 3 | `ehr_department_snap`、人员部门字段 | `organizations`、`organization_versions` | 父级名称冲突进入拒绝清单 |
| 4 | `ehr_employee_info`、`ehr_employee_onboarded_info` | `persons`、`employments` | 工号六位；同一自然人有效劳动关系不重叠 |
| 5 | 部门、职务、汇报、兼岗字段 | `employment_assignments`、`reporting_relations` | 生效区间和关系类型必须明确 |
| 6 | `ehr_employee_label` | `person_labels` | 标签来源、类型、有效日期齐全 |
| 7 | 离职与调动表 | `hr_events` 及新版本关系 | 事件枚举和优先级确认后才能生效 |
| 8 | 审批与招聘表 | workflow、candidate、application | 流程图和状态对照确认 |
| 9 | 日报、月报、排班表 | attendance 结果与排班 | 员工对照、假类字典和分钟/天换算确认 |
| 10 | 组织人数月度结果 | snapshot 批次与明细 | 时区、月份边界和版本确认 |

## 3. 核心人员表拆分

### `ehr_employee_info`

| 源字段 | coreHR 目标 | 转换 |
|---|---|---|
| `employee_no` | `persons.employee_number` | 必须是六位数字；二次入职复用 |
| `realname` | `persons.display_name` | 原值仅进入受控目标字段，不写日志 |
| `gender_id` | `persons.gender_code` | 通过字典映射，禁止使用显示名称作为稳定码 |
| `birthday` | `persons.birth_date` | 日期 |
| `country` | `persons.nationality_code`或`persons.country_code`候选 | 必须先确认字段业务含义，并通过 `country` 表转换为ISO代码 |
| `nationality_id`、`nationality` | 民族扩展字典候选 | 首行样例为“汉族”，证明源字段实际语义是民族而非国籍；禁止写入 `persons.nationality_code` |
| `employee_type_id` | `employments.employee_type_code` | 需确认枚举对照 |
| `employee_status_id` | `employments.status` | 需确认枚举对照 |
| `on_boarding_date` | `employments.actual_start_date` | 待入职来源为空时使用计划日期 |
| `end_probation_date` | `employments.probation_end_date` | 日期 |
| `leave_date` | `employments.end_date` | 事件结果优先于当前表 |
| `department_id` | `employment_assignments.organization_id` | 经来源 ID 对照转换 UUID |
| `duty_id` | `employment_assignments.job_id` | 经职务来源 ID 对照转换 UUID |
| `report_leader_id` | `reporting_relations.manager_person_id` | 先解析负责人自然人 |
| `dashed_report_leader_id`、`dashed_report_leader2_id` | `reporting_relations` | `relation_type=dotted`，保留有效期 |
| `corporation_name` | `legal_entities` 候选 | 名称只能生成候选，不能替代法人编码 |
| `duty_level`、`position_class_name`、`sub_class_name` | `job_catalog` | 分别映射职级/职类等字段，字典确认后导入 |

以下字段暂缓：证件号、电话、个人邮箱、紧急联系人、办公地址、头像、银行卡、婚姻状态和详细教育信息。目标敏感档案、加密和字段级授权未确认前，不放入 `persons` 或 JSON。

## 4. 历史与关系表

| 源表 | coreHR 目标 | 处理方式 |
|---|---|---|
| `ehr_employee_onboarded_info` | Person + Employment + Assignment | 创建待入职结果；工号可空 |
| `ehr_employee_dimission_info` | Employment | 只补充离职日期候选；事件结果优先 |
| `ehr_employee_info_move` | HrEvent + Assignment | `effect_date` 作为计划生效时间 |
| `ehr_employee_move_record` | HrEvent + Assignment | 使用实际生效/失效时间重建版本 |
| `ehr_employee_part_dept` | Assignment + ReportingRelation | 映射兼岗、兼职和虚线汇报关系 |
| `ehr_dept_employee_relation` | Assignment 候选 | 缺生效日期，不可覆盖已确认历史 |
| `ehr_employee_info_log` | AuditLog/历史证据 | 无普通主键，不直接生成当前结果 |

## 5. 招聘、流程与附件

- `ehr_approve` 和 `ehr_approve_local_param` 只能作为旧流程历史；不得直接发布为新流程定义。
- `ehr_channel_resume_record` 可拆出候选人和应聘来源，但必须先确认外部简历 ID、职位 ID 和状态码。
- 招聘机器人 `ehr_cruise_agent_*` 表不复制；只对最终进入候选人/应聘记录的数据建立 `external_record_links`。
- `ehr_attachment` 在文件对象存储、病毒扫描、访问权限和原文件可用性确认前不迁移。

## 6. 考勤结果

| 源表 | coreHR 目标 | 转换 |
|---|---|---|
| `ehr_employee_report_day` | `attendance_daily_results` | 工时换算分钟；动态假类字段进入受控 `evidence` |
| `ehr_employee_report_month` | `attendance_monthly_results` | 年月合成月初日期；小数天数使用 Decimal |
| `ehr_attendance_shift` | `schedule_assignments` | 只映射员工、日期和班次名称候选 |
| `ehr_attendance_shift_diff` | 导入问题/审计 | 不作为排班事实 |

源排班表没有班次起止时间，不能独立生成 `shifts`；需补充正式班次规则表。

## 7. 导入前必须补充的对照

1. 员工类型、员工状态、性别、民族、国籍/国家、学历、职级、职类等字典代码；其中源 `nationality*` 已确认不能按国籍直接迁移。
2. 法人名称到统一法人编码的对照表。
3. 部门 ID、历史部门编码、父级组织及组织类型对照。
4. 人事事件类型、状态及新旧记录优先级。
5. 审批主类型/子类型、结果和审批人状态对照。
6. 招聘职位、候选人状态、应聘阶段和外部渠道对照。
7. 考勤状态、假期类型、工时单位和月报口径。
8. 敏感档案加密、密钥、脱敏、字段级权限和审计方案。

## 8. 验收

- 每个来源记录最多对应一个同类型目标记录。
- 失败记录有明确错误码，不吞错、不写半条结果。
- 重新执行同一批次不会增加重复目标记录。
- 当前结果、历史版本和事件结果可以相互追溯。
- 日志、测试和交付文档中不存在真实人员值、凭据或薪酬明细。
