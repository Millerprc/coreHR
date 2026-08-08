# EHR 源表到 coreHR 处置清单

> 本报告由本地只读结构扫描生成，不包含任何原始人员数据。

- 源表：114 张
- 可归一化或部分映射：27 张
- 暂不合并、延期或排除：87 张

## 可归一化或部分映射

| 源表 | 处置 | coreHR 目标 | 说明 |
|---|---|---|---|
| `city` | `target_extension` | `data_dictionary_items` | 地区字典；第五阶段启用多国家/地区能力前仅保留映射 |
| `country` | `target_extension` | `data_dictionary_items` | 国家代码字典 |
| `ehr_ai_interview_record` | `target_extension` | `candidate_interviews` | 第二阶段候选人面试实体尚未建立 |
| `ehr_approve` | `partial_mapping` | `workflow_instances/workflow_tasks` | 需补 main_type/sub_type、状态及审批人转换表 |
| `ehr_approve_local_param` | `partial_mapping` | `workflow_instances.context` | 作为旧审批上下文保留，禁止直接驱动新流程 |
| `ehr_attachment` | `target_extension` | `attachments` | 需先确定文件存储、病毒扫描及访问权限 |
| `ehr_attendance_shift` | `partial_mapping` | `schedule_assignments` | 按员工和日期映射；源表缺班次起止时刻，不能生成完整 shifts |
| `ehr_attendance_shift_diff` | `partial_mapping` | `audit_logs/import_issues` | 仅作为历史对账差异，不作为排班事实 |
| `ehr_channel_resume_check_record` | `partial_mapping` | `job_applications` | 评分和解析响应只能作为受控证据，不能直接决定状态 |
| `ehr_channel_resume_record` | `partial_mapping` | `candidates/job_applications` | 需外部简历 ID、职位 ID 和状态枚举映射 |
| `ehr_department_snap` | `partial_mapping` | `organization_versions/headcount_snapshots` | 可导入月度组织人数结果；父级只有名称，层级需校验 |
| `ehr_dept_employee_relation` | `partial_mapping` | `employment_assignments` | 源表缺生效区间，只能作为当前关系候选 |
| `ehr_dict` | `target_extension` | `data_dictionaries` | 结构明确，可归一化为数据字典定义 |
| `ehr_dict_element` | `target_extension` | `data_dictionary_items` | 结构明确，保留父子层级和来源 ID |
| `ehr_employee_dimission_info` | `partial_mapping` | `employments` | 可补离职日期；离职原因和事件优先级需与人事事件对齐 |
| `ehr_employee_info` | `partial_mapping` | `persons/employments/employment_assignments/reporting_relations/job_catalog/legal_entities` | 核心来源；敏感和未归一化字段不得整体复制 |
| `ehr_employee_info_log` | `partial_mapping` | `hr_events/audit_logs` | 无普通主键，作为历史证据而非当前结果 |
| `ehr_employee_info_move` | `partial_mapping` | `hr_events/employment_assignments` | effect_date 可驱动历史版本，事件类型需枚举映射 |
| `ehr_employee_label` | `target_extension` | `person_labels` | 结构明确，支持来源、有效性和 AI 标记 |
| `ehr_employee_label_del_info` | `partial_mapping` | `audit_logs/person_labels` | 只保留删除审计，不重放物理删除 |
| `ehr_employee_move_record` | `partial_mapping` | `hr_events/employment_assignments` | 可恢复调动有效期，需确认新旧事件优先级 |
| `ehr_employee_onboarded_info` | `partial_mapping` | `persons/employments/employment_assignments` | 待入职来源；空工号允许，证件数据另行受控 |
| `ehr_employee_part_dept` | `partial_mapping` | `employment_assignments/reporting_relations` | 兼岗/兼职组织关系，需 relation_type 对照 |
| `ehr_employee_referral_expert` | `target_extension` | `candidate_referrals` | 第二阶段推荐关系模型尚未建立 |
| `ehr_employee_report_day` | `partial_mapping` | `attendance_daily_results` | 固定指标直接映射，假类宽列进入 evidence 并按字典归一化 |
| `ehr_employee_report_month` | `partial_mapping` | `attendance_monthly_results` | 年月合成为 period_month，假类宽列进入 evidence |
| `ehr_employee_risk_acceptance` | `target_extension` | `person_consents/audit_logs` | 需确认同意书类型、版本和留存要求 |

