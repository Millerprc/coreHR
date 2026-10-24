# 分片 B：第一阶段需求规格 + 组织与主体 + 编制与人力结果 ↔ 实现 对账

> 审计对象：`docs/01-foundation/01-第一阶段需求规格.md`、`05-组织与主体领域规范.md`、`06-编制与人力结果领域规范.md`
> 审计日期：2026-10-24　　代码基线：`apps/api/src/hris`（workforce / platform / workflow）+ `apps/web/src/business/features`
> 判定口径：`已实现` / `部分实现` / `未实现` / `与PRD冲突` / `待企业输入` / `待决策`
> 权限码口径：仅采用 `ORGANIZATION_VIEW`、`ORGANIZATION_ADMIN`、`ORGANIZATION_EVENT_APPLY`、`WORKFORCE_ADMIN`、`LIFECYCLE_ADMIN`、`ATTENDANCE_ADMIN`、`CONFIGURATION_VIEW`、`CONFIGURATION_ADMIN`、`DATA_GOVERNANCE_VIEW`、`DATA_GOVERNANCE_ADMIN` 及 `*`

## 汇总

| 判定 | 条数 |
|---|---|
| 已实现 | 74 |
| 部分实现 | 44 |
| 未实现 | 11 |
| 与PRD冲突 | 3 |
| 待企业输入 | 1 |
| 待决策 | 1 |
| **合计** | **134** |

分文档分布：`01` 65 条（已实现 41 / 部分实现 17 / 未实现 4 / 与PRD冲突 2 / 待企业输入 1）、`05` 37 条（已实现 19 / 部分实现 13 / 未实现 4 / 与PRD冲突 1）、`06` 32 条（已实现 14 / 部分实现 14 / 未实现 3 / 待决策 1）。

**全局性前提（贯穿本分片，非单条缺陷）**：`docs/01-foundation/00-正式文档目录.md:28-31` 已把 `01`/`05`/`06` 全部标为 `MIGRATION_INPUT / PARTIAL`，正文头部亦写明「本文件保留为模块功能需求迁移输入，不再单独构成开发批准」。因此本报告的「与PRD冲突」只表示**与当前文档正文条款冲突**（需要改文档或改实现，二选一由产品决策），不表示与已批准基线冲突；同时这三份文档在迁入 `17` 号规范批准的功能文档前，**不能直接作为新增开发范围的依据**（`05:7`、`06:7`、`01:6`）。

## 明细

### 文档 01：第一阶段需求规格

#### §2 领域边界

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `01:25` | 系统基础含登录、账号、角色权限底座、字典、编码、审计、**附件**、导入导出 | 部分实现 | 已有：`apps/api/src/hris/modules/platform/api.py:24-44`（登录/登出/me）、`account_admin_api.py:39-79`（账号/角色）、`configuration_api.py:40-154`（字典）、`numbering.py:8-41`（编码）、`audit_api.py:58-152`（审计+导出）、`import_api.py:54-162`（导入导出）。**附件缺失**：检索词 `attachment`、`Attachment` 全库仅命中 `Content-Disposition` 响应头（`audit_api.py:143-147`、`import_api.py:70-74`），无附件模型/上传/下载接口 | 附件能力整体缺失。文档 `01:25` 把附件列入第一阶段系统基础，建议二选一：补最小附件（对象关联+版本+审计），或在 `17` 号功能文档迁移时把附件明确移出第一阶段并同步修订 `01:25` | P1 |
| `01:27` | 组织：单父业务组织树、可配置组织类型、负责人、虚拟组织与成员关系 | 已实现 | `organization_service.py:178-267`（建组织+单父+无环）、`:781-888`（负责人≤3）、`organization_models.py:47-130`（负责人/BP/关系）、`extended_schemas.py:294`（关系类型枚举） | — | — |
| `01:28` | 成本中心：档案、组织分摊比例、生效日期和版本 | 已实现 | `models.py:240-295`（CostCenter + OrganizationCostAllocation 含 effective_from/to、version、is_current）、`organization_service.py:1259-1407`（分摊写入） | — | — |
| `01:29` | 收入目标：叶子组织年度/月度目标、币种、版本、按币种向上汇总 | 部分实现 | `models.py:298-321` + `organization_models.py:133-148`（RevenueTarget/RevenueTargetMonth）、`organization_service.py:1450-1586`（写入+版本）、`:1600-1699`（按币种汇总）。**缺口**：检索词 `leaf`、`叶子`、`is_leaf`、`child_count` 全库 0 匹配——录入时不校验叶子身份 | 见 `05:221` 同源缺陷；见明细 `05-29` | P1 |
| `01:31` | 编制：按组织+职务+年月维护编制数，展示人员结果和差额 | 已实现 | `models.py:804-832`（HeadcountPlan 唯一键 org+job+period+version）、`extended_service.py:1134-1189`（维护）、`:1495-1573`（结果含 planned/current/variance/月初/月末/月均） | — | — |
| `01:32` | 招聘需求：创建、状态跟踪、与组织/职务的弱关联 | 部分实现 | `workflow/extended_api.py:126-190`、`workflow/extended_service.py:198-357`（创建/列表/状态机）、`extended_service.py:1495-1573`（弱关联编制数据）。**缺口**：状态集合与 `01:291-294` 不符 | 见明细 `01-57` | P1 |
| `01:34` | 雇佣关系：每次雇佣独立记录，二次入职复用自然人和工号 | 已实现 | `models.py:604-642`（Employment 独立记录）、`models.py:324-337`（Person.employee_number 六位唯一 + `CheckConstraint employee_number ~ '^[0-9]{6}$'`）、`extended_service.py:721-735`（占号/复用） | — | — |
| `01:35` | 人事数据：当前结果维护、有效期、变更日志、快照及事件衔接 | 部分实现 | 有效期：`models.py:691-717`；事件衔接：`workflow/extended_service.py:1690-1765`（任职按事件生效/结束）。**缺口**：无独立变更日志实体、快照内容只覆盖编制维度 | 见明细 `06-10`、`01-46` | P1 |
| `01:45` | 不纳入：编制阻断招聘或自动预留 | 已实现 | 检索词 `headcount` 出现在招聘路径只有读取：`workflow/extended_service.py:198-244`（创建需求不查编制）、`:284-320`（状态变更不校验编制）；前端 `RecruitmentWorkspace.tsx:112-127` 只拉取展示。测试 `apps/api/tests/integration/test_recruitment_request_api.py:17` 显式验证「可见但不被冻结阻断」 | 符合边界，无需改动 | — |
| `01:46` | 不纳入：未来日期组织树预览 | 已实现 | `organization_api.py:133-138`：带 `effective_at` 请求 `/organizations/tree` 直接返回 422 `CURRENT_TREE_ONLY`；`OrganizationVersionDrawer.tsx` 按生效日期在详情内查看 | 符合边界，无需改动 | — |

#### §3.1 自然人与雇佣

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `01:58` | 工号六位纯数字，二次入职复用 | 已实现 | `models.py:327-330`（库级正则约束）、`:333-337`（unique+index）、`extended_service.py:662-735`（`_allocate_employee_number`/`reserve_employee_number`） | — | — |
| `01:70-71` | 同一雇佣关系同一生效日期四类主体各一个有效值；四者默认相同但可分别调整 | 已实现 | `models.py:645-688`（EmploymentLegalEntityRelation，`relation_kind IN ('contract','payroll','social_insurance','tax')`、唯一键 employment+kind+effective_from、版本>0）、`extended_service.py:764-870`（建雇佣时四类取同一主体）、`:895-960`（可分别新增版本并回写 employment 投影字段） | — | — |
| `01:74` | 同一自然人同一有效期间只能有一条法人劳动关系 | 已实现 | `workflow/extended_service.py` 合同/协议关系校验（`employment_id` 与 `agreement_relationship_id` 互斥，`workflow/models.py:196-199`）；协议关系独立表 `models.py:778-801` | — | — |
| `01:75` | 合作、劳务派遣等协议关系可同时存在，不计为第二条法人劳动关系 | 已实现 | `models.py:778-801`（AgreementRelationship 独立表，含 `source`、`counterparty_name`）；`extended_service.py:1019-1047`（`create_agreement_relationship`） | — | — |

#### §3.2 组织

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `01:88` | 组织类型由管理员配置 | 已实现 | `models.py:26-32`（code/name/sort_order/is_active）、`organization_api.py:69-107`（建/列/改） | — | — |
| `01:89` | 不限制不同组织类型之间的上下级组合 | 已实现 | `organization_service.py:194-199`、`:350-354` 只校验上级有效，不校验类型组合 | — | — |
| `01:90` | 业务组织树中每个组织同一时间只能有一个直接上级 | 已实现 | `models.py:64-67`（单列 `parent_organization_id`，每版本唯一）、`organization_service.py:1861-1890`（新版本应用时把上一版本 `effective_to` 收口，前一版本 `is_current=False`，天然不重叠） | — | — |
| `01:91` | 组织编码使用纯流水号自动生成 | 已实现 | `organization_service.py:201-206`（`next_number(sequence_code="ORG_NUMBER", width=6, max_value=999_999)`）、`platform/numbering.py:8-41` | — | — |
| `01:92` | 初始化导入保留历史组织编码，**新编码自动避让冲突** | 部分实现 | 保留历史编码 ✅：`import_service.py:2832`（`Organization(code=payload.code)`，模板列见 `_TEMPLATES["organization"]` `import_service.py:209-213`）。**避让缺失 ❌**：检索词 `ORG_NUMBER` 全库仅 2 处命中（`organization_service.py:201`、`:203`），导入路径**不回写 `NumberSequence`**；`numbering.py:20-41` 只自增 `NumberSequence.current_value`，不比对 `organizations.code` | 导入历史编码 `000001` 后首次新建组织会取到同样的 `000001`，撞 `organizations.code` 唯一约束（`models.py:38`）→ 500。修复：导入时按 `max(历史编码数值)` 推进 `ORG_NUMBER` 序列，或在 `next_number` 增加 `exclude_codes` 参数跳过已占用值 | P0 |
| `01:93` | 组织改名、换上级、合并、拆分、撤销支持未来生效 | 部分实现 | 改名/换上级/改类型/改状态 ✅：`organization_service.py:269-406`（`schedule_version` 排期）+`:1861-1911`（`_apply_event` 生效）。**合并/拆分/撤销 ❌**：检索词 `MERGE`、`SPLIT`、`REVOKE`（忽略大小写）全库 0 匹配业务语义命中；`OrganizationEvent.event_type` 实际只有 `CREATE`（`organization_service.py:242`）与 `VERSION_CHANGE`（`:369`） | 合并/拆分是组织域最高风险的结构变更，当前完全缺位。建议在 `17` 号功能文档迁移时明确：一期只做改名/换上级/改类型/撤销（用 `status` 表达），合并/拆分标注 `ENTERPRISE_INPUT_PENDING` 并列入第二阶段 | P1 |
| `01:94` | 产品仅展示当前有效组织树；未来变更在组织详情中按生效日期查看版本、事件和快照信息 | 部分实现 | 当前树 ✅：`organization_api.py:124-139`。详情按日期看版本/事件 ✅：`organization_api.py:142-177`（`effective_at` + `/events`）、前端 `OrganizationWorkspace.tsx:381-402`（未来变更面板 + 取消事件）、`OrganizationVersionDrawer.tsx`。**快照 ❌**：无组织级快照实体（`models.py` 快照表只有 `SnapshotBatch`/`HeadcountSnapshot`） | 组织详情目前查不到「对应快照信息」。随 `01-46` 快照范围扩充一并解决 | P1 |