## 暂不合并、延期或排除

| 源表 | 处置 | 说明 |
|---|---|---|
| `ads_employee_dept_gross_profit_total_df` | `exclude_analytics` | 数据仓库宽表或派生指标，不进入交易型 Core HR |
| `auth_browser_fingerprint` | `exclude_security` | 旧认证、会话、2FA、设备和票据不得迁入新认证模型 |
| `auth_countries` | `exclude_security` | 旧认证、会话、2FA、设备和票据不得迁入新认证模型 |
| `auth_google_2fa` | `exclude_security` | 旧认证、会话、2FA、设备和票据不得迁入新认证模型 |
| `auth_roles` | `exclude_security` | 旧认证、会话、2FA、设备和票据不得迁入新认证模型 |
| `auth_send_email_time` | `exclude_security` | 旧认证、会话、2FA、设备和票据不得迁入新认证模型 |
| `auth_seqno` | `exclude_security` | 旧认证、会话、2FA、设备和票据不得迁入新认证模型 |
| `auth_service` | `exclude_security` | 旧认证、会话、2FA、设备和票据不得迁入新认证模型 |
| `auth_service_ticket` | `exclude_security` | 旧认证、会话、2FA、设备和票据不得迁入新认证模型 |
| `auth_ticket_grant_ticket` | `exclude_security` | 旧认证、会话、2FA、设备和票据不得迁入新认证模型 |
| `auth_trust_device` | `exclude_security` | 旧认证、会话、2FA、设备和票据不得迁入新认证模型 |
| `auth_user` | `exclude_security` | 旧认证、会话、2FA、设备和票据不得迁入新认证模型 |
| `auth_user_avatar_content` | `exclude_security` | 旧认证、会话、2FA、设备和票据不得迁入新认证模型 |
| `auth_user_uuid` | `exclude_security` | 旧认证、会话、2FA、设备和票据不得迁入新认证模型 |
| `batch_alloc_job_record` | `exclude_technical` | 旧任务、消息或文件生成运行记录不迁移 |
| `config_general_setting` | `exclude_technical` | 旧应用技术配置和迁移版本不复用 |
| `config_metadata` | `exclude_technical` | 旧应用技术配置和迁移版本不复用 |
| `config_migration` | `exclude_technical` | 旧应用技术配置和迁移版本不复用 |
| `config_server_setting` | `exclude_technical` | 旧应用技术配置和迁移版本不复用 |
| `culture_attachment` | `exclude_content` | 企业文化内容系统不在第一至三阶段边界 |
| `culture_column` | `exclude_content` | 企业文化内容系统不在第一至三阶段边界 |
| `culture_column_article` | `exclude_content` | 企业文化内容系统不在第一至三阶段边界 |
| `culture_column_article_browse` | `exclude_content` | 企业文化内容系统不在第一至三阶段边界 |
| `dws_question_employee_nl_df` | `exclude_analytics` | 数据仓库宽表或派生指标，不进入交易型 Core HR |
| `dws_question_employee_nl_df1` | `exclude_analytics` | 数据仓库宽表或派生指标，不进入交易型 Core HR |
| `dws_question_employee_nl_df2` | `exclude_analytics` | 数据仓库宽表或派生指标，不进入交易型 Core HR |
| `ehr_abc_biz_import_month` | `needs_definition` | 包含业务呼叫与人数指标，不能假定为编制或收入目标 |
| `ehr_access_record` | `needs_definition` | 旧系统按员工和模块直接授权，必须先定义到 RBAC 的转换规则 |
| `ehr_creat_pdf` | `exclude_technical` | 旧任务、消息或文件生成运行记录不迁移 |
| `ehr_cruise_agent_async_task` | `external_recruitment_subsystem` | 招聘机器人内部配置、任务或日志，仅保留外部记录对照 |
| `ehr_cruise_agent_boss_verify_record` | `external_recruitment_subsystem` | 招聘机器人内部配置、任务或日志，仅保留外部记录对照 |
| `ehr_cruise_agent_channel_plugin` | `external_recruitment_subsystem` | 招聘机器人内部配置、任务或日志，仅保留外部记录对照 |
| `ehr_cruise_agent_channel_plugin_user` | `external_recruitment_subsystem` | 招聘机器人内部配置、任务或日志，仅保留外部记录对照 |
| `ehr_cruise_agent_channel_settings` | `external_recruitment_subsystem` | 招聘机器人内部配置、任务或日志，仅保留外部记录对照 |
| `ehr_cruise_agent_channel_task` | `external_recruitment_subsystem` | 招聘机器人内部配置、任务或日志，仅保留外部记录对照 |
| `ehr_cruise_agent_equity_card_rollback_record` | `external_recruitment_subsystem` | 招聘机器人内部配置、任务或日志，仅保留外部记录对照 |
| `ehr_cruise_agent_filter_category` | `external_recruitment_subsystem` | 招聘机器人内部配置、任务或日志，仅保留外部记录对照 |
| `ehr_cruise_agent_filter_enum` | `external_recruitment_subsystem` | 招聘机器人内部配置、任务或日志，仅保留外部记录对照 |
| `ehr_cruise_agent_filter_item` | `external_recruitment_subsystem` | 招聘机器人内部配置、任务或日志，仅保留外部记录对照 |
| `ehr_cruise_agent_job` | `external_recruitment_subsystem` | 招聘机器人内部配置、任务或日志，仅保留外部记录对照 |
| `ehr_cruise_agent_job_chat` | `external_recruitment_subsystem` | 招聘机器人内部配置、任务或日志，仅保留外部记录对照 |
| `ehr_cruise_agent_job_filter_config` | `external_recruitment_subsystem` | 招聘机器人内部配置、任务或日志，仅保留外部记录对照 |
| `ehr_cruise_agent_job_filter_publish_snapshot` | `external_recruitment_subsystem` | 招聘机器人内部配置、任务或日志，仅保留外部记录对照 |
| `ehr_cruise_agent_job_keyword` | `external_recruitment_subsystem` | 招聘机器人内部配置、任务或日志，仅保留外部记录对照 |
| `ehr_cruise_agent_job_seek_module` | `external_recruitment_subsystem` | 招聘机器人内部配置、任务或日志，仅保留外部记录对照 |
| `ehr_cruise_agent_package` | `external_recruitment_subsystem` | 招聘机器人内部配置、任务或日志，仅保留外部记录对照 |
| `ehr_cruise_agent_plugin_environment` | `external_recruitment_subsystem` | 招聘机器人内部配置、任务或日志，仅保留外部记录对照 |
| `ehr_cruise_agent_plugin_log` | `external_recruitment_subsystem` | 招聘机器人内部配置、任务或日志，仅保留外部记录对照 |
| `ehr_cruise_agent_record_action` | `external_recruitment_subsystem` | 招聘机器人内部配置、任务或日志，仅保留外部记录对照 |
| `ehr_cruise_agent_record_candidate_communication` | `external_recruitment_subsystem` | 招聘机器人内部配置、任务或日志，仅保留外部记录对照 |
| `ehr_cruise_agent_record_candidate_info.bak` | `exclude_backup` | 备份表不迁移 |
| `ehr_cruise_agent_record_candidate_view` | `external_recruitment_subsystem` | 招聘机器人内部配置、任务或日志，仅保留外部记录对照 |
| `ehr_cruise_agent_record_job_processing` | `external_recruitment_subsystem` | 招聘机器人内部配置、任务或日志，仅保留外部记录对照 |
| `ehr_cruise_agent_record_op_log` | `external_recruitment_subsystem` | 招聘机器人内部配置、任务或日志，仅保留外部记录对照 |
| `ehr_cruise_agent_record_workflow` | `external_recruitment_subsystem` | 招聘机器人内部配置、任务或日志，仅保留外部记录对照 |
| `ehr_cruise_agent_service_record` | `external_recruitment_subsystem` | 招聘机器人内部配置、任务或日志，仅保留外部记录对照 |
| `ehr_cruise_agent_service_user` | `external_recruitment_subsystem` | 招聘机器人内部配置、任务或日志，仅保留外部记录对照 |
| `ehr_cruise_agent_temporary_channel_job_seek_module` | `external_recruitment_subsystem` | 招聘机器人内部配置、任务或日志，仅保留外部记录对照 |
| `ehr_cruise_agent_temporary_job_filter_config` | `external_recruitment_subsystem` | 招聘机器人内部配置、任务或日志，仅保留外部记录对照 |
| `ehr_cruise_agent_temporary_job_keyword` | `external_recruitment_subsystem` | 招聘机器人内部配置、任务或日志，仅保留外部记录对照 |
| `ehr_cruise_agent_temporary_job_task` | `external_recruitment_subsystem` | 招聘机器人内部配置、任务或日志，仅保留外部记录对照 |
| `ehr_dury_message` | `exclude_technical` | 旧任务、消息或文件生成运行记录不迁移 |
| `ehr_employee_departmental_deduction` | `defer_phase_4` | 部门扣减语义可能影响薪酬/绩效，第四阶段再确认 |
| `ehr_field_condition_rule` | `needs_definition` | 旧字段条件表达式不能直接执行，需白名单转换 |
| `ehr_field_unlimited_constraint` | `needs_definition` | 旧无限制表达式不能直接成为新权限规则 |
| `ehr_file_message` | `exclude_technical` | 旧任务、消息或文件生成运行记录不迁移 |
| `ehr_humancost_actual_salary` | `defer_phase_4` | 薪酬及人力成本属于第四阶段 |
| `ehr_humancost_actual_salary_new` | `defer_phase_4` | 薪酬及人力成本属于第四阶段 |
| `ehr_humancost_batch_actual_salary` | `defer_phase_4` | 薪酬及人力成本属于第四阶段 |
| `ehr_humancost_batch_actual_salary_new` | `defer_phase_4` | 薪酬及人力成本属于第四阶段 |
| `ehr_humancost_day` | `defer_phase_4` | 薪酬及人力成本属于第四阶段 |
| `ehr_humancost_day_bak` | `exclude_backup` | 薪酬/人力成本复制或备份表不迁移 |
| `ehr_humancost_day_copy1` | `exclude_backup` | 薪酬/人力成本复制或备份表不迁移 |
| `ehr_humancost_day_new` | `defer_phase_4` | 薪酬及人力成本属于第四阶段 |
| `ehr_humancost_day_new_copy1` | `exclude_backup` | 薪酬/人力成本复制或备份表不迁移 |
| `ehr_humancost_day_new_copy2` | `exclude_backup` | 薪酬/人力成本复制或备份表不迁移 |
| `ehr_humancost_day_new_copy3` | `exclude_backup` | 薪酬/人力成本复制或备份表不迁移 |
| `ehr_humancost_day_param` | `defer_phase_4` | 薪酬及人力成本属于第四阶段 |
| `ehr_humancost_day_param_copy1` | `exclude_backup` | 薪酬/人力成本复制或备份表不迁移 |
| `ehr_humancost_day_param_new` | `defer_phase_4` | 薪酬及人力成本属于第四阶段 |
| `ehr_humancost_day_status` | `defer_phase_4` | 薪酬及人力成本属于第四阶段 |
| `ehr_humancost_day_status_copy1` | `exclude_backup` | 薪酬/人力成本复制或备份表不迁移 |
| `ehr_humancost_direct_income` | `defer_phase_4` | 薪酬及人力成本属于第四阶段 |
| `ehr_humancost_indirect_income` | `defer_phase_4` | 薪酬及人力成本属于第四阶段 |
| `ehr_humcost_salary` | `defer_phase_4` | 薪酬及人力成本属于第四阶段 |
| `ehr_humcost_salary_copy1` | `exclude_backup` | 薪酬/人力成本复制或备份表不迁移 |
| `ehr_humcost_social_cost` | `defer_phase_4` | 薪酬及人力成本属于第四阶段 |