#### §3.3 虚拟组织及 BP

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `01:100` | BP 类型包含 HRBP、EBP、TBP、FBP | 已实现 | `organization_models.py:85-87`（`CheckConstraint bp_type IN ('HRBP','EBP','TBP','FBP')`）、前端 `OrganizationRelationsTabs.tsx:305` | — | — |
| `01:101` | 同一个人在同一有效期间只能兼一种 BP 类型 | 已实现 | `organization_service.py:920-940`：重叠检测命中即 409 `BP_TYPE_OVERLAP` | — | — |
| `01:102-103` | 一个 BP 可服务多个业务组织；一个业务组织可被多个 BP 服务 | 已实现 | `organization_service.py:890-989`（`BpServiceScope` 批量建）、`:1010-1118`（改服务范围）、`organization_models.py:107-130`（多对多表） | — | — |
| `01:104` | BP 服务关系不改变员工主组织和主职务 | 已实现 | BP 走独立表 `person_bp_memberships`/`bp_service_scopes`，不写 `employment_assignments`；统计口径 `extended_service.py:1355-1362` 只取 `relation_type == "primary"` | — | — |

#### §3.4 负责人

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `01:108-109` | 每个组织最多三名负责人；三人均为主负责人，不设第一/副负责人 | 已实现 | `organization_service.py:786-791`（>3 直接 409 `LEADER_LIMIT_EXCEEDED`）；`organization_models.py:47-77` 无 `is_primary`/`priority` 字段，前端 `OrganizationRelationsTabs.tsx:250-277` 无主次控件 | — | — |
| `01:110` | 流程中可能使用会签或或签，不以负责人排序决定 | 已实现 | 负责人表无排序语义；会签/或签在流程侧 `workflow/conditions.py`、`extended_api.py:446-459` 独立实现 | — | — |

#### §3.5 法人及四类主体

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `01:114-117` | 法人作为独立主数据，不等同于组织；一个 BU 可关联多个法人，一个法人可关联多个组织 | 已实现 | `models.py:76-92`（LegalEntity 独立表）、`:95-124`（OrganizationLegalEntity 多对多 + 有效期 + 版本 + is_current）、`organization_service.py:666-780`（`set_legal_entities`） | — | — |
| `01:118-120` | 劳动合同、发薪、社保、个税申报主体分别保存；基础主体关系允许按生效日期直接维护 | 已实现 | `models.py:645-688`、`extended_service.py:895-960`（按 `effective_from` 新增版本，前一版本自动收口 `effective_to`） | — | — |

#### §3.6 成本中心

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `01:128` | 同一组织同一有效期间分摊比例合计必须为 100% | 已实现 | `organization_policy.py:39-49`（`assert_allocation_total` 量化到 4 位后精确等于 100.0000）、`organization_service.py:1284-1289` 调用并转 422 | — | — |
| `01:129-130` | 分摊关系具有生效日期、失效日期和版本；数据模型不得阻碍未来员工级覆盖 | 部分实现 | 生效/失效/版本 ✅：`models.py:292-295`。**员工级预留 ❌**：模型只有 `organization_id`，无 `person_id`/`scope_type` 之类的扩展位，检索 `organization_cost_allocations` 表结构确认无员工级字段 | 「不阻碍」目前靠表结构可加列被动满足，没有显式扩展点。建议在 `models.py:258` 增加 `scope_type` 枚举（默认 `organization`），为二期员工级覆盖预留位，避免二期改表 | P2 |

#### §3.7 职务与编制

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `01:134` | 当前编制维度为组织+职务+年月 | 已实现 | `models.py:807-812`（`UniqueConstraint organization_id, job_id, period_month, version`）、`extended_service.py:1158-1174` | — | — |
| `01:136-137` | 正式员工和「校招生」占编；其他人员类型当前不占编，但占编规则必须可配置 | 部分实现 | 规则机制 ✅：`models.py:835-849`（OccupancyRule 唯一键 employee_type+effective_from+version）、`extended_service.py:1191-1230`（新增版本，前版自动收口）、`:1343-1372`（`_count_people` 按 `counts_for_headcount` 过滤）。**缺默认口径 ❌**：检索词 `校招生`、`OccupancyRule(`（种子）、`counts_for_headcount=True` 全库 0 匹配业务种子；`alembic/versions/6247e614f4a2_phase_1_3_core_schema.py:141-153` 只建表不插数据 | 新库 `occupancy_rules` 为空 ⇒ `_count_people` 的 INNER JOIN 永为空 ⇒ **当前人数恒为 0**，而 `Employment.employee_type_code`（`models.py:619`）取值未定义。需补：① 企业人员类型码表（正式/校招生/外包/派遣/兼职/实习）——属企业输入；② 一份可重复执行的规则初始化脚本 | P1 |
| `01:138` | 创建待入职档案并明确待入职日期后，进入相关统计 | 已实现 | `extended_service.py:1364`（`Employment.planned_start_date <= as_of` 即计入） | — | — |
| `01:140-145` | 编制只作台账与结果展示：不阻断招聘、不预留名额、不要求有空编、招聘需求只弱关联 | 已实现 | 见 `01-45` 行的检索证据；`RecruitmentWorkspace.tsx:143`、`:186` 页面明示「不阻断招聘」 | — | — |

#### §3.8 编制指标

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `01:151-158` | 六项指标口径：月度编制数、月初人数、月末人数、月均人数、当前人数、编制差额 | 已实现 | `extended_service.py:1495-1573`：`planned_count`、`month_start_count`/`month_end_count`（取最新 completed 批次）、`average_count = (start+end)/2`、`current_count`、`variance = planned - current`；前端 `HeadcountWorkspace.tsx:215-222` 六列齐备 | — | — |
| `01:160` | 年度页面展示当前月份的编制和人员结果，不将 12 个月人数相加 | 未实现 | 检索词 `annual`、`year_view` 在 `extended_api.py:371-395`（headcount-plans）、`:496`（headcount-results）无年度聚合路由；`HeadcountWorkspace.tsx:57` 只有单 `month` 状态，`:192` 只有「年月」控件，无年度视图 | 缺年度视图。建议在 `headcount-results` 增加 `period_year` 参数 + 年度视图只回当月口径，**严禁**把 12 个月人数相加（与 `06:109` 同口径） | P2 |

#### §3.9 冻结

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `01:169` | 冻结范围由年月、组织、职务三个维度任意组合，未选择表示全部范围 | 已实现 | `models.py:852-865`（三列均可空 + `freeze_type`）、`extended_service.py:1309-1341`（`_matching_freezes` 三维匹配，组织侧含全部下级：`:1281-1307` `_organization_in_scope`） | — | — |
| `01:170-172` | 普通角色不得修改对应月度编制；授权角色可以解冻或调整，必须记录原因和日志 | 部分实现 | 冻结阻断 ✅：`extended_service.py:1143-1157`（命中冻结且未 `override_freeze` → 409 `HEADCOUNT_PLAN_FROZEN`）；解冻留痕 ✅：`:1260-1279`（`close_headcount_freeze` 写 reason + 审计）；绕过需填原因 ✅：`:1177-1188` 审计 `freeze_override`。**缺权限分级 ❌**：全部编制接口只挂 `WORKFORCE_ADMIN`（`extended_api.py:60`），不存在「普通维护者 vs 授权解冻者」两个权限码 | 文档要求「普通角色/授权角色」两级，当前只有一级。建议新增 `*` 内的细分码（如编制维护 / 编制解冻 / 快照补跑）并按 `06:221-230`、`05:245-246` 一起落地 | P1 |
| `01:173` | 招聘需求只显示冻结提示，不阻断创建或推进 | 已实现 | 后端 `workflow/extended_service.py:198-244` 不查冻结；前端 `RecruitmentWorkspace.tsx:192` 在编制参考抽屉显示冻结状态；测试 `test_recruitment_request_api.py:17` | — | — |

#### §3.10 收入目标

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `01:177-178` | 每个叶子组织可维护年度和月度收入目标；每条目标含金额、币种、生效信息和版本 | 部分实现 | 金额/币种/版本 ✅：`models.py:298-321`（`year`+`currency_code`+`annual_amount`+`version`+`is_current`+`change_reason`）、`organization_models.py:133-148`（月度明细）。**叶子限制缺失 ❌**：见 `01-29` 的检索词 | 见 `05-29` | P1 |
| `01:179-180` | 上级组织不手工录入，按下级目标自动汇总；汇总结果按币种分别呈现，不做汇率折算 | 已实现 | `organization_service.py:1600-1699`（`aggregate_revenue_tree` 按币种聚合）、`organization_api.py:410-425`（`include_descendants` 参数）；前端 `OrganizationRelationsTabs.tsx:424-435` 按币种选择 | — | — |
| `01:181` | 目标调整保留历史版本和快照 | 部分实现 | 历史版本 ✅：`organization_service.py:1487-1546`（旧版本 `is_current=False` 保留 + 新版本）。**快照 ❌**：`HeadcountSnapshot`（`models.py:891-918`）只存 org/job/plan/人数/证据，不含收入目标版本 | 快照范围缺口，见 `01-46` | P1 |
#### §4 快照与历史

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `01:188` | 系统在月初和月末自动生成快照 | 未实现 | 检索词 `scheduler`、`APScheduler`、`celery`、`cron` 在 `apps/api/src` 全库 0 匹配；`SnapshotBatch` 只由人工调用 `POST /api/v1/workforce/headcount-snapshots` 产生（`extended_api.py:480-495` → `extended_service.py:1374-1493`），前端 `HeadcountWorkspace.tsx:253` 也是「生成快照」按钮 | 缺调度器。建议在 `scripts/` 或 API 进程内加月度定时任务，按 `01:189` 的快照策略时区触发；触发前先补齐快照策略配置项（当前时区是请求参数，不是配置） | P1 |
| `01:189-190` | 月份边界按快照策略配置的时区计算，不写死服务器时区；每个批次保存时区、边界时刻和规则版本 | 已实现 | `models.py:868-888`（`timezone`/`boundary_at`/`rule_version`/`version`/`parent_batch_id`）、`extended_service.py:1378-1397`（按 IANA 时区换算本地日期并校验边界与月份一致，非法 → 422 `SNAPSHOT_BOUNDARY_DATE_INVALID`） | — | — |
| `01:191` | 管理员可以按权限手工补跑或生成修订版本 | 已实现 | `extended_api.py:480-495`（挂在 `WORKFORCE_ADMIN`）、`extended_service.py:1398-1430`（同边界同参数幂等返回原批次；修订必须传 `parent_batch_id`，否则 409 `SNAPSHOT_REVISION_PARENT_REQUIRED`） | — | — |
| `01:195-203` | 快照至少包含：组织层级、组织与法人关系、组织与成本中心关系及比例、收入目标版本、月度编制、在职/待入职及其他人员统计、员工组织/职务/法人/汇报关系（8 项） | 部分实现 | 实际仅覆盖 1 项：`models.py:891-918`（`HeadcountSnapshot` 只有 organization_id / job_id / headcount_plan_id / person_count / evidence）、`extended_service.py:1448-1477`（按当月 `HeadcountPlan` 逐行落 `person_count`）。**缺 7 项**：无组织层级、法人关系、成本分摊比例、收入目标版本快照表；`evidence` 仅存 `as_of` 与 `rule_version`（`:1470-1473`），不含可复核的人员范围 | 快照范围严重不足，「历史可复核」只对编制维度成立。建议新增组织域快照实体（或在 `HeadcountSnapshot.evidence` 内嵌组织/法人/分摊/目标快照 JSON），并把员工口径证据（人员范围/排除规则）写入 `evidence` | P1 |
| `01:207-213` | 快照修订五步：永久保留原始快照 → 先更正源数据 → 授权用户生成修订版本 → 记录原因/操作者/与原版本关系 → 将修订版本重新冻结 | 部分实现 | ① 保留原始 ✅：`models.py:882-886`（版本递增 + `parent_batch_id` 关联原批次）；④ 记录原因与关系 ✅：`extended_service.py:1440-1445`、`:1480-1492`（审计写 reason + version + parent）；③ 授权用户 ✅（权限位）。**② 无引导 ❌**：无「先更正源业务数据」的前置校验或流程约束（无修订前源数据校验）；**⑤ 重新冻结 ❌**：修订完成后没有任何重新冻结机制（`HeadcountFreeze` 不会因快照修订而重建） | 补 ⑤：在修订批次完成时，按 `period_month` 自动重建对应月结冻结记录并写审计；补 ②：在 `parent_batch_id` 提交前校验源数据已变更，否则拒绝修订 | P1 |

#### §5 数据导入与导出

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `01:219-220` | 先完成整批校验；**任一阻断错误存在时，整批不入库** | 与PRD冲突 | 校验 ✅：`import_service.py:263-455`（逐行状态 valid/rejected，批次状态 `validated` 或 `validated_with_errors`）。**冲突点**：`import_service.py:471-478` 允许 `validated_with_errors` 的批次进入 `execute_batch`，`:481` 取 `status == "valid"` 的行落库 ⇒ **有错误行时正确行仍会写入**，不存在「整批不入库」模式。检索词 `all_or_nothing`、`strict`、`blocking`、`整批` 在 `import_service.py` 无模式开关命中 | 红线冲突：初始化导入半成功会留下残缺主数据（如组织树导入 100 行、其中 3 行父级缺失 → 97 行已建，层级不完整）。修复：给 `ImportBatch` 增加 `mode`（`initialize` / `daily`），`initialize` 模式在 `rejected_rows > 0` 时直接拒绝执行（409）并提示先修正；`daily` 保持现有部分成功语义。这与 `06:138-139`「初始化导入整批校验、整批写入；日常批量维护允许正确行成功」是同一处修复 | P0 |
| `01:221-223` | 返回行号、字段、错误码和修改建议；修正后重新提交；导入成功后生成批次号和审计记录 | 已实现 | `import_service.py:886-895`（逐字段错误含 field/code/message）、`import_schemas.py:39-52`（`source_record_id` 行标识）、`import_api.py:101-153`（校验/批次查询）、`import_models.py:14`（`ImportBatch` 批次号 + `idempotency_key`）、审计动作 `governance.import_batch.validate`（`import_service.py:450-454`） | — | — |
| `01:227-229` | 日常批量维护允许正确行成功、错误行退回；必须提供成功数、失败数和错误明细；每行操作具备幂等标识 | 已实现 | `import_service.py:470-481`（只执行 valid 行，rejected 行原样保留并可回看）、`import_models.py` 批次计数列（total/valid/rejected/imported/skipped）、`:268-280`（`idempotency_key` + `request_checksum` 冲突检测） | — | — |
| `01:233-240` | 第一阶段重点模板：组织、法人、成本中心及分摊、职务体系、月度编制、收入目标、自然人和雇佣档案、当前人员关系（8 类） | 部分实现 | `import_schemas.py:9-21` 实际支持：`dictionary`、`dictionary_item`、`organization_type`、`legal_entity`、`job_dimension`、`job_dimension_version`、`job`、`job_version`、`organization`、`organization_version`、`person_basic`（11 类）。**缺 4 类**：成本中心及分摊、月度编制、收入目标、雇佣档案（Employment）/当前人员关系（EmploymentAssignment）无导入模板 | 导入能力与「组织/法人/职务体系/自然人基础层」已对齐，但**编制和收入目标没有导入通道**（这两类恰是 `01:231-240` 强调的重点模板），意味着大批量初始化只能逐条调 API。建议按 `06:137`（年月+组织编码+职务编码+编制数）优先补月度编制模板 | P1 |

#### §6 权限与审计

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `01:247-251` | 首批用户为系统管理员 + SSC 管理员；第一阶段不预置只读审计员；权限模型仍需支持后续自定义角色和只读审计角色 | 待企业输入 | 可配置角色模型 ✅：`platform/models.py:23-75`（Role/Permission/UserRole/RolePermission）、`account_admin_api.py:39-79`（角色与用户维护）。**但首批角色清单未定**：检索词 `SSC`、`系统管理员` 在 `apps/api/src` 无角色种子命中，权限码仅 `ORGANIZATION_VIEW`/`ORGANIZATION_ADMIN`/`ORGANIZATION_EVENT_APPLY`/`WORKFORCE_ADMIN`/`LIFECYCLE_ADMIN`/`ATTENDANCE_ADMIN`/`CONFIGURATION_VIEW`/`CONFIGURATION_ADMIN`/`DATA_GOVERNANCE_VIEW`/`DATA_GOVERNANCE_ADMIN` | SSC 是否为独立角色、SSC 与系统管理员的权限差集，属企业输入。建议在 `17` 号功能文档迁移时固化「角色 × 权限码」矩阵，代码侧只预留 `*` 扩展码 | P1 |
| `01:256-262` | 权限能力应支持：菜单/功能权限；增删改导入导出动作权限；按组织/下级组织/法人/BP 服务范围的数据范围授权；字段级查看/明文/修改/导出权限；月结解冻等高风险独立权限 | 部分实现 | 动作级 ✅：`platform/dependencies.py:83-97`（`require_permission` / `require_permissions`）、各 API 按码挂载（`organization_api.py:43-54`、`extended_api.py:60-63`、`audit_api.py:24-27`、`import_api.py:32-35`）。字段级 ✅（部分）：`workforce/extended_api.py:61-63` 用 `PERSON_VIEW` + `PERSON_SENSITIVE_VIEW` 区分明文，`personnel_service.py:706-720` 按字段掩码。**缺数据范围授权 ❌**：检索词 `data_scope`、`scope_organization`、`scope_legal_entity` 在 `apps/api/src` 无授权范围实现，`ORGANIZATION_VIEW` 一律返回全量组织树（`organization_api.py:124-139` 无范围过滤）；**缺菜单权限 ❌**、**缺高风险独立权限 ❌**（月结解冻与普通编制维护共用 `WORKFORCE_ADMIN`） | 「按组织/法人/BP 范围授权」是本分片最大权限缺口：现在有权限码 = 有全部数据。建议在 `require_permission` 之上加一层 scope 解析（用户→授权组织子树/法人/BP 集合→查询过滤），并把月结解冻/快照补跑拆成独立 `*` 权限码 | P1 |
| `01:265-269` | 身份证件、银行卡、薪资等敏感字段加密存储；页面默认脱敏；查看明文、导出和打印必须有独立权限并写访问日志 | 已实现 | 加密 ✅：`core/personnel_security.py:41-156`（AESGCM、密钥版本轮换、HMAC 检索摘要）、`models.py:418-422`（密文/掩码/摘要分列存储）；脱敏 ✅：`personnel_security.py:201-235`（`mask_document_number`/`mask_phone`/`mask_email`/`mask_text`）；独立权限 ✅：`extended_api.py:61-63`（`PERSON_SENSITIVE_VIEW`） | 银行卡/薪资字段当前不在人员档案模型内（`models.py:382-602` 仅证件/联系方式/地址/紧急联系人/教育/工作/家庭），该部分随薪酬域不在本分片 | — |
| `01:272-276` | 系统记录修改前值、修改后值、操作人、时间、来源和原因；界面引导核心人事关系优先走更正事件 | 部分实现 | 记录机制 ✅：`workforce/models.py:992-1016`（AuditLog：actor_id/trace_id/action/object_type/object_id/reason/before_payload/after_payload/source）、`organization_service.py:2206-2250`（组织域 `_audit` + `_outbox`）。**编制域缺修改前值 ❌**：`extended_service.py:1177-1188` 调 `_audit` 时**未传 `before`**，只写 after（`_audit` 签名 `before` 可选，见 `:64-73`）⇒ 编制改前值丢失 | 补 `before={"planned_count": existing.planned_count, "version": existing.version}`。这直接对应 `06:66`「Headcount Change Log：编制修改前后值」和 `06:232` 审计要求 | P1 |

#### §7 招聘需求

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `01:280-287` | 创建需求、选择组织和职务、录入需求人数/期望到岗日期/原因、展示相关编制数据但不校验阻断、跟踪状态、关闭或取消需求 | 已实现 | `workflow/extended_service.py:198-244`（创建，编号自动生成 `RECRUITMENT_REQUEST_NUMBER`）、`:246-282`（列表/详情）、`:284-357`（状态变更 + 审计）；前端 `RecruitmentWorkspace.tsx:76-127`（创建表单含组织/职务/人数/目标月份/原因）、`:112-127`（拉取编制参考）、`:166-168`（关闭/取消） | — | — |
| `01:291-294` | 第一阶段状态机：草稿 → 已通过 → 招聘中 → 已完成；草稿/已通过/招聘中 → 已取消 | 与PRD冲突 | 实际状态集合：`workflow/extended_schemas.py:75`（`Literal["draft","submitted","closed","cancelled"]`）、`workflow/extended_service.py:298-303`（允许转移：`draft→{draft,submitted,cancelled,closed}`、`submitted→{submitted,cancelled,closed}`、`closed→{closed}`、`cancelled→{cancelled}`）；前端 `RecruitmentWorkspace.tsx:166-168` 只有「提交/关闭/取消」三按钮。**冲突点**：文档的「已通过」「招聘中」两个中间态不存在，`submitted` 语义与文档预留的「审批中」重名，「已完成」被实现为 `closed` | 两条路二选一：① 改文档——把第一阶段状态机收敛为 `草稿→已提交→已关闭/已取消`（最省事，且与「不创建审批实例」一致）；② 改实现——补 `approved`/`recruiting` 两态并放开 `draft→approved→recruiting→completed`。建议 ①，同时把 `01:296` 的预留态与 `submitted` 命名对齐，避免二期接流程引擎时状态含义再改 | P0 |
| `01:296` | `审批中`、`已驳回`、`已撤回` 作为预留状态，第二阶段接入流程引擎后启用 | 未实现 | 检索词 `审批中`、`已驳回`、`已撤回`、`rejected`、`withdrawn`（招聘需求状态语境）在 `workflow/extended_schemas.py:75`、`workflow/extended_service.py:298-303` 无对应枚举值；`RecruitmentRequest.workflow_instance_id`（`models.py:947`）字段已预留但第一阶段不使用 | 属第二阶段范围，文档已自述为预留。按现状判为未实现（第二阶段再落地），迁移到 `17` 号功能文档时应显式标注 `DEFERRED` | P2 |

#### §8 非功能需求

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `01:302` | 业务数据不得物理删除 | 已实现 | 关系终止走软结束：组织版本 `organization_service.py:1866-1867`（`effective_to` + `is_current=False`）、汇报关系 `reporting_service.py:208-211`（`effective_to = max(business_date, effective_from)`，注释明写「软结束保留历史记录」）、任职 `workflow/extended_service.py:1693-1694`；人员子档案按 `personnel_service.py:596-613` 走有效期失效 | — | — |
| `01:303-305` | 所有主数据关系必须支持生效区间；同一维度有效区间不得非法重叠；数据库变更必须使用迁移工具 | 已实现 | 生效区间 ✅：库级 `CheckConstraint effective_to IS NULL OR effective_to >= effective_from`（如 `models.py:45-48`、`:103-106`、`:667-668`）；重叠 ✅：新版本写入前收口前版（`organization_service.py:1866`、`:837-838`、`:1347-1349`），关系集合另加 `_assert_new_relation_period`（`:2107-2117`）；迁移 ✅：`apps/api/alembic/versions/6247e614f4a2_phase_1_3_core_schema.py` | — | — |
| `01:309-312` | 不允许默认管理员密码/固定密钥进生产；可移植研究包凭据不得复用；所有管理端接口必须鉴权；高风险操作必须记录审计 | 已实现 | 鉴权 ✅：全部管理路由挂 `require_permission(s)`（`organization_api.py:43-54`、`extended_api.py:60-63`、`audit_api.py:24-27`、`import_api.py:32-35`、`configuration_api.py:29-32`）；审计 ✅：`organization_service.py:2206-2250`（`_audit` + `_outbox` 事务内同写）、`extended_service.py:64-87`；密钥 ✅：`core/personnel_security.py:159-175`（`protector_from_settings` 缺配置直接抛错） | — | — |
| `01:316-317` | 核心规则必须具备单元测试；API 必须具备集成测试 | 已实现 | 单元 ✅：`apps/api/tests/test_organization_policy.py`（`assert_no_cycle` / `assert_allocation_total` / `assert_revenue_total`）；集成 ✅：`test_organization_api.py`、`test_organization_relations_api.py`、`test_headcount_results_api.py`、`test_recruitment_request_api.py`、`test_import_governance_api.py`、`test_job_architecture_api.py`、`test_reporting_relations_api.py` | — | — |
| `01:318` | 核心页面必须具备端到端测试 | 未实现 | 检索词 `playwright`、`cypress`、`puppeteer`、`nightwatch` 在仓库全库 0 匹配；前端只有 24 个组件级 `.test.tsx`（如 `HeadcountWorkspace.test.tsx`、`OrganizationWorkspace.test.tsx`、`RecruitmentWorkspace.test.tsx`），跑在 vitest + RTL，无浏览器端到端链路 | 缺 E2E。组织/编制这类多步流程（导入→建组织→编编制→冻结→快照）目前只能靠人工回归。建议至少为「组织版本生效」和「编制冻结绕过」两条主链补 E2E | P2 |
| `01:319-320` | 导入、快照、生效日期和权限必须有异常用例；第三、四阶段前增加万人在线专项压测 | 已实现 | 异常用例 ✅：`test_headcount_results_api.py:35`（冻结绕过与快照不可变）、`:150-156`（未关联原批次的修订 → 409 `SNAPSHOT_REVISION_PARENT_REQUIRED`）、`:199-201`（命中冻结 → 409 `HEADCOUNT_PLAN_FROZEN`）、`test_import_governance_api.py`（幂等冲突/重复来源/循环/缺失父级）。压测属第三、四阶段前置，当前阶段不要求 | — | — |
### 文档 05：组织与主体领域规范

#### §1–§3 目标与业务组织树

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `05:11` | 规范定义第一阶段的法人、业务组织、虚拟组织、负责人、BP 服务关系、成本中心和收入目标 | 已实现 | 法人 `models.py:76-124`；业务组织 `models.py:35-73`；虚拟/兼岗 `models.py:691-745`；负责人 `organization_models.py:47-77`；BP `organization_models.py:80-130`；成本中心 `models.py:240-295`；收入目标 `models.py:298-321` + `organization_models.py:133-148` | — | — |
| `05:16-19` | 表达组织/法人/成本中心多对多；表达主组织/兼岗/借调/项目/虚拟组织关系；管理负责人与四类 BP；支持未来生效、历史查询和月度快照 | 部分实现 | 多对多 ✅；主组织/兼岗等 ✅（`EmploymentAssignment.relation_type`）；负责人与 BP ✅；未来生效/历史查询 ✅（`organization_api.py:151`、`:315` 的 `effective_at`）；**月度快照 ❌**：`models.py:891-918` 快照只落编制维度，无组织层级/法人/分摊/目标快照（见 `05-35`） | 与 `05-35`/`01-46` 同一处缺口 | P1 |
| `05:21` | 本规范不定义第二阶段的组织审批流，也不实现未来组织树预演 | 已实现 | `organization_api.py:133-138` 明确拒绝 `effective_at` 树查询（422 `CURRENT_TREE_ONLY`） | — | — |
| `05:49` | 管理员可配置组织类型的编码、名称、启停状态和显示顺序；不限制某类组织只能挂在特定类型下 | 已实现 | `models.py:26-32`（code/name/sort_order/is_active）、`organization_api.py:69-107`；挂载不校验类型组合（`organization_service.py:194-199`、`:350-354` 只校验上级有效） | — | — |
| `05:53-56` | 每个有效业务组织同一时点最多一个直接上级；根组织没有上级；不允许成环；不能移动到自身或自身下级 | 已实现 | 单父 ✅：`models.py:64-67` 单列 + `organization_service.py:1861-1890` 收口前版；根 ✅：`parent_organization_id` 可空；无环 ✅：`organization_policy.py:22-36`（`assert_no_cycle`），调用点 `organization_service.py:211-219`（建）、`:356-365`（排期） | — | — |
| `05:61-65` | 新组织编码纯流水号、自动生成、创建后不得随意修改；初始化导入保留历史编码；**自动编号必须避开已导入的历史编码**；位数/起始值/补零在编码规则中配置 | 部分实现 | 纯流水号/自动 ✅：`organization_service.py:201-206`（`ORG_NUMBER`、width=6）；不可随意修改 ✅：`code` 只在 `organizations` 主表，版本表不含 code（`models.py:38` vs `:41-73`）；保留历史编码 ✅：`import_service.py:2832`。**避让 ❌**：见 `01-92`（`ORG_NUMBER` 序列不回写）；**规则可配置 ❌**：width/max_value/起始值硬编码在调用点（`organization_service.py:201-206`），`platform/numbering.py:34-41` 只暴露「耗尽」错误 | 修复见 `01-92`；编码规则外置为配置项（当前 `NumberSequence` 表已有 `width`/`max_value` 列，`platform/models.py:96-103`，但起始值与补零策略不可配） | P1 |
| `05:69-80` | 组织建议字段：编码/名称/类型/直接上级/国家地区/状态（草稿、待生效、有效、失效）/生效日期/失效日期/说明/版本 | 部分实现 | 命中 ✅：编码 `models.py:38`、名称 `:58`、类型 `:59-63`、上级 `:64-67`、国家 `:68`、状态 `:69`、生效 `:70-71`、版本 `:57`；**说明 ❌**：`OrganizationVersion` 无 description/remark 字段（`:41-73` 只有 `change_reason`）；**状态枚举未约束 ❌**：`status` 为自由 `String(30)`，无 CheckConstraint 限定四态 | 补 `description` 字段（文档标为可空，低优先）；状态加 CheckConstraint（`draft`/`pending`/`active`/`inactive`）并与前端字典对齐 | P2 |

#### §4 组织生效事件

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `05:86-94` | 组织支持七类事件：新建、改名、修改组织类型、换上级、合并、拆分、撤销或失效 | 部分实现 | 命中 4 类：`CREATE`（`organization_service.py:242`）、`VERSION_CHANGE`（`:369`，其 payload 同时承载改名/改类型/换上级/改状态：`event_payload` 见 `:276-286`）、撤销/失效（通过 `status` 置为失效表达，`models.py:69`）。**缺 2 类**：合并、拆分 —— 检索词 `MERGE`、`SPLIT`（忽略大小写）全库 0 匹配 | 合并/拆分见 `01-93` 结论（建议一期收敛范围，二期承接） | P1 |
| `05:98-101` | 每个事件必须填生效日期；未来生效事件在生效前不改变当前树；当前产品只展示有效组织树；不建独立待生效事件页面，在组织详情按生效日期查看 | 已实现 | 生效日期必填 ✅：`organization_models.py:37`（`nullable=False`）+ `organization_schemas.py` 的 `effective_date` 校验；未来不改变当前树 ✅：`organization_service.py:231-232`（`is_current` 按业务日判定）、`:404-405`（生效日 ≤ 今日才立即 apply）；只展示有效树 ✅：`organization_api.py:124-139`；无独立待生效页面 ✅：前端 `OrganizationWorkspace.tsx:388-402` 在详情内展示未来变更 | — | — |
| `05:102` | **生效时**重新校验上级有效性、环路、有效期冲突和关联约束 | 与PRD冲突 | 排期时校验 ✅：`organization_service.py:336-365`（类型启用、上级有效、环路；且 `_parent_map_as_of` 已把已到期 planned 事件折进父链，`:1804-1808`，故排期期互为父级的未来事件会被 `assert_no_cycle` 拦下）；**生效时不校验 ❌**：`_apply_event`（`:1861-1911`）只做版本号比对与版本收口，**不复核上级有效性、有效期冲突与关联约束** | 红线冲突：文档要求「**生效时**重新校验」，实现只在排期时校验。排期到生效之间若上级被撤销/失效（或被其他事件改级），事件仍会落库，形成指向失效上级的有效版本——上级有效性这道校验在真正生效的那一刻缺位。修复：把 `:336-365` 的校验块抽成 `_validate_version_target(org_id, parent_id, effective_date)`，在 `_apply_event` 落库前 `await` 一次（上级有效性 + 有效期冲突 + 关联约束） | P0 |
| `05:103` | 事件生效、失败、取消和回退均记录日志 | 部分实现 | 生效 ✅：`organization_service.py:1894-1901`（`organization.version.apply`）；取消 ✅：`cancel_event`（`:408-473`）；失败 ✅：异常路径由 `ApiError` 统一转换。**回退 ❌**：组织域无回退能力（见 `05-12`） | — | P1 |
| `05:104-107` | 回退策略：按事件类型采用补偿事件/历史版本恢复/两者组合；支持直接生效和审批生效；未注册策略时默认拒绝自动回退；回退创建新的事件和结果版本，不删除或覆盖原事件；已同步下游的数据通过新的回退记录再次同步并关联原同步记录 | 未实现 | 检索词 `rollback`、`compensat`（组织域语境）在 `apps/api/src/hris/modules/workforce/organization_*.py` 0 匹配；`OrganizationEvent`（`organization_models.py:23-44`）无 `rollback_of`/`strategy` 字段；`organization_api.py` 无回退路由。**注意**：`rollback_hr_event`（`workflow/extended_api.py:549`）属人事事件域，不覆盖组织事件 | 整条回退能力缺失，且与 `05:106`「不删除或覆盖原事件」这一回退安全原则绑定。建议在 `17` 号功能文档中把组织回退明确划到第二阶段受控领域动作（与 `05:109` 一致） | P1 |
| `05:109` | 第一阶段普通组织变更不走通用审批；回退审批作为受控领域动作实现；第二阶段流程引擎接管后支持会签和或签 | 未实现 | 组织变更确实不走通用审批 ✅（`organization_api.py:180-195` 直接 `schedule_version`）；**回退审批 ❌**（无回退能力，见 `05-12`） | 随 `05-12` 一并处理 | P2 |

#### §5 法人及主体关系

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `05:115` | 法人主体独立于组织维护；一个 BU 可关联多个法人，一个法人可覆盖多个组织 | 已实现 | `models.py:76-92`（LegalEntity 独立主数据）、`:95-124`（OrganizationLegalEntity 多对多）、`organization_service.py:666-780`（`set_legal_entities` 批量维护 + 有效期 + 版本 + 审计） | — | — |
| `05:117-126` | 法人候选字段：主体编码与名称、国家/地区、注册名称、统一社会信用代码或当地注册标识、注册地址、状态和有效期 | 部分实现 | 命中 ✅：编码 `models.py:85`、名称 `:86`、国家 `:88`、注册名称 `:87`、注册标识 `:89`、状态 `:90`、有效期 `:91-92`。**缺 1 项**：注册地址 —— `LegalEntity` 无地址字段（`:76-92`） | 文档本写「具体字段等待现有主体表结构」（`05:126`），属企业输入；建议在企业主数据到位前保持缺口并标注 `ENTERPRISE_INPUT_PENDING` | P2 |
| `05:130-134` | 组织与法人多对多；关系记录生效/失效日期和历史版本；组织树上下级不推导法人归属；不因上级关联某法人而强制所有下级关联；人员四类主体不能仅由组织法人关系替代 | 已实现 | 多对多 ✅：`:95-124` + `organization_service.py:666-780`；有效期+历史版本 ✅：`:121-124`（effective_from/to、version、is_current），新版本收口前版（`organization_service.py:750-780`）；不推导 ✅：`set_legal_entities` 只处理传入集合，无任何按父级扩散逻辑；四类主体独立 ✅：`models.py:645-688` | — | — |
| `05:138-145` | 每条有效雇佣在同一生效日期分别保存劳动合同/发薪/社保/个税主体；四者默认同一主体但可分别调整；每类同一时点只能一个有效值 | 已实现 | `models.py:645-688`（唯一键 employment+kind+effective_from、version>0、kind 四值约束）、`extended_service.py:833-855`（建雇佣时四类取同一主体）、`:895-960`（分别新增版本：旧版 `effective_to` 收口 + 回写 `Employment` 投影字段） | — | — |

#### §6 组织负责人

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `05:149-152` | 每组织同一有效期间最多三名负责人；三名均为主负责人、不设主次排序；负责人关系记录生效/失效日期；同一人员可负责多个组织 | 已实现 | 上限 ✅：`organization_service.py:786-791`（>3 → 409 `LEADER_LIMIT_EXCEEDED`）；无主次 ✅：`organization_models.py:47-77` 无优先级字段；有效期 ✅：`:74-75`；一人多组织 ✅：唯一键是 (organization_id, person_id, effective_from, version)，不限制 person 维度 | — | — |
| `05:153-154` | 负责人不自动获得全部敏感字段权限，数据权限另行授权；后续审批可按业务配置使用全部会签或任一或签 | 已实现 | 负责人仅写 `organization_leaders` 表，不进角色/权限表（`organization_service.py:781-888` 全程无 `UserRole`/`RolePermission` 写入）；敏感字段走独立 `PERSON_SENSITIVE_VIEW`（`extended_api.py:61-63`）；会签/或签在流程侧（`workflow/extended_api.py:446-459`、`workflow/conditions.py`） | — | — |
| `05:156` | 组织详情同时展示当前负责人和历史负责人 | 部分实现 | 后端可查历史 ✅：`organization_api.py:306-321`（`/relations` 带 `effective_at`）、`organization_service.py:1147-1161`（按 `effective_at` 过滤）。**前端未提供历史视图 ❌**：`OrganizationRelationsTabs.tsx:250-277` 负责人页签只渲染当前 `leader_person_ids`，无历史切换或历史列表 | 建议在负责人页签加「当前/历史」切换，按 `effective_at` 调用同一接口（后端已就绪，前端补交互即可） | P2 |

#### §7 虚拟组织与 BP

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `05:162-170` | 非业务树关系至少支持兼岗、借调、项目、虚拟组织、委员会；**关系类型可配置**；每条关系记录人员、组织、关系类型、生效/失效日期和说明 | 部分实现 | 类型集合 ❌：`extended_schemas.py:294` 硬编码 `Literal["primary","concurrent","secondment","project","virtual"]` —— 有兼岗/借调/项目/虚拟，但**缺「委员会」**，且把「主组织」也混在关系类型里；**可配置 ❌**：无关系类型字典表（检索词 `RELATION_TYPE`、`组织关系类型` 0 匹配）。记录字段 ✅：`models.py:691-717`（EmploymentAssignment，含 effective_from/to、change_reason）；`models.py:720-745` 的 `OrganizationPersonRelation`（含 `note` 说明字段）**全库无任何服务/接口使用**——仅在 `shared/db/models.py:49` 元数据注册 | ① 关系类型改为基础资料字典驱动（与标签库/字典模块一致）；② 补「委员会」类型；③ `OrganizationPersonRelation` 要么接入要么移除，避免死表 | P1 |
| `05:172` | 员工同一时间只有一个主组织，但可同时存在多个其他类型的有效组织关系 | 已实现 | `extended_service.py:978-990`：新增 `primary` 任职时检测同期重叠并拒绝（唯一键 `employment_id+relation_type+effective_from`，`models.py:693-698`）；非 primary 类型允许多条 | — | — |
| `05:185-188` | 同一人同一有效期间只能兼一种 BP 类型；一个 BP 可服务多个组织；一个组织可由多个 BP 服务；BP 服务关系不改变主组织、主职务或实线汇报关系 | 已实现 | 唯一性 ✅：`organization_service.py:920-940`（重叠 → 409 `BP_TYPE_OVERLAP`）；多对多服务 ✅：`:962-972`（`BpServiceScope` 批量）+ `:1010-1118`（改范围）；不改变主组织 ✅：BP 走独立表，不写 `employment_assignments`/`reporting_relations` | — | — |
| `05:189` | BP 中心是否作为独立组织由实际组织数据决定，不设系统强制 | 已实现 | `organization_service.py:917-918` 只校验服务组织在该日期有有效状态，不校验组织类型是否为 BP 中心 | — | — |

#### §8 实线与虚线汇报

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `05:193-197` | 实线汇报=主要业务管理关系；虚线汇报=兼岗/项目/专业/协同；汇报关系独立于组织负责人和 BP 服务关系；每条关系含上级人员、下级人员、关系类型和有效期；是否限制同时有效的实线上级数量待真实数据确认 | 已实现 | `models.py:748-776`（ReportingRelation 独立表，含 manager/subordinate/relation_type/effective_from/to、禁止自环）；`reporting_api.py:60-118`（建/列/软结束）；`reporting_service.py:231-...`（`_ensure_no_cycle`，按关系类型分别查环）；独立性 ✅：与 `organization_leaders`/`bp_service_scopes` 无外键关联 | 最后一条「是否限制实线上级数量」文档自述待确认，本实现不限制，符合未定状态 | — |

#### §9 成本中心

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `05:203` | 成本中心独立维护编码、名称、国家/地区、状态和有效期；多个组织可归集到同一成本中心 | 已实现 | `models.py:240-255`（code/name/country_code/status/effective_from/to/version）、`organization_service.py:1207-1250`（建档）、`:1251-1257`（列表） | — | — |
| `05:207-213` | 一个组织可分摊至多个成本中心；同一组织同一有效期间有效比例合计必须 100%；比例使用统一精度且舍入后仍通过合计校验；分摊方案记录生效/失效日期和版本；未来版本生效前不改变当前方案；第一阶段只实现组织级分摊；数据模型保留未来员工级覆盖能力 | 部分实现 | 多成本中心 ✅：`organization_service.py:1279-1308`；100% 合计 ✅：`organization_policy.py:39-49`（统一量化 4 位后精确等于 100.0000，`:7-8` 定义精度）；生效/失效/版本 ✅：`models.py:292-295`；未来版本不改当前 ✅：`organization_service.py:1343-1349`（新版本生效前旧版 `is_current=False` 且 `effective_to` 收口）。**员工级预留 ❌**：见 `01-129-130`（表结构无扩展位） | 与 `01-129-130` 同一处，建议加 `scope_type` 预留位 | P2 |
| `05:215` | 第一阶段只保存和展示分摊关系，不执行薪酬或费用核算 | 已实现 | 检索词 `payroll`、`cost_accrual` 在 `apps/api/src/hris/modules/workforce` 无成本核算实现；分摊只读写 `organization_cost_allocations`（`organization_service.py:1259-1407`） | — | — |

#### §10 收入目标

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `05:221` | **只有叶子业务组织可以录入收入目标** | 未实现 | 检索词 `leaf`、`叶子`、`is_leaf`、`child_count` 在 `apps/api/src` 全库 0 匹配；`organization_service.py:1450-1586`（`set_revenue_target`）的校验只有：月份不重复（`:1471-1479`）、年度=月度合计（`:1480-1483`）、组织存在且当日有有效状态（`:1485-1486`）——**无叶子判定**；`aggregate_revenue_tree`（`:1600-1699`）也未区分叶子与非叶子的录入权限 | 允许非叶子组织录入 ⇒ 上级组织既有自身目标又有汇总值，与 `05:231`「非叶子组织不直接维护汇总目标」直接矛盾，且汇总时会出现"自身 + 下级"双算风险。修复：在 `set_revenue_target` 中按目标年度的当期组织树判定该组织是否为叶子（非叶子 → 422 `REVENUE_TARGET_LEAF_ONLY`） | P1 |
| `05:222-225` | 收入目标只有一个业务字段，不区分 GMV/营收/利润；同时保存年度目标和月度目标；每条目标必须选择币种；调整时生成新版本并保留原版本 | 已实现 | 单一字段 ✅：`models.py:298-321` 只有 `annual_amount`（无类型字段）；年月并存 ✅：`organization_models.py:133-148`（RevenueTargetMonth，month 1–12 约束）；币种必填 ✅：`models.py:317`（`currency_code` `nullable=False`）；版本保留 ✅：`organization_service.py:1487-1546`（旧版 `is_current=False` 保留 + 新版 version+1） | — | — |
| `05:226` | 月度快照保留当时有效目标 | 未实现 | `models.py:891-918`（HeadcountSnapshot）与 `:868-888`（SnapshotBatch）均无收入目标字段；`extended_service.py:1448-1477` 生成快照时只遍历 `HeadcountPlan` | 快照范围缺口，见 `01-46`/`05-35` | P1 |
| `05:230-234` | 上级目标由当前有效下级自动向上汇总；非叶子组织不直接维护汇总目标；不同币种分别汇总和展示；不做汇率折算和集团币种合并；不管理实际收入、不计算完成率 | 已实现 | 汇总 ✅：`organization_service.py:1600-1699`（`aggregate_revenue_tree` 按 `currency_code` 分组，`include_descendants` 控制范围）、`organization_api.py:410-425`；无汇率字段/无完成率字段（`models.py:298-321` 只有目标额） | 「非叶子不直接维护」这一条未在写入侧强制（见 `05-221`），汇总侧只读不写，属可接受现状 | P1 |
| `05:236` | 年度目标必须拆解到 12 个月，12 个月月度目标合计必须等于年度目标 | 已实现 | `organization_policy.py:52-70`（`assert_revenue_total`：必须恰为 1–12 月且合计相等）、`organization_service.py:1471-1483` 调用并转 422 | — | — |

#### §11–§13 权限、快照与异常

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `05:240-248` | 按组织和全部下级授权；按法人授权；按 BP 服务范围授权（一期不默认开放 BP 角色）；组织维护/负责人维护/成本分摊/目标维护/事件回退分为独立动作权限；导入导出和高风险操作独立授权；所有变更记录对象、版本、修改前后值、操作者、时间、原因和来源 | 部分实现 | 变更记录 ✅：`organization_service.py:2206-2250`（`_audit` 写 object/object_id/version/before/after/actor/trace_id/reason/source + `_outbox`）；`organization_api.py` 现有码：`ORGANIZATION_VIEW`（读）、`ORGANIZATION_ADMIN`（组织/负责人/分摊/目标维护合并为一档）、`ORGANIZATION_EVENT_APPLY`（事件生效）、`DATA_GOVERNANCE_ADMIN`（导入导出，`platform/import_api.py:32-35`）。**缺**：动作权限未按文档 5 类拆分（组织维护/负责人/分摊/目标/回退共用 `ORGANIZATION_ADMIN`）；**缺**数据范围授权（见 `01-256-262`）；**缺**回退动作权限（无回退能力） | 建议把 `ORGANIZATION_ADMIN` 拆成 `*` 范围内的 4–5 个动作码，并补 scope 过滤层；BP 范围授权按文档「一期不默认开放」可不实现，但需在文档侧写清 | P1 |
| `05:252-259` | 月初/月末快照至少保存：当时有效的业务组织层级、组织状态和组织类型、组织与法人关系、组织负责人和 BP 服务关系、组织与成本中心分摊、收入目标版本（6 项） | 部分实现 | 实际快照内容为 0 项组织域数据：`models.py:891-918` 只有 organization_id/job_id/headcount_plan_id/person_count/evidence；`extended_service.py:1448-1477` 只遍历 `HeadcountPlan` 生成行 | 组织域快照整体缺失，文档 `05:19`「支持……月度快照」与 `05:287`「当前树、历史版本、快照和审计结果一致」因此无法成立。建议新建组织域快照实体，或在 `HeadcountSnapshot.evidence` 内嵌 6 项组织域快照 JSON | P1 |
| `05:263-267` | 支持：查询当前有效组织树；在组织详情按生效日期查询关系历史、事件和对应快照信息；查询指定法人覆盖的组织和人员；查询指定组织关联的法人、成本中心、负责人和 BP；对比两个快照时点的组织结果（5 项） | 部分实现 | ① 当前有效树 ✅：`organization_api.py:124-139`；② 关系历史 ✅（`effective_at`，`:306-321`）、事件 ✅（`:160-177`）、**对应快照信息 ❌**（无组织快照）；③ **法人反查未实现 ❌**：检索词 `legal-entities/{` 在 `apps/api/src` 无路由（`extended_api.py:98` 只有 `GET /legal-entities` 列表），无「某法人覆盖的组织与人员」接口；④ 组织关联的法人/分摊/负责人/BP ✅（`:306-321` + `:367-382`）；⑤ **快照对比未实现 ❌**：无快照对比路由 | 补 ③ 与 ⑤ 两条查询能力；② 的快照部分随组织快照落地 | P1 |
| `05:271-276` | 异常规则 6 条：上级失效前须处理下级；合并/拆分不自动改写人员与主体关系；负责人/BP 人员失效时提示受影响关系不静默删除；成本分摊不足或超 100% 不得生效；叶子变非叶子须处理其收入目标；未来事件冲突不得静默覆盖先创建事件 | 部分实现 | ③ 部分 ✅：`organization_service.py:809-816`（负责人非 active 拒绝新增）、`:909-916`（BP 人员非 active 拒绝），但**无「受影响关系提示」查询**；④ ✅：`organization_policy.py:39-49` + `organization_service.py:1284-1289`；⑥ ✅：`organization_service.py:319-334`（`EFFECTIVE_DATE_SEQUENCE_INVALID`，后创建事件不得早于已有 planned 事件）；① ❌（无「上级失效前须处理下级」校验）、② ❌（随合并/拆分缺失）、⑤ ❌（随叶子校验缺失） | ① 建议在组织失效/撤销时校验有效下级并拒绝或提示；⑤ 随 `05-221` 一并落地 | P1 |
### 文档 06：编制与人力结果领域规范

#### §2–§4 业务边界、核心维度与数据对象

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `06:25-29` | 第一阶段包括：月度编制台账、人员占编规则配置、当前和快照人数统计、业务冻结与月结冻结、导入导出历史和审计 | 部分实现 | 编制台账 ✅、占编规则 ✅、当前人数 ✅、冻结 ✅（`freeze_type` 含 `month_close`/`business`，`HeadcountWorkspace.tsx:241`、`:272`）；**导入 ❌**（无编制导入模板，见 `06-22`）、**导出 ❌**（无编制导出，见 `06-23`） | 与 `06-22`/`06-23` 同一处 | P1 |
| `06:33-38` | 第一阶段不包括：招聘空编预留、Offer 占编、无空编禁止招聘、超编审批或特批、编制申请/增减/调拨完整审批流程、编制预警通知 | 已实现 | 检索词 `reserve_headcount`、`preallocate`、`headcount_request`、`quota` 在 `apps/api/src` 无编制占用/预留/预警实现；`batch_change_models.py:61-82` 是**人事事件**批量方案（`HrEventBatch`），不是编制申请 | 边界符合。`batch_change`（开发中）不要与编制调拨混淆 | — |
| `06:44-46` | 月度编制唯一维度为「组织 + 职务 + 年月」 | 已实现 | `models.py:807-812`（`UniqueConstraint organization_id, job_id, period_month, version`）、`extended_service.py:1158-1174`（同维度取当前版本再递增） | — | — |
| `06:50` | 组织必须是该月份有效的业务组织 | 部分实现 | `extended_service.py:1135-1136` 只校验 `Organization` **存在**（不存在 → 404 `ORGANIZATION_NOT_FOUND`），**不校验该组织在 `period_month` 是否有有效版本**；对照：职务做了有效期校验（`:1137-1142` → 422 `JOB_NOT_EFFECTIVE`），组织侧缺失 | 允许给目标月无效的组织建编制，会产生口径错误的编制行。修复：复用 `organization_service._state_as_of(org_id, period_month)` 或直接查 `OrganizationVersion` 在该月是否有效 | P1 |
| `06:51` | 职务必须是有效职务 | 已实现 | `extended_service.py:1137-1142` → `_job_effective_at`（`:463-473`）→ 不在目标月生效则 422 `JOB_NOT_EFFECTIVE` | — | — |
| `06:52` | 年月使用自然月 | 已实现 | `models.py:828`（`period_month` Date，索引）；前端 `HeadcountWorkspace.tsx:115` 统一提交为 `${YYYY-MM}-01` | — | — |
| `06:53` | 编制数为非负数；**是否允许小数等待真实业务数据确认** | 待决策 | 非负 ✅：`models.py:813`（`CheckConstraint planned_count >= 0`）；但实现已单方面选择允许小数：`models.py:829`（`Numeric(12,2)`）、前端 `HeadcountWorkspace.tsx:263`（`precision={2}`）、`extended_service.py:1560`（`variance` 走 Decimal） | 文档写明该口径「等待真实业务数据确认」，代码已按「允许两位小数」落地。属**未确认即定型**。建议在企业输入包中冻结该口径（人员数通常为整数，但编制常含 0.5 FTE），并把 `Numeric(12,2)` 与文档口径写进 `17` 号功能文档 | P1 |
| `06:54` | 同一维度可以有多个历史版本，但同一时点只有一个当前有效版本 | 已实现 | `models.py:830-831`（`version` + `is_current`）、`extended_service.py:1158-1174`（旧版 `is_current=False`、新版本 version+1） | — | — |
| `06:56` | 第一阶段不把法人、成本中心或招聘需求加入编制唯一维度 | 已实现 | `models.py:804-832` 唯一键只含 organization_id/job_id/period_month/version | — | — |

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `06:60-66` | 建议数据对象：Headcount Plan、Occupancy Rule、Headcount Freeze、Headcount Snapshot、Headcount Change Log（5 个） | 部分实现 | 命中 4 个：Plan `models.py:804-832`、OccupancyRule `:835-849`、Freeze `:852-865`、Snapshot `:891-918`。**缺 Headcount Change Log ❌**：检索词 `headcount_change_log`、`HeadcountChangeLog` 全库 0 匹配；编制变更只落通用 `AuditLog`（`models.py:992-1016`），且写入时**未记录修改前值**（`extended_service.py:1177-1188` 只传 `after`） | 文档把「编制修改前后值、原因和操作者」作为独立对象，实现退化为通用审计且丢 before。建议：① 补 before 记录；② 提供按 (organization, job, period) 的编制变更历史查询（现只能靠 `platform/audit-logs?object_type=headcount_plan` 手工过滤） | P1 |
| `06:68-78` | 月度编制建议字段：年月、组织、职务、编制数、版本、冻结状态、变更原因、来源批次、创建与修改信息（9 项） | 部分实现 | 命中 6 项：年月 `:828`、组织 `:816-821`、职务 `:822-827`、编制数 `:829`、版本 `:830`、变更原因 `:832`、创建与修改信息（`TimestampMixin`）。**缺 2 项**：`冻结状态`（模型无该列，冻结状态由 `HeadcountFreeze` 实时计算，见 `extended_service.py:1564-1570`）、`来源批次`（无 `source_batch_id` 列，无法区分人工维护/批量导入/快照修订写入） | ① 冻结状态：实时计算可接受，但导出要求「数据版本和冻结状态」（`06:150`）需要同源计算；② 来源批次缺失 ⇒ 无法回答「这行编制是谁/哪批导入进来的」，建议加 `source_batch_id`（可空 UUID，指向 `ImportBatch.id`） | P1 |
| `06:84-87` | 占编规则：正式员工计入；「校招生」计入；外包/派遣/兼职/实习等不计入；所有人员类型均进入人员主数据，是否占编由配置决定 | 部分实现 | 「由配置决定」✅：`models.py:835-849` + `extended_service.py:1191-1230`（按人员类型码配置、带生效日期和版本）、`:1367-1369`（统计按 `counts_for_headcount` 过滤）；「所有人员类型均进入人员主数据」✅（`Person` 不按类型限制，类型在 `Employment.employee_type_code`，`models.py:619`）。**默认口径缺失 ❌**：检索词 `校招生`、`OccupancyRule(`、`counts_for_headcount=True` 全库 0 种子命中；迁移 `alembic/versions/6247e614f4a2_phase_1_3_core_schema.py:141-153` 只建表 | 规则表为空 ⇒ `_count_people` 的 INNER JOIN 永空 ⇒ **当前人数恒 0**（页面上编制有值、人数全 0）。修复：随企业人员类型码表到位，提供一份幂等的规则初始化脚本（正式/校招生=是；外包/派遣/兼职/实习=否），并在 `17` 号功能文档固化人员类型码枚举 | P1 |
| `06:88` | 创建待入职档案并明确计划入职日期后，按适用月份进入相关人数统计 | 已实现 | `extended_service.py:1364`（`Employment.planned_start_date <= as_of` 即计入，且 `end_date` 未到）；`workflow/extended_service.py:673-679`（录用转待入职时同步建主任职，planned_start_date 来自入职计划） | — | — |
| `06:89-90` | 调岗、离职、入职撤回等人事流程完成后在生效日期释放原占用；未来生效事件在未来生效日期释放或转移，不提前改变当前人数 | 已实现 | `workflow/extended_service.py:1690-1694`（调岗/离职把原 `EmploymentAssignment.effective_to` 设为事件生效日 → 统计按 `effective_to >= as_of` 排除，`:1359-1363`）；`Employment.status.not_in(("withdrawn","terminated"))`（`:1366`）排除撤回/终止 | — | — |
| `06:92` | 第一阶段无完整入转调离流程时，人数结果基于有效人员档案和已生效关系计算 | 已实现 | `extended_service.py:1343-1372`（`_count_people` 只按有效档案 + 有效任职 + 生效占编规则计算） | — | — |

#### §6–§7 指标口径与统计归属

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `06:100-105` | 六项指标口径（编制数/月初/月末/月均/当前/差额） | 已实现 | `extended_service.py:1495-1573`：`planned_count`；月初/月末取当月最新 `completed` 批次（`:1512-1533`）；月均 `(start+end)/2`（`:1544-1548`）；当前 `_count_people`（`:1541`）；差额 `planned - current`（`:1560`） | — | — |
| `06:107` | 月均人数可以产生小数 | 已实现 | `extended_service.py:1544-1548`（`Decimal` 除法，保留小数）；前端 `HeadcountWorkspace.tsx:220` 直出 | — | — |
| `06:109` | 年度页面展示当前月份的编制数、当前人数和差额，不把 12 个月人数相加 | 未实现 | 检索词 `period_year`、`year` 在 `extended_api.py:371-395`、`:496-...` 无年度聚合参数；`HeadcountWorkspace.tsx:57` 只有 `month` state，`:192` 只有「年月」控件，页面无年度视图 | 与 `01:160` 同源。修复：新增年度视图（只展示当月口径），实现时**不得**对 12 个月人数求和 | P2 |
| `06:111-112` | 待入职人员按计划入职日期归入对应月份统计；月初月末边界按快照策略配置的时区计算，每个批次保存时区和边界时刻 | 已实现 | 归月 ✅：`extended_service.py:1364`（`planned_start_date <= as_of`，`_count_people` 的 as_of 取快照本地日 `:1468`）；时区 ✅：`:1378-1382`（`ZoneInfo` 换算本地日期）、`:1383-1397`（边界必须与月份+类型一致）；批次保存 ✅：`models.py:876-881`（`timezone`/`boundary_at`/`rule_version`） | — | — |
| `06:116-122` | 统计归属：按统计时点有效的主组织和主职务；兼岗/借调/项目/虚拟默认不重复占编；BP 服务、实线/虚线汇报、四类主体均不改变组织+职务维度 | 已实现 | `extended_service.py:1355-1362`（`EmploymentAssignment.organization_id` + `job_id` + `relation_type == "primary"`，生效区间过滤）；兼岗等非 primary 不计（`:1358`）；BP 走独立表（`organization_models.py:107-130`）不参与；汇报关系表独立（`models.py:748-776`）；四类主体只影响 `EmploymentLegalEntityRelation`（`models.py:645-688`） | — | — |

#### §8 月度维护

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `06:128-133` | 页面维护 6 条：先选年月；页面平铺显示组织+职务明细；修改指定月份的编制数；修改时填写原因；保存后生成新版本和变更日志；不允许修改其他月份的值作为当前月份的副作用 | 部分实现 | 选年月 ✅：`HeadcountWorkspace.tsx:192`；平铺明细 ✅：`:206-224`（组织+职务行表）；填原因 ✅：`:286`（`change_reason` 必填）+ 后端 `models.py:832` 必填；新版本 ✅：`extended_service.py:1166-1174`；不影响其他月份 ✅（写入只针对 `period_month` 单一维度，`:1158-1174`）。**但「平铺维护」未达成 ❌**：明细表**只读**，编辑需弹「维护编制」Modal 重新选年月/组织/职务/编制数（`HeadcountWorkspace.tsx:188`、`:257-265`、`:259-263`），无法在平铺表上直接改数；且 Modal 内 `period_month` 可独立改（`initialValue={month}` 但可编辑），与页面当前年月解耦，易误写到别的月份 | 建议把表格改为可编辑单元格（行内改数 → 弹原因确认 → 调同一 `POST /headcount-plans`），并把 Modal 里的 `period_month` 改为只读跟随页面筛选月份 | P1 |
| `06:137-141` | 批量导入：模板含年月、组织编码、职务编码、编制数；初始化导入整批校验整批写入；日常批量允许正确行成功、错误行返回；重复导入用幂等键避免重复版本；错误明细含行号、字段、错误码、修正建议 | 未实现 | 检索词 `headcount` 在 `platform/import_schemas.py:9-21` 的 `ImportEntityType` 枚举中不存在（11 类模板无月度编制）；`import_service.py:853-865` 的 entity_type→schema 映射无编制项；`import_service.py:1180-1193` 目标表映射无 `headcount_plans` | 编制无导入通道 ⇒ 批量初始化只能逐条调 API。建议按 `06:137` 的四列模板新增 `headcount_plan` 导入类型，并复用现有 `idempotency_key` + `source_record_id` 幂等机制（`import_service.py:268-280`） | P1 |
| `06:145-152` | 导出至少支持：当前选择年月、组织和全部下级范围、编制/月初/月末/月均/当前人数/差额、数据版本和冻结状态；导出结果必须与页面使用同一统计服务和口径 | 未实现 | 检索词 `headcount` 在 `platform/import_schemas.py:23-32` 的 `ExportEntityType` 枚举中不存在；`platform/master_data_export.py:48-85` 的 `_rows` 只覆盖 8 类主数据；`import_api.py:54-67` 的 `/exports/{entity_type}` 无编制分支 | 导出缺编制维度，且「与页面同一统计服务」这一要求没有落点。修复：新增 `GET /api/v1/workforce/headcount-export`，**直接复用** `extended_service.headcount_results`（`:1495-1573`），保证口径单一来源 | P1 |

#### §9 冻结

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `06:162-165` | 月结冻结：普通维护者不能修改已冻结月份的编制；授权角色可解冻或创建修订版本；解冻、修改、重新冻结均记录原因和日志；不覆盖原月度快照 | 部分实现 | 阻断 ✅：`extended_service.py:1143-1157`（命中冻结且未 `override_freeze` → 409 `HEADCOUNT_PLAN_FROZEN`）；解冻 ✅：`:1260-1279`（`close_headcount_freeze` 置 `status="closed"`、`ends_at`、写 reason + 审计）；修订版本 ✅：绕过冻结后写入生成新 version（`:1166-1174`）；不覆盖原快照 ✅（快照只新增版本，测试 `test_headcount_results_api.py:35` 覆盖）。**缺「重新冻结」❌**：没有「重新冻结」动作（解冻后无法再冻回），`close_headcount_freeze` 只能单向结束 | 补 `POST /headcount-freezes/{id}/reopen`（或按修订批次自动重建月结冻结），与 `01:213`「将修订版本重新冻结」对齐 | P1 |
| `06:169-181` | 业务冻结：年月/组织（含下级）/职务三维任意组合；未选表示全部；保存起止时间、发起人、原因和当前状态；普通角色不能修改命中范围；授权角色可解冻或调整，绕过必须填原因并记日志；招聘需求仅显示冻结提示不阻断；多个冻结同时命中时任一有效即保持冻结；冻结范围变更创建新版本，不无痕改写历史范围 | 部分实现 | 三维组合 ✅：`models.py:852-865` + `extended_service.py:1309-1341`（组织侧含全部下级：`:1281-1307`）；起止时间/原因/状态 ✅：`:863-865`；多冻结任一命中即冻结 ✅：`:1333-1341`；绕过需原因+日志 ✅：`:1177-1188`；招聘不阻断 ✅（见 `01-173`）。**缺「发起人」❌**：`HeadcountFreeze` 无 `created_by` 列（`:852-865`），发起人只能从审计日志反查（`object_type=headcount_freeze`）；**缺「范围变更创建新版本」❌**：模型无 `version` 列，且只有 create/close 两个接口，**无法修改冻结范围** | ① 加 `created_by` + `version`；② 补「改范围=新建版本」接口；③ 这两项同时服务于 `06:181` 与 `01:172` | P1 |

#### §10 与招聘需求的关系

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `06:185-190` | 6 条：招聘需求可选组织和职务；页面可展示相同年月/组织/职务的编制及人员结果；需求人数不预占编制；无空编或超编只展示不禁止；关闭或取消不改变月度编制；编制变化也不自动改变招聘需求人数或状态 | 已实现 | 选择组织/职务 ✅：`workflow/extended_service.py:202-235`；展示编制 ✅：`RecruitmentWorkspace.tsx:112-127`、`:184-196`；不预占 ✅（编制表无 `reserved_count` 字段，`models.py:804-832`；`RecruitmentRequest` 无写编制逻辑，`workflow/extended_service.py:198-357`）；不阻断 ✅（同上 + `test_recruitment_request_api.py:17`）；互不影响 ✅（两侧无交叉写入） | — | — |

#### §11 快照

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `06:194-204` | 快照至少保存 7 项：年月、组织和职务、当时有效的月度编制版本、当时人数、参与统计的人员范围或可复核依据、生成批次/生成时间/规则版本；系统按快照策略自动生成月初月末快照；月份边界用策略时区；快照保存时区、边界时刻和规则版本，配置变化不追溯覆盖历史 | 部分实现 | 命中 5 项：年月 `models.py:875`、组织和职务 `:903-912`、当时编制版本 `:913-916`（`headcount_plan_id`）、当时人数 `:917`、批次/生成时间/规则版本 `:868-888` + `extended_service.py:1480-1492`；时区边界 ✅：`:1378-1397`；不追溯覆盖 ✅（`rule_version` 存快照自身，`:1470-1473`）。**缺 2 项**：「参与统计的人员范围或可复核依据」——`evidence` 只存 `as_of` 与 `rule_version`（`:1470-1473`），没有人员清单/排除原因，**人数不可复核**；**「自动生成」缺失**——检索词 `scheduler`/`APScheduler`/`celery`/`cron` 全库 0 匹配，只有人工调用 | ① `evidence` 补人员范围口径（人员 ID 摘要 + 排除规则 + 占编规则版本），否则快照不可复核，直接违反 `06:212`；② 补月度调度 | P1 |
| `06:208-217` | 快照 10 条要求：任务可重复执行但不静默覆盖既有结果；补跑或修订生成新版本；原始版本保持可查；快照失败可安全重试；规则配置变化后历史快照仍可解释当时规则；月结后发现错误先更正源业务数据；原始月初月末快照永久保留且不可直接修改；授权用户生成与原版本关联的修订版本并填写原因；修订版本完成复核后重新冻结；修订、重新冻结和所有失败重试均写入审计日志 | 部分实现 | 幂等不覆盖 ✅：`extended_service.py:1398-1415`（同参数直接返回原批次）；修订新版本 ✅：`:1416-1439`（必须传 `parent_batch_id`，否则 409；版本号自增）；原始可查 ✅（`SnapshotBatch` 全部保留，`:868-888`）；失败可重试 ✅（事务回滚，状态 `running`→`completed`，`:1440-1478`）；规则可解释 ✅（`rule_version` + `evidence.rule_version`）；不可直接修改 ✅（无 update 路径）；关联修订+原因 ✅（`:1422-1430`、`:1444`）；审计 ✅（修订/生成写审计 `:1480-1492`）。**缺 3 条**：「先更正源业务数据」无任何前置校验或引导（❌）；「修订版本完成复核后重新冻结」无机制（❌，与 `06-165` 同源）；「所有失败重试写入审计日志」无失败路径审计（❌，异常回滚不落审计） | 补 ① 修订前置的源数据校验；② 重新冻结动作；③ 失败重试审计（捕获异常写一条失败审计） | P1 |

#### §12 权限与审计

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `06:221-230` | 建议拆分 8 个权限：查看编制和人数、维护月度编制、批量导入、导出、设置业务冻结、月结冻结和解冻、补跑或修订快照、查看变更历史 | 部分实现 | 实际只有 1 档：`extended_api.py:60`（`AdminUser = require_permission("WORKFORCE_ADMIN")`）覆盖 `:371`（编制）、`:399`（占编规则）、`:433`/`:467`（冻结）、`:480`（快照）、`:496`（结果）全部写与读；导入导出为 `DATA_GOVERNANCE_ADMIN`（`platform/import_api.py:32-35`）且不含编制类型 | 文档建议的 8 档与实现 1 档差距最大。建议在 `*` 范围内补 `HEADCOUNT_VIEW` / `HEADCOUNT_EDIT` / `HEADCOUNT_FREEZE_SET` / `HEADCOUNT_MONTH_CLOSE` / `HEADCOUNT_SNAPSHOT_RUN` / `HEADCOUNT_HISTORY_VIEW` 六个码，与 `01:170-172` 的普通/授权两级、`06:177-178` 的授权绕过配套 | P1 |
| `06:232` | 审计至少记录：编制修改、批量导入、冻结、解冻、快照生成和修订 | 部分实现 | 编制修改 ✅（`extended_service.py:1177-1188`）但**缺 before**；冻结 ✅（`:1246-1257`）；解冻 ✅（`:1271-1278`）；快照生成 ✅（`:1480-1492`）；快照修订 ✅（同审计，reason 区分）；**批量导入 ❌**（编制无导入，见 `06-22`） | 补编制修改 before + 编制导入审计 | P1 |

#### §13 异常规则

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| `06:236-238` | 组织或职务在目标月份无效时不允许新增该维度编制；组织未来换上级不改写历史月份编制；人员主组织或职务缺失时不静默计入未知维度，进入数据质量异常 | 部分实现 | 职务 ✅：`extended_service.py:1137-1142`；组织 ❌（仅存在性，见 `06-50`）；历史不改写 ✅（`HeadcountPlan` 不存层级，统计按 `as_of` 取当期版本 `organization_service.py:1700-1768`）；缺失维度不静默计入 ✅（`_count_people` 用 INNER JOIN，缺任职/缺占编规则的人自然不计入，`:1346-1370`）但**无「数据质量异常」清单/报表**（❌），异常只表现为「人数莫名偏少」 | ① 补组织在目标月的有效性校验；② 补一份「数据质量异常」查询（主组织/主职务缺失、占编规则缺失、期间重叠），否则 `06:238` 的兜底机制不存在 | P1 |
| `06:239-241` | 人员有效期重叠导致重复计数时统计任务失败并给出异常明细；规则配置变更需要记录生效日期，不能无痕重算历史；删除或停用组织、职务前，需要提示关联的未来月份编制 | 部分实现 | 重叠 ❌：`_count_people` 用 `count(distinct Employment.person_id)`（`:1345`）**静默去重**，不报错也不产出异常明细，与文档要求的「统计任务失败并给出异常明细」相反；生效日期 ✅：`models.py:847-848`（`effective_from`/`effective_to`）+ `extended_service.py:1204-1210`（新规则生效日必须晚于当前版本，前版自动收口）⇒ 历史不被无痕重算；停用提示 ❌：删除/停用组织或职务前无「关联未来月份编制」提示（检索词无对应实现） | ① 统计前做重叠检测并产出异常明细（至少不要静默去重）；② 补停用前的影响面提示（组织/职务停用前列出受影响未来月份编制） | P1 |

## 本分片 3 条最该先修的

1. **`01:219-220` 初始化导入的「整批不入库」红线**（明细 `01:219-220`，P0）——现在 `execute_batch` 对含错误行的批次照样写入正确行（`import_service.py:471-481`），一旦组织树/法人初始化导入半成功，落库的就是一套层级残缺的主数据，且没有回滚入口；这一条同时违反 `06:138-139` 的两段式要求，是本分片唯一会直接产出脏主数据的缺陷。
2. **`05:102` 事件生效时的重新校验**（明细 `05:102`，P0）——上级有效性只在排期时校验（`organization_service.py:336-365`），`_apply_event`（`:1861-1911`）落库前不复检；排期到生效之间上级若被撤销/失效，事件照样生效，组织树会留下指向失效上级的有效版本——组织结构正确性最后一道闸门的缺位。
3. **`01:92` 组织编码自动避让导入的历史编码**（明细 `01:92`，P0）——`ORG_NUMBER` 序列在导入路径不回写（检索词 `ORG_NUMBER` 仅 `organization_service.py:201` 一处），导入历史编码后再建组织会取到相同编码并撞唯一约束（`models.py:38`），直接打断「先导入历史组织再继续自动编号」的验收路径 `05:280`。

## 附：审计方法与局限

- 判定依据为当前工作区代码（`apps/api/src/hris`、`apps/web/src/business/features`），未运行服务、未连数据库，全部结论来自静态阅读与检索；未执行测试套件。
- 「未实现」结论均附检索词与全库 0 匹配结果：`leaf`/`叶子`/`child_count`（叶子组织判定）、`MERGE`/`SPLIT`/`REVOKE`（组织合并拆分撤销）、`scheduler`/`APScheduler`/`celery`/`cron`（快照自动生成）、`all_or_nothing`/`strict`/`blocking`（整批导入模式开关）、`playwright`/`cypress`/`puppeteer`（端到端测试框架）、`headcount_change_log`（编制变更日志实体）、`legal-entities/{`（法人反查路由）。
- 交叉参考（不在本分片审计范围，仅用于定位）：`docs/review/phase-1-3-implementation-conformance-review.md`（2026-08-12 第一至三阶段符合性审查）中对第一阶段各项标为 PASS 的结论，与本表存在口径差；本表以**当前代码**为准，并按 `01`/`05`/`06` 正文条款逐条重判。
- 未审计（其他分片负责）：`16`（总体PRD）、`07`/`08`（人员档案、人事事件）、`12`（第二阶段）、`14`（第三阶段）、`docs/input-packs/`。
- 权限码口径提醒：本表只使用题面给定的权限码全集；代码中另存在 `PERSON_VIEW` / `PERSON_SENSITIVE_VIEW` 等 `*` 范围内的码，涉及 `01:256-262` 的权限拆分判定时已按「`*` 可扩展」口径处理。